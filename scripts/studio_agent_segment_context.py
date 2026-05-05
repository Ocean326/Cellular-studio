#!/usr/bin/env python3
"""
Pure stdlib helpers for summarizing materialized studio-agent samples and exporting
visual context bundles (visual_context.json + Leaflet index.html).
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any

# Mirrors web/offline_tile_lib.BEIJING_BBOX — duplicated to keep this module import-light.
BEIJING_OFFLINE_BBOX = (115.4, 39.4, 117.5, 41.1)


class SegmentContextError(ValueError):
	pass


def _read_json(path: Path) -> dict[str, Any]:
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except json.JSONDecodeError as exc:
		raise SegmentContextError(f"Invalid JSON: {path}") from exc
	if not isinstance(payload, dict):
		raise SegmentContextError(f"Expected JSON object in {path}")
	return payload


def load_materialized_context(sample_root: Path) -> dict[str, Any]:
	root = Path(sample_root).expanduser().resolve()
	path = root / "context.json"
	if not path.is_file():
		raise SegmentContextError(f"Missing context.json under {root}")
	return _read_json(path)


def discover_uid_csv_paths(sample_root: Path, context: dict[str, Any] | None = None) -> list[Path]:
	root = Path(sample_root).expanduser().resolve()
	ctx = context if context is not None else load_materialized_context(root)
	paths: list[Path] = []
	for item in ctx.get("files") or []:
		if not isinstance(item, dict):
			continue
		rp = str(item.get("relative_path") or "").strip()
		if not rp.lower().endswith(".csv"):
			continue
		full = root / rp
		if full.is_file():
			paths.append(full)
	if paths:
		return paths
	# Fallback: any CSV under sample tree (excluding typical export folder).
	out: list[Path] = []
	for p in sorted(root.rglob("*.csv")):
		if "visual_export" in p.parts:
			continue
		out.append(p)
	return out


def _norm_header(name: str) -> str:
	return str(name or "").strip().lower()


def _pick_lat_lon(row_lc: dict[str, str]) -> tuple[float | None, float | None]:
	lat_keys = ("latitude", "lat", "latitude_deg", "y_lat")
	lon_keys = ("longitude", "lon", "lng", "longitude_deg", "x_lon")
	lat_val: float | None = None
	lon_val: float | None = None
	for k in lat_keys:
		if k in row_lc and str(row_lc[k]).strip() != "":
			try:
				lat_val = float(row_lc[k])
			except ValueError:
				lat_val = None
			break
	for k in lon_keys:
		if k in row_lc and str(row_lc[k]).strip() != "":
			try:
				lon_val = float(row_lc[k])
			except ValueError:
				lon_val = None
			break
	return lat_val, lon_val


def _row_scalar_time(row_lc: dict[str, str]) -> float | None:
	for key in ("timestamp_ms", "timestamp", "time_ms", "time", "t_in", "t_out"):
		if key not in row_lc:
			continue
		raw = str(row_lc[key]).strip()
		if raw == "":
			continue
		try:
			return float(raw)
		except ValueError:
			continue
	return None


def _parse_float_cell(row_lc: dict[str, str], keys: tuple[str, ...]) -> float | None:
	for key in keys:
		raw = row_lc.get(key)
		if raw is None or str(raw).strip() == "":
			continue
		try:
			return float(raw)
		except ValueError:
			continue
	return None


def _row_interval_times(row_lc: dict[str, str]) -> tuple[float | None, float | None]:
	start_keys = ("t_in", "start_time", "start_ts", "segment_start_time", "segment_start_ts")
	end_keys = ("t_out", "end_time", "end_ts", "segment_end_time", "segment_end_ts")
	start = _parse_float_cell(row_lc, start_keys)
	end = _parse_float_cell(row_lc, end_keys)
	return start, end


def _pick_first_text(row_lc: dict[str, str], keys: tuple[str, ...]) -> str:
	for key in keys:
		raw = row_lc.get(key)
		if raw is not None and str(raw).strip() != "":
			return str(raw).strip()
	return ""


def _row_time_values(row: dict[str, Any]) -> list[float]:
	out: list[float] = []
	for key in ("time_scalar", "t_in", "t_out"):
		value = row.get(key)
		if isinstance(value, (int, float)) and math.isfinite(float(value)):
			out.append(float(value))
	return out


def _group_time_range(rows: list[dict[str, Any]]) -> dict[str, float] | None:
	values: list[float] = []
	for row in rows:
		values.extend(_row_time_values(row))
	if not values:
		return None
	return {"min": min(values), "max": max(values)}


def _update_bounds(
	bounds: dict[str, float] | None,
	lat: float,
	lon: float,
) -> dict[str, float]:
	if bounds is None:
		return {"min_lat": lat, "max_lat": lat, "min_lon": lon, "max_lon": lon}
	bounds["min_lat"] = min(bounds["min_lat"], lat)
	bounds["max_lat"] = max(bounds["max_lat"], lat)
	bounds["min_lon"] = min(bounds["min_lon"], lon)
	bounds["max_lon"] = max(bounds["max_lon"], lon)
	return bounds


def _consecutive_segments(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
	if not rows or field not in rows[0]:
		return []
	segments: list[dict[str, Any]] = []
	start = 0
	prev = rows[0].get(field)
	for idx in range(1, len(rows) + 1):
		cur = rows[idx].get(field) if idx < len(rows) else object()
		if idx == len(rows) or cur != prev:
			group_rows = rows[start:idx]
			segment = {
				field: prev,
				"start_row": start,
				"end_row": idx - 1,
				"count": idx - start,
			}
			time_range = _group_time_range(group_rows)
			if time_range is not None:
				segment["time_range"] = time_range
			segments.append(segment)
			if idx < len(rows):
				start = idx
				prev = rows[idx].get(field)
	return segments


def downsample_coordinates(points: list[tuple[float, float]], max_points: int) -> list[list[float]]:
	if max_points <= 0:
		return []
	if len(points) <= max_points:
		return [[lon, lat] for lon, lat in points]
	step = (len(points) - 1) / float(max_points - 1)
	out: list[list[float]] = []
	for i in range(max_points):
		idx = int(round(i * step))
		idx = min(idx, len(points) - 1)
		lon, lat = points[idx]
		out.append([lon, lat])
	last_lon, last_lat = points[-1]
	if out and (out[-1][0] != last_lon or out[-1][1] != last_lat):
		out[-1] = [last_lon, last_lat]
	return out


def parse_uid_csv(csv_path: Path) -> dict[str, Any]:
	path = Path(csv_path)
	text = path.read_text(encoding="utf-8", errors="replace")
	reader = csv.DictReader(io.StringIO(text))
	if reader.fieldnames is None:
		raise SegmentContextError(f"No CSV header in {path}")
	raw_rows = list(reader)
	row_models: list[dict[str, Any]] = []
	bounds: dict[str, float] | None = None
	time_vals: list[float] = []
	point_track: list[tuple[float, float]] = []

	for raw in raw_rows:
		row_lc = {_norm_header(k): ("" if v is None else str(v)) for k, v in raw.items()}
		lat, lon = _pick_lat_lon(row_lc)
		t_scalar = _row_scalar_time(row_lc)
		t_start, t_end = _row_interval_times(row_lc)
		status = _pick_first_text(row_lc, ("status",))
		source = _pick_first_text(row_lc, ("source",))
		match_type = _pick_first_text(row_lc, ("match_type", "type", "geometry_type"))
		segment_idx = _pick_first_text(row_lc, ("segment_idx", "segment_id", "seg_idx"))
		od_segment_idx = _pick_first_text(row_lc, ("od_segment_idx", "od_segment_id"))
		entry: dict[str, Any] = {
			"latitude": lat,
			"longitude": lon,
			"time_scalar": t_scalar,
			"t_in": t_start,
			"t_out": t_end,
			"status": status,
			"source": source,
			"match_type": match_type,
			"segment_idx": segment_idx,
			"od_segment_idx": od_segment_idx,
		}
		row_models.append(entry)
		if lat is not None and lon is not None:
			bounds = _update_bounds(bounds, lat, lon)
			point_track.append((lon, lat))
		if t_scalar is not None:
			time_vals.append(t_scalar)
		if t_start is not None:
			time_vals.append(t_start)
		if t_end is not None:
			time_vals.append(t_end)

	row_models_sorted = sorted(
		row_models,
		key=lambda r: (
			r["time_scalar"] is None,
			float(r["time_scalar"]) if r["time_scalar"] is not None else 0.0,
			r["t_in"] is None,
			float(r["t_in"]) if r["t_in"] is not None else 0.0,
		),
	)

	time_range: dict[str, float] | None = None
	if time_vals:
		time_range = {"min": min(time_vals), "max": max(time_vals)}

	return {
		"relative_path": str(path.as_posix()),
		"name": path.name,
		"row_count": len(raw_rows),
		"parsed_points": len(point_track),
		"bounds": bounds,
		"time_range": time_range,
		"status_segments": _consecutive_segments(row_models_sorted, "status"),
		"source_segments": _consecutive_segments(row_models_sorted, "source"),
		"match_type_segments": _consecutive_segments(row_models_sorted, "match_type"),
		"segment_idx_segments": _consecutive_segments(row_models_sorted, "segment_idx"),
		"od_segment_idx_segments": _consecutive_segments(row_models_sorted, "od_segment_idx"),
		"track_lonlat": point_track,
	}


def _bbox_outside_offline_basemap(bounds: dict[str, float]) -> bool:
	min_lon, min_lat, max_lon, max_lat = BEIJING_OFFLINE_BBOX
	if bounds["max_lon"] < min_lon or bounds["min_lon"] > max_lon:
		return True
	if bounds["max_lat"] < min_lat or bounds["min_lat"] > max_lat:
		return True
	return False


def _merge_bounds(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
	return {
		"min_lat": min(a["min_lat"], b["min_lat"]),
		"max_lat": max(a["max_lat"], b["max_lat"]),
		"min_lon": min(a["min_lon"], b["min_lon"]),
		"max_lon": max(a["max_lon"], b["max_lon"]),
	}


def _suggest_zoom(bounds: dict[str, float]) -> int:
	lat_span = max(bounds["max_lat"] - bounds["min_lat"], 1e-6)
	lon_span = max(bounds["max_lon"] - bounds["min_lon"], 1e-6)
	span = max(lat_span, lon_span)
	# Empirical fit: smaller span -> closer zoom (capped).
	zoom = int(round(math.log2(360.0 / span)))
	return max(4, min(zoom, 17))


def summarize_materialized_sample(sample_root: Path | str) -> dict[str, Any]:
	root = Path(sample_root).expanduser().resolve()
	context = load_materialized_context(root)
	csv_paths = discover_uid_csv_paths(root, context)
	layers: list[dict[str, Any]] = []
	combined_bounds: dict[str, float] | None = None
	combined_time_min: float | None = None
	combined_time_max: float | None = None
	total_rows = 0

	for csv_path in csv_paths:
		layer = parse_uid_csv(csv_path)
		try:
			rel = str(csv_path.relative_to(root).as_posix())
		except ValueError:
			rel = csv_path.name
		layer_public = {
			k: v
			for k, v in layer.items()
			if k != "track_lonlat"
		}
		layer_public["relative_path"] = rel
		layers.append(layer_public)
		total_rows += int(layer["row_count"])
		b = layer.get("bounds")
		if isinstance(b, dict):
			combined_bounds = b if combined_bounds is None else _merge_bounds(combined_bounds, b)
		tr = layer.get("time_range")
		if isinstance(tr, dict):
			t0, t1 = float(tr["min"]), float(tr["max"])
			combined_time_min = t0 if combined_time_min is None else min(combined_time_min, t0)
			combined_time_max = t1 if combined_time_max is None else max(combined_time_max, t1)

	aggregate_time = None
	if combined_time_min is not None and combined_time_max is not None:
		aggregate_time = {"min": combined_time_min, "max": combined_time_max}

	warnings: list[str] = []
	if combined_bounds and _bbox_outside_offline_basemap(combined_bounds):
		warnings.append("outside_offline_basemap_bbox")

	return {
		"sample_root": str(root),
		"uid": str(context.get("uid") or ""),
		"batch": str(context.get("batch") or ""),
		"context_tags": list(context.get("tags") or []),
		"layers": layers,
		"aggregate": {
			"csv_files": len(layers),
			"total_row_count": total_rows,
			"bounds": combined_bounds,
			"time_range": aggregate_time,
		},
		"warnings": warnings,
	}


def _geojson_linestring(coords: list[list[float]]) -> dict[str, Any]:
	return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {}}


def build_visual_context_payload(
	summary: dict[str, Any],
	*,
	base_url: str,
	max_points_per_layer: int = 384,
) -> dict[str, Any]:
	base = str(base_url).rstrip("/")
	tile_template = f"{base}/offline_tiles/beijing/{{z}}/{{x}}/{{y}}.png"
	bounds_out: list[list[float]] | None = None
	agg_bounds = summary.get("aggregate") or {}
	raw_b = agg_bounds.get("bounds")
	if isinstance(raw_b, dict):
		bounds_out = [
			[raw_b["min_lat"], raw_b["min_lon"]],
			[raw_b["max_lat"], raw_b["max_lon"]],
		]
	center: list[float] = [39.9042, 116.4074]
	zoom_s = 11
	if isinstance(raw_b, dict):
		center = [
			(raw_b["min_lat"] + raw_b["max_lat"]) / 2.0,
			(raw_b["min_lon"] + raw_b["max_lon"]) / 2.0,
		]
		zoom_s = _suggest_zoom(raw_b)

	map_layers: list[dict[str, Any]] = []
	for layer in summary.get("layers") or []:
		name = str(layer.get("name") or Path(str(layer.get("relative_path") or "layer")).name)
		full_path = Path(str(layer.get("relative_path") or name))
		# Recover track from disk path under sample_root
		sample_root = Path(str(summary["sample_root"]))
		candidate = sample_root / str(layer.get("relative_path") or "")
		if candidate.is_file():
			full_parse = parse_uid_csv(candidate)
			track = full_parse.get("track_lonlat") or []
		else:
			track = []
		coords = downsample_coordinates(track, max_points_per_layer)
		map_layers.append(
			{
				"id": full_path.stem,
				"name": name,
				"relative_path": layer.get("relative_path"),
				"geojson": _geojson_linestring(coords) if len(coords) >= 2 else None,
				"markers": coords[: min(48, len(coords))],
			}
		)

	return {
		"schema": "studio_agent_visual_context/v1",
		"uid": summary.get("uid"),
		"batch": summary.get("batch"),
		"base_url": base,
		"tile_url_template": tile_template,
		"leaflet_css_url": f"{base}/web/vendor/leaflet/leaflet.css",
		"leaflet_js_url": f"{base}/web/vendor/leaflet/leaflet.js",
		"basemap": {
			"mode": "offline_tiles",
			"attribution": "Offline Beijing tiles (review server)",
		},
		"bounds": bounds_out,
		"center": center,
		"zoom": zoom_s,
		"layers": map_layers,
		"summary": summary,
		"warnings": list(summary.get("warnings") or []),
	}


def render_visual_index_html(payload: dict[str, Any]) -> str:
	data = json.dumps(payload, ensure_ascii=False)
	base = str(payload.get("base_url") or "").rstrip("/")
	# Embed JSON safely for inline script parsing.
	return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
	<meta charset="UTF-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>Visual context — {payload.get("uid") or "sample"}</title>
	<link rel="stylesheet" href="{payload["leaflet_css_url"]}" />
	<script src="{payload["leaflet_js_url"]}"></script>
	<style>
		html, body, #map {{ height: 100%; margin: 0; }}
		body {{ font-family: system-ui, sans-serif; }}
		#banner {{
			position: absolute; z-index: 1000; left: 8px; top: 8px; background: rgba(255,255,255,0.92);
			padding: 8px 12px; border-radius: 6px; font-size: 13px; max-width: 420px;
			box-shadow: 0 1px 4px rgba(0,0,0,0.2);
		}}
	</style>
</head>
<body>
	<div id="banner">离线底图 + 轨迹层（Leaflet）。如瓦片空白，请确认 review server 已启动且路径可访问。</div>
	<div id="map"></div>
	<script type="application/json" id="__VC_DATA__">{data}</script>
	<script>
	(function () {{
		const vc = JSON.parse(document.getElementById('__VC_DATA__').textContent);
		const map = L.map('map', {{ zoomControl: true }});
		const layer = L.tileLayer(vc.tile_url_template, {{
			maxZoom: 18,
			minZoom: 3,
			attribution: vc.basemap && vc.basemap.attribution ? vc.basemap.attribution : ''
		}});
		layer.addTo(map);
		const overlays = L.featureGroup();
		(vc.layers || []).forEach(function (layerDef) {{
			if (layerDef.geojson && layerDef.geojson.geometry) {{
				const gj = L.geoJSON(layerDef.geojson, {{
					style: {{ color: '#c12f2f', weight: 4, opacity: 0.85 }}
				}});
				gj.addTo(overlays);
			}}
			(layerDef.markers || []).forEach(function (pt) {{
				if (pt && pt.length === 2) {{
					L.circleMarker([pt[1], pt[0]], {{ radius: 3, fillOpacity: 0.9, color: '#1846a3' }}).addTo(overlays);
				}}
			}});
		}});
		overlays.addTo(map);
		if (vc.bounds && vc.bounds.length === 2) {{
			const southWest = L.latLng(vc.bounds[0][0], vc.bounds[0][1]);
			const northEast = L.latLng(vc.bounds[1][0], vc.bounds[1][1]);
			map.fitBounds(L.latLngBounds(southWest, northEast), {{ padding: [28, 28] }});
		}} else {{
			map.setView(vc.center || [39.9, 116.4], vc.zoom || 12);
		}}
		const base = {json.dumps(base)};
		console.info('visual_context loaded', base, vc.uid);
	}})();
	</script>
</body>
</html>
"""


def export_visual_context(
	sample_root: Path | str,
	output_dir: Path | str | None = None,
	*,
	base_url: str = "http://127.0.0.1:8016",
	max_points_per_layer: int = 384,
) -> dict[str, Any]:
	root = Path(sample_root).expanduser().resolve()
	out = Path(output_dir).expanduser().resolve() if output_dir is not None else root / "visual_export"
	out.mkdir(parents=True, exist_ok=True)
	summary = summarize_materialized_sample(root)
	payload = build_visual_context_payload(summary, base_url=base_url, max_points_per_layer=max_points_per_layer)
	json_path = out / "visual_context.json"
	html_path = out / "index.html"
	json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	html_path.write_text(render_visual_index_html(payload), encoding="utf-8")
	return {
		"sample_root": str(root),
		"output_dir": str(out),
		"visual_context_path": str(json_path),
		"index_html_path": str(html_path),
		"payload": payload,
	}


__all__ = [
	"BEIJING_OFFLINE_BBOX",
	"SegmentContextError",
	"build_visual_context_payload",
	"discover_uid_csv_paths",
	"downsample_coordinates",
	"export_visual_context",
	"load_materialized_context",
	"parse_uid_csv",
	"render_visual_index_html",
	"summarize_materialized_sample",
]
