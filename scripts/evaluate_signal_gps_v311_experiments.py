#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.signal_gps_compare.build_batch import (
	Point,
	densify_polyline,
	distance_m,
	interpolate_point,
	nearest_line_distance,
	write_json,
)
from adapters.signal_gps_compare.build_v311_comparison_batch import (
	assign_truth_tracks_to_signal_tracks,
	iter_truth_paths,
	read_gps_truth_wgs,
	read_points_csv,
	read_signal_segment_wgs,
	row_point_wgs,
)
from scripts import run_signal6_v311_demo
from scripts.user_upload_adapter_lib import (
	SIGNAL6_MAINROAD_COST_FIELD,
	build_signal6_result,
	ensure_signal6_mainroad_weighted_edges,
)


DEFAULT_INPUT = Path("data/source_uploads/current_two_sources/testing_signal6_input.csv")
DEFAULT_SIGNAL_SEGMENT_DIR = Path("data/source_uploads/current_two_sources/gps_rar/测试号")
DEFAULT_GPS_TRUTH_DIR = Path("data/source_uploads/current_two_sources/gps_truth_csv")
DEFAULT_BASELINE_ROOT = Path("data/work/testing_signal6_v311_result")
DEFAULT_EXPERIMENT_ROOT = Path("data/work/testing_signal6_v311_experiments")

THRESHOLDS_M = (50.0, 80.0, 100.0, 120.0, 150.0, 180.0, 200.0, 250.0, 300.0, 400.0, 500.0)
TRIMS_M = (0.0, 300.0, 500.0, 1000.0, 1500.0)
GPS_COVERAGE_STEP_M = 20.0
KEY_SCENARIOS = (
	(50.0, 0.0),
	(100.0, 0.0),
	(100.0, 300.0),
	(100.0, 500.0),
	(100.0, 1000.0),
	(180.0, 0.0),
	(250.0, 0.0),
)
MAINROAD_PROFILE_BALANCED = {
	"highway_penalties": {
		"motorway": 0.75,
		"motorway_link": 0.75,
		"trunk": 0.75,
		"trunk_link": 0.75,
		"primary": 0.85,
		"primary_link": 0.85,
		"secondary": 0.85,
		"secondary_link": 0.85,
		"tertiary": 1.0,
		"tertiary_link": 1.0,
		"residential": 1.25,
		"unclassified": 1.25,
		"living_street": 1.4,
		"service": 1.4,
		"track": 1.4,
	},
	"default_penalty": 1.15,
}
MAINROAD_PROFILE_STRONG = {
	"highway_penalties": {
		"motorway": 0.55,
		"motorway_link": 0.55,
		"trunk": 0.55,
		"trunk_link": 0.55,
		"primary": 0.70,
		"primary_link": 0.70,
		"secondary": 0.78,
		"secondary_link": 0.78,
		"tertiary": 1.05,
		"tertiary_link": 1.05,
		"residential": 1.55,
		"unclassified": 1.55,
		"living_street": 1.80,
		"service": 1.80,
		"track": 1.80,
	},
	"default_penalty": 1.35,
}
MAINROAD_PROFILE_VERY_STRONG = {
	"highway_penalties": {
		"motorway": 0.45,
		"motorway_link": 0.45,
		"trunk": 0.45,
		"trunk_link": 0.45,
		"primary": 0.58,
		"primary_link": 0.58,
		"secondary": 0.68,
		"secondary_link": 0.68,
		"tertiary": 1.15,
		"tertiary_link": 1.15,
		"residential": 1.90,
		"unclassified": 1.90,
		"living_street": 2.30,
		"service": 2.30,
		"track": 2.30,
	},
	"default_penalty": 1.60,
}


@dataclass(frozen=True)
class Variant:
	name: str
	description: str
	kind: str
	options: dict[str, Any] | None = None


VARIANTS: dict[str, Variant] = {
	"post_snap_kf": Variant(
		name="post_snap_kf",
		description="snap 后再跑一遍 Kalman，用更平滑速度进入 OD/FMM",
		kind="pipeline",
		options={"post_snap_kf": True},
	),
	"move_block": Variant(
		name="move_block",
		description="把连续 move OD 行合并成更长 FMM 匹配窗口，增加上下文/点密度",
		kind="pipeline",
		options={"od_fmm_matching_granularity": "move_block"},
	),
	"od_points": Variant(
		name="od_points",
		description="FMM 输入改用 OD 起终点，而不是窗口内全部 snap/reconstruct 点",
		kind="pipeline",
		options={"od_fmm_input_mode": "od_points"},
	),
	"kalman_no_snap": Variant(
		name="kalman_no_snap",
		description="不 snap 回原始点，直接用 Kalman 平滑结果进入 OD/FMM",
		kind="pipeline",
		options={"snap_to_original": False, "post_snap_kf": False},
	),
	"road_only_wide": Variant(
		name="road_only_wide",
		description="只走 road FMM，扩大 road 搜索半径/误差，禁用 subway/railway",
		kind="pipeline",
		options={
			"fmm_variant_params": {
				"road": {"r": 0.030, "k": 512, "error": 0.015},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			}
		},
	),
	"major_roads": Variant(
		name="major_roads",
		description="过滤路网到 motorway/trunk/primary/secondary 及 link，模拟优先大路",
		kind="pipeline",
		options={
			"fmm_variant_params": {
				"road": {"r": 0.035, "k": 512, "error": 0.018},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			}
		},
	),
	"direct_snap_fmm": Variant(
		name="direct_snap_fmm",
		description="跳过 OD 切窗，直接把 baseline snap 点整段送 road-only FMM",
		kind="direct_snap",
		options={
			"fmm_variant_params": {
				"road": {"r": 0.030, "k": 512, "error": 0.015},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			}
		},
	),
	"mainroad_weighted": Variant(
		name="mainroad_weighted",
		description="保留全路网，用加权 routing cost 给主路低成本；候选距离/输出几何仍走原始 FMM",
		kind="pipeline",
		options={
			"fmm_version": "mainroad",
			"fmm_variant_params": {
				"road": {
					"r": 0.018,
					"k": 512,
					"error": 0.008,
					"reverse_tolerance": 0.05,
					"ubodt_delta_multiplier": 1.35,
				},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			},
		},
	),
	"mainroad_weighted_strong": Variant(
		name="mainroad_weighted_strong",
		description="保留全路网，进一步加大主路低成本和支路高成本的 routing cost 偏好；候选/防绕路仍走原始几何",
		kind="pipeline",
		options={
			"fmm_version": "mainroad",
			"fmm_mainroad_profile": "strong",
			"fmm_mainroad_highway_penalties": MAINROAD_PROFILE_STRONG["highway_penalties"],
			"fmm_mainroad_default_penalty": MAINROAD_PROFILE_STRONG["default_penalty"],
			"fmm_variant_params": {
				"road": {
					"r": 0.018,
					"k": 512,
					"error": 0.008,
					"reverse_tolerance": 0.05,
					"ubodt_delta_multiplier": 1.35,
				},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			},
		},
	),
	"mainroad_weighted_very_strong": Variant(
		name="mainroad_weighted_very_strong",
		description="保留全路网，最大化本轮主路偏好强度；候选/防绕路仍走原始几何",
		kind="pipeline",
		options={
			"fmm_version": "mainroad",
			"fmm_mainroad_profile": "very_strong",
			"fmm_mainroad_highway_penalties": MAINROAD_PROFILE_VERY_STRONG["highway_penalties"],
			"fmm_mainroad_default_penalty": MAINROAD_PROFILE_VERY_STRONG["default_penalty"],
			"fmm_variant_params": {
				"road": {
					"r": 0.018,
					"k": 512,
					"error": 0.008,
					"reverse_tolerance": 0.05,
					"ubodt_delta_multiplier": 1.35,
				},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			},
		},
	),
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Run/evaluate signal GPS v311 accuracy experiments.")
	parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
	parser.add_argument("--signal-segment-dir", type=Path, default=DEFAULT_SIGNAL_SEGMENT_DIR)
	parser.add_argument("--gps-truth-dir", type=Path, default=DEFAULT_GPS_TRUTH_DIR)
	parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
	parser.add_argument("--experiment-root", type=Path, default=DEFAULT_EXPERIMENT_ROOT)
	parser.add_argument("--output-json", type=Path, default=None)
	parser.add_argument("--variants", default=",".join(VARIANTS), help="Comma-separated variant names.")
	parser.add_argument("--run-variants", action="store_true", help="Generate missing variant outputs before evaluation.")
	parser.add_argument("--force-runs", action="store_true", help="Delete and rerun selected variant outputs.")
	parser.add_argument("--skip-baseline", action="store_true")
	return parser.parse_args()


def deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
	result = dict(base)
	if not override:
		return result
	for key, value in override.items():
		if isinstance(result.get(key), dict) and isinstance(value, dict):
			result[key] = deep_merge(result[key], value)
		else:
			result[key] = value
	return result


def selected_variants(raw: str) -> list[Variant]:
	names = [item.strip() for item in str(raw or "").split(",") if item.strip()]
	result: list[Variant] = []
	for name in names:
		if name not in VARIANTS:
			raise ValueError(f"unknown variant {name!r}; available: {', '.join(VARIANTS)}")
		result.append(VARIANTS[name])
	return result


def is_route04_uid(uid: str) -> bool:
	return "测试4" in uid or "route_04" in uid


def point_from_row(row: dict[str, Any]) -> Point | None:
	return row_point_wgs(row)


def read_line_points(path: Path) -> list[Point]:
	if not path.exists():
		return []
	rows = read_points_csv(path)
	points = [point for row in rows if (point := point_from_row(row)) is not None]
	deduped: list[Point] = []
	for point in points:
		if deduped and distance_m(deduped[-1], point) < 0.2:
			continue
		deduped.append(point)
	return deduped


def route_dirs(result_root: Path) -> list[Path]:
	return sorted(path for path in result_root.iterdir() if path.is_dir() and path.name.startswith("route_"))


def find_route_dir(dirs: list[Path], index: int) -> Path:
	prefix = f"route_{index:02d}_"
	for path in dirs:
		if path.name.startswith(prefix):
			return path
	return dirs[index - 1]


def coverage_for_route(
	restored_points: list[Point],
	truth_points: list[Point],
	*,
	threshold_m: float,
	trim_m: float,
	step_m: float = GPS_COVERAGE_STEP_M,
) -> dict[str, Any]:
	segments, total_full_m = build_route_coverage_segments(restored_points, truth_points, step_m=step_m)
	return coverage_from_segments(segments, total_full_m, threshold_m=threshold_m, trim_m=trim_m)


def build_route_coverage_segments(
	restored_points: list[Point],
	truth_points: list[Point],
	*,
	step_m: float = GPS_COVERAGE_STEP_M,
) -> tuple[list[tuple[float, float, float]], float]:
	densified_truth = densify_polyline(truth_points, step_m)
	segments: list[tuple[float, float, float]] = []
	total_full_m = 0.0
	for start, end in zip(densified_truth, densified_truth[1:]):
		segment_length_m = distance_m(start, end)
		if segment_length_m < 1.0:
			continue
		midpoint = interpolate_point(start, end, 0.5)
		distance_to_restored = (
			nearest_line_distance(midpoint, restored_points)[0]
			if len(restored_points) >= 2
			else float("inf")
		)
		segments.append((total_full_m + segment_length_m / 2.0, segment_length_m, distance_to_restored))
		total_full_m += segment_length_m
	return segments, total_full_m


def coverage_from_segments(
	segments: list[tuple[float, float, float]],
	total_full_m: float,
	*,
	threshold_m: float,
	trim_m: float,
) -> dict[str, Any]:
	if total_full_m <= 0.0:
		return {"covered_length_m": 0.0, "total_length_m": 0.0, "accuracy_percent": 0.0}

	left = float(trim_m)
	right = total_full_m - float(trim_m)
	if right <= left:
		left = 0.0
		right = total_full_m

	covered = 0.0
	total = 0.0
	missed_runs: list[dict[str, Any]] = []
	current_missed: dict[str, Any] | None = None
	for segment_index, (chain_mid_m, segment_length_m, distance_to_restored) in enumerate(segments):
		if chain_mid_m < left or chain_mid_m > right:
			continue
		total += segment_length_m
		matched = distance_to_restored <= threshold_m
		if matched:
			covered += segment_length_m
			if current_missed is not None:
				missed_runs.append(current_missed)
				current_missed = None
			continue
		if current_missed is None:
			current_missed = {
				"start_segment_index": segment_index,
				"end_segment_index": segment_index,
				"length_m": 0.0,
				"max_distance_m": 0.0,
			}
		current_missed["end_segment_index"] = segment_index
		current_missed["length_m"] = float(current_missed["length_m"]) + segment_length_m
		current_missed["max_distance_m"] = max(float(current_missed["max_distance_m"]), distance_to_restored)
	if current_missed is not None:
		missed_runs.append(current_missed)

	missed_runs.sort(key=lambda item: float(item["length_m"]), reverse=True)
	return {
		"covered_length_m": covered,
		"total_length_m": total,
		"accuracy_percent": covered / total * 100.0 if total else 0.0,
		"trimmed_total_length_m": total,
		"full_total_length_m": total_full_m,
		"top_missed_runs": [
			{
				"start_segment_index": int(item["start_segment_index"]),
				"end_segment_index": int(item["end_segment_index"]),
				"length_m": round(float(item["length_m"]), 2),
				"max_distance_m": round(float(item["max_distance_m"]), 2),
			}
			for item in missed_runs[:3]
		],
	}


def summarize_scenarios(by_uid_stats: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
	scenarios: list[dict[str, Any]] = []
	for threshold_m in THRESHOLDS_M:
		for trim_m in TRIMS_M:
			key = scenario_key(threshold_m, trim_m)
			total_covered = 0.0
			total_length = 0.0
			non04_covered = 0.0
			non04_length = 0.0
			non04_percents: list[float] = []
			by_uid: dict[str, Any] = {}
			for uid, stats_by_scenario in by_uid_stats.items():
				stats = stats_by_scenario[key]
				covered = float(stats["covered_length_m"])
				length = float(stats["total_length_m"])
				percent = covered / length * 100.0 if length else 0.0
				by_uid[uid] = {
					"accuracy_percent": round(percent, 2),
					"covered_length_m": round(covered, 2),
					"total_length_m": round(length, 2),
				}
				total_covered += covered
				total_length += length
				if not is_route04_uid(uid):
					non04_covered += covered
					non04_length += length
					non04_percents.append(percent)
			scenarios.append(
				{
					"threshold_m": threshold_m,
					"trim_each_end_m": trim_m,
					"overall_accuracy_percent": round(total_covered / total_length * 100.0, 2) if total_length else 0.0,
					"excluding_route04_accuracy_percent": round(non04_covered / non04_length * 100.0, 2) if non04_length else 0.0,
					"excluding_route04_min_uid_accuracy_percent": round(min(non04_percents), 2) if non04_percents else 0.0,
					"overall_covered_length_m": round(total_covered, 2),
					"overall_total_length_m": round(total_length, 2),
					"by_uid": by_uid,
				}
			)
	return scenarios


def scenario_key(threshold_m: float, trim_m: float) -> str:
	return f"{int(threshold_m)}m_trim{int(trim_m)}m"


def first_ge90(scenarios: list[dict[str, Any]], field: str, *, max_threshold_m: float | None = None) -> dict[str, Any] | None:
	if max_threshold_m is None:
		candidates = list(scenarios)
	else:
		candidates = [
			item
			for item in scenarios
			if float(item["threshold_m"]) <= max_threshold_m
		]
	candidates.sort(key=lambda item: (float(item["threshold_m"]), float(item["trim_each_end_m"])))
	for item in candidates:
		if float(item.get(field, 0.0)) >= 90.0:
			return item
	return None


def best_scenario(scenarios: list[dict[str, Any]], field: str, *, max_threshold_m: float | None = None) -> dict[str, Any] | None:
	candidates = [
		item
		for item in scenarios
		if max_threshold_m is None or float(item["threshold_m"]) <= max_threshold_m
	]
	if not candidates:
		return None
	return max(candidates, key=lambda item: float(item.get(field, 0.0)))


def evaluate_result_root(
	*,
	name: str,
	description: str,
	result_root: Path,
	signal_segment_dir: Path,
	gps_truth_dir: Path,
) -> dict[str, Any]:
	result_root = result_root.expanduser().resolve()
	if not result_root.exists():
		raise FileNotFoundError(f"result root does not exist: {result_root}")

	signal_tracks = [read_signal_segment_wgs(path) for path in sorted(signal_segment_dir.expanduser().resolve().glob("2026*.csv"))]
	truth_tracks = [read_gps_truth_wgs(path) for path in iter_truth_paths(gps_truth_dir)]
	signal_to_truth = assign_truth_tracks_to_signal_tracks(truth_tracks, signal_tracks)
	dirs = route_dirs(result_root)
	if len(dirs) < len(signal_tracks):
		raise ValueError(f"{result_root} has {len(dirs)} route dirs, expected at least {len(signal_tracks)}")

	by_uid_stats: dict[str, dict[str, dict[str, Any]]] = {}
	route_details: dict[str, Any] = {}
	for index, signal_track in enumerate(signal_tracks, start=1):
		uid = f"route_{index:02d}_{signal_track.path.stem}"
		route_dir = find_route_dir(dirs, index)
		truth = signal_to_truth[signal_track.path.name]
		line_path = route_dir / "line.csv"
		if not line_path.exists():
			line_path = route_dir / "snap.csv"
		restored_points = read_line_points(line_path)
		coverage_segments, total_full_m = build_route_coverage_segments(restored_points, truth.points)
		stats_by_scenario: dict[str, dict[str, Any]] = {}
		for threshold_m in THRESHOLDS_M:
			for trim_m in TRIMS_M:
				stats_by_scenario[scenario_key(threshold_m, trim_m)] = coverage_from_segments(
					coverage_segments,
					total_full_m,
					threshold_m=threshold_m,
					trim_m=trim_m,
				)
		by_uid_stats[uid] = stats_by_scenario
		route_details[uid] = {
			"result_dir": str(route_dir),
			"line_file": str(line_path),
			"line_points": len(restored_points),
			"gps_truth_file": truth.path.name,
			"signal_segment_file": signal_track.path.name,
			"metrics": {
				key: {
					"accuracy_percent": round(stats_by_scenario[key]["accuracy_percent"], 2),
					"covered_length_m": round(stats_by_scenario[key]["covered_length_m"], 2),
					"total_length_m": round(stats_by_scenario[key]["total_length_m"], 2),
					"top_missed_runs": stats_by_scenario[key].get("top_missed_runs", []),
				}
				for key in [scenario_key(*item) for item in KEY_SCENARIOS]
			},
		}

	scenarios = summarize_scenarios(by_uid_stats)
	key_metrics: dict[str, Any] = {}
	for threshold_m, trim_m in KEY_SCENARIOS:
		key = scenario_key(threshold_m, trim_m)
		scenario = next(
			item for item in scenarios if item["threshold_m"] == threshold_m and item["trim_each_end_m"] == trim_m
		)
		key_metrics[key] = {
			"overall_accuracy_percent": scenario["overall_accuracy_percent"],
			"excluding_route04_accuracy_percent": scenario["excluding_route04_accuracy_percent"],
			"excluding_route04_min_uid_accuracy_percent": scenario["excluding_route04_min_uid_accuracy_percent"],
			"by_uid_accuracy_percent": {
				uid: values["accuracy_percent"]
				for uid, values in scenario["by_uid"].items()
			},
		}

	return {
		"name": name,
		"description": description,
		"result_root": str(result_root),
		"metric_definition": "GPS truth geometry length whose densified segment midpoint is within threshold meters of reconstructed line; optional trim removes distance from each end of each GPS truth route.",
		"thresholds_m": list(THRESHOLDS_M),
		"trim_each_end_m": list(TRIMS_M),
		"key_metrics": key_metrics,
		"first_overall_ge90": first_ge90(scenarios, "overall_accuracy_percent"),
		"first_excluding_route04_ge90": first_ge90(scenarios, "excluding_route04_accuracy_percent"),
		"first_all_non04_each_ge90": first_ge90(scenarios, "excluding_route04_min_uid_accuracy_percent"),
		"first_excluding_route04_ge90_under_100m": first_ge90(
			scenarios,
			"excluding_route04_accuracy_percent",
			max_threshold_m=100.0,
		),
		"best_excluding_route04_under_100m": best_scenario(
			scenarios,
			"excluding_route04_accuracy_percent",
			max_threshold_m=100.0,
		),
		"scenarios": scenarios,
		"routes": route_details,
	}


def project_root() -> Path:
	return Path(__file__).resolve().parents[2]


def cellular_quality_src() -> Path:
	return project_root() / "my_history_methods" / "cellular_quality" / "src"


def fmm_assets() -> dict[str, Path]:
	root = project_root()
	return {
		"edges": root / "project_data" / "map_assets" / "beijing" / "edges.shp",
		"fmm": root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "fmm",
		"ubodt": root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "ubodt_gen",
		"fmm_mainroad": root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build_mainroad" / "fmm",
		"ubodt_mainroad": root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build_mainroad" / "ubodt_gen",
	}


def parse_highway_values(value: Any) -> set[str]:
	if value is None:
		return set()
	text = str(value).strip()
	if not text or text.lower() == "nan":
		return set()
	if text.startswith("[") and text.endswith("]"):
		try:
			parsed = ast.literal_eval(text)
		except Exception:
			parsed = text.strip("[]").split(",")
		if isinstance(parsed, (list, tuple, set)):
			return {str(item).strip().strip("'\"") for item in parsed if str(item).strip()}
	return {text}


def ensure_major_road_edges(experiment_root: Path) -> Path:
	target_dir = experiment_root / "road_network_variants" / "major_roads"
	target = target_dir / "edges.shp"
	if target.exists():
		return target.resolve()

	import geopandas as gpd

	allowed = {
		"motorway",
		"motorway_link",
		"trunk",
		"trunk_link",
		"primary",
		"primary_link",
		"secondary",
		"secondary_link",
	}
	assets = fmm_assets()
	gdf = gpd.read_file(assets["edges"])
	mask = gdf["highway"].apply(lambda value: bool(parse_highway_values(value) & allowed))
	filtered = gdf.loc[mask].copy()
	if filtered.empty:
		raise ValueError("major road filter produced empty edges dataframe")
	target_dir.mkdir(parents=True, exist_ok=True)
	filtered.to_file(target)
	return target.resolve()


def ensure_mainroad_weighted_edges(experiment_root: Path, variant: Variant) -> Path:
	options = variant.options or {}
	target = experiment_root / "road_network_variants" / variant.name / "edges.shp"
	assets = fmm_assets()
	return ensure_signal6_mainroad_weighted_edges(
		assets["edges"],
		target,
		cost_field=SIGNAL6_MAINROAD_COST_FIELD,
		highway_penalties=options.get("fmm_mainroad_highway_penalties") if isinstance(options, dict) else None,
		default_penalty=options.get("fmm_mainroad_default_penalty") if isinstance(options, dict) else None,
	)


def pipeline_options_for(variant: Variant, experiment_root: Path) -> dict[str, Any]:
	options = run_signal6_v311_demo.default_pipeline_options()
	options = deep_merge(options, variant.options or {})
	if variant.name == "major_roads":
		options = deep_merge(options, {"fmm_edges": str(ensure_major_road_edges(experiment_root))})
	if str(options.get("fmm_version", "")).strip().lower() == "mainroad":
		options = deep_merge(options, {"fmm_edges_mainroad_weighted": str(ensure_mainroad_weighted_edges(experiment_root, variant))})
	return options


def run_pipeline_variant(
	*,
	variant: Variant,
	input_path: Path,
	experiment_root: Path,
	force: bool,
) -> Path:
	variant_dir = experiment_root / variant.name
	result_root = variant_dir / "result"
	if result_root.exists():
		if not force:
			return result_root
		shutil.rmtree(variant_dir)
	variant_dir.mkdir(parents=True, exist_ok=True)
	options = pipeline_options_for(variant, experiment_root)
	write_json(variant_dir / "variant_config.json", {"name": variant.name, "description": variant.description, "options": options})
	build_signal6_result(
		input_path.expanduser().resolve(),
		result_root.resolve(),
		title=f"测试号信令v311还原实验-{variant.name}",
		pipeline_mode="v311",
		pipeline_options=options,
	)
	return result_root


def normalize_frame_uid(df: Any, mapping: dict[int, str], uid_col: str) -> Any:
	if df is None or df.empty or uid_col not in df.columns:
		return df
	out = df.copy()
	out[uid_col] = out[uid_col].map(lambda value: mapping.get(int(value), str(value)))
	return out


def run_direct_snap_variant(
	*,
	variant: Variant,
	source_root: Path,
	experiment_root: Path,
	force: bool,
) -> Path:
	variant_dir = experiment_root / variant.name
	result_root = variant_dir / "result"
	if result_root.exists():
		if not force:
			return result_root
		shutil.rmtree(variant_dir)
	variant_dir.mkdir(parents=True, exist_ok=True)

	src = cellular_quality_src()
	if str(src) not in sys.path:
		sys.path.insert(0, str(src))

	import pandas as pd
	from panzhi_pipline import FMMMatcher
	from process_steps.FMM.od import map_od_segments_with_fmm

	assets = fmm_assets()
	for label, path in assets.items():
		if not path.exists():
			raise FileNotFoundError(f"missing FMM asset {label}: {path}")

	frames: list[Any] = []
	od_by_uid: dict[int, Any] = {}
	pipeline_to_original: dict[int, str] = {}
	source_dirs = route_dirs(source_root)
	for pipeline_uid, route_dir in enumerate(source_dirs, start=1):
		snap_path = route_dir / "snap.csv"
		if not snap_path.exists():
			continue
		df = pd.read_csv(snap_path)
		if df.empty:
			continue
		original_uid = str(df["uid"].iloc[0])
		pipeline_to_original[pipeline_uid] = original_uid
		work = df.copy()
		work["UID"] = pipeline_uid
		work["CID"] = pd.to_numeric(work.get("cid", 0), errors="coerce").fillna(0).astype("int64")
		work["latitude"] = pd.to_numeric(work["latitude"], errors="coerce")
		work["longitude"] = pd.to_numeric(work["longitude"], errors="coerce")
		work["t_in"] = pd.to_numeric(work["t_in"], errors="coerce")
		work["t_out"] = pd.to_numeric(work.get("t_out", work["t_in"]), errors="coerce").fillna(work["t_in"])
		work = work.dropna(subset=["latitude", "longitude", "t_in"]).sort_values("t_in").reset_index(drop=True)
		if len(work) < 2:
			continue
		frames.append(work[["UID", "CID", "latitude", "longitude", "t_in", "t_out"]])
		first = work.iloc[0]
		last = work.iloc[-1]
		start_time = float(work["t_in"].min())
		end_time = float(work["t_out"].max())
		od_by_uid[pipeline_uid] = pd.DataFrame(
			[
				{
					"start_latitude": float(first["latitude"]),
					"start_longitude": float(first["longitude"]),
					"end_latitude": float(last["latitude"]),
					"end_longitude": float(last["longitude"]),
					"start_time": start_time,
					"end_time": end_time,
					"time_diff": max(0.0, end_time - start_time),
					"speed": 0.0,
					"is_stationary": False,
				}
			]
		)

	if not frames:
		raise ValueError(f"no usable snap frames found under {source_root}")
	reconstructed_df = pd.concat(frames, ignore_index=True)

	options = pipeline_options_for(variant, experiment_root)
	write_json(variant_dir / "variant_config.json", {"name": variant.name, "description": variant.description, "options": options})
	fmm_version = str(options.get("fmm_version", "original"))
	edges_path = str(assets["edges"])
	ubodt_cmd = str(assets["ubodt"])
	fmm_cmd = str(assets["fmm"])
	network_cost_field = ""
	if fmm_version == "mainroad":
		edges_path = str(ensure_mainroad_weighted_edges(experiment_root, variant))
		ubodt_cmd = str(assets["ubodt_mainroad"])
		fmm_cmd = str(assets["fmm_mainroad"])
		network_cost_field = SIGNAL6_MAINROAD_COST_FIELD
	matcher = FMMMatcher(
		edges_shp=edges_path,
		cache_dir=str(variant_dir / "cache" / "fmm"),
		save_dir=str(variant_dir / "fmm_outputs"),
		ubodt_cmd=ubodt_cmd,
		fmm_cmd=fmm_cmd,
		network_cost_field=network_cost_field,
		fmm_version=fmm_version,
	)
	mapped = map_od_segments_with_fmm(
		od_df_by_uid=od_by_uid,
		reconstructed_df=reconstructed_df,
		matcher=matcher,
		from_scratch=True,
		pkl_name="direct_snap_fmm_results.pkl",
		variant_params_config=options.get("fmm_variant_params"),
		mode_selection_config=options.get("fmm_mode_selection_config"),
		input_mode="reconstruct",
		matching_granularity="move_block",
		split_local_day=True,
		max_gap_sec=None,
		max_duration_sec=None,
		match_timezone="Asia/Shanghai",
		uid_col="UID",
		cid_col="CID",
		time_col="t_in",
		lat_col="latitude",
		lon_col="longitude",
	)

	points_df = normalize_frame_uid(mapped.points_df, pipeline_to_original, "UID")
	line_df = normalize_frame_uid(mapped.fmm_line_df, pipeline_to_original, "UID")
	result_root.mkdir(parents=True, exist_ok=True)
	for pipeline_uid, route_dir in enumerate(source_dirs, start=1):
		if pipeline_uid not in pipeline_to_original:
			continue
		target_dir = result_root / route_dir.name
		target_dir.mkdir(parents=True, exist_ok=True)
		for csv_name in ("raw.csv", "snap.csv", "od.csv"):
			source_csv = route_dir / csv_name
			if source_csv.exists():
				shutil.copy2(source_csv, target_dir / csv_name)
		original_uid = pipeline_to_original[pipeline_uid]
		if points_df is not None and not points_df.empty:
			uid_points = points_df.loc[points_df["UID"] == original_uid].rename(columns={"UID": "uid", "CID": "cid"})
			uid_points.to_csv(target_dir / "fmm.csv", index=False)
		else:
			(target_dir / "fmm.csv").write_text("uid,cid,latitude,longitude,t_in,match_type\n", encoding="utf-8")
		if line_df is not None and not line_df.empty:
			uid_line = line_df.loc[line_df["UID"] == original_uid].rename(columns={"UID": "uid", "CID": "cid"})
			keep_cols = [
				col
				for col in (
					"uid",
					"latitude",
					"longitude",
					"match_type",
					"segment_idx",
					"od_segment_idx",
					"is_stationary",
					"point_order",
					"segment_start_time",
					"segment_end_time",
				)
				if col in uid_line.columns
			]
			uid_line[keep_cols].to_csv(target_dir / "line.csv", index=False)
		else:
			(target_dir / "line.csv").write_text("uid,latitude,longitude,match_type,segment_idx,is_stationary,point_order\n", encoding="utf-8")
	write_json(result_root / "manifest.json", {"variant": variant.name, "source_root": str(source_root), "uids": list(pipeline_to_original.values())})
	return result_root


def run_variant(
	*,
	variant: Variant,
	input_path: Path,
	baseline_root: Path,
	experiment_root: Path,
	force: bool,
) -> Path:
	if variant.kind == "pipeline":
		return run_pipeline_variant(
			variant=variant,
			input_path=input_path,
			experiment_root=experiment_root,
			force=force,
		)
	if variant.kind == "direct_snap":
		return run_direct_snap_variant(
			variant=variant,
			source_root=baseline_root,
			experiment_root=experiment_root,
			force=force,
		)
	raise ValueError(f"unsupported variant kind: {variant.kind}")


def print_summary_table(evaluations: list[dict[str, Any]]) -> None:
	cols = [
		"variant",
		"50m",
		"100m",
		"100m+500m trim",
		"100m+1000m trim",
		"180m",
		"best<=100m",
	]
	print("\t".join(cols))
	for item in evaluations:
		key = item["key_metrics"]
		best_under_100 = item.get("best_excluding_route04_under_100m") or {}
		values = [
			item["name"],
			f"{key['50m_trim0m']['excluding_route04_accuracy_percent']:.2f}",
			f"{key['100m_trim0m']['excluding_route04_accuracy_percent']:.2f}",
			f"{key['100m_trim500m']['excluding_route04_accuracy_percent']:.2f}",
			f"{key['100m_trim1000m']['excluding_route04_accuracy_percent']:.2f}",
			f"{key['180m_trim0m']['excluding_route04_accuracy_percent']:.2f}",
			(
				f"{best_under_100.get('excluding_route04_accuracy_percent', 0.0):.2f}"
				f"@{int(best_under_100.get('threshold_m', 0))}m+{int(best_under_100.get('trim_each_end_m', 0))}m"
				if best_under_100
				else ""
			),
		]
		print("\t".join(values))


def main() -> int:
	args = parse_args()
	experiment_root = args.experiment_root.expanduser().resolve()
	experiment_root.mkdir(parents=True, exist_ok=True)
	output_json = args.output_json or (experiment_root / "experiment_summary.json")

	evaluations: list[dict[str, Any]] = []
	if not args.skip_baseline:
		evaluations.append(
			evaluate_result_root(
				name="baseline_current",
				description="当前 demo 使用的 v311 snap+OD+FMM 输出",
				result_root=args.baseline_root,
				signal_segment_dir=args.signal_segment_dir,
				gps_truth_dir=args.gps_truth_dir,
			)
		)

	for variant in selected_variants(args.variants):
		result_root = experiment_root / variant.name / "result"
		if args.run_variants or args.force_runs or not result_root.exists():
			if not args.run_variants and not args.force_runs:
				continue
			result_root = run_variant(
				variant=variant,
				input_path=args.input,
				baseline_root=args.baseline_root.expanduser().resolve(),
				experiment_root=experiment_root,
				force=args.force_runs,
			)
		evaluations.append(
			evaluate_result_root(
				name=variant.name,
				description=variant.description,
				result_root=result_root,
				signal_segment_dir=args.signal_segment_dir,
				gps_truth_dir=args.gps_truth_dir,
			)
		)

	report = {
		"metric_definition": "GPS truth geometry length covered by reconstructed line within threshold; trim removes meters from both ends of each GPS truth route before scoring.",
		"experiment_root": str(experiment_root),
		"baseline_root": str(args.baseline_root.expanduser().resolve()),
		"thresholds_m": list(THRESHOLDS_M),
		"trim_each_end_m": list(TRIMS_M),
		"evaluations": evaluations,
	}
	write_json(output_json.expanduser().resolve(), report)
	print_summary_table(evaluations)
	print(json.dumps({"ok": True, "output_json": str(output_json.expanduser().resolve()), "variant_count": len(evaluations)}, ensure_ascii=False))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
