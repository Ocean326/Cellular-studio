#!/usr/bin/env python3
"""Build a studio batch for reconstructed signal trajectories and GPS comparison.

Input shape used by the June 2026 demo data:

- reconstruction CSVs: no header, Baidu Mercator x/y in the first two columns
- raw signal CSV: optional station/event lon/lat file such as 测试13031180432.csv
- GPS CSVs: lon/lat columns, optional or unreliable time column

Because GPS time is not a dependable join key for this demo, matching is
geometry-first: each reconstructed trajectory is paired with the nearest GPS
polyline, then every reconstructed point is scored by distance to that GPS line.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MC_BANDS = [12890594.86, 8362377.87, 5591021.0, 3481989.83, 1678043.12, 0.0]
MC_TO_LL = [
	[1.410526172116255e-8, 8.98305509648872e-6, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
	[-7.435856389565537e-9, 8.983055097726239e-6, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
	[-3.030883460898826e-8, 8.98305509983578e-6, 0.30071316287616, 59.74293618442277, 7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
	[-1.981981304930552e-8, 8.983055099779535e-6, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
	[3.09191371068437e-9, 8.983055096812155e-6, 0.00006995724062, 23.10934304144901, -0.00023663490511, -0.6321817810242, -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
	[2.890871144776878e-9, 8.983055095805407e-6, -0.00000003068298, 7.47137025468032, -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5],
]
X_PI = math.pi * 3000.0 / 180.0
EARTH_RADIUS_M = 6371000.0
LOCAL_TIMEZONE = timezone(timedelta(hours=8))
GCJ_A = 6378245.0
GCJ_EE = 0.00669342162296594323

RECON_FIELDS = [
	"uid",
	"point_index",
	"latitude",
	"longitude",
	"timestamp_ms",
	"state",
	"status",
	"distance_to_gps_m",
	"matched_gps_file",
	"gps_segment_index",
	"source_x",
	"source_y",
]
GPS_FIELDS = ["uid", "point_index", "latitude", "longitude", "timestamp_ms", "source_time", "source_file"]
SIGNAL_FIELDS = [
	"uid",
	"event_index",
	"cid",
	"lat",
	"lon",
	"latitude",
	"longitude",
	"t_in",
	"t_out",
	"source_time",
	"source_file",
	"distance_to_gps_m",
	"status",
]
SEGMENT_FIELDS = ["uid", "segment_index", "state", "start_index", "end_index", "point_count", "accuracy", "start_time", "end_time"]
ROAD_SEGMENT_FIELDS = [
	"uid",
	"truth_segment_index",
	"truth_lng",
	"truth_lat",
	"truth_heading",
	"segment_length_m",
	"matched",
	"covered_length_m",
	"matched_distance_m",
	"matched_heading_delta",
]
SIGNAL_GPS_MAPPING_FIELDS = [
	"uid",
	"segment_order",
	"gps_file",
	"declared_gps_start",
	"declared_gps_end",
	"gps_start",
	"gps_end",
	"gps_point_index",
	"gps_source_time",
	"gps_lng",
	"gps_lat",
	"signal_match_count",
	"first_signal_source_time",
	"mapping_status",
]


@dataclass(frozen=True)
class Point:
	lat: float
	lon: float


@dataclass
class Reconstruction:
	path: Path
	points: list[Point]
	source_xy: list[tuple[float, float]]


@dataclass
class GpsTrack:
	path: Path
	points: list[Point]
	source_times: list[str]
	source_time_ms: list[int | None]
	start_ms: int | None
	end_ms: int | None
	declared_start_ms: int | None
	declared_end_ms: int | None


@dataclass
class SignalObservation:
	point: Point
	source_time: str
	time_ms: int | None
	user_id: str
	source_file: str


def point_key(point: Point) -> tuple[float, float]:
	return (round(point.lon, 5), round(point.lat, 5))


def point_overlap_ratio(reference: list[Point], candidates: list[Point]) -> float:
	reference_keys = {point_key(point) for point in reference}
	candidate_keys = {point_key(point) for point in candidates}
	if not candidate_keys:
		return 0.0
	return len(reference_keys & candidate_keys) / len(candidate_keys)


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fields)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in fields})


def ensure_empty_dir(path: Path, force: bool) -> None:
	if path.exists():
		if not force:
			raise FileExistsError(f"output already exists: {path}")
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def initialize_batch_dirs(batch_root: Path) -> None:
	for rel in (
		"result",
		"review/system",
		"review/reviewers",
		"review/aggregate",
		"accepted_assets/reviewers",
		"review_exports/aggregate",
	):
		(batch_root / rel).mkdir(parents=True, exist_ok=True)


def convertor(x: float, y: float, coeff: list[float]) -> tuple[float, float]:
	x_abs = abs(x)
	y_abs = abs(y)
	lon = coeff[0] + coeff[1] * x_abs
	t = y_abs / coeff[9]
	lat = coeff[2] + coeff[3] * t + coeff[4] * t**2 + coeff[5] * t**3 + coeff[6] * t**4 + coeff[7] * t**5 + coeff[8] * t**6
	return (-lon if x < 0 else lon), (-lat if y < 0 else lat)


def bd_mercator_to_bd09(x: float, y: float) -> tuple[float, float]:
	coeff = MC_TO_LL[-1]
	for band, candidate in zip(MC_BANDS, MC_TO_LL):
		if abs(y) >= band:
			coeff = candidate
			break
	return convertor(x, y, coeff)


def bd09_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
	x = lon - 0.0065
	y = lat - 0.006
	z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
	theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
	return z * math.cos(theta), z * math.sin(theta)


def out_of_china(lon: float, lat: float) -> bool:
	return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(x: float, y: float) -> float:
	ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
	ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
	ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
	ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
	return ret


def _transform_lon(x: float, y: float) -> float:
	ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
	ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
	ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
	ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
	return ret


def wgs84_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
	if out_of_china(lon, lat):
		return lon, lat
	dlat = _transform_lat(lon - 105.0, lat - 35.0)
	dlon = _transform_lon(lon - 105.0, lat - 35.0)
	radlat = lat / 180.0 * math.pi
	magic = math.sin(radlat)
	magic = 1 - GCJ_EE * magic * magic
	sqrt_magic = math.sqrt(magic)
	dlat = (dlat * 180.0) / ((GCJ_A * (1 - GCJ_EE)) / (magic * sqrt_magic) * math.pi)
	dlon = (dlon * 180.0) / (GCJ_A / sqrt_magic * math.cos(radlat) * math.pi)
	return lon + dlon, lat + dlat


def gcj02_to_wgs84(lon: float, lat: float) -> tuple[float, float]:
	if out_of_china(lon, lat):
		return lon, lat
	gcj_lon, gcj_lat = wgs84_to_gcj02(lon, lat)
	return lon * 2 - gcj_lon, lat * 2 - gcj_lat


def bd_mercator_to_gcj_point(x: float, y: float) -> Point:
	bd_lon, bd_lat = bd_mercator_to_bd09(x, y)
	gcj_lon, gcj_lat = bd09_to_gcj02(bd_lon, bd_lat)
	return Point(lat=gcj_lat, lon=gcj_lon)


def bd_mercator_to_wgs_point(x: float, y: float) -> Point:
	bd_lon, bd_lat = bd_mercator_to_bd09(x, y)
	gcj_lon, gcj_lat = bd09_to_gcj02(bd_lon, bd_lat)
	wgs_lon, wgs_lat = gcj02_to_wgs84(gcj_lon, gcj_lat)
	return Point(lat=wgs_lat, lon=wgs_lon)


def parse_float(value: Any) -> float | None:
	try:
		return float(str(value).strip().strip("\t"))
	except (TypeError, ValueError):
		return None


def parse_datetime_ms(value: str) -> int | None:
	text = str(value or "").strip().strip("\t")
	if not text:
		return None
	for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
		try:
			return int(datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TIMEZONE).timestamp() * 1000)
		except ValueError:
			continue
	return None


def parse_gps_filename_window(path: Path) -> tuple[int | None, int | None]:
	name = path.name
	match = re.match(r"^(\d{8})(\d{4})-(\d{4})", name)
	if match:
		day, start_hm, end_hm = match.groups()
	else:
		match = re.match(r"^(\d{8})(\d{2})-(\d{2})-(\d{4})", name)
		if not match:
			return None, None
		day, hour, minute, end_hm = match.groups()
		start_hm = f"{hour}{minute}"
	start_text = f"{day}{start_hm}00"
	end_text = f"{day}{end_hm}59"
	start_ms = parse_datetime_ms(start_text)
	end_ms = parse_datetime_ms(end_text)
	if start_ms is not None and end_ms is not None and end_ms < start_ms:
		end_ms += 24 * 60 * 60 * 1000
	return start_ms, end_ms


def read_reconstruction(path: Path) -> Reconstruction:
	points: list[Point] = []
	source_xy: list[tuple[float, float]] = []
	with path.open(encoding="utf-8", newline="") as handle:
		for row in csv.reader(handle):
			if len(row) < 2:
				continue
			x = parse_float(row[0])
			y = parse_float(row[1])
			if x is None or y is None:
				continue
			points.append(bd_mercator_to_gcj_point(x, y))
			source_xy.append((x, y))
	if len(points) < 2:
		raise ValueError(f"reconstruction csv has fewer than 2 usable points: {path}")
	return Reconstruction(path=path, points=points, source_xy=source_xy)


def read_gps(path: Path) -> GpsTrack:
	records: list[tuple[int | None, str, Point]] = []
	declared_start_ms, declared_end_ms = parse_gps_filename_window(path)
	with path.open(encoding="gbk", errors="ignore", newline="") as handle:
		for row in csv.reader(handle):
			cells = [str(cell).strip().strip("\t").strip() for cell in row]
			numbers = [parse_float(cell) for cell in cells]
			nums = [num for num in numbers if num is not None]
			if len(nums) >= 3 and nums[1] > 100 and 30 <= nums[2] <= 50:
				lon, lat = nums[1], nums[2]
				source_time = cells[0] if cells else ""
			elif len(nums) >= 2 and nums[0] > 100 and 30 <= nums[1] <= 50:
				lon, lat = nums[0], nums[1]
				source_time = cells[0] if cells else ""
			else:
				continue
			lon, lat = wgs84_to_gcj02(lon, lat)
			point = Point(lat=lat, lon=lon)
			time_ms = parse_datetime_ms(source_time)
			if declared_start_ms is not None and declared_end_ms is not None:
				if time_ms is None or time_ms < declared_start_ms or time_ms > declared_end_ms:
					continue
			records.append((time_ms, source_time, point))
	records.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))
	points: list[Point] = []
	source_times: list[str] = []
	source_time_ms: list[int | None] = []
	for time_ms, source_time, point in records:
		if points and abs(points[-1].lat - point.lat) < 1e-10 and abs(points[-1].lon - point.lon) < 1e-10:
			continue
		points.append(point)
		source_times.append(source_time)
		source_time_ms.append(time_ms)
	if len(points) < 2:
		raise ValueError(f"gps csv has fewer than 2 usable points: {path}")
	valid_times = [time_ms for time_ms in source_time_ms if time_ms is not None]
	return GpsTrack(
		path=path,
		points=points,
		source_times=source_times,
		source_time_ms=source_time_ms,
		start_ms=min(valid_times) if valid_times else None,
		end_ms=max(valid_times) if valid_times else None,
		declared_start_ms=declared_start_ms,
		declared_end_ms=declared_end_ms,
	)


def read_signal_observations(path: Path) -> list[SignalObservation]:
	observations: list[SignalObservation] = []
	with path.open(encoding="gbk", errors="ignore", newline="") as handle:
		for row in csv.reader(handle):
			cells = [str(cell).strip().strip("\t").strip() for cell in row]
			numbers = [parse_float(cell) for cell in cells]
			nums = [num for num in numbers if num is not None]
			if len(nums) < 2:
				continue
			lon = nums[-2]
			lat = nums[-1]
			if not (lon > 100 and 30 <= lat <= 50):
				continue
			lon, lat = wgs84_to_gcj02(lon, lat)
			observations.append(
				SignalObservation(
					point=Point(lat=lat, lon=lon),
					source_time=cells[0] if cells else "",
					time_ms=parse_datetime_ms(cells[0] if cells else ""),
					user_id=cells[1] if len(cells) > 1 else "",
					source_file=path.name,
				)
			)
	return observations


def discover_signal_observation_files(gps_dir: Path) -> list[Path]:
	result: list[Path] = []
	for path in sorted(gps_dir.glob("*.csv")):
		if path.name.startswith("测试"):
			result.append(path)
	return result


def project(point: Point, ref_lat: float) -> tuple[float, float]:
	return (
		math.radians(point.lon) * EARTH_RADIUS_M * math.cos(math.radians(ref_lat)),
		math.radians(point.lat) * EARTH_RADIUS_M,
	)


def point_segment_distance_m(point: Point, start: Point, end: Point) -> float:
	ref_lat = (point.lat + start.lat + end.lat) / 3.0
	px, py = project(point, ref_lat)
	ax, ay = project(start, ref_lat)
	bx, by = project(end, ref_lat)
	dx = bx - ax
	dy = by - ay
	if dx == 0 and dy == 0:
		return math.hypot(px - ax, py - ay)
	t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
	return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_m(a: Point, b: Point) -> float:
	return point_segment_distance_m(a, b, b)


def interpolate_point(start: Point, end: Point, ratio: float) -> Point:
	return Point(
		lat=start.lat + (end.lat - start.lat) * ratio,
		lon=start.lon + (end.lon - start.lon) * ratio,
	)


def bearing_degrees(start: Point, end: Point) -> float:
	lon_delta = math.radians(end.lon - start.lon)
	lat1 = math.radians(start.lat)
	lat2 = math.radians(end.lat)
	y = math.sin(lon_delta) * math.cos(lat2)
	x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon_delta)
	return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def heading_delta_degrees(a: float, b: float) -> float:
	return abs((a - b + 180.0) % 360.0 - 180.0)


def densify_polyline(points: list[Point], max_step_m: float) -> list[Point]:
	if len(points) <= 1:
		return list(points)
	result: list[Point] = []
	for start, end in zip(points, points[1:]):
		if not result:
			result.append(start)
		segment_length = distance_m(start, end)
		steps = max(1, math.ceil(segment_length / max(1.0, max_step_m)))
		for step in range(1, steps + 1):
			result.append(interpolate_point(start, end, step / steps))
	return result


def reconstruct_signal_baseline(points: list[Point], *, max_step_m: float) -> list[Point]:
	deduped: list[Point] = []
	for point in points:
		if deduped and distance_m(deduped[-1], point) < 1.0:
			continue
		deduped.append(point)
	return densify_polyline(deduped, max_step_m)


def road_segment_samples(points: list[Point], *, step_m: float) -> list[tuple[Point, float]]:
	densified = densify_polyline(points, step_m)
	samples: list[tuple[Point, float]] = []
	for start, end in zip(densified, densified[1:]):
		if distance_m(start, end) < 10.0:
			continue
		samples.append((interpolate_point(start, end, 0.5), bearing_degrees(start, end)))
	return samples


def build_road_segment_match_rows(
	uid: str,
	restored_points: list[Point],
	truth_points: list[Point],
	*,
	step_m: float,
	distance_threshold_m: float,
	heading_threshold_degrees: float,
) -> tuple[list[dict[str, Any]], int, int]:
	restored_segments = road_segment_samples(restored_points, step_m=step_m)
	truth_segments = road_segment_samples(truth_points, step_m=step_m)
	rows: list[dict[str, Any]] = []
	matched_count = 0
	for index, (truth_midpoint, truth_heading) in enumerate(truth_segments):
		best_distance = float("inf")
		best_heading_delta = float("inf")
		for restored_midpoint, restored_heading in restored_segments:
			candidate_distance = distance_m(truth_midpoint, restored_midpoint)
			candidate_heading_delta = heading_delta_degrees(truth_heading, restored_heading)
			if (candidate_distance, candidate_heading_delta) < (best_distance, best_heading_delta):
				best_distance = candidate_distance
				best_heading_delta = candidate_heading_delta
		matched = best_distance <= distance_threshold_m and best_heading_delta <= heading_threshold_degrees
		if matched:
			matched_count += 1
		rows.append(
			{
				"uid": uid,
				"truth_segment_index": index,
				"truth_lng": f"{truth_midpoint.lon:.8f}",
				"truth_lat": f"{truth_midpoint.lat:.8f}",
				"truth_heading": f"{truth_heading:.2f}",
				"matched": "1" if matched else "0",
				"matched_distance_m": f"{best_distance:.2f}" if math.isfinite(best_distance) else "",
				"matched_heading_delta": f"{best_heading_delta:.2f}" if math.isfinite(best_heading_delta) else "",
			}
		)
	return rows, matched_count, len(truth_segments)


def build_gps_coverage_rows(
	uid: str,
	restored_points: list[Point],
	truth_points: list[Point],
	*,
	step_m: float,
	distance_threshold_m: float,
) -> tuple[list[dict[str, Any]], float, float]:
	densified_truth = densify_polyline(truth_points, step_m)
	rows: list[dict[str, Any]] = []
	covered_length_m = 0.0
	total_length_m = 0.0
	for index, (start, end) in enumerate(zip(densified_truth, densified_truth[1:])):
		segment_length_m = distance_m(start, end)
		if segment_length_m < 1.0:
			continue
		total_length_m += segment_length_m
		midpoint = interpolate_point(start, end, 0.5)
		heading = bearing_degrees(start, end)
		distance = nearest_line_distance(midpoint, restored_points)[0] if len(restored_points) >= 2 else float("inf")
		matched = distance <= distance_threshold_m
		if matched:
			covered_length_m += segment_length_m
		rows.append(
			{
				"uid": uid,
				"truth_segment_index": index,
				"truth_lng": f"{midpoint.lon:.8f}",
				"truth_lat": f"{midpoint.lat:.8f}",
				"truth_heading": f"{heading:.2f}",
				"segment_length_m": f"{segment_length_m:.2f}",
				"matched": "1" if matched else "0",
				"covered_length_m": f"{segment_length_m if matched else 0.0:.2f}",
				"matched_distance_m": f"{distance:.2f}" if math.isfinite(distance) else "",
				"matched_heading_delta": "",
			}
		)
	return rows, covered_length_m, total_length_m


def nearest_line_distance(point: Point, line: list[Point]) -> tuple[float, int]:
	best_distance = float("inf")
	best_segment = 0
	for index in range(len(line) - 1):
		distance = point_segment_distance_m(point, line[index], line[index + 1])
		if distance < best_distance:
			best_distance = distance
			best_segment = index
	return best_distance, best_segment


def sample_evenly(items: list[Point], max_count: int) -> list[Point]:
	if len(items) <= max_count:
		return items
	step = (len(items) - 1) / float(max_count - 1)
	return [items[round(index * step)] for index in range(max_count)]


def average_distance_to_line(points: list[Point], line: list[Point], sample_count: int = 240) -> float:
	sampled = sample_evenly(points, sample_count)
	distances = [nearest_line_distance(point, line)[0] for point in sampled]
	return sum(distances) / len(distances)


def slug_from_filename(path: Path, fallback: str) -> str:
	stem = path.stem
	cjk = re.findall(r"[\u4e00-\u9fff]+", stem)
	if cjk:
		value = "-".join(cjk[:3])
	else:
		value = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-")
	return value or fallback


def assign_tracks(recons: list[Reconstruction], gps_tracks: list[GpsTrack]) -> dict[str, GpsTrack]:
	pairs: list[tuple[float, Reconstruction, GpsTrack]] = []
	for recon in recons:
		for gps in gps_tracks:
			pairs.append((average_distance_to_line(recon.points, gps.points), recon, gps))
	pairs.sort(key=lambda item: item[0])
	assigned_recon: set[Path] = set()
	assigned_gps: set[Path] = set()
	result: dict[str, GpsTrack] = {}
	for _distance, recon, gps in pairs:
		if recon.path in assigned_recon or gps.path in assigned_gps:
			continue
		assigned_recon.add(recon.path)
		assigned_gps.add(gps.path)
		result[recon.path.name] = gps
	for recon in recons:
		if recon.path.name not in result:
			best = min(gps_tracks, key=lambda gps: average_distance_to_line(recon.points, gps.points))
			result[recon.path.name] = best
	return result


def assign_reconstructions_to_gps(recons: list[Reconstruction], gps_tracks: list[GpsTrack]) -> dict[str, Reconstruction]:
	recon_to_gps = assign_tracks(recons, gps_tracks)
	result: dict[str, Reconstruction] = {}
	for recon in recons:
		gps = recon_to_gps.get(recon.path.name)
		if gps is not None:
			result[gps.path.name] = recon
	return result


def interpolate_time_ms(start_ms: int | None, end_ms: int | None, index: int, count: int, fallback_step_ms: int) -> int:
	if start_ms is None:
		return index * fallback_step_ms
	if end_ms is None or end_ms <= start_ms or count <= 1:
		return start_ms + index * fallback_step_ms
	return start_ms + round((end_ms - start_ms) * (index / (count - 1)))


def format_time_ms(value: int | None) -> str:
	if value is None:
		return ""
	return datetime.fromtimestamp(value / 1000, tz=LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def build_segments(uid: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	segments: list[dict[str, Any]] = []
	for row in rows:
		state = str(row["state"])
		if segments and segments[-1]["state"] == state:
			segments[-1]["end_index"] = row["point_index"]
			segments[-1]["end_time"] = row["timestamp_ms"]
			segments[-1]["point_count"] += 1
			continue
		segments.append(
			{
				"uid": uid,
				"segment_index": len(segments),
				"state": state,
				"start_index": row["point_index"],
				"end_index": row["point_index"],
				"point_count": 1,
				"start_time": row["timestamp_ms"],
				"end_time": row["timestamp_ms"],
			}
		)
	for segment in segments:
		points = [row for row in rows if segment["start_index"] <= row["point_index"] <= segment["end_index"]]
		correct_count = sum(1 for row in points if row["state"] == "gps_match")
		segment["accuracy"] = f"{(correct_count / len(points)):.4f}" if points else "0"
	return segments


def percentile(values: list[float], q: float) -> float:
	if not values:
		return 0.0
	index = min(len(values) - 1, max(0, round((len(values) - 1) * q)))
	return sorted(values)[index]


def build_signal_rows(
	uid: str,
	observations: list[SignalObservation],
	gps: GpsTrack,
	*,
	fallback_step_ms: int,
) -> list[dict[str, Any]]:
	candidates: list[tuple[float, SignalObservation]] = []
	for observation in observations:
		if gps.start_ms is not None and gps.end_ms is not None:
			if observation.time_ms is None or observation.time_ms < gps.start_ms or observation.time_ms > gps.end_ms:
				continue
		distance, _segment_index = nearest_line_distance(observation.point, gps.points)
		candidates.append((distance, observation))
	candidates.sort(key=lambda item: (item[1].time_ms or 0, item[0]))
	rows: list[dict[str, Any]] = []
	for event_index, (distance, observation) in enumerate(candidates):
		time_ms = observation.time_ms
		if time_ms is None:
			time_ms = event_index * fallback_step_ms
		rows.append(
			{
				"uid": uid,
				"event_index": event_index,
				"cid": observation.user_id,
				"lat": f"{observation.point.lat:.8f}",
				"lon": f"{observation.point.lon:.8f}",
				"latitude": f"{observation.point.lat:.8f}",
				"longitude": f"{observation.point.lon:.8f}",
				"t_in": time_ms,
				"t_out": time_ms + fallback_step_ms,
				"source_time": observation.source_time,
				"source_file": observation.source_file,
				"distance_to_gps_m": f"{distance:.2f}",
				"status": "raw_signal",
			}
		)
	return rows


def build_signal_gps_mapping_rows(
	uid: str,
	segment_order: int,
	gps: GpsTrack,
	observations: list[SignalObservation],
) -> list[dict[str, Any]]:
	by_time_and_coord: dict[tuple[int | None, tuple[float, float]], list[SignalObservation]] = {}
	by_coord: dict[tuple[float, float], list[SignalObservation]] = {}
	for observation in observations:
		if gps.start_ms is not None and gps.end_ms is not None:
			if observation.time_ms is None or observation.time_ms < gps.start_ms or observation.time_ms > gps.end_ms:
				continue
		coord_key = point_key(observation.point)
		by_time_and_coord.setdefault((observation.time_ms, coord_key), []).append(observation)
		by_coord.setdefault(coord_key, []).append(observation)

	rows: list[dict[str, Any]] = []
	for point_index, point in enumerate(gps.points):
		time_ms = gps.source_time_ms[point_index] if point_index < len(gps.source_time_ms) else None
		source_time = gps.source_times[point_index] if point_index < len(gps.source_times) else ""
		coord_key = point_key(point)
		exact_matches = by_time_and_coord.get((time_ms, coord_key), [])
		coord_matches = by_coord.get(coord_key, [])
		if exact_matches:
			matches = exact_matches
			status = "exact_time_coord_match"
		elif coord_matches:
			matches = coord_matches
			status = "coord_match_inside_segment"
		else:
			matches = []
			status = "missing_in_signal_slice"
		rows.append(
			{
				"uid": uid,
				"segment_order": segment_order,
				"gps_file": gps.path.name,
				"declared_gps_start": format_time_ms(gps.declared_start_ms),
				"declared_gps_end": format_time_ms(gps.declared_end_ms),
				"gps_start": format_time_ms(gps.start_ms),
				"gps_end": format_time_ms(gps.end_ms),
				"gps_point_index": point_index,
				"gps_source_time": source_time,
				"gps_lng": f"{point.lon:.8f}",
				"gps_lat": f"{point.lat:.8f}",
				"signal_match_count": len(matches),
				"first_signal_source_time": matches[0].source_time if matches else "",
				"mapping_status": status,
			}
		)
	return rows


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--signal-dir", required=True, type=Path, help="Directory containing reconstructed CSV files")
	parser.add_argument("--gps-dir", required=True, type=Path, help="Directory containing GPS CSV files")
	parser.add_argument("--raw-signal-csv", default="", type=Path, help="Optional raw signal/station CSV. Defaults to 测试*.csv under gps-dir")
	parser.add_argument("--output-batch-root", required=True, type=Path, help="Output studio batch root")
	parser.add_argument("--batch-name", default="signal_gps_compare_demo", help="Batch name")
	parser.add_argument("--label", default="信令还原 GPS 比对", help="Batch display label")
	parser.add_argument("--signal-layer-label", default="测试信令", help="Display label for the sliced raw signal layer")
	parser.add_argument("--reconstruction-layer-label", default="信令还原结果", help="Display label for the dense trajectory layer")
	parser.add_argument("--reference-layer-label", default="", help="Display label for the segmented reference layer")
	parser.add_argument("--comparison-label", default="", help="Display label for the comparison panel")
	parser.add_argument("--threshold-meters", type=float, default=1200.0, help="Distance threshold counted as correct road")
	parser.add_argument("--reconstruct-from-signal", action="store_true", help="Build reconstruction.csv from the segmented signal points and use signal-dir as GPS truth trajectories")
	parser.add_argument("--reconstruct-step-meters", type=float, default=40.0, help="Max interpolation step for the signal reconstruction baseline")
	parser.add_argument("--road-segment-step-meters", type=float, default=80.0, help="Sampling step for GPS-derived road truth segments")
	parser.add_argument("--road-segment-distance-meters", type=float, default=180.0, help="Max midpoint distance for a restored segment to match a GPS truth segment")
	parser.add_argument("--road-segment-heading-degrees", type=float, default=60.0, help="Max heading delta for a restored segment to match a GPS truth segment")
	parser.add_argument("--synthetic-step-ms", type=int, default=1000, help="Synthetic time step when input has no usable time")
	parser.add_argument("--force", action="store_true", help="Replace output batch root if it already exists")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	signal_dir = args.signal_dir.expanduser().resolve()
	gps_dir = args.gps_dir.expanduser().resolve()
	output_batch_root = args.output_batch_root.expanduser().resolve()
	if not signal_dir.is_dir():
		raise FileNotFoundError(f"signal-dir not found: {signal_dir}")
	if not gps_dir.is_dir():
		raise FileNotFoundError(f"gps-dir not found: {gps_dir}")
	recons = [read_reconstruction(path) for path in sorted(signal_dir.glob("*.csv"))]
	gps_tracks = [read_gps(path) for path in sorted(gps_dir.glob("*.csv")) if not path.name.startswith("测试130")]
	raw_signal_arg = str(args.raw_signal_csv or "").strip()
	raw_signal_paths = [args.raw_signal_csv.expanduser().resolve()] if raw_signal_arg and raw_signal_arg != "." else discover_signal_observation_files(gps_dir)
	signal_observations: list[SignalObservation] = []
	for path in raw_signal_paths:
		if path.is_file():
			signal_observations.extend(read_signal_observations(path))
	raw_signal_coord_keys = {point_key(observation.point) for observation in signal_observations}
	gps_coord_keys = {point_key(point) for gps in gps_tracks for point in gps.points}
	gps_overlap_ratio = (len(gps_coord_keys & raw_signal_coord_keys) / len(gps_coord_keys)) if gps_coord_keys and raw_signal_coord_keys else 0.0
	signal_layer_label = getattr(args, "signal_layer_label", "测试信令")
	reconstruction_layer_label = getattr(args, "reconstruction_layer_label", "信令还原结果")
	reference_layer_label_arg = getattr(args, "reference_layer_label", "")
	comparison_label_arg = getattr(args, "comparison_label", "")
	reconstruct_from_signal = bool(getattr(args, "reconstruct_from_signal", False))
	reconstruct_step_meters = float(getattr(args, "reconstruct_step_meters", 40.0))
	road_segment_step_meters = float(getattr(args, "road_segment_step_meters", 80.0))
	road_segment_distance_meters = float(getattr(args, "road_segment_distance_meters", 180.0))
	road_segment_heading_degrees = float(getattr(args, "road_segment_heading_degrees", 60.0))
	reference_layer_label = reference_layer_label_arg or ("GPS分段文件（与信令坐标重合）" if gps_overlap_ratio >= 0.95 else "GPS 真值分段")
	comparison_label = comparison_label_arg or ("比对 GPS分段文件" if gps_overlap_ratio >= 0.95 else "比对 GPS")
	if not recons:
		raise ValueError(f"no reconstruction csv files found under: {signal_dir}")
	if not gps_tracks:
		raise ValueError(f"no gps csv files found under: {gps_dir}")

	ensure_empty_dir(output_batch_root, force=bool(args.force))
	initialize_batch_dirs(output_batch_root)
	result_root = output_batch_root / "result"
	gps_to_recon = assign_reconstructions_to_gps(recons, gps_tracks)
	generated_at = utc_now_iso()

	uids: list[str] = []
	states_index: dict[str, list[str]] = {}
	by_uid: dict[str, dict[str, Any]] = {}
	all_distances: list[float] = []
	total_points = 0
	total_correct = 0
	total_road_segments = 0
	total_road_correct = 0

	alignment_segments: list[dict[str, Any]] = []
	signal_gps_mapping_rows: list[dict[str, Any]] = []
	for index, gps in enumerate(gps_tracks, start=1):
		recon = gps_to_recon.get(gps.path.name)
		uid = f"route_{index:02d}_{slug_from_filename(gps.path, f'track_{index:02d}')}"
		uids.append(uid)
		uid_dir = result_root / uid
		recon_rows: list[dict[str, Any]] = []
		distances: list[float] = []
		correct_count = 0
		signal_rows = build_signal_rows(
			uid,
			signal_observations,
			gps,
			fallback_step_ms=args.synthetic_step_ms,
		)
		signal_points = [
			Point(lat=float(row["latitude"]), lon=float(row["longitude"]))
			for row in signal_rows
			if row.get("latitude") and row.get("longitude")
		]
		restored_points = (
			reconstruct_signal_baseline(gps.points, max_step_m=reconstruct_step_meters)
			if reconstruct_from_signal
			else (recon.points if recon is not None else [])
		)
		truth_points = recon.points if recon is not None else []
		comparison_points = truth_points if reconstruct_from_signal else gps.points
		if recon is not None:
			for point_index, point in enumerate(restored_points):
				distance, segment_index = nearest_line_distance(point, comparison_points)
				state = "gps_match" if distance <= args.threshold_meters else "gps_mismatch"
				if state == "gps_match":
					correct_count += 1
				distances.append(distance)
				all_distances.append(distance)
				source_x, source_y = (
					("", "")
					if reconstruct_from_signal or point_index >= len(recon.source_xy)
					else recon.source_xy[point_index]
				)
				recon_rows.append(
					{
						"uid": uid,
						"point_index": point_index,
						"latitude": f"{point.lat:.8f}",
						"longitude": f"{point.lon:.8f}",
						"timestamp_ms": interpolate_time_ms(gps.start_ms, gps.end_ms, point_index, len(restored_points), args.synthetic_step_ms),
						"state": state,
						"status": state,
						"distance_to_gps_m": f"{distance:.2f}",
						"matched_gps_file": recon.path.name if reconstruct_from_signal else gps.path.name,
						"gps_segment_index": segment_index,
						"source_x": f"{source_x:.6f}" if isinstance(source_x, (int, float)) else source_x,
						"source_y": f"{source_y:.6f}" if isinstance(source_y, (int, float)) else source_y,
					}
				)
		gps_row_points = truth_points if reconstruct_from_signal and truth_points else gps.points
		gps_rows = []
		for point_index, point in enumerate(gps_row_points):
			source_time = gps.source_times[point_index] if not reconstruct_from_signal and point_index < len(gps.source_times) else ""
			timestamp_ms = (
				gps.source_time_ms[point_index]
				if not reconstruct_from_signal and point_index < len(gps.source_time_ms) and gps.source_time_ms[point_index] is not None
				else interpolate_time_ms(gps.start_ms, gps.end_ms, point_index, len(gps_row_points), args.synthetic_step_ms)
			)
			gps_rows.append(
				{
					"uid": uid,
					"point_index": point_index,
					"latitude": f"{point.lat:.8f}",
					"longitude": f"{point.lon:.8f}",
					"timestamp_ms": timestamp_ms,
					"source_time": source_time,
					"source_file": recon.path.name if reconstruct_from_signal and recon is not None else gps.path.name,
				}
			)
		gps_signal_overlap_ratio = point_overlap_ratio(signal_points, gps.points)
		segment_mapping_rows = build_signal_gps_mapping_rows(uid, index, gps, signal_observations)
		signal_gps_mapping_rows.extend(segment_mapping_rows)
		exact_signal_gps_matches = sum(1 for row in segment_mapping_rows if row["mapping_status"] == "exact_time_coord_match")
		missing_signal_gps_matches = sum(1 for row in segment_mapping_rows if row["mapping_status"] == "missing_in_signal_slice")
		segments = build_segments(uid, recon_rows)
		road_rows, road_correct_count, road_segment_count = (
			build_road_segment_match_rows(
				uid,
				restored_points,
				truth_points,
				step_m=road_segment_step_meters,
				distance_threshold_m=road_segment_distance_meters,
				heading_threshold_degrees=road_segment_heading_degrees,
			)
			if reconstruct_from_signal and truth_points and restored_points
			else ([], 0, 0)
		)
		write_csv(uid_dir / "signal.csv", SIGNAL_FIELDS, signal_rows)
		write_csv(uid_dir / "reconstruction.csv", RECON_FIELDS, recon_rows)
		write_csv(uid_dir / "gps.csv", GPS_FIELDS, gps_rows)
		write_csv(uid_dir / "gps_compare_segments.csv", SEGMENT_FIELDS, segments)
		write_csv(uid_dir / "road_segment_compare.csv", ROAD_SEGMENT_FIELDS, road_rows)
		point_accuracy = correct_count / len(recon_rows) if recon_rows else None
		road_accuracy = road_correct_count / road_segment_count if road_segment_count else None
		accuracy = road_accuracy if reconstruct_from_signal and road_accuracy is not None else point_accuracy
		states_index[uid] = ["gps_match"] if accuracy is not None and accuracy >= 0.9 else (["gps_missing_reconstruction"] if recon is None else ["gps_mismatch"])
		by_uid[uid] = {
			"uid": uid,
			"accuracy": round(accuracy, 4) if accuracy is not None else None,
			"accuracy_percent": round(accuracy * 100, 2) if accuracy is not None else None,
			"point_accuracy": round(point_accuracy, 4) if point_accuracy is not None else None,
			"point_accuracy_percent": round(point_accuracy * 100, 2) if point_accuracy is not None else None,
			"road_segment_accuracy": round(road_accuracy, 4) if road_accuracy is not None else None,
			"road_segment_accuracy_percent": round(road_accuracy * 100, 2) if road_accuracy is not None else None,
			"road_truth_segments": road_segment_count,
			"road_matched_segments": road_correct_count,
			"correct_points": correct_count,
			"total_points": len(recon_rows),
			"threshold_meters": args.threshold_meters,
			"mean_distance_m": round(sum(distances) / len(distances), 2) if distances else None,
			"median_distance_m": round(percentile(distances, 0.5), 2) if distances else None,
			"p95_distance_m": round(percentile(distances, 0.95), 2) if distances else None,
			"reconstruction_file": recon.path.name if recon is not None else "",
			"raw_signal_points": len(signal_rows),
			"matched_gps_file": gps.path.name,
			"gps_points": len(gps_rows),
			"gps_truth_file": recon.path.name if reconstruct_from_signal and recon is not None else gps.path.name,
			"signal_segment_file": gps.path.name,
			"gps_start": format_time_ms(gps.start_ms),
			"gps_end": format_time_ms(gps.end_ms),
			"declared_gps_start": format_time_ms(gps.declared_start_ms),
			"declared_gps_end": format_time_ms(gps.declared_end_ms),
			"segment_count": len(segments),
			"gps_signal_coordinate_overlap": round(gps_signal_overlap_ratio, 4),
			"gps_points_with_exact_signal_match": exact_signal_gps_matches,
			"gps_points_missing_signal_match": missing_signal_gps_matches,
		}
		alignment_segments.append(
			{
				"uid": uid,
				"gps_file": gps.path.name,
				"gps_start": format_time_ms(gps.start_ms),
				"gps_end": format_time_ms(gps.end_ms),
				"declared_gps_start": format_time_ms(gps.declared_start_ms),
				"declared_gps_end": format_time_ms(gps.declared_end_ms),
				"gps_points": len(gps_rows),
				"signal_slice_points": len(signal_rows),
				"reconstruction_file": recon.path.name if recon is not None else "",
				"reconstruction_points": len(recon_rows),
				"alignment_status": "aligned" if recon is not None else "gps_signal_only_missing_reconstruction",
				"accuracy_percent": round(accuracy * 100, 2) if accuracy is not None else None,
				"point_accuracy_percent": round(point_accuracy * 100, 2) if point_accuracy is not None else None,
				"road_segment_accuracy_percent": round(road_accuracy * 100, 2) if road_accuracy is not None else None,
				"road_truth_segments": road_segment_count,
				"road_matched_segments": road_correct_count,
				"gps_signal_coordinate_overlap": round(gps_signal_overlap_ratio, 4),
				"gps_points_with_exact_signal_match": exact_signal_gps_matches,
				"gps_points_missing_signal_match": missing_signal_gps_matches,
				"provenance_warning": "GPS segmented coordinates are identical to the sliced raw-signal coordinates at rounded 1e-5 precision." if gps_signal_overlap_ratio >= 0.95 else "",
			}
		)
		if recon_rows:
			total_points += len(recon_rows)
			total_correct += correct_count
		if road_segment_count:
			total_road_segments += road_segment_count
			total_road_correct += road_correct_count

	point_overall_accuracy = total_correct / total_points if total_points else 0.0
	road_overall_accuracy = total_road_correct / total_road_segments if total_road_segments else 0.0
	overall_accuracy = road_overall_accuracy if reconstruct_from_signal and total_road_segments else point_overall_accuracy
	comparison = {
		"generated_at": generated_at,
		"method": "signal_reconstruction_baseline_and_gps_road_segment_match" if reconstruct_from_signal else "geometry_nearest_gps_polyline",
		"coordinate_system": "GPS truth/reconstruction BD09 Mercator -> GCJ-02; raw signal WGS84 -> GCJ-02 for Gaode basemap" if reconstruct_from_signal else "reconstruction BD09 Mercator -> GCJ-02; raw signal/GPS WGS84 -> GCJ-02 for Gaode basemap",
		"reference_layer_label": reference_layer_label,
		"comparison_label": comparison_label,
		"time_alignment": "raw signal is sliced by each GPS segment time window; reconstruction timestamps are interpolated inside the matched GPS window",
		"raw_signal_files": [path.name for path in raw_signal_paths if path.exists()],
		"raw_signal_days": sorted({format_time_ms(observation.time_ms)[:10] for observation in signal_observations if observation.time_ms is not None}),
		"gps_coordinate_overlap_with_raw_signal": round(gps_overlap_ratio, 4),
		"reference_provenance_warning": "Current segmented reference files overlap the raw signal coordinate set at rounded 1e-5 precision; treat that layer as segmented signal/reference, not independent GPS truth." if gps_overlap_ratio >= 0.95 else "",
		"threshold_meters": args.threshold_meters,
		"road_segment_step_meters": road_segment_step_meters,
		"road_segment_distance_meters": road_segment_distance_meters,
		"road_segment_heading_degrees": road_segment_heading_degrees,
		"overall_accuracy": round(overall_accuracy, 4),
		"overall_accuracy_percent": round(overall_accuracy * 100, 2),
		"point_overall_accuracy": round(point_overall_accuracy, 4),
		"point_overall_accuracy_percent": round(point_overall_accuracy * 100, 2),
		"road_overall_accuracy": round(road_overall_accuracy, 4) if total_road_segments else None,
		"road_overall_accuracy_percent": round(road_overall_accuracy * 100, 2) if total_road_segments else None,
		"road_matched_segments": total_road_correct,
		"road_truth_segments": total_road_segments,
		"correct_points": total_correct,
		"total_points": total_points,
		"mean_distance_m": round(sum(all_distances) / len(all_distances), 2) if all_distances else None,
		"median_distance_m": round(percentile(all_distances, 0.5), 2) if all_distances else None,
		"p95_distance_m": round(percentile(all_distances, 0.95), 2) if all_distances else None,
		"alignment_method": [
			"1. Parse the multi-day raw signal file by timestamp.",
			"2. Parse each testing signal segment file and use its filename/row timestamps as the segment window.",
			"3. Slice raw signal rows into each segment by timestamp.",
			"4. Match available GPS truth trajectories to signal segments by nearest-polyline geometry.",
			"5. In reconstruct-from-signal mode, reconstruct a baseline trajectory from sorted signal points by de-duplication and distance-bounded interpolation.",
			"6. Derive GPS road truth segments by resampling the GPS truth trajectory, then count a reconstructed segment as correct when midpoint distance and heading both match.",
			"7. Report signal-vs-segment coordinate overlap to verify the testing segment files are signal-derived.",
		],
		"alignment_segments": alignment_segments,
		"by_uid": by_uid,
	}
	write_json(result_root / "gps_comparison_summary.json", comparison)
	write_csv(result_root / "signal_gps_mapping.csv", SIGNAL_GPS_MAPPING_FIELDS, signal_gps_mapping_rows)
	write_json(
		result_root / "signal_gps_mapping_summary.json",
		{
			"generated_at": generated_at,
			"raw_signal_files": [path.name for path in raw_signal_paths if path.exists()],
			"gps_files": [gps.path.name for gps in gps_tracks],
			"mapping": alignment_segments,
			"total_gps_points": len(signal_gps_mapping_rows),
			"exact_time_coord_matches": sum(1 for row in signal_gps_mapping_rows if row["mapping_status"] == "exact_time_coord_match"),
			"coord_only_matches": sum(1 for row in signal_gps_mapping_rows if row["mapping_status"] == "coord_match_inside_segment"),
			"missing_signal_matches": sum(1 for row in signal_gps_mapping_rows if row["mapping_status"] == "missing_in_signal_slice"),
		},
	)

	manifest = {
		"dataset_name": args.batch_name,
		"label": args.label,
		"title": args.label,
		"generated_at": generated_at,
		"ui_mode": "trajectory_layers",
		"uids": uids,
		"layers": ["signal", "reconstruction", "gps"],
		"layer_labels": {
			"signal": signal_layer_label,
			"reconstruction": reconstruction_layer_label,
			"gps": reference_layer_label,
		},
		"layer_specs": {
			"signal": {
				"filename": "signal.csv",
				"kind": "signal",
				"defaultColor": "#f59e0b",
				"defaultOpacity": 0.72,
				"hasLine": True,
			},
			"gps": {
				"filename": "gps.csv",
				"kind": "gps",
				"defaultColor": "#2563eb",
				"defaultOpacity": 0.82,
				"hasLine": True,
			},
			"reconstruction": {
				"filename": "reconstruction.csv",
				"kind": "gps",
				"defaultColor": "#dc2626",
				"defaultOpacity": 0.78,
				"hasLine": True,
				"review_reference": True,
			},
		},
		"layer_visibility": {"signal": True, "reconstruction": True, "gps": True},
		"time_scrubber_preferred_layers": ["reconstruction", "gps", "signal"],
		"review_reference_files": ["signal.csv", "reconstruction.csv", "gps.csv", "gps_compare_segments.csv", "road_segment_compare.csv"],
		"hide_review_panel": True,
		"states": states_index,
		"filter_state_options": ["gps_match", "gps_mismatch", "gps_missing_reconstruction"],
		"point_status_types": ["gps_match", "gps_mismatch", "gps_missing_reconstruction"],
		"point_status_styles": {
			"gps_match": {"color": "#16a34a", "size": 5},
			"gps_mismatch": {"color": "#dc2626", "size": 6},
			"gps_missing_reconstruction": {"color": "#64748b", "size": 5},
		},
		"gps_comparison": comparison,
		"triage_columns": [
			{"key": "pending", "title": "待查看", "subtitle": "GPS 分段对齐批次", "decisions": ["unreviewed"]},
			{"key": "accept", "title": "已保留", "subtitle": "人工保留", "decisions": ["accept"]},
			{"key": "other", "title": "其他", "subtitle": "排除 / 跳过", "decisions": ["reject", "skip"]},
		],
	}
	write_json(result_root / "manifest.json", manifest)
	write_json(result_root / "states_index.json", states_index)
	write_json(
		output_batch_root / "batch_meta.json",
		{
			"name": args.batch_name,
			"label": args.label,
			"version": "signal-gps-compare-v1",
			"created_at": generated_at,
			"keywords": ["signal-gps-compare", "demo", "gps"],
			"status": "prepared",
			"result_mode": "copied",
			"source_result_root": str(result_root),
			"uid_count": len(uids),
			"ui_config": {
				"ui_mode": "trajectory_layers",
				"hide_review_panel": True,
				"layers": ["signal", "reconstruction", "gps"],
				"layer_labels": {
					"signal": signal_layer_label,
					"reconstruction": reconstruction_layer_label,
					"gps": reference_layer_label,
				},
				"review_reference_files": ["signal.csv", "reconstruction.csv", "gps.csv", "gps_compare_segments.csv", "road_segment_compare.csv"],
				"point_status_types": ["gps_match", "gps_mismatch", "gps_missing_reconstruction"],
			},
			"gps_comparison": comparison,
		},
	)
	write_json(
		output_batch_root / "source_batch.json",
		{
			"generated_at": generated_at,
			"source": "adapters/signal_gps_compare/build_batch.py",
			"signal_dir": str(signal_dir),
			"gps_dir": str(gps_dir),
			"raw_signal_files": [str(path) for path in raw_signal_paths if path.exists()],
			"threshold_meters": args.threshold_meters,
		},
	)
	print(
		json.dumps(
			{
				"ok": True,
				"batch_root": str(output_batch_root),
				"result_root": str(result_root),
				"uid_count": len(uids),
				"overall_accuracy_percent": comparison["overall_accuracy_percent"],
				"threshold_meters": args.threshold_meters,
			},
			ensure_ascii=False,
			indent=2,
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
