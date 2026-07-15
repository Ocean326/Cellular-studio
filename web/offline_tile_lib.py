from __future__ import annotations

import io
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
	import shapefile  # type: ignore
except ImportError:  # pragma: no cover - exercised in runtime environments without pyshp
	shapefile = None

try:
	from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - exercised in runtime environments without pillow
	Image = None
	ImageDraw = None


TILE_SIZE = 256
BEIJING_BBOX = (115.4, 39.4, 117.5, 41.1)
CELL_SIZE_DEGREES = 0.05


@dataclass(frozen=True)
class VectorLayerStyle:
	name: str
	shapefile_path: Path
	color: tuple[int, int, int, int]
	base_width: int
	simplify_tolerance: float
	z_order: int


@dataclass(frozen=True)
class PreparedFeature:
	layer_name: str
	bbox: tuple[float, float, float, float]
	parts: tuple[tuple[tuple[float, float], ...], ...]
	z_order: int


def _bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
	return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _mercator_world_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
	scale = TILE_SIZE * (2 ** zoom)
	clamped_lat = max(min(lat, 85.05112878), -85.05112878)
	siny = math.sin(math.radians(clamped_lat))
	x = (lon + 180.0) / 360.0 * scale
	y = (0.5 - math.log((1.0 + siny) / (1.0 - siny)) / (4.0 * math.pi)) * scale
	return x, y


def _tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
	n = 2.0 ** z
	left = x / n * 360.0 - 180.0
	right = (x + 1) / n * 360.0 - 180.0
	top_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
	bottom_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 1) / n)))
	top = math.degrees(top_rad)
	bottom = math.degrees(bottom_rad)
	return left, bottom, right, top


def _simplify_points(points: list[tuple[float, float]], tolerance: float) -> tuple[tuple[float, float], ...]:
	if len(points) <= 2 or tolerance <= 0:
		return tuple(points)
	kept: list[tuple[float, float]] = [points[0]]
	last_lon, last_lat = points[0]
	for lon, lat in points[1:-1]:
		if abs(lon - last_lon) >= tolerance or abs(lat - last_lat) >= tolerance:
			kept.append((lon, lat))
			last_lon, last_lat = lon, lat
	kept.append(points[-1])
	return tuple(kept)


class OfflineTileRenderer:
	def __init__(
		self,
		*,
		cache_root: str | Path,
		layer_styles: list[VectorLayerStyle],
		beijing_bbox: tuple[float, float, float, float] = BEIJING_BBOX,
	) -> None:
		self.cache_root = Path(cache_root).expanduser().resolve()
		self.layer_styles = list(layer_styles)
		self.beijing_bbox = beijing_bbox
		self._features: list[PreparedFeature] | None = None
		self._grid: dict[tuple[int, int], list[int]] = {}
		self._lock = threading.Lock()

	def _ensure_dependencies(self) -> None:
		if shapefile is None:
			raise RuntimeError("offline tile rendering requires pyshp; install package 'pyshp'")
		if Image is None or ImageDraw is None:
			raise RuntimeError("offline tile rendering requires pillow; install package 'Pillow'")

	def _cell_range(self, bbox: tuple[float, float, float, float]) -> tuple[range, range]:
		min_lon, min_lat, max_lon, max_lat = bbox
		base_min_lon, base_min_lat, _, _ = self.beijing_bbox
		x_start = math.floor((min_lon - base_min_lon) / CELL_SIZE_DEGREES)
		x_end = math.floor((max_lon - base_min_lon) / CELL_SIZE_DEGREES)
		y_start = math.floor((min_lat - base_min_lat) / CELL_SIZE_DEGREES)
		y_end = math.floor((max_lat - base_min_lat) / CELL_SIZE_DEGREES)
		return range(x_start, x_end + 1), range(y_start, y_end + 1)

	def _load_features(self) -> None:
		if self._features is not None:
			return
		self._ensure_dependencies()
		with self._lock:
			if self._features is not None:
				return
			features: list[PreparedFeature] = []
			grid: dict[tuple[int, int], list[int]] = {}
			for style in sorted(self.layer_styles, key=lambda item: item.z_order):
				reader = shapefile.Reader(str(style.shapefile_path))
				for shape in reader.shapes():
					if shape.shapeType not in (
						shapefile.POLYLINE,
						shapefile.POLYLINEZ,
						shapefile.POLYLINEM,
					):
						continue
					if not shape.points:
						continue
					bbox = tuple(shape.bbox) if shape.bbox else None
					if not bbox or not _bbox_intersects(bbox, self.beijing_bbox):
						continue
					part_boundaries = list(shape.parts) + [len(shape.points)]
					parts: list[tuple[tuple[float, float], ...]] = []
					for start, end in zip(part_boundaries[:-1], part_boundaries[1:]):
						part_points = [(float(lon), float(lat)) for lon, lat in shape.points[start:end]]
						if len(part_points) < 2:
							continue
						simplified = _simplify_points(part_points, style.simplify_tolerance)
						if len(simplified) >= 2:
							parts.append(simplified)
					if not parts:
						continue
					feature = PreparedFeature(
						layer_name=style.name,
						bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
						parts=tuple(parts),
						z_order=style.z_order,
					)
					feature_index = len(features)
					features.append(feature)
					x_range, y_range = self._cell_range(feature.bbox)
					for cell_x in x_range:
						for cell_y in y_range:
							grid.setdefault((cell_x, cell_y), []).append(feature_index)
			self._features = features
			self._grid = grid

	def _feature_candidates(self, tile_bbox: tuple[float, float, float, float]) -> list[PreparedFeature]:
		self._load_features()
		assert self._features is not None
		x_range, y_range = self._cell_range(tile_bbox)
		feature_indexes: set[int] = set()
		for cell_x in x_range:
			for cell_y in y_range:
				feature_indexes.update(self._grid.get((cell_x, cell_y), []))
		candidates = [
			self._features[index]
			for index in sorted(feature_indexes)
			if _bbox_intersects(self._features[index].bbox, tile_bbox)
		]
		return sorted(candidates, key=lambda feature: feature.z_order)

	def _style_for_feature(self, feature: PreparedFeature) -> VectorLayerStyle:
		for style in self.layer_styles:
			if style.name == feature.layer_name:
				return style
		raise KeyError(f"missing layer style for {feature.layer_name}")

	def _line_width(self, style: VectorLayerStyle, zoom: int) -> int:
		if style.name == "roads":
			return max(1, int(round(style.base_width + max(0, zoom - 8) * 0.35)))
		if style.name == "subway":
			return max(1, int(round(style.base_width + max(0, zoom - 9) * 0.2)))
		return max(1, int(round(style.base_width + max(0, zoom - 10) * 0.18)))

	def _render_image(self, z: int, x: int, y: int):
		tile_bbox = _tile_bounds_lonlat(z, x, y)
		self._load_features()
		assert Image is not None
		assert ImageDraw is not None
		image = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (243, 247, 250, 255))
		draw = ImageDraw.Draw(image, "RGBA")
		if not _bbox_intersects(tile_bbox, self.beijing_bbox):
			return image
		for feature in self._feature_candidates(tile_bbox):
			style = self._style_for_feature(feature)
			width = self._line_width(style, z)
			for part in feature.parts:
				points: list[tuple[float, float]] = []
				for lon, lat in part:
					world_x, world_y = _mercator_world_pixel(lon, lat, z)
					points.append((world_x - x * TILE_SIZE, world_y - y * TILE_SIZE))
				if len(points) >= 2:
					draw.line(points, fill=style.color, width=width, joint="curve")
		return image

	def _tile_path(self, z: int, x: int, y: int) -> Path:
		return self.cache_root / "beijing" / str(z) / str(x) / f"{y}.png"

	def render_tile_bytes(self, z: int, x: int, y: int) -> bytes:
		cache_path = self._tile_path(z, x, y)
		if cache_path.exists():
			return cache_path.read_bytes()
		cache_path.parent.mkdir(parents=True, exist_ok=True)
		image = self._render_image(z, x, y)
		buffer = io.BytesIO()
		image.save(buffer, format="PNG", optimize=True)
		payload = buffer.getvalue()
		cache_path.write_bytes(payload)
		return payload


class OfflineTileService:
	def __init__(
		self,
		*,
		project_root: str | Path,
		runtime_root: str | Path,
		cache_root: str | Path | None = None,
		repo_root: str | Path | None = None,
	) -> None:
		project_root_path = Path(project_root).expanduser().resolve()
		runtime_root_path = Path(runtime_root).expanduser().resolve()
		repo_root_path = Path(repo_root).expanduser().resolve() if repo_root else project_root_path.parent
		project_data_root = repo_root_path / "project_data" / "map_assets"
		layer_styles = [
			VectorLayerStyle(
				name="roads",
				shapefile_path=project_data_root / "beijing" / "edges.shp",
				color=(104, 118, 138, 176),
				base_width=1,
				simplify_tolerance=0.0008,
				z_order=1,
			),
			VectorLayerStyle(
				name="subway",
				shapefile_path=project_data_root / "beijing_subway" / "edges.shp",
				color=(234, 88, 12, 220),
				base_width=2,
				simplify_tolerance=0.00035,
				z_order=2,
			),
			VectorLayerStyle(
				name="railway",
				shapefile_path=project_data_root / "beijing_railway" / "edges.shp",
				color=(37, 99, 235, 212),
				base_width=2,
				simplify_tolerance=0.00045,
				z_order=3,
			),
		]
		for style in layer_styles:
			if not style.shapefile_path.exists():
				raise FileNotFoundError(f"offline tile shapefile not found: {style.shapefile_path}")
		self.renderer = OfflineTileRenderer(
			cache_root=cache_root or (runtime_root_path / "offline_tiles_cache"),
			layer_styles=layer_styles,
		)

	def render_png(self, z: int, x: int, y: int) -> bytes:
		return self.renderer.render_tile_bytes(z, x, y)


__all__ = [
	"BEIJING_BBOX",
	"OfflineTileRenderer",
	"OfflineTileService",
]
