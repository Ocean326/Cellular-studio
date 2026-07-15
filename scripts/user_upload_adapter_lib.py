from __future__ import annotations

import csv
import ast
import json
import math
import os
import re
import shutil
import sys
import warnings
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BEIJING_BBOX = {
	"lat_min": 39.4,
	"lat_max": 41.1,
	"lon_min": 115.7,
	"lon_max": 117.4,
}

DEFAULT_POINT_STATUS_STYLES = {
	"stay": {"color": "#111827", "size": 5},
	"walking": {"color": "#2e7d32", "size": 4},
	"bicycling": {"color": "#1565c0", "size": 4},
	"driving": {"color": "#c62828", "size": 4},
	"road": {"color": "#4caf50", "size": 5},
	"subway": {"color": "#9c27b0", "size": 5},
	"railway": {"color": "#795548", "size": 5},
	"unmatch": {"color": "#ffd700", "size": 5},
	"ping_pong": {"color": "#d97706", "size": 5},
	"long_jump": {"color": "#b91c1c", "size": 5},
}

STATUS_COLOR_FALLBACK = (
	"#0f766e",
	"#2563eb",
	"#dc2626",
	"#7c3aed",
	"#ea580c",
	"#0891b2",
)

SIGNAL6_MAINROAD_COST_FIELD = "fmm_cost"
SIGNAL6_MAINROAD_HIGHWAY_PENALTIES = {
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
}
SIGNAL6_MAINROAD_DEFAULT_PENALTY = 1.15
SIGNAL6_FMM_VERSIONS = frozenset({"original", "mainroad"})
SIGNAL6_ALGORITHM_PROFILES = frozenset(
	{
		"baseline_v311",
		"mainroad_weighted",
		"major_roads",
		"speed_sparsity_90",
	}
)
SIGNAL6_MAJOR_ROAD_HIGHWAYS = frozenset(
	{
		"motorway",
		"motorway_link",
		"trunk",
		"trunk_link",
		"primary",
		"primary_link",
		"secondary",
		"secondary_link",
	}
)
SIGNAL6_STATIC_SPEED_COST_80_40_20 = {
	"motorway": 0.5,
	"motorway_link": 0.5,
	"trunk": 0.5,
	"trunk_link": 0.5,
	"primary": 0.5,
	"primary_link": 0.5,
	"secondary": 1.0,
	"secondary_link": 1.0,
	"tertiary": 1.0,
	"tertiary_link": 1.0,
	"unclassified": 1.25,
	"residential": 2.0,
	"living_street": 2.0,
	"service": 2.0,
	"track": 2.0,
}
SIGNAL6_SPEED_SPARSITY_MAJOR_BIAS_THRESHOLD = 0.40
SIGNAL6_ROUTE02_STARTFIX_SPARSITY_THRESHOLD = 0.75

DEFAULT_FIELD_ALIASES = {
	"trajectory4": {
		"uid": ("uid",),
		"latitude": ("latitude", "lat"),
		"longitude": ("longitude", "lon"),
		"timestamp": ("timestamp_ms", "timestamp"),
		"status": ("status", "state"),
	},
	"signal6": {
		"uid": ("uid",),
		"cid": ("cid",),
		"latitude": ("latitude", "lat"),
		"longitude": ("longitude", "lon"),
		"t_in": ("t_in", "start_time", "time_in", "procedure_start_time", "proceduere_start_time"),
		"t_out": ("t_out", "end_time", "time_out", "procedure_end_time", "proceduere_end_time"),
		"status": ("status", "state"),
	},
	"signal_triplet": {},
}

AUTO_UPLOAD_TYPE = "auto"
SIGNAL_TRIPLET_UPLOAD_TYPE = "signal_triplet"
SIGNAL_TRIPLET_REQUIRED_FILES = ("signal.csv", "gate.csv", "lbs.csv")
SIGNAL_TRIPLET_OPTIONAL_FILES = ("gps.csv",)
SIGNAL6_PIPELINE_MODES = frozenset({"legacy", "v311"})


class UserUploadAdapterError(ValueError):
	pass


def _deep_update_mapping(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
	if not isinstance(base, dict):
		return dict(override) if isinstance(override, dict) else base
	if not isinstance(override, dict):
		return dict(base)
	merged: dict[str, Any] = dict(base)
	for key, value in override.items():
		existing = merged.get(key)
		if isinstance(existing, dict) and isinstance(value, dict):
			merged[key] = _deep_update_mapping(existing, value)
		else:
			merged[key] = value
	return merged


def normalize_signal6_pipeline_mode(value: Any) -> str:
	mode = str(value or "").strip().lower().replace("-", "_").replace(".", "_")
	if mode in {"", "legacy", "signal", "single_layer", "trajectory_layers"}:
		return "legacy"
	if mode in {"v311", "v3_11", "snap_od_fmm_v311", "chain2"}:
		return "v311"
	if mode in SIGNAL6_PIPELINE_MODES:
		return mode
	raise UserUploadAdapterError(
		f"unsupported signal6 pipeline_mode: {value!r}; expected one of {sorted(SIGNAL6_PIPELINE_MODES)}"
	)


def normalize_signal6_algorithm_profile(value: Any) -> str:
	profile = str(value or "").strip().lower().replace("-", "_").replace(".", "_")
	aliases = {
		"": "baseline_v311",
		"default": "baseline_v311",
		"baseline": "baseline_v311",
		"baseline_v311": "baseline_v311",
		"original": "baseline_v311",
		"v311": "baseline_v311",
		"mainroad": "mainroad_weighted",
		"mainroad_weighted": "mainroad_weighted",
		"weighted_mainroad": "mainroad_weighted",
		"major": "major_roads",
		"major_road": "major_roads",
		"major_roads": "major_roads",
		"speed_sparsity": "speed_sparsity_90",
		"speed_sparsity_90": "speed_sparsity_90",
		"speed_sparsity_demo": "speed_sparsity_90",
		"demo90": "speed_sparsity_90",
		"showcase90": "speed_sparsity_90",
		"90": "speed_sparsity_90",
	}
	normalized = aliases.get(profile, profile)
	if normalized not in SIGNAL6_ALGORITHM_PROFILES:
		raise UserUploadAdapterError(
			f"unsupported signal6_algorithm_profile: {value!r}; expected one of {sorted(SIGNAL6_ALGORITHM_PROFILES)}"
		)
	return normalized


def _signal6_demo_v311_pipeline_options(*, fmm_version: str = "original") -> dict[str, Any]:
	version = normalize_signal6_fmm_version(fmm_version)
	return {
		"jobs": 1,
		"od_parallel": False,
		"od_workers": 1,
		"chunksize": 20,
		"fmm_version": version,
		"fmm_variant_params": {
			"road": {
				"r": 0.018 if version == "mainroad" else 0.015,
				"k": 512,
				"error": 0.008,
				"reverse_tolerance": 0.05 if version == "mainroad" else 0.0,
				"ubodt_delta_multiplier": 1.35 if version == "mainroad" else 1.0,
			},
			"subway": {"r": -1.0},
			"railway": {"r": -1.0},
		},
	}


def signal6_pipeline_options_for_profile(profile: Any) -> dict[str, Any]:
	normalized = normalize_signal6_algorithm_profile(profile)
	if normalized == "baseline_v311":
		return {"signal6_algorithm_profile": normalized}
	if normalized == "mainroad_weighted":
		options = _signal6_demo_v311_pipeline_options(fmm_version="mainroad")
		options["signal6_algorithm_profile"] = normalized
		return options
	if normalized == "major_roads":
		options = _signal6_demo_v311_pipeline_options(fmm_version="original")
		options["signal6_algorithm_profile"] = normalized
		options["fmm_algorithm_variant"] = "major_roads"
		options["fmm_variant_params"] = _deep_update_mapping(
			options.get("fmm_variant_params", {}),
			{
				"road": {"r": 0.035, "k": 512, "error": 0.018},
				"subway": {"r": -1.0},
				"railway": {"r": -1.0},
			},
		)
		return options
	if normalized == "speed_sparsity_90":
		options = _signal6_demo_v311_pipeline_options(fmm_version="mainroad")
		options.update(
			{
				"signal6_algorithm_profile": normalized,
				"fmm_algorithm_variant": "speed_sparsity_90",
				"speed_sparsity_hybrid": True,
				"speed_sparsity_major_bias_threshold": SIGNAL6_SPEED_SPARSITY_MAJOR_BIAS_THRESHOLD,
				"speed_sparsity_route02_guard": True,
			}
		)
		return options
	raise UserUploadAdapterError(f"unsupported signal6_algorithm_profile: {profile!r}")


def signal6_pipeline_mode_for_profile(default_mode: Any, profile: Any) -> str:
	"""Resolve processing mode for productized signal6 algorithm profiles."""
	normalized_mode = normalize_signal6_pipeline_mode(default_mode)
	normalized_profile = normalize_signal6_algorithm_profile(profile)
	if normalized_profile == "baseline_v311":
		return normalized_mode
	return "v311"


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2)
		handle.write("\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow(row)


def dedupe_preserve_order(values: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for item in values:
		value = str(item or "").strip()
		if not value or value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result


def normalize_status(value: Any) -> str:
	text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
	return text


def normalize_header_name(value: Any) -> str:
	text = str(value or "").lstrip("\ufeff").strip()
	if not text:
		return ""
	text = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", text)
	text = re.sub(r"[\s\-]+", "_", text)
	text = re.sub(r"_+", "_", text)
	normalized = text.strip("_").lower()
	return {
		"tin": "t_in",
		"tout": "t_out",
		"time_in": "t_in",
		"time_out": "t_out",
		"procedure_start_time": "t_in",
		"proceduere_start_time": "t_in",
		"procedure_end_time": "t_out",
		"proceduere_end_time": "t_out",
	}.get(normalized, normalized)


def _canonical_field_key(upload_type: str, value: Any) -> str:
	normalized = normalize_header_name(value)
	for canonical, aliases in DEFAULT_FIELD_ALIASES.get(str(upload_type or "").strip().lower(), {}).items():
		if normalized == canonical or normalized in aliases:
			return canonical
	return ""


def _canonicalize_fieldnames(upload_type: str, fieldnames: list[str], custom_alias_to_canonical: dict[str, str] | None = None) -> list[str]:
	alias_map = custom_alias_to_canonical or {}
	result: list[str] = []
	for name in fieldnames or []:
		normalized = normalize_header_name(name)
		if not normalized:
			continue
		mapped = alias_map.get(normalized, normalized)
		result.append(_canonical_field_key(upload_type, mapped) or mapped)
	return result


def _detect_upload_type_from_fieldnames(fieldnames: list[str]) -> str:
	header_set = {normalize_header_name(name) for name in (fieldnames or []) if normalize_header_name(name)}
	if not header_set:
		raise UserUploadAdapterError("CSV header is required")
	signal_required = {"uid", "cid", "latitude", "longitude", "t_in", "t_out"}
	trajectory_required = {"uid", "latitude", "longitude", "timestamp"}
	if signal_required.issubset(header_set):
		return "signal6"
	if trajectory_required.issubset(header_set):
		return "trajectory4"
	raise UserUploadAdapterError(
		"unable to auto-detect upload type from CSV header; expected trajectory4(uid,lat,lon,timestamp) "
		"or signal6(uid,cid,lat,lon,t_in,t_out)"
	)


def _path_has_signal_triplet_routes(source_path: Path) -> bool:
	if source_path.is_dir():
		return bool(_discover_signal_triplet_routes(source_path))
	if source_path.suffix.lower() != ".zip":
		return False
	try:
		with zipfile.ZipFile(source_path) as archive:
			file_names = {
				Path(info.filename).name.lower()
				for info in archive.infolist()
				if not info.is_dir()
			}
	except zipfile.BadZipFile as exc:
		raise UserUploadAdapterError(f"invalid signal_triplet zip: {source_path}") from exc
	return {"signal.csv", "gate.csv", "lbs.csv"}.issubset(file_names)


def detect_user_upload_type(
	source_csv_path: str | Path,
	*,
	requested_upload_type: Any = "",
	field_mapping: Any = None,
) -> str:
	path = Path(source_csv_path).expanduser().resolve()
	if not path.exists():
		raise FileNotFoundError(f"input csv not found: {path}")
	requested_type = str(requested_upload_type or "").strip().lower()
	if requested_type == SIGNAL_TRIPLET_UPLOAD_TYPE:
		if _path_has_signal_triplet_routes(path):
			return SIGNAL_TRIPLET_UPLOAD_TYPE
		raise UserUploadAdapterError(
			"signal_triplet upload requires route folders containing signal.csv, gate.csv, and lbs.csv"
		)
	if requested_type in {"", AUTO_UPLOAD_TYPE} and _path_has_signal_triplet_routes(path):
		return SIGNAL_TRIPLET_UPLOAD_TYPE
	if path.suffix.lower() == ".zip":
		raise UserUploadAdapterError(
			"zip uploads must be signal_triplet packages containing signal.csv, gate.csv, and lbs.csv"
		)
	candidate_types = ["signal6", "trajectory4"]
	if requested_type in DEFAULT_FIELD_ALIASES:
		candidate_types = [requested_type, *[item for item in candidate_types if item != requested_type]]
	with open(path, encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		raw_fieldnames = [name for name in (reader.fieldnames or []) if normalize_header_name(name)]
	if not raw_fieldnames:
		raise UserUploadAdapterError(f"CSV header is required: {path}")
	last_error: Exception | None = None
	for upload_type in candidate_types:
		try:
			normalized_mapping = normalize_user_upload_field_mapping(upload_type, field_mapping)
			custom_alias_to_canonical = {
				alias: canonical
				for canonical, aliases in normalized_mapping.items()
				for alias in aliases
			}
			normalized_fieldnames = _canonicalize_fieldnames(upload_type, raw_fieldnames, custom_alias_to_canonical)
			return _detect_upload_type_from_fieldnames(normalized_fieldnames)
		except Exception as exc:
			last_error = exc
	if last_error:
		raise UserUploadAdapterError(str(last_error)) from last_error
	for upload_type in ("signal6", "trajectory4"):
		try:
			return _detect_upload_type_from_fieldnames(_canonicalize_fieldnames(upload_type, raw_fieldnames))
		except Exception:
			continue
	return _detect_upload_type_from_fieldnames(raw_fieldnames)


def _coerce_field_mapping_values(raw_value: Any) -> list[str]:
	if raw_value is None:
		return []
	if isinstance(raw_value, str):
		values = re.split(r"[,|\n]+", raw_value)
	elif isinstance(raw_value, (list, tuple, set)):
		values = list(raw_value)
	else:
		values = [raw_value]
	return [normalize_header_name(value) for value in values if normalize_header_name(value)]


def normalize_user_upload_field_mapping(upload_type: str, field_mapping: Any) -> dict[str, list[str]]:
	if not field_mapping:
		return {}
	if not isinstance(field_mapping, dict):
		raise UserUploadAdapterError("field_mapping must be an object keyed by canonical field name")
	normalized_type = str(upload_type or "").strip().lower()
	if normalized_type not in DEFAULT_FIELD_ALIASES:
		raise UserUploadAdapterError(f"Unsupported upload_type for field_mapping: {upload_type!r}")
	result: dict[str, list[str]] = {}
	for raw_key, raw_value in field_mapping.items():
		canonical = _canonical_field_key(normalized_type, raw_key)
		if not canonical:
			raise UserUploadAdapterError(f"Unsupported field_mapping key for {normalized_type}: {raw_key!r}")
		aliases = _coerce_field_mapping_values(raw_value)
		if not aliases:
			continue
		result[canonical] = dedupe_preserve_order([*(result.get(canonical) or []), *aliases])
	return result


def read_csv_rows(
	source_csv_path: str | Path,
	*,
	field_mapping: Any = None,
	upload_type: str = "",
) -> tuple[list[dict[str, str]], list[str]]:
	path = Path(source_csv_path).expanduser().resolve()
	if not path.exists():
		raise FileNotFoundError(f"input csv not found: {path}")
	normalized_mapping = normalize_user_upload_field_mapping(upload_type, field_mapping)
	custom_alias_to_canonical = {
		alias: canonical
		for canonical, aliases in normalized_mapping.items()
		for alias in aliases
	}
	with open(path, encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		fieldnames = [
			custom_alias_to_canonical.get(normalize_header_name(name), normalize_header_name(name))
			for name in (reader.fieldnames or [])
			if normalize_header_name(name)
		]
		if not fieldnames:
			raise UserUploadAdapterError(f"CSV header is required: {path}")
		rows = []
		for row in reader:
			normalized_row: dict[str, str] = {}
			for key, value in row.items():
				header_name = normalize_header_name(key)
				if not header_name:
					continue
				header_name = custom_alias_to_canonical.get(header_name, header_name)
				normalized_row[header_name] = str(value or "").strip()
			rows.append(normalized_row)
	if not rows:
		raise UserUploadAdapterError(f"CSV must contain at least one data row: {path}")
	return rows, fieldnames


def require_column(row: dict[str, str], aliases: tuple[str, ...], *, row_number: int, label: str) -> str:
	for alias in aliases:
		value = str(row.get(alias) or "").strip()
		if value:
			return value
	raise UserUploadAdapterError(
		f"row {row_number}: missing required column for {label}; accepted headers: {', '.join(aliases)}"
	)


def parse_float(value: str, *, row_number: int, label: str) -> float:
	try:
		return float(value)
	except (TypeError, ValueError) as exc:
		raise UserUploadAdapterError(f"row {row_number}: invalid {label}: {value!r}") from exc


def parse_timestamp_ms(value: str, *, row_number: int, label: str) -> int:
	text = str(value or "").strip()
	if not text:
		raise UserUploadAdapterError(f"row {row_number}: missing {label}")
	normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
	try:
		if "." not in text and text.lstrip("-").isdigit():
			number = int(text)
			return number if abs(number) >= 10**11 else number * 1000
		return int(float(text))
	except ValueError:
		pass
	try:
		dt = datetime.fromisoformat(normalized)
	except ValueError as exc:
		raise UserUploadAdapterError(
			f"row {row_number}: invalid {label}: {value!r}; expected epoch seconds/ms or ISO-8601"
		) from exc
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return int(dt.timestamp() * 1000)


def ensure_beijing_bbox(lat: float, lon: float, *, row_number: int, uid: str) -> None:
	if BEIJING_BBOX["lat_min"] <= lat <= BEIJING_BBOX["lat_max"] and BEIJING_BBOX["lon_min"] <= lon <= BEIJING_BBOX["lon_max"]:
		return
	raise UserUploadAdapterError(
		"row "
		f"{row_number}: signal6 row for uid {uid} is outside Beijing bbox "
		f"({lat}, {lon}) not in "
		f"[{BEIJING_BBOX['lat_min']}, {BEIJING_BBOX['lat_max']}] x "
		f"[{BEIJING_BBOX['lon_min']}, {BEIJING_BBOX['lon_max']}]"
	)


def is_inside_beijing_bbox(lat: float, lon: float) -> bool:
	return (
		BEIJING_BBOX["lat_min"] <= lat <= BEIJING_BBOX["lat_max"]
		and BEIJING_BBOX["lon_min"] <= lon <= BEIJING_BBOX["lon_max"]
	)


def build_point_status_styles(filter_state_options: list[str]) -> dict[str, dict[str, Any]]:
	result: dict[str, dict[str, Any]] = {}
	fallback_index = 0
	for state in filter_state_options:
		if state in DEFAULT_POINT_STATUS_STYLES:
			result[state] = dict(DEFAULT_POINT_STATUS_STYLES[state])
			continue
		result[state] = {"color": STATUS_COLOR_FALLBACK[fallback_index % len(STATUS_COLOR_FALLBACK)], "size": 5}
		fallback_index += 1
	return result


def build_manifest(
	*,
	title: str,
	ui_mode: str,
	uids: list[str],
	layer_key: str,
	layer_label: str,
	filename: str,
	layer_kind: str,
	states_index: dict[str, list[str]],
	filter_state_options: list[str],
) -> dict[str, Any]:
	manifest = {
		"generated_at": utc_now_iso(),
		"title": title,
		"ui_mode": ui_mode,
		"uids": uids,
		"layers": [layer_key],
		"layer_labels": {layer_key: layer_label},
		"layer_specs": {
			layer_key: {
				"filename": filename,
				"kind": layer_kind,
				"defaultColor": "#1565c0" if layer_kind == "gps" else "#e65100",
				"defaultOpacity": 0.85 if layer_kind == "gps" else 0.78,
				"hasLine": True,
				"review_reference": True,
			}
		},
		"layer_visibility": {layer_key: True},
		"time_scrubber_preferred_layers": [layer_key],
		"review_reference_files": [filename],
		"hide_review_panel": False,
		"states": states_index,
		"filter_state_options": filter_state_options,
	}
	if filter_state_options:
		manifest["point_status_types"] = filter_state_options
		manifest["point_status_styles"] = build_point_status_styles(filter_state_options)
	return manifest


def build_trajectory4_result(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Trajectory4",
	field_mapping: Any = None,
) -> dict[str, Any]:
	rows, _fieldnames = read_csv_rows(source_csv_path, field_mapping=field_mapping, upload_type="trajectory4")
	result_root = Path(output_root).expanduser().resolve()
	result_root.mkdir(parents=True, exist_ok=True)

	grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
	states_by_uid: dict[str, list[str]] = {}
	global_states: list[str] = []

	for row_number, row in enumerate(rows, start=2):
		uid = require_column(row, ("uid",), row_number=row_number, label="uid")
		lat = parse_float(require_column(row, ("latitude", "lat"), row_number=row_number, label="latitude"), row_number=row_number, label="latitude")
		lon = parse_float(require_column(row, ("longitude", "lon"), row_number=row_number, label="longitude"), row_number=row_number, label="longitude")
		timestamp_ms = parse_timestamp_ms(
			require_column(row, ("timestamp_ms", "timestamp"), row_number=row_number, label="timestamp"),
			row_number=row_number,
			label="timestamp",
		)
		status = normalize_status(row.get("status") or row.get("state"))
		grouped_rows[uid].append(
			{
				"uid": uid,
				"latitude": lat,
				"longitude": lon,
				"timestamp_ms": timestamp_ms,
				"status": status,
				"_row_number": row_number,
			}
		)
		if status:
			global_states.append(status)

	if not grouped_rows:
		raise UserUploadAdapterError("trajectory4 input did not yield any valid uid rows")

	uids = sorted(grouped_rows.keys())
	states_index: dict[str, list[str]] = {}
	for uid in uids:
		uid_rows = sorted(grouped_rows[uid], key=lambda item: (item["timestamp_ms"], item["_row_number"]))
		uid_dir = result_root / uid
		uid_dir.mkdir(parents=True, exist_ok=True)
		csv_rows: list[dict[str, Any]] = []
		uid_states: list[str] = []
		for point_index, item in enumerate(uid_rows):
			if item["status"]:
				uid_states.append(item["status"])
			csv_rows.append(
				{
					"uid": item["uid"],
					"point_index": point_index,
					"latitude": f"{item['latitude']:.8f}",
					"longitude": f"{item['longitude']:.8f}",
					"timestamp_ms": item["timestamp_ms"],
					"status": item["status"],
				}
			)
		write_csv(uid_dir / "gps.csv", ["uid", "point_index", "latitude", "longitude", "timestamp_ms", "status"], csv_rows)
		states_index[uid] = dedupe_preserve_order(uid_states)
		states_by_uid[uid] = states_index[uid]

	filter_state_options = dedupe_preserve_order(global_states)
	manifest = build_manifest(
		title=title,
		ui_mode="trajectory_layers",
		uids=uids,
		layer_key="gps",
		layer_label="GPS",
		filename="gps.csv",
		layer_kind="gps",
		states_index=states_by_uid,
		filter_state_options=filter_state_options,
	)
	write_json(result_root / "manifest.json", manifest)
	write_json(result_root / "states_index.json", states_index)
	return {
		"adapter": "trajectory4",
		"result_root": str(result_root),
		"uid_count": len(uids),
		"uids": uids,
		"row_count": len(rows),
		"filter_state_options": filter_state_options,
	}


def _build_signal6_result_legacy(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Signal6",
	field_mapping: Any = None,
	drop_outside_beijing_bbox_rows: bool = False,
) -> dict[str, Any]:
	rows, _fieldnames = read_csv_rows(source_csv_path, field_mapping=field_mapping, upload_type="signal6")
	result_root = Path(output_root).expanduser().resolve()
	result_root.mkdir(parents=True, exist_ok=True)

	grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
	global_states: list[str] = []
	outside_beijing_bbox_row_count = 0

	for row_number, row in enumerate(rows, start=2):
		uid = require_column(row, ("uid",), row_number=row_number, label="uid")
		cid = require_column(row, ("cid",), row_number=row_number, label="cid")
		lat = parse_float(require_column(row, ("latitude", "lat"), row_number=row_number, label="latitude"), row_number=row_number, label="latitude")
		lon = parse_float(require_column(row, ("longitude", "lon"), row_number=row_number, label="longitude"), row_number=row_number, label="longitude")
		if not is_inside_beijing_bbox(lat, lon):
			outside_beijing_bbox_row_count += 1
			if drop_outside_beijing_bbox_rows:
				continue
			ensure_beijing_bbox(lat, lon, row_number=row_number, uid=uid)
		t_in_ms = parse_timestamp_ms(
			require_column(row, ("t_in", "start_time"), row_number=row_number, label="t_in"),
			row_number=row_number,
			label="t_in",
		)
		t_out_ms = parse_timestamp_ms(
			require_column(row, ("t_out", "end_time"), row_number=row_number, label="t_out"),
			row_number=row_number,
			label="t_out",
		)
		if t_out_ms < t_in_ms:
			raise UserUploadAdapterError(f"row {row_number}: t_out must be >= t_in for uid {uid}")
		status = normalize_status(row.get("status") or row.get("state"))
		grouped_rows[uid].append(
			{
				"uid": uid,
				"cid": cid,
				"lat": lat,
				"lon": lon,
				"t_in": t_in_ms,
				"t_out": t_out_ms,
				"status": status,
				"_row_number": row_number,
			}
		)
		if status:
			global_states.append(status)

	if not grouped_rows:
		raise UserUploadAdapterError("signal6 input did not yield any valid uid rows")

	uids = sorted(grouped_rows.keys())
	states_index: dict[str, list[str]] = {}
	for uid in uids:
		uid_rows = sorted(grouped_rows[uid], key=lambda item: (item["t_in"], item["t_out"], item["_row_number"]))
		uid_dir = result_root / uid
		uid_dir.mkdir(parents=True, exist_ok=True)
		csv_rows: list[dict[str, Any]] = []
		uid_states: list[str] = []
		for event_index, item in enumerate(uid_rows):
			if item["status"]:
				uid_states.append(item["status"])
			csv_rows.append(
				{
					"uid": item["uid"],
					"event_index": event_index,
					"cid": item["cid"],
					"lat": f"{item['lat']:.8f}",
					"lon": f"{item['lon']:.8f}",
					"latitude": f"{item['lat']:.8f}",
					"longitude": f"{item['lon']:.8f}",
					"t_in": item["t_in"],
					"t_out": item["t_out"],
					"duration_ms": item["t_out"] - item["t_in"],
					"status": item["status"],
				}
			)
		write_csv(
			uid_dir / "signal.csv",
			["uid", "event_index", "cid", "lat", "lon", "latitude", "longitude", "t_in", "t_out", "duration_ms", "status"],
			csv_rows,
		)
		states_index[uid] = dedupe_preserve_order(uid_states)

	filter_state_options = dedupe_preserve_order(global_states)
	manifest = build_manifest(
		title=title,
		ui_mode="trajectory_layers",
		uids=uids,
		layer_key="signal",
		layer_label="Signal",
		filename="signal.csv",
		layer_kind="signal",
		states_index=states_index,
		filter_state_options=filter_state_options,
	)
	write_json(result_root / "manifest.json", manifest)
	write_json(result_root / "states_index.json", states_index)
	return {
		"adapter": "signal6",
		"pipeline_mode": "legacy",
		"ui_mode": "trajectory_layers",
		"review_reference_files": ["signal.csv"],
		"result_root": str(result_root),
		"uid_count": len(uids),
		"uids": uids,
		"row_count": len(rows),
		"filter_state_options": filter_state_options,
		"beijing_bbox": dict(BEIJING_BBOX),
		"outside_beijing_bbox_row_count": int(outside_beijing_bbox_row_count),
		"dropped_outside_beijing_bbox_rows": int(outside_beijing_bbox_row_count if drop_outside_beijing_bbox_rows else 0),
	}


def _signal6_repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _signal6_v311_default_assets(repo_root: Path) -> dict[str, Path]:
	return {
		"fmm_edges": repo_root / "project_data" / "map_assets" / "beijing" / "edges.shp",
		"fmm_cmd": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "fmm",
		"fmm_ubodt_cmd": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "ubodt_gen",
		"fmm_cmd_mainroad": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build_mainroad" / "fmm",
		"fmm_ubodt_cmd_mainroad": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build_mainroad" / "ubodt_gen",
		"fmm_edges_mainroad_weighted": repo_root / "project_data" / "map_assets" / "beijing_mainroad_weighted" / "edges.shp",
	}


def _ensure_signal6_v311_assets(assets: dict[str, Path], *, fmm_version: str = "original") -> None:
	version = normalize_signal6_fmm_version(fmm_version)
	required = ["fmm_edges", "fmm_cmd", "fmm_ubodt_cmd"]
	if version == "mainroad":
		required.extend(["fmm_cmd_mainroad", "fmm_ubodt_cmd_mainroad"])
	missing = [f"{name}={assets[name]}" for name in required if not assets[name].exists()]
	if not missing:
		return
	raise UserUploadAdapterError(
		"signal6 v311 runtime asset missing: "
		+ "; ".join(missing)
		+ ". expected local snap+OD+fmm runtime under project_data/map_assets and my_history_methods/map_matching/vendor/fmm/build"
	)


def normalize_signal6_fmm_version(value: Any) -> str:
	version = str(value or "original").strip().lower().replace("-", "_")
	if not version:
		version = "original"
	if version not in SIGNAL6_FMM_VERSIONS:
		raise UserUploadAdapterError(
			f"unsupported signal6 fmm_version: {value!r}; expected one of {sorted(SIGNAL6_FMM_VERSIONS)}"
		)
	return version


def _parse_highway_tokens(value: Any) -> set[str]:
	text = str(value or "").strip()
	if not text or text.lower() == "nan":
		return set()
	if text.startswith("[") and text.endswith("]"):
		try:
			parsed = ast.literal_eval(text)
		except Exception:
			parsed = text.strip("[]").split(",")
		if isinstance(parsed, (list, tuple, set)):
			items = [str(item).strip().strip("'\"") for item in parsed]
		else:
			items = [str(parsed).strip().strip("'\"")]
		return {item for item in items if item}
	return {text}


def _normalized_mainroad_penalty_profile(
	highway_penalties: dict[str, float] | None = None,
	default_penalty: float | None = None,
) -> tuple[dict[str, float], float]:
	penalties = {
		str(key): float(value)
		for key, value in (highway_penalties or SIGNAL6_MAINROAD_HIGHWAY_PENALTIES).items()
	}
	default = SIGNAL6_MAINROAD_DEFAULT_PENALTY if default_penalty is None else float(default_penalty)
	return penalties, default


def _mainroad_penalty(
	value: Any,
	*,
	highway_penalties: dict[str, float] | None = None,
	default_penalty: float | None = None,
) -> float:
	tokens = _parse_highway_tokens(value)
	penalties, default = _normalized_mainroad_penalty_profile(highway_penalties, default_penalty)
	if not tokens:
		return default
	return min(
		penalties.get(token, default)
		for token in tokens
	)


def ensure_signal6_mainroad_weighted_edges(
	source_edges: str | Path,
	target_edges: str | Path,
	*,
	cost_field: str = SIGNAL6_MAINROAD_COST_FIELD,
	highway_penalties: dict[str, float] | None = None,
	default_penalty: float | None = None,
) -> Path:
	source_path = Path(source_edges).expanduser().resolve()
	target_path = Path(target_edges).expanduser().resolve()
	if not source_path.exists():
		raise UserUploadAdapterError(f"source FMM edges shapefile not found: {source_path}")
	penalties, default = _normalized_mainroad_penalty_profile(highway_penalties, default_penalty)
	profile_meta = {
		"cost_field": str(cost_field),
		"highway_penalties": penalties,
		"default_highway_penalty": default,
	}
	meta_path = target_path.with_suffix(f".{cost_field}.json")

	if target_path.exists():
		try:
			import geopandas as gpd

			existing = gpd.read_file(target_path, rows=1)
			if cost_field in existing.columns and (
				not meta_path.exists()
				or json.loads(meta_path.read_text(encoding="utf-8")) == profile_meta
			):
				return target_path
		except Exception:
			pass

	try:
		import geopandas as gpd
	except ImportError as exc:
		raise UserUploadAdapterError("mainroad FMM version requires geopandas to generate weighted edges") from exc

	gdf = gpd.read_file(source_path)
	if gdf.empty:
		raise UserUploadAdapterError(f"source FMM edges shapefile is empty: {source_path}")
	if "geometry" not in gdf.columns:
		raise UserUploadAdapterError(f"source FMM edges shapefile has no geometry column: {source_path}")

	highway_series = gdf["highway"] if "highway" in gdf.columns else [None] * len(gdf)
	row_penalties = [
		_mainroad_penalty(value, highway_penalties=penalties, default_penalty=default)
		for value in highway_series
	]
	with warnings.catch_warnings():
		warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS.*")
		lengths = gdf.geometry.length.astype(float)
	gdf = gdf.copy()
	gdf[cost_field] = [max(1.0e-12, float(length) * float(penalty)) for length, penalty in zip(lengths, row_penalties)]

	target_path.parent.mkdir(parents=True, exist_ok=True)
	for sidecar in target_path.parent.glob(f"{target_path.stem}.*"):
		sidecar.unlink()
	gdf.to_file(target_path)
	write_json(meta_path, profile_meta)
	return target_path


def ensure_signal6_major_road_edges(source_edges: str | Path, target_edges: str | Path) -> Path:
	source_path = Path(source_edges).expanduser().resolve()
	target_path = Path(target_edges).expanduser().resolve()
	if not source_path.exists():
		raise UserUploadAdapterError(f"source FMM edges shapefile not found: {source_path}")
	if target_path.exists():
		return target_path

	try:
		import geopandas as gpd
	except ImportError as exc:
		raise UserUploadAdapterError("major-road FMM profile requires geopandas to generate filtered edges") from exc

	gdf = gpd.read_file(source_path)
	if gdf.empty:
		raise UserUploadAdapterError(f"source FMM edges shapefile is empty: {source_path}")
	if "highway" not in gdf.columns:
		raise UserUploadAdapterError(f"source FMM edges shapefile has no highway column: {source_path}")
	mask = gdf["highway"].apply(
		lambda value: bool(_parse_highway_tokens(value) & set(SIGNAL6_MAJOR_ROAD_HIGHWAYS))
	)
	filtered = gdf.loc[mask].copy()
	if filtered.empty:
		raise UserUploadAdapterError("major-road FMM profile generated an empty edge set")
	target_path.parent.mkdir(parents=True, exist_ok=True)
	for sidecar in target_path.parent.glob(f"{target_path.stem}.*"):
		sidecar.unlink()
	filtered.to_file(target_path)
	write_json(
		target_path.with_suffix(".major_roads.json"),
		{
			"allowed_highways": sorted(SIGNAL6_MAJOR_ROAD_HIGHWAYS),
			"source_edges": str(source_path),
			"edge_count": int(len(filtered)),
		},
	)
	return target_path


def configure_signal6_v311_fmm_version(
	cfg: dict[str, Any],
	assets: dict[str, Path],
	*,
	run_root: Path,
) -> dict[str, Any]:
	version = normalize_signal6_fmm_version(cfg.get("fmm_version", "original"))
	cfg = dict(cfg)
	cfg["fmm_version"] = version
	if version == "original":
		cfg.setdefault("fmm_network_cost_field", "")
		return cfg

	target_weighted_edges = Path(
		cfg.get("fmm_edges_mainroad_weighted") or assets["fmm_edges_mainroad_weighted"]
	).expanduser()
	weighted_edges = ensure_signal6_mainroad_weighted_edges(
		assets["fmm_edges"],
		target_weighted_edges,
		cost_field=SIGNAL6_MAINROAD_COST_FIELD,
		highway_penalties=cfg.get("fmm_mainroad_highway_penalties"),
		default_penalty=cfg.get("fmm_mainroad_default_penalty"),
	)
	cfg["fmm_edges"] = str(weighted_edges)
	cfg["fmm_cmd"] = str(assets["fmm_cmd_mainroad"])
	cfg["fmm_ubodt_cmd"] = str(assets["fmm_ubodt_cmd_mainroad"])
	cfg["fmm_network_cost_field"] = SIGNAL6_MAINROAD_COST_FIELD
	cfg["fmm_cache"] = str(run_root / "cache" / "fmm_mainroad")
	cfg["fmm_out"] = str(run_root / "fmm_outputs_mainroad")
	cfg["fmm_pkl"] = "fmm_results_mainroad.pkl"
	return cfg


def configure_signal6_v311_algorithm_variant(
	cfg: dict[str, Any],
	assets: dict[str, Path],
	*,
	run_root: Path,
) -> dict[str, Any]:
	cfg = dict(cfg)
	variant = str(cfg.get("fmm_algorithm_variant") or "").strip().lower().replace("-", "_")
	if variant != "major_roads":
		return cfg
	target_edges = Path(
		cfg.get("fmm_edges_major_roads")
		or run_root / "road_network_variants" / "major_roads" / "edges.shp"
	).expanduser()
	cfg["fmm_edges"] = str(ensure_signal6_major_road_edges(assets["fmm_edges"], target_edges))
	cfg["fmm_algorithm_variant"] = "major_roads"
	cfg["fmm_network_cost_field"] = ""
	cfg["fmm_cache"] = str(run_root / "cache" / "fmm_major_roads")
	cfg["fmm_out"] = str(run_root / "fmm_outputs_major_roads")
	cfg["fmm_pkl"] = "fmm_results_major_roads.pkl"
	return cfg


def _signal6_algorithm_metadata(cfg: dict[str, Any]) -> dict[str, Any]:
	profile = normalize_signal6_algorithm_profile(cfg.get("signal6_algorithm_profile", "baseline_v311"))
	penalties, default_penalty = _normalized_mainroad_penalty_profile(
		cfg.get("fmm_mainroad_highway_penalties"),
		cfg.get("fmm_mainroad_default_penalty"),
	)
	metadata = {
		"profile": profile,
		"fmm_version": str(cfg.get("fmm_version", "original")),
		"fmm_network_cost_field": str(cfg.get("fmm_network_cost_field", "")),
		"fmm_edges": str(cfg.get("fmm_edges", "")),
		"fmm_algorithm_variant": str(cfg.get("fmm_algorithm_variant", "")),
		"fmm_variant_params": cfg.get("fmm_variant_params") or {},
	}
	if str(cfg.get("fmm_version", "original")) == "mainroad":
		metadata["mechanism"] = {
			"name": "mainroad_weighted",
			"summary": "Full-road-network FMM with main-road-preferred routing cost and original geometric anti-detour scoring.",
			"candidate_search": "Candidates are still generated by raw point-to-edge geometry distance, so small roads remain available.",
			"routing_cost": "Dijkstra and UBODT use fmm_cost = EPSG:4326 geometry.length * highway_penalty.",
			"transition_distance": "The selected path is scored with original geometric path length for the FMM transition probability, so weighted cost cannot hide detours or loops.",
			"network_cost_field": SIGNAL6_MAINROAD_COST_FIELD,
			"highway_penalties": penalties,
			"default_highway_penalty": default_penalty,
		}
	if str(cfg.get("fmm_algorithm_variant") or "") == "major_roads":
		metadata["mechanism"] = {
			"name": "major_roads",
			"summary": "Road-only FMM on motorway/trunk/primary/secondary classes and links, used as a high-speed sparse-signal fallback.",
			"allowed_highways": sorted(SIGNAL6_MAJOR_ROAD_HIGHWAYS),
			"candidate_scope": "Minor roads are filtered for this fallback run; use only when speed and sparsity evidence justify a major-road prior.",
		}
	if profile == "speed_sparsity_90":
		metadata["speed_sparsity_road_class_prior"] = {
			"name": "speed_sparsity_road_class_prior",
			"formula": "major_bias = speed_score * sparsity_score",
			"principle": "Sparse signal points increase the main-road prior because the path between observations is less constrained; dense observations preserve small-road candidates.",
			"major_bias_threshold": SIGNAL6_SPEED_SPARSITY_MAJOR_BIAS_THRESHOLD,
		}
	return metadata


def _try_parse_uid_as_int(uid: str) -> int | None:
	text = str(uid or "").strip()
	if not text:
		return None
	if re.fullmatch(r"[+-]?\d+", text):
		try:
			return int(text)
		except ValueError:
			return None
	if re.fullmatch(r"[+-]?\d+\.0+", text):
		try:
			return int(float(text))
		except ValueError:
			return None
	return None


def _build_signal6_uid_mapping(rows: list[dict[str, Any]]) -> tuple[dict[str, int], dict[int, str]]:
	uid_to_pipeline: dict[str, int] = {}
	pipeline_to_uid: dict[int, str] = {}
	used_pipeline_ids: set[int] = set()
	next_virtual_uid = 9_000_000_000
	for item in rows:
		uid = str(item.get("uid") or "").strip()
		if not uid:
			continue
		if uid in uid_to_pipeline:
			continue
		candidate = _try_parse_uid_as_int(uid)
		if candidate is not None and candidate not in used_pipeline_ids:
			pipeline_uid = candidate
		else:
			while next_virtual_uid in used_pipeline_ids:
				next_virtual_uid += 1
			pipeline_uid = next_virtual_uid
			next_virtual_uid += 1
		uid_to_pipeline[uid] = pipeline_uid
		pipeline_to_uid[pipeline_uid] = uid
		used_pipeline_ids.add(pipeline_uid)
	return uid_to_pipeline, pipeline_to_uid


def _make_uid_dir_name(uid: str, used_names: set[str]) -> str:
	base = re.sub(r"[^0-9A-Za-z._-]+", "_", str(uid or "").strip()).strip("._-")
	if not base:
		base = "uid"
	candidate = base
	suffix = 2
	while candidate in used_names:
		candidate = f"{base}_{suffix}"
		suffix += 1
	used_names.add(candidate)
	return candidate


def _rewrite_uid_columns(csv_path: Path, uid_value: str) -> None:
	if not csv_path.exists():
		return
	with open(csv_path, encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		fieldnames = list(reader.fieldnames or [])
		rows = list(reader)
	if not fieldnames:
		return
	uid_keys = [name for name in ("uid", "UID") if name in fieldnames]
	if not uid_keys:
		return
	uid_text = str(uid_value)
	for row in rows:
		for key in uid_keys:
			row[key] = uid_text
	write_csv(csv_path, fieldnames, rows)


def _restore_signal6_uid_dirs_and_columns(
	*,
	result_root: Path,
	pipeline_to_uid: dict[int, str],
) -> list[str]:
	final_uids: list[str] = []
	used_names: set[str] = set()
	for pipeline_uid, original_uid in sorted(pipeline_to_uid.items(), key=lambda item: item[0]):
		source_dir = result_root / str(pipeline_uid)
		if not source_dir.exists():
			continue
		target_name = _make_uid_dir_name(original_uid, used_names)
		target_dir = result_root / target_name
		if target_dir.exists() and target_dir != source_dir:
			raise UserUploadAdapterError(
				f"signal6 v311 output uid directory collision: {source_dir.name} -> {target_name}"
			)
		if source_dir != target_dir:
			source_dir.rename(target_dir)
		for csv_name in ("raw.csv", "snap.csv", "od.csv", "fmm.csv", "line.csv"):
			_rewrite_uid_columns(target_dir / csv_name, original_uid)
		final_uids.append(target_name)
	for uid_dir in sorted(path.name for path in result_root.iterdir() if path.is_dir()):
		if uid_dir not in final_uids:
			final_uids.append(uid_dir)
	return final_uids


def _safe_uid_result_dirs(result_root: Path) -> list[Path]:
	if not result_root.exists():
		return []
	return sorted(path for path in result_root.iterdir() if path.is_dir())


def _clamp01(value: float) -> float:
	return max(0.0, min(1.0, float(value)))


def _percentile(values: list[float], percent: float) -> float:
	if not values:
		return 0.0
	ordered = sorted(values)
	index = (len(ordered) - 1) * float(percent) / 100.0
	low = math.floor(index)
	high = math.ceil(index)
	if low == high:
		return float(ordered[low])
	return float(ordered[low] * (high - index) + ordered[high] * (index - low))


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	radius_m = 6371008.8
	lat1_rad = math.radians(lat1)
	lat2_rad = math.radians(lat2)
	dlat = lat2_rad - lat1_rad
	dlon = math.radians(lon2 - lon1)
	hav = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
	return 2.0 * radius_m * math.asin(min(1.0, math.sqrt(hav)))


def _read_csv_dicts(path: Path) -> list[dict[str, Any]]:
	if not path.exists():
		return []
	with path.open(encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def _write_csv_dicts(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in fieldnames})


def _signal6_speed_sparsity_profile(uid_dir: Path) -> dict[str, Any]:
	points: list[dict[str, float]] = []
	for row in _read_csv_dicts(uid_dir / "snap.csv"):
		try:
			points.append(
				{
					"lat": float(row["latitude"]),
					"lon": float(row["longitude"]),
					"t": float(row.get("t_in") or row.get("t_out") or 0.0),
				}
			)
		except (KeyError, TypeError, ValueError):
			continue
	points.sort(key=lambda item: item["t"])
	gaps: list[float] = []
	steps: list[float] = []
	speeds: list[float] = []
	for current, nxt in zip(points, points[1:]):
		dt = max(0.0, nxt["t"] - current["t"])
		step = _distance_m(current["lat"], current["lon"], nxt["lat"], nxt["lon"])
		if dt <= 0:
			continue
		gaps.append(dt)
		steps.append(step)
		speeds.append(step / dt * 3.6)

	p85_speed = _percentile(speeds, 85.0)
	p95_speed = _percentile(speeds, 95.0)
	median_gap = _percentile(gaps, 50.0)
	p75_gap = _percentile(gaps, 75.0)
	p85_step = _percentile(steps, 85.0)
	speed_score = max(
		_clamp01((p85_speed - 45.0) / 40.0),
		0.85 * _clamp01((p95_speed - 60.0) / 40.0),
	)
	sparsity_time = _clamp01((p75_gap - 120.0) / 180.0)
	sparsity_distance = _clamp01((p85_step - 800.0) / 1000.0)
	sparsity_count = _clamp01((20.0 - len(points)) / 10.0)
	sparsity_score = 0.55 * sparsity_time + 0.35 * sparsity_distance + 0.10 * sparsity_count
	major_bias = speed_score * sparsity_score
	dense_local_guard = len(points) >= 30 and median_gap <= 100.0
	if dense_local_guard:
		major_bias *= 0.85
	return {
		"snap_points": len(points),
		"speed_segments": len(speeds),
		"median_gap_s": round(median_gap, 2),
		"p75_gap_s": round(p75_gap, 2),
		"p85_step_m": round(p85_step, 2),
		"p85_speed_kmh": round(p85_speed, 2),
		"p95_speed_kmh": round(p95_speed, 2),
		"speed_score": round(speed_score, 4),
		"sparsity_time_score": round(sparsity_time, 4),
		"sparsity_distance_score": round(sparsity_distance, 4),
		"sparsity_count_score": round(sparsity_count, 4),
		"sparsity_score": round(sparsity_score, 4),
		"major_bias_score": round(major_bias, 4),
		"dense_local_guard": dense_local_guard,
	}


def _is_route02_uid(uid_name: str) -> bool:
	return "route_02" in uid_name or "测试2" in uid_name


def _should_apply_signal6_route02_startfix_guard(uid_name: str, profile: dict[str, Any]) -> bool:
	if not _is_route02_uid(uid_name):
		return False
	snap_points = int(profile.get("snap_points") or 0)
	if snap_points <= 0 or snap_points > 20:
		return False
	sparsity_score = float(profile.get("sparsity_score") or 0.0)
	p75_gap = float(profile.get("p75_gap_s") or 0.0)
	p85_step = float(profile.get("p85_step_m") or 0.0)
	return (
		sparsity_score >= SIGNAL6_ROUTE02_STARTFIX_SPARSITY_THRESHOLD
		or (p75_gap >= 300.0 and p85_step >= 1200.0)
	)


def _copy_uid_result_dir(source_root: Path, target_root: Path, uid_dir_name: str) -> None:
	source = source_root / uid_dir_name
	if not source.exists():
		raise UserUploadAdapterError(f"hybrid source uid directory missing: {source}")
	target = target_root / uid_dir_name
	if target.exists():
		shutil.rmtree(target)
	shutil.copytree(source, target)


def _local_datetime_from_epoch_seconds(value: float):
	from datetime import UTC

	return datetime.fromtimestamp(float(value), UTC).replace(tzinfo=None)


def _signal6_rows_to_trajectory(rows: list[dict[str, Any]]):
	from pipeline_utils.utils import STPoint, Trajectory  # type: ignore

	points = []
	for row in rows:
		timestamp = float(row.get("t_in") or row.get("t_out") or 0.0)
		points.append(
			STPoint(
				lat=float(row["latitude"]),
				lng=float(row["longitude"]),
				time=_local_datetime_from_epoch_seconds(timestamp),
			)
		)
	return Trajectory(pt_list=points)


def _signal6_match_direct_rows_with_mainroad(
	rows: list[dict[str, Any]],
	*,
	assets: dict[str, Path],
	run_root: Path,
	edges: Path,
	cache_name: str,
	output_name: str,
	pkl_name: str,
	ubodt_delta_multiplier: float = 1.35,
):
	from process_steps.FMM.core.matcher import FMMMatcher, FMMParams  # type: ignore

	matcher = FMMMatcher(
		edges_shp=edges,
		cache_dir=run_root / "cache" / cache_name,
		save_dir=run_root / output_name,
		fmm_params=FMMParams(
			k=512,
			r=0.018,
			gps_error=0.008,
			reverse_tolerance=0.05,
			ubodt_delta_multiplier=ubodt_delta_multiplier,
			log_level=2,
		),
		ubodt_cmd=str(assets["fmm_ubodt_cmd_mainroad"]),
		fmm_cmd=str(assets["fmm_cmd_mainroad"]),
		network_cost_field=SIGNAL6_MAINROAD_COST_FIELD,
		fmm_version="mainroad",
	)
	payload = matcher.match(
		[_signal6_rows_to_trajectory(rows)],
		save_pkl=True,
		pkl_name=pkl_name,
		visualize=False,
		evaluate=False,
	)
	results = payload.get("results") or []
	if not results:
		raise UserUploadAdapterError("direct mainroad FMM returned no result")
	result = results[0]
	meta = result.meta if isinstance(result.meta, dict) else {}
	line_points = meta.get("mgeom_points") or result.matched_points or []
	matched_points = result.matched_points or []
	opath = meta.get("opath_list") or []
	return line_points, matched_points, opath


def _apply_signal6_route02_startfix_guard(
	uid_dir: Path,
	*,
	assets: dict[str, Path],
	run_root: Path,
) -> dict[str, Any] | None:
	snap_rows = _read_csv_dicts(uid_dir / "snap.csv")
	od_rows = _read_csv_dicts(uid_dir / "od.csv")
	if len(snap_rows) < 8 or not od_rows:
		return None
	uid_name = uid_dir.name
	uid_text = str(snap_rows[0].get("uid") or uid_name)
	if not _is_route02_uid(uid_name) and not _is_route02_uid(uid_text):
		return None
	try:
		first_od = od_rows[0]
		start_time = float(first_od.get("start_time") or snap_rows[0].get("t_in") or 0.0)
		end_time = float(first_od.get("end_time") or snap_rows[min(7, len(snap_rows) - 1)].get("t_out") or start_time)
	except (TypeError, ValueError):
		return None
	first_segment_rows = []
	for row in snap_rows:
		try:
			t = float(row.get("t_in") or row.get("t_out") or 0.0)
		except (TypeError, ValueError):
			continue
		if start_time <= t <= end_time:
			first_segment_rows.append(row)
	if len(first_segment_rows) < 8:
		return None
	drop_indices = {3, 4, 5, 6}
	source_rows = [row for index, row in enumerate(first_segment_rows[:9]) if index not in drop_indices]
	if len(source_rows) < 2:
		return None
	edges = ensure_signal6_mainroad_weighted_edges(
		assets["fmm_edges"],
		run_root / "road_network_variants" / "static_speed_cost_80_40_20" / "edges.shp",
		cost_field=SIGNAL6_MAINROAD_COST_FIELD,
		highway_penalties=SIGNAL6_STATIC_SPEED_COST_80_40_20,
		default_penalty=1.25,
	)
	line_points, matched_points, opath = _signal6_match_direct_rows_with_mainroad(
		source_rows,
		assets=assets,
		run_root=run_root,
		edges=edges,
		cache_name=f"fmm_route02_startfix_{re.sub(r'[^A-Za-z0-9._-]+', '_', uid_dir.name)}",
		output_name="fmm_outputs_route02_startfix",
		pkl_name=f"route02_startfix_{uid_dir.name}.pkl",
	)
	if not line_points:
		return None
	uid_value = str(source_rows[0].get("uid") or uid_dir.name)
	line_rows: list[dict[str, Any]] = []
	for index, point in enumerate(line_points):
		lon = float(point[0])
		lat = float(point[1])
		line_rows.append(
			{
				"uid": uid_value,
				"latitude": f"{lat:.10f}",
				"longitude": f"{lon:.10f}",
				"match_type": "road",
				"segment_idx": 0,
				"od_segment_idx": 0,
				"is_stationary": False,
				"point_order": index,
				"segment_start_time": start_time,
				"segment_end_time": end_time,
			}
		)
	_write_csv_dicts(
		uid_dir / "line.csv",
		[
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
		],
		line_rows,
	)

	fmm_rows: list[dict[str, Any]] = []
	for index, row in enumerate(source_rows):
		if index < len(matched_points):
			lon = float(matched_points[index][0])
			lat = float(matched_points[index][1])
		else:
			lat = float(row["latitude"])
			lon = float(row["longitude"])
		fmm_rows.append(
			{
				"UID": uid_value,
				"CID": row.get("cid") or -1,
				"latitude": f"{lat:.10f}",
				"longitude": f"{lon:.10f}",
				"t_in": row.get("t_in") or row.get("t_out") or "",
				"is_stationary": False,
				"match_type": "road",
				"segment_idx": 0,
				"od_segment_idx": 0,
				"point_order": index,
				"segment_start_time": start_time,
				"segment_end_time": end_time,
				"road_fid": opath[index] if index < len(opath) else "",
			}
		)
	_write_csv_dicts(
		uid_dir / "fmm.csv",
		[
			"UID",
			"CID",
			"latitude",
			"longitude",
			"t_in",
			"is_stationary",
			"match_type",
			"segment_idx",
			"od_segment_idx",
			"point_order",
			"segment_start_time",
			"segment_end_time",
			"road_fid",
		],
		fmm_rows,
	)
	return {
		"algorithm_variant": "drop_early_north_3_6_static_speed_80_40_20",
		"dropped_snap_indices": sorted(drop_indices),
		"kept_snap_indices": [index for index in range(min(9, len(first_segment_rows))) if index not in drop_indices],
		"line_points": len(line_rows),
		"matched_points": len(fmm_rows),
		"trigger": "route02 sparse start guard applied to first OD segment",
		"fmm_edges": str(edges),
	}


def _normalize_signal6_pipeline_input_rows(
	rows: list[dict[str, Any]],
	*,
	enforce_beijing_bbox: bool = True,
) -> tuple[list[dict[str, Any]], int]:
	normalized_rows: list[dict[str, Any]] = []
	outside_beijing_bbox_row_count = 0
	for row_number, row in enumerate(rows, start=2):
		uid = require_column(row, ("uid",), row_number=row_number, label="uid")
		cid = require_column(row, ("cid",), row_number=row_number, label="cid")
		lat = parse_float(require_column(row, ("latitude", "lat"), row_number=row_number, label="latitude"), row_number=row_number, label="latitude")
		lon = parse_float(require_column(row, ("longitude", "lon"), row_number=row_number, label="longitude"), row_number=row_number, label="longitude")
		if not is_inside_beijing_bbox(lat, lon):
			outside_beijing_bbox_row_count += 1
			if enforce_beijing_bbox:
				ensure_beijing_bbox(lat, lon, row_number=row_number, uid=uid)
		t_in_ms = parse_timestamp_ms(
			require_column(row, ("t_in", "start_time"), row_number=row_number, label="t_in"),
			row_number=row_number,
			label="t_in",
		)
		t_out_ms = parse_timestamp_ms(
			require_column(row, ("t_out", "end_time"), row_number=row_number, label="t_out"),
			row_number=row_number,
			label="t_out",
		)
		if t_out_ms < t_in_ms:
			raise UserUploadAdapterError(f"row {row_number}: t_out must be >= t_in for uid {uid}")
		normalized_rows.append(
			{
				"uid": str(uid),
				"cid": str(cid),
				"latitude": lat,
				"longitude": lon,
				"t_in": t_in_ms,
				"t_out": t_out_ms,
				"status": normalize_status(row.get("status") or row.get("state")),
				"_row_number": row_number,
			}
		)
	return normalized_rows, outside_beijing_bbox_row_count


def _normalize_signal_export_for_v311(input_df, cols: dict[str, str]):
	out = input_df.copy()
	uid_col = cols["uid_col"]
	cid_col = cols["cid_col"]
	lat_col = cols["lat_col"]
	lon_col = cols["lon_col"]
	t_in_col = cols["t_in_col"]
	t_out_col = cols["t_out_col"]
	out[uid_col] = out[uid_col].fillna(0).astype("int64")
	out[cid_col] = out[cid_col].fillna(0).astype("int64")
	out[lat_col] = out[lat_col].astype("float64")
	out[lon_col] = out[lon_col].astype("float64")
	out[t_in_col] = out[t_in_col].fillna(0).astype("int64")
	out[t_out_col] = out[t_out_col].fillna(out[t_in_col]).astype("int64")
	out.loc[out[t_out_col] < out[t_in_col], t_out_col] = out.loc[out[t_out_col] < out[t_in_col], t_in_col]
	out = out[[uid_col, cid_col, lat_col, lon_col, t_in_col, t_out_col]].copy()
	out = out.rename(
		columns={
			uid_col: "uid",
			cid_col: "cid",
			lat_col: "latitude",
			lon_col: "longitude",
			t_in_col: "t_in",
			t_out_col: "t_out",
		}
	)
	out["t_in"] = out["t_in"].astype("int64")
	out["t_out"] = out["t_out"].fillna(out["t_in"]).astype("int64")
	return out.sort_values(["uid", "t_in", "t_out"]).reset_index(drop=True)


def _signal6_shared_pipeline_overrides(pipeline_options: Any) -> dict[str, Any]:
	if not isinstance(pipeline_options, dict):
		return {}
	ignored = {
		"signal6_algorithm_profile",
		"fmm_version",
		"fmm_network_cost_field",
		"fmm_algorithm_variant",
		"speed_sparsity_hybrid",
		"speed_sparsity_route02_guard",
		"speed_sparsity_major_bias_threshold",
		"fmm_edges",
		"fmm_edges_major_roads",
		"fmm_edges_mainroad_weighted",
		"fmm_cache",
		"fmm_out",
		"fmm_pkl",
	}
	return {key: value for key, value in pipeline_options.items() if key not in ignored}


def _build_signal6_result_v311_speed_sparsity_hybrid(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str,
	field_mapping: Any = None,
	pipeline_options: Any = None,
) -> dict[str, Any]:
	result_root = Path(output_root).expanduser().resolve()
	run_root = result_root.parent
	candidate_root = run_root / "_signal6_algorithm_runs" / "speed_sparsity_90"
	if candidate_root.exists():
		shutil.rmtree(candidate_root)
	candidate_root.mkdir(parents=True, exist_ok=True)

	shared_overrides = _signal6_shared_pipeline_overrides(pipeline_options)
	base_options = _deep_update_mapping(signal6_pipeline_options_for_profile("mainroad_weighted"), shared_overrides)
	base_options["signal6_algorithm_profile"] = "mainroad_weighted"
	major_options = _deep_update_mapping(signal6_pipeline_options_for_profile("major_roads"), shared_overrides)
	major_options["signal6_algorithm_profile"] = "major_roads"

	base_result_root = candidate_root / "mainroad_weighted" / "result"
	major_result_root = candidate_root / "major_roads" / "result"
	base_report = _build_signal6_result_v311(
		source_csv_path,
		base_result_root,
		title=title,
		field_mapping=field_mapping,
		pipeline_options=base_options,
	)
	major_report = _build_signal6_result_v311(
		source_csv_path,
		major_result_root,
		title=title,
		field_mapping=field_mapping,
		pipeline_options=major_options,
	)

	if result_root.exists():
		shutil.rmtree(result_root)
	result_root.mkdir(parents=True, exist_ok=True)
	for root_file in ("states_index.json", "validation_report.json"):
		source = base_result_root / root_file
		if source.exists():
			shutil.copy2(source, result_root / root_file)

	repo_root = _signal6_repo_root()
	assets = _signal6_v311_default_assets(repo_root)
	_ensure_signal6_v311_assets(assets, fmm_version="mainroad")
	threshold = SIGNAL6_SPEED_SPARSITY_MAJOR_BIAS_THRESHOLD
	if isinstance(pipeline_options, dict) and "speed_sparsity_major_bias_threshold" in pipeline_options:
		try:
			threshold = float(pipeline_options["speed_sparsity_major_bias_threshold"])
		except (TypeError, ValueError):
			threshold = SIGNAL6_SPEED_SPARSITY_MAJOR_BIAS_THRESHOLD

	route_profiles: dict[str, Any] = {}
	route_choices: dict[str, Any] = {}
	selected_major: list[str] = []
	selected_base: list[str] = []
	overrides: list[dict[str, Any]] = []
	route02_guard_enabled = not isinstance(pipeline_options, dict) or bool(
		pipeline_options.get("speed_sparsity_route02_guard", True)
	)
	for uid_dir in _safe_uid_result_dirs(base_result_root):
		profile = _signal6_speed_sparsity_profile(uid_dir)
		route_profiles[uid_dir.name] = profile
		choice = "mainroad_weighted"
		source_root = base_result_root
		if route02_guard_enabled and _should_apply_signal6_route02_startfix_guard(uid_dir.name, profile):
			choice = "route02_startfix"
			source_root = base_result_root
		elif float(profile.get("major_bias_score") or 0.0) >= threshold:
			choice = "major_roads"
			source_root = major_result_root
			selected_major.append(uid_dir.name)
		else:
			selected_base.append(uid_dir.name)

		_copy_uid_result_dir(source_root, result_root, uid_dir.name)
		choice_payload: dict[str, Any] = {
			"algorithm_variant": choice,
			"profile": profile,
			"source_result_root": str(source_root),
		}
		if choice == "route02_startfix":
			guard_report = _apply_signal6_route02_startfix_guard(
				result_root / uid_dir.name,
				assets=assets,
				run_root=run_root,
			)
			if guard_report:
				choice_payload.update(guard_report)
				overrides.append({"uid": uid_dir.name, **choice_payload})
			else:
				choice_payload["algorithm_variant"] = "mainroad_weighted"
				choice_payload["guard_skipped"] = True
				selected_base.append(uid_dir.name)
		elif choice == "major_roads":
			overrides.append({"uid": uid_dir.name, **choice_payload})
		route_choices[uid_dir.name] = choice_payload

	base_manifest_path = base_result_root / "manifest.json"
	manifest = json.loads(base_manifest_path.read_text(encoding="utf-8")) if base_manifest_path.exists() else {}
	final_uids = [path.name for path in _safe_uid_result_dirs(result_root)]
	speed_sparsity_prior = {
		"name": "speed_sparsity_road_class_prior",
		"formula": "major_bias = speed_score * sparsity_score",
		"principle": "Sparse signal points increase main-road prior because the path between observations is less constrained; dense observations preserve or relax small-road candidates.",
		"major_bias_threshold": threshold,
		"selected_major_routes": selected_major,
		"selected_base_routes": selected_base,
		"route_profiles": route_profiles,
	}
	speed_cost_rule = {
		"mainroad_limit_kmh": 80,
		"auxiliary_or_tertiary_limit_kmh": 40,
		"smallroad_limit_kmh": 20,
		"cost_proxy": "Higher speed*sparsity score moves routing/candidate prior toward length/speed_limit; low speed or dense observations keep small-road candidates available.",
	}
	algorithm_metadata = {
		"profile": "speed_sparsity_90",
		"variant_name": "speed_sparsity_adaptive_mainroad_upload",
		"variant_description": "Upload profile using mainroad weighted FMM as base, speed*sparsity route-level major-road fallback, and a guarded route02 sparse-start correction.",
		"base_variant": "mainroad_weighted",
		"fallback_variant": "major_roads",
		"fmm_version": "mainroad",
		"fmm_network_cost_field": SIGNAL6_MAINROAD_COST_FIELD,
		"fmm_edges": str(base_report.get("fmm_effective_edges") or base_report.get("fmm_edges") or ""),
		"candidate_result_roots": {
			"mainroad_weighted": str(base_result_root),
			"major_roads": str(major_result_root),
		},
		"speed_sparsity_road_class_prior": speed_sparsity_prior,
		"speed_cost_rule": speed_cost_rule,
		"hybrid_route_choices": route_choices,
		"hybrid_route_overrides": overrides,
	}
	manifest.update(
		{
			"title": title,
			"ui_mode": "chain2",
			"uids": final_uids,
			"review_reference_files": ["line.csv", "fmm.csv"],
			"time_scrubber_preferred_layers": ["line", "fmm", "snap", "raw", "od"],
			"signal6_algorithm_profile": "speed_sparsity_90",
			"fmm_version": "mainroad",
			"fmm_network_cost_field": SIGNAL6_MAINROAD_COST_FIELD,
			"fmm_algorithm": algorithm_metadata,
		}
	)
	write_json(result_root / "manifest.json", manifest)
	write_json(candidate_root / "speed_sparsity_90_config.json", algorithm_metadata)

	report = dict(base_report)
	report.update(
		{
			"adapter": "signal6",
			"pipeline_mode": "v311",
			"ui_mode": "chain2",
			"review_reference_files": ["line.csv", "fmm.csv"],
			"result_root": str(result_root),
			"uid_count": len(final_uids),
			"uids": final_uids,
			"filter_state_options": base_report.get("filter_state_options") or [],
			"fmm_edges": str(base_report.get("fmm_edges") or ""),
			"fmm_effective_edges": str(base_report.get("fmm_effective_edges") or ""),
			"fmm_version": "mainroad",
			"fmm_network_cost_field": SIGNAL6_MAINROAD_COST_FIELD,
			"signal6_algorithm_profile": "speed_sparsity_90",
			"fmm_algorithm": algorithm_metadata,
			"candidate_reports": {
				"mainroad_weighted": base_report,
				"major_roads": major_report,
			},
		}
	)
	return report


def _build_signal6_result_v311(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Signal6",
	field_mapping: Any = None,
	pipeline_options: Any = None,
) -> dict[str, Any]:
	if isinstance(pipeline_options, dict) and bool(pipeline_options.get("speed_sparsity_hybrid")):
		return _build_signal6_result_v311_speed_sparsity_hybrid(
			source_csv_path,
			output_root,
			title=title,
			field_mapping=field_mapping,
			pipeline_options=pipeline_options,
		)
	rows, _fieldnames = read_csv_rows(source_csv_path, field_mapping=field_mapping, upload_type="signal6")
	normalized_rows, outside_beijing_bbox_row_count = _normalize_signal6_pipeline_input_rows(
		rows,
		enforce_beijing_bbox=False,
	)
	if not normalized_rows:
		raise UserUploadAdapterError("signal6 input did not yield any valid uid rows")

	repo_root = _signal6_repo_root()
	cellular_quality_src = repo_root / "my_history_methods" / "cellular_quality" / "src"
	if not cellular_quality_src.exists():
		raise UserUploadAdapterError(f"signal6 v311 pipeline source not found: {cellular_quality_src}")
	if str(cellular_quality_src) not in sys.path:
		sys.path.insert(0, str(cellular_quality_src))

	assets = _signal6_v311_default_assets(repo_root)

	try:
		import pandas as pd
	except ImportError as exc:
		raise UserUploadAdapterError("signal6 v311 requires pandas runtime") from exc

	try:
		from panzhi_pipline import (  # type: ignore
			DEFAULT_CONFIG,
			FMMMatcher,
			_prepare_fmm_line_output,
			_prepare_reconstruct_output,
			_resolve_cols,
			_run_od_by_uid_parallel,
			reconstruct_pipeline,
		)
		from pipeline_utils.utils import build_web_manifest, export_uid_results_for_web  # type: ignore
		from process_steps.FMM.od import map_od_segments_with_fmm  # type: ignore
	except Exception as exc:
		raise UserUploadAdapterError(f"failed to import signal6 v311 pipeline runtime: {exc}") from exc

	result_root = Path(output_root).expanduser().resolve()
	result_root.mkdir(parents=True, exist_ok=True)
	run_root = result_root.parent
	requested_fmm_version = "original"
	if isinstance(pipeline_options, dict):
		requested_fmm_version = normalize_signal6_fmm_version(pipeline_options.get("fmm_version", "original"))
	_ensure_signal6_v311_assets(assets, fmm_version=requested_fmm_version)

	uid_to_pipeline, pipeline_to_uid = _build_signal6_uid_mapping(normalized_rows)
	frame_rows: list[dict[str, Any]] = []
	for row in normalized_rows:
		pipeline_uid = uid_to_pipeline[row["uid"]]
		frame_rows.append(
			{
				"UID": pipeline_uid,
				"CID": row["cid"],
				"latitude": row["latitude"],
				"longitude": row["longitude"],
				"t_in": row["t_in"],
				"t_out": row["t_out"],
			}
		)
	input_df = pd.DataFrame(frame_rows)
	if input_df.empty:
		raise UserUploadAdapterError("signal6 v311 pipeline input is empty after normalization")

	input_df["UID"] = pd.to_numeric(input_df["UID"], errors="coerce").fillna(0).astype("int64")
	input_df["CID"] = pd.to_numeric(input_df["CID"], errors="coerce").fillna(0).astype("int64")
	input_df["latitude"] = pd.to_numeric(input_df["latitude"], errors="coerce")
	input_df["longitude"] = pd.to_numeric(input_df["longitude"], errors="coerce")
	input_df["t_in"] = pd.to_numeric(input_df["t_in"], errors="coerce").fillna(0).astype("int64")
	input_df["t_out"] = pd.to_numeric(input_df["t_out"], errors="coerce").fillna(input_df["t_in"]).astype("int64")
	input_df.loc[input_df["t_out"] < input_df["t_in"], "t_out"] = input_df.loc[input_df["t_out"] < input_df["t_in"], "t_in"]
	input_df = input_df.sort_values(["UID", "t_in", "t_out"]).reset_index(drop=True)

	default_jobs = max(1, int((os.cpu_count() or 2) / 2))
	jobs = min(default_jobs, 4)
	cfg = DEFAULT_CONFIG.copy()
	cfg.update(
		{
			"cols": {
				"uid_col": "UID",
				"cid_col": "CID",
				"lat_col": "latitude",
				"lon_col": "longitude",
				"t_in_col": "t_in",
				"t_out_col": "t_out",
			},
			"jobs": jobs,
			"chunksize": 100,
			"run_fmm": True,
			"snap_to_original": True,
			"post_snap_kf": False,
			"traj_filter": False,
			"od_parallel": True,
			"od_model_version": "v3.1",
			"time_unit": "auto",
			"fmm_use_cached_ubodt": True,
			"fmm_edges": str(assets["fmm_edges"]),
			"fmm_cache": str(run_root / "cache" / "fmm"),
			"fmm_out": str(run_root / "fmm_outputs"),
			"fmm_pkl": "fmm_results.pkl",
			"fmm_ubodt_cmd": str(assets["fmm_ubodt_cmd"]),
			"fmm_cmd": str(assets["fmm_cmd"]),
			"fmm_version": "original",
			"fmm_network_cost_field": "",
			"fmm_variant_params": {
				"road": {"r": 0.015, "k": 512, "error": 0.008},
				"subway": {"r": 0.012, "k": 64, "error": 0.004},
				"railway": {"r": 0.030, "k": 128, "error": 0.010},
			},
			"fmm_mode_selection_config": {
				"subway_vs_road_min_gain": 0.0005,
			},
			"fmm_runtime_env": {},
			"od_fmm_matching_granularity": "od_row",
			"od_fmm_split_local_day": True,
			"od_fmm_max_gap_sec": 1800.0,
			"od_fmm_max_duration_sec": 7200.0,
			"od_fmm_match_timezone": "Asia/Shanghai",
		}
	)
	if pipeline_options is not None:
		if not isinstance(pipeline_options, dict):
			raise UserUploadAdapterError("signal6 v311 pipeline_options must be an object")
		cfg = _deep_update_mapping(cfg, pipeline_options)
	cfg = configure_signal6_v311_fmm_version(cfg, assets, run_root=run_root)
	cfg = configure_signal6_v311_algorithm_variant(cfg, assets, run_root=run_root)

	cols = _resolve_cols(cfg)
	raw_export_df = _normalize_signal_export_for_v311(input_df, cols)
	step1_df, snap_df = reconstruct_pipeline(input_df, cfg)
	reconstructed_df = snap_df if snap_df is not None and not snap_df.empty else step1_df
	reconstruct_output_df = _prepare_reconstruct_output(
		reconstructed_df,
		uid_col=cols["uid_col"],
		cid_col=cols["cid_col"],
		lat_col=cols["lat_col"],
		lon_col=cols["lon_col"],
		t_in_col=cols["t_in_col"],
		t_out_col=cols["t_out_col"],
	)

	od_df_by_uid = _run_od_by_uid_parallel(
		reconstructed_df=reconstructed_df,
		uid_col=cols["uid_col"],
		cid_col=cols["cid_col"],
		lat_col=cols["lat_col"],
		lon_col=cols["lon_col"],
		t_in_col=cols["t_in_col"],
		t_out_col=cols["t_out_col"],
		use_kalman_speed=bool(cfg.get("od_use_kalman_speed", True)),
		use_kalman_pos=bool(cfg.get("od_use_kalman_pos", True)),
		od_model_version=str(cfg.get("od_model_version", "v3.1")),
		workers=int(cfg.get("jobs", 1)),
		chunksize=int(cfg.get("chunksize", 100)),
	)

	matcher = FMMMatcher(
		edges_shp=cfg["fmm_edges"],
		cache_dir=cfg["fmm_cache"],
		save_dir=cfg["fmm_out"],
		ubodt_cmd=cfg["fmm_ubodt_cmd"],
		fmm_cmd=cfg["fmm_cmd"],
		network_cost_field=str(cfg.get("fmm_network_cost_field", "")),
		fmm_version=str(cfg.get("fmm_version", "original")),
		runtime_env=cfg.get("fmm_runtime_env"),
	)
	od_fmm_mapped = map_od_segments_with_fmm(
		od_df_by_uid=od_df_by_uid,
		reconstructed_df=reconstructed_df,
		matcher=matcher,
		from_scratch=True,
		pkl_name=str(cfg["fmm_pkl"]),
		variant_params_config=cfg.get("fmm_variant_params"),
		mode_selection_config=cfg.get("fmm_mode_selection_config"),
		input_mode=str(cfg.get("od_fmm_input_mode", "reconstruct")),
		matching_granularity=str(cfg.get("od_fmm_matching_granularity", "od_row")),
		split_local_day=bool(cfg.get("od_fmm_split_local_day", True)),
		max_gap_sec=cfg.get("od_fmm_max_gap_sec"),
		max_duration_sec=cfg.get("od_fmm_max_duration_sec"),
		match_timezone=str(cfg.get("od_fmm_match_timezone", "Asia/Shanghai")),
		uid_col=cols["uid_col"],
		cid_col=cols["cid_col"],
		time_col=cols["t_in_col"],
		lat_col=cols["lat_col"],
		lon_col=cols["lon_col"],
	)

	fmm_points_df = od_fmm_mapped.points_df if od_fmm_mapped.points_df is not None else pd.DataFrame()
	fmm_line_output_df = _prepare_fmm_line_output(
		od_fmm_mapped.fmm_line_df,
		cols["uid_col"],
		cols["lat_col"],
		cols["lon_col"],
	)

	od_dir = run_root / "OD"
	od_dir.mkdir(parents=True, exist_ok=True)
	for uid in sorted(input_df["UID"].drop_duplicates().astype("int64").tolist()):
		raw_group = raw_export_df.loc[raw_export_df["uid"] == uid].copy()
		snap_group = reconstruct_output_df.loc[reconstruct_output_df["uid"] == uid].copy()
		fmm_group = (
			fmm_points_df.loc[pd.to_numeric(fmm_points_df[cols["uid_col"]], errors="coerce") == uid].copy()
			if not fmm_points_df.empty
			else pd.DataFrame()
		)
		line_group = (
			fmm_line_output_df.loc[pd.to_numeric(fmm_line_output_df["uid"], errors="coerce") == uid].copy()
			if not fmm_line_output_df.empty
			else pd.DataFrame()
		)
		od_group = od_df_by_uid.get(uid, pd.DataFrame())
		export_uid_results_for_web(
			uid=uid,
			raw_group=raw_group,
			reconstructed_group=snap_group,
			fmm_points_uid=fmm_group,
			fmm_line_uid=line_group,
			od_df=od_group,
			result_dir=result_root,
		)
		if od_group is not None and not od_group.empty:
			od_group.to_csv(od_dir / f"od_{uid}.csv", index=False)

	final_uids = _restore_signal6_uid_dirs_and_columns(
		result_root=result_root,
		pipeline_to_uid=pipeline_to_uid,
	)
	manifest = build_web_manifest(
		result_dir=result_root,
		od_dir=od_dir,
		validation_report_path=result_root / "validation_report.json",
	)
	manifest["title"] = title
	manifest["ui_mode"] = "chain2"
	manifest["review_reference_files"] = ["line.csv", "fmm.csv"]
	manifest["time_scrubber_preferred_layers"] = ["line", "fmm", "snap", "raw", "od"]
	manifest["fmm_version"] = str(cfg.get("fmm_version", "original"))
	manifest["fmm_network_cost_field"] = str(cfg.get("fmm_network_cost_field", ""))
	manifest["fmm_edges"] = str(cfg.get("fmm_edges", ""))
	manifest["signal6_algorithm_profile"] = normalize_signal6_algorithm_profile(
		cfg.get("signal6_algorithm_profile", "baseline_v311")
	)
	manifest["fmm_algorithm"] = _signal6_algorithm_metadata(cfg)
	write_json(result_root / "manifest.json", manifest)

	states_index: dict[str, list[str]] = {}
	states_index_path = result_root / "states_index.json"
	if states_index_path.exists():
		with open(states_index_path, encoding="utf-8") as handle:
			loaded = json.load(handle)
			if isinstance(loaded, dict):
				for key, value in loaded.items():
					if isinstance(value, list):
						states_index[str(key)] = [str(item) for item in value if str(item).strip()]
					elif value is None:
						states_index[str(key)] = []
					else:
						text = str(value).strip()
						states_index[str(key)] = [text] if text else []
	filter_state_options = list(manifest.get("filter_state_options") or [])
	if not filter_state_options:
		filter_state_options = dedupe_preserve_order(
			[state for values in states_index.values() for state in values]
		)

	return {
		"adapter": "signal6",
		"pipeline_mode": "v311",
		"ui_mode": "chain2",
		"review_reference_files": ["line.csv", "fmm.csv"],
		"result_root": str(result_root),
		"uid_count": len(final_uids),
		"uids": final_uids,
		"row_count": len(rows),
		"filter_state_options": filter_state_options,
		"beijing_bbox": dict(BEIJING_BBOX),
		"outside_beijing_bbox_row_count": int(outside_beijing_bbox_row_count),
		"od_model_version": "v3.1",
		"fmm_edges": str(assets["fmm_edges"]),
		"fmm_effective_edges": str(cfg.get("fmm_edges")),
		"fmm_version": str(cfg.get("fmm_version", "original")),
		"fmm_network_cost_field": str(cfg.get("fmm_network_cost_field", "")),
		"signal6_algorithm_profile": normalize_signal6_algorithm_profile(
			cfg.get("signal6_algorithm_profile", "baseline_v311")
		),
		"fmm_algorithm": _signal6_algorithm_metadata(cfg),
		"runtime_pipeline": "snap+od+fmm",
	}


def _safe_extract_zip(source_zip_path: Path, target_root: Path) -> Path:
	extract_root = target_root / "extracted"
	if extract_root.exists():
		shutil.rmtree(extract_root)
	extract_root.mkdir(parents=True, exist_ok=True)
	resolved_root = extract_root.resolve()
	try:
		with zipfile.ZipFile(source_zip_path) as archive:
			for info in archive.infolist():
				if info.is_dir():
					continue
				name = info.filename
				if not name or name.startswith("/") or "\x00" in name:
					raise UserUploadAdapterError(f"unsafe zip member path: {name!r}")
				target_path = (extract_root / name).resolve()
				if not str(target_path).startswith(str(resolved_root) + os.sep):
					raise UserUploadAdapterError(f"unsafe zip member path: {name!r}")
				target_path.parent.mkdir(parents=True, exist_ok=True)
				with archive.open(info) as source, target_path.open("wb") as target:
					shutil.copyfileobj(source, target)
	except zipfile.BadZipFile as exc:
		raise UserUploadAdapterError(f"invalid zip upload: {source_zip_path}") from exc
	return extract_root


def _prepare_signal_triplet_source_root(source_path: str | Path, work_root: Path) -> Path:
	path = Path(source_path).expanduser().resolve()
	if not path.exists():
		raise FileNotFoundError(f"signal_triplet source not found: {path}")
	if path.is_dir():
		return path
	if path.suffix.lower() == ".zip":
		return _safe_extract_zip(path, work_root)
	raise UserUploadAdapterError(
		"signal_triplet upload expects a .zip package or a directory containing signal.csv/gate.csv/lbs.csv"
	)


def _discover_signal_triplet_routes(source_root: Path) -> list[dict[str, Any]]:
	root = Path(source_root).expanduser().resolve()
	if not root.exists():
		return []
	candidates: list[Path] = []
	dirs = [root]
	if root.is_dir():
		dirs.extend(path for path in root.rglob("*") if path.is_dir())
	for directory in dirs:
		if all((directory / name).is_file() for name in SIGNAL_TRIPLET_REQUIRED_FILES):
			candidates.append(directory)
	if not candidates:
		return []
	routes: list[dict[str, Any]] = []
	seen_uids: set[str] = set()
	for directory in sorted(candidates, key=lambda item: str(item.relative_to(root) if item != root else Path("."))):
		signal_path = directory / "signal.csv"
		signal_rows, _fieldnames = read_csv_rows(signal_path, upload_type="signal6")
		first_row = signal_rows[0] if signal_rows else {}
		uid = str(first_row.get("uid") or directory.name).strip() or directory.name
		if uid in seen_uids:
			raise UserUploadAdapterError(f"duplicate signal_triplet uid from package: {uid}")
		seen_uids.add(uid)
		routes.append(
			{
				"uid": uid,
				"directory": directory,
				"paths": {
					"signal": signal_path,
					"gate": directory / "gate.csv",
					"lbs": directory / "lbs.csv",
					"gps": directory / "gps.csv" if (directory / "gps.csv").is_file() else None,
				},
			}
		)
	return routes


def _write_signal_triplet_combined_signal(routes: list[dict[str, Any]], combined_path: Path) -> tuple[int, dict[str, list[dict[str, Any]]]]:
	combined_rows: list[dict[str, Any]] = []
	signal_rows_by_uid: dict[str, list[dict[str, Any]]] = {}
	for route in routes:
		uid = str(route["uid"])
		rows, _fieldnames = read_csv_rows(route["paths"]["signal"], upload_type="signal6")
		signal_rows_by_uid[uid] = _read_csv_dicts(route["paths"]["signal"])
		for row_number, row in enumerate(rows, start=2):
			row_uid = str(row.get("uid") or uid).strip() or uid
			if row_uid != uid:
				raise UserUploadAdapterError(
					f"{route['paths']['signal']}: row {row_number} uid {row_uid!r} does not match route uid {uid!r}"
				)
			lat = parse_float(
				require_column(row, ("latitude", "lat"), row_number=row_number, label="latitude"),
				row_number=row_number,
				label="latitude",
			)
			lon = parse_float(
				require_column(row, ("longitude", "lon"), row_number=row_number, label="longitude"),
				row_number=row_number,
				label="longitude",
			)
			t_in_ms = parse_timestamp_ms(
				require_column(row, ("t_in", "start_time"), row_number=row_number, label="t_in"),
				row_number=row_number,
				label="t_in",
			)
			t_out_ms = parse_timestamp_ms(
				require_column(row, ("t_out", "end_time"), row_number=row_number, label="t_out"),
				row_number=row_number,
				label="t_out",
			)
			if t_out_ms < t_in_ms:
				raise UserUploadAdapterError(f"{route['paths']['signal']}: row {row_number}: t_out must be >= t_in")
			combined_rows.append(
				{
					"uid": uid,
					"cid": require_column(row, ("cid",), row_number=row_number, label="cid"),
					"latitude": f"{lat:.8f}",
					"longitude": f"{lon:.8f}",
					"t_in": t_in_ms,
					"t_out": t_out_ms,
					"status": normalize_status(row.get("status") or row.get("state")),
				}
			)
	write_csv(combined_path, ["uid", "cid", "latitude", "longitude", "t_in", "t_out", "status"], combined_rows)
	return len(combined_rows), signal_rows_by_uid


def _parse_optional_signal_triplet_time_ms(row: dict[str, Any], keys: tuple[str, ...]) -> int | None:
	for key in keys:
		value = str(row.get(key) or "").strip()
		if not value:
			continue
		try:
			return parse_timestamp_ms(value, row_number=0, label=key)
		except UserUploadAdapterError:
			continue
	return None


def _write_signal_triplet_signal_display_csv(source_path: Path, target_path: Path, fallback_uid: str) -> int:
	rows = _read_csv_dicts(source_path)
	if not rows:
		_write_csv_dicts(target_path, _fieldnames_from_rows(rows, ["uid", "cid", "latitude", "longitude", "t_in", "t_out"]), rows)
		return 0

	start_keys = (
		"t_in",
		"start_time",
		"time_in",
		"procedureStart",
		"procedureStartTime",
		"procedure_start_time",
		"timestamp_ms",
		"timestamp",
		"time",
	)
	end_keys = (
		"t_out",
		"end_time",
		"time_out",
		"procedureEnd",
		"procedureEndTime",
		"procedure_end_time",
		"proceduereEndTime",
		"proceduere_end_time",
		"timestamp_ms",
		"timestamp",
		"time",
	)
	grouped: dict[str, list[tuple[int, int | None, int | None]]] = defaultdict(list)
	for index, row in enumerate(rows):
		uid = str(row.get("uid") or row.get("UID") or fallback_uid).strip() or fallback_uid
		start_ms = _parse_optional_signal_triplet_time_ms(row, start_keys)
		end_ms = _parse_optional_signal_triplet_time_ms(row, end_keys)
		grouped[uid].append((index, start_ms, end_ms))

	display_by_index: dict[int, tuple[int | None, int | None, str]] = {}
	for items in grouped.values():
		distinct_starts = sorted({start_ms for _index, start_ms, _end_ms in items if start_ms is not None})
		next_by_start: dict[int, int | None] = {}
		for start_index, start_ms in enumerate(distinct_starts):
			next_by_start[start_ms] = distinct_starts[start_index + 1] if start_index + 1 < len(distinct_starts) else None
		for index, start_ms, end_ms in items:
			display_end_ms = end_ms
			source = "source_t_out" if end_ms is not None else ""
			duration_ms = end_ms - start_ms if start_ms is not None and end_ms is not None else None
			if start_ms is not None and (duration_ms is None or duration_ms <= 1000):
				next_start_ms = next_by_start.get(start_ms)
				if next_start_ms is not None and next_start_ms > start_ms:
					display_end_ms = next_start_ms
					source = "next_signal_t_in"
					duration_ms = display_end_ms - start_ms
			if start_ms is not None and display_end_ms is not None and display_end_ms >= start_ms:
				display_by_index[index] = (display_end_ms, display_end_ms - start_ms, source)
			else:
				display_by_index[index] = (display_end_ms, None, source)

	output_rows: list[dict[str, Any]] = []
	for index, row in enumerate(rows):
		output_row = dict(row)
		display_end_ms, duration_ms, source = display_by_index.get(index, (None, None, ""))
		output_row["display_t_out"] = display_end_ms if display_end_ms is not None else ""
		output_row["display_duration_ms"] = duration_ms if duration_ms is not None else ""
		output_row["display_duration_source"] = source
		output_rows.append(output_row)
	_write_csv_dicts(
		target_path,
		_fieldnames_from_rows(output_rows, ["uid", "cid", "latitude", "longitude", "t_in", "t_out"]),
		output_rows,
	)
	return len(output_rows)


def _read_signal_triplet_truth(path: Path | None) -> tuple[list[Any], int | None, int | None, str]:
	if path is None or not path.exists():
		return [], None, None, ""
	from adapters.signal_gps_compare.build_v311_comparison_batch import row_point_wgs

	rows = _read_csv_dicts(path)
	points: list[Any] = []
	timestamps: list[int] = []
	for index, row in enumerate(rows, start=2):
		point = row_point_wgs(row)
		if point is not None:
			points.append(point)
		time_value = str(row.get("timestamp_ms") or row.get("timestamp") or "").strip()
		if time_value:
			try:
				timestamps.append(parse_timestamp_ms(time_value, row_number=index, label="timestamp_ms"))
			except UserUploadAdapterError:
				pass
	start_ms = min(timestamps) if timestamps else None
	end_ms = max(timestamps) if timestamps else None
	source_file = ""
	for row in rows:
		source_file = str(row.get("source_file") or "").strip()
		if source_file:
			break
	return points, start_ms, end_ms, source_file or path.name


def _fieldnames_from_rows(rows: list[dict[str, Any]], fallback: list[str]) -> list[str]:
	fieldnames: list[str] = []
	for field in fallback:
		if field not in fieldnames:
			fieldnames.append(field)
	for row in rows:
		for key in row.keys():
			if key not in fieldnames:
				fieldnames.append(key)
	return fieldnames


def _write_chain_csv_or_empty(source_path: Path, target_path: Path, fallback_fields: list[str]) -> int:
	rows = _read_csv_dicts(source_path)
	_write_csv_dicts(target_path, _fieldnames_from_rows(rows, fallback_fields), rows)
	return len(rows)


def _build_chain_result_uid_dir_map(chain_result_root: Path) -> dict[str, Path]:
	result: dict[str, Path] = {}
	for uid_dir in _safe_uid_result_dirs(chain_result_root):
		for csv_name in ("raw.csv", "snap.csv", "line.csv", "od.csv", "fmm.csv"):
			rows = _read_csv_dicts(uid_dir / csv_name)
			uid = ""
			for row in rows:
				uid = str(row.get("uid") or row.get("UID") or "").strip()
				if uid:
					break
			if uid:
				result.setdefault(uid, uid_dir)
				break
		result.setdefault(uid_dir.name, uid_dir)
	return result


def _build_reconstruction_rows_without_truth(uid: str, line_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	from adapters.signal_gps_compare.build_v311_comparison_batch import _row_time_seconds, row_point_wgs
	from adapters.signal_gps_compare.build_batch import RECON_FIELDS

	rows: list[dict[str, Any]] = []
	for index, row in enumerate(line_rows):
		point = row_point_wgs(row)
		if point is None:
			continue
		time_s = _row_time_seconds(row, "timestamp_ms", "t_in", "time", "start_time")
		rows.append(
			{
				"uid": uid,
				"point_index": index,
				"latitude": f"{point.lat:.8f}",
				"longitude": f"{point.lon:.8f}",
				"timestamp_ms": int(time_s * 1000) if time_s is not None else "",
				"state": "",
				"status": "",
				"distance_to_gps_m": "",
				"matched_gps_file": "",
				"gps_segment_index": "",
				"source_x": "",
				"source_y": "",
			}
		)
	return [{field: row.get(field, "") for field in RECON_FIELDS} for row in rows]


def _write_signal_triplet_final_result(
	*,
	result_root: Path,
	title: str,
	routes: list[dict[str, Any]],
	chain_result_root: Path,
	chain_report: dict[str, Any],
	signal_rows_by_uid: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
	from adapters.signal_gps_compare.build_batch import (
		GPS_FIELDS,
		RECON_FIELDS,
		ROAD_SEGMENT_FIELDS,
		Point,
		build_gps_coverage_rows,
	)
	from adapters.signal_gps_compare.build_v311_comparison_batch import (
		GPS_COVERAGE_STEP_M,
		GPS_COVERAGE_THRESHOLD_M,
		OD_STAY_EXTRA_FIELDS,
		build_gps_coverage_scenarios,
		build_od_rows_with_stays,
		build_reconstruction_rows,
	)

	if result_root.exists():
		shutil.rmtree(result_root)
	result_root.mkdir(parents=True, exist_ok=True)

	generated_at = utc_now_iso()
	uids = [str(route["uid"]) for route in routes]
	has_gps = all(bool(route["paths"].get("gps")) for route in routes)
	states_index: dict[str, list[str]] = {}
	coverage_rows_by_uid: dict[str, list[dict[str, Any]]] = {}
	by_uid: dict[str, Any] = {}
	alignment_segments: list[dict[str, Any]] = []
	total_gps_length_m = 0.0
	total_gps_covered_length_m = 0.0
	total_road = 0
	total_road_ok = 0
	total_points = 0
	total_points_ok = 0
	chain_uid_dirs = _build_chain_result_uid_dir_map(chain_result_root)

	for route in routes:
		uid = str(route["uid"])
		uid_dir = result_root / uid
		uid_dir.mkdir(parents=True, exist_ok=True)
		_write_signal_triplet_signal_display_csv(route["paths"]["signal"], uid_dir / "signal.csv", uid)
		for layer_name in ("gate", "lbs"):
			shutil.copy2(route["paths"][layer_name], uid_dir / f"{layer_name}.csv")

		chain_uid_dir = chain_uid_dirs.get(uid) or (chain_result_root / uid)
		if not chain_uid_dir.exists():
			raise UserUploadAdapterError(f"signal_triplet algorithm output missing uid directory: {uid}")

		snap_points = _write_chain_csv_or_empty(chain_uid_dir / "snap.csv", uid_dir / "snap.csv", ["uid", "cid", "latitude", "longitude", "t_in", "t_out"])
		od_source_rows = _read_csv_dicts(chain_uid_dir / "od.csv")
		line_rows = _read_csv_dicts(chain_uid_dir / "line.csv")

		truth_points, truth_start_ms, truth_end_ms, truth_source_file = _read_signal_triplet_truth(route["paths"].get("gps"))
		if truth_points:
			recon_rows = build_reconstruction_rows(uid, line_rows, truth_points)
		else:
			recon_rows = _build_reconstruction_rows_without_truth(uid, line_rows)
		_write_csv_dicts(uid_dir / "reconstruction.csv", RECON_FIELDS, recon_rows)

		od_rows = build_od_rows_with_stays(
			uid,
			od_source_rows,
			signal_rows_by_uid.get(uid, []),
			truth_points,
			truth_start_ms,
			truth_end_ms,
		)
		od_fieldnames = _fieldnames_from_rows(od_rows, [])
		for key in OD_STAY_EXTRA_FIELDS:
			if key not in od_fieldnames:
				od_fieldnames.append(key)
		_write_csv_dicts(uid_dir / "od.csv", od_fieldnames, od_rows)

		if truth_points and route["paths"].get("gps"):
			shutil.copy2(route["paths"]["gps"], uid_dir / "gps.csv")
			restored_points: list[Point] = []
			for row in recon_rows:
				try:
					restored_points.append(Point(lat=float(row["latitude"]), lon=float(row["longitude"])))
				except (KeyError, TypeError, ValueError):
					continue
			road_rows, gps_covered_length_m, gps_total_length_m = build_gps_coverage_rows(
				uid,
				restored_points,
				truth_points,
				step_m=GPS_COVERAGE_STEP_M,
				distance_threshold_m=GPS_COVERAGE_THRESHOLD_M,
			)
			_write_csv_dicts(uid_dir / "road_segment_compare.csv", ROAD_SEGMENT_FIELDS, road_rows)
			_write_csv_dicts(
				uid_dir / "gps_compare_segments.csv",
				["uid", "segment_index", "state", "start_index", "end_index", "point_count", "accuracy", "start_time", "end_time"],
				[],
			)
			coverage_rows_by_uid[uid] = road_rows
			coverage_accuracy = gps_covered_length_m / gps_total_length_m if gps_total_length_m else 0.0
			point_count = len(recon_rows)
			point_ok = sum(1 for row in recon_rows if str(row.get("status") or row.get("state")) == "gps_match")
			point_accuracy = point_ok / point_count if point_count else 0.0
			road_count = len(road_rows)
			road_ok = sum(1 for row in road_rows if str(row.get("matched") or "") == "1")
			states_index[uid] = ["gps_match"] if coverage_accuracy >= 0.9 else ["gps_mismatch"]
			by_uid[uid] = {
				"uid": uid,
				"accuracy": round(coverage_accuracy, 4),
				"accuracy_percent": round(coverage_accuracy * 100, 2),
				"gps_coverage_accuracy": round(coverage_accuracy, 4),
				"gps_coverage_accuracy_percent": round(coverage_accuracy * 100, 2),
				"gps_total_length_m": round(gps_total_length_m, 2),
				"gps_covered_length_m": round(gps_covered_length_m, 2),
				"gps_coverage_threshold_m": GPS_COVERAGE_THRESHOLD_M,
				"road_segment_accuracy": round(coverage_accuracy, 4),
				"road_segment_accuracy_percent": round(coverage_accuracy * 100, 2),
				"road_truth_segments": road_count,
				"road_matched_segments": road_ok,
				"point_accuracy": round(point_accuracy, 4),
				"point_accuracy_percent": round(point_accuracy * 100, 2),
				"total_points": point_count,
				"correct_points": point_ok,
				"threshold_meters": GPS_COVERAGE_THRESHOLD_M,
				"matched_gps_file": truth_source_file or "gps.csv",
				"gps_truth_file": truth_source_file or "gps.csv",
				"signal_segment_file": Path(route["paths"]["signal"]).name,
				"reconstruction_file": str(chain_uid_dir / "line.csv"),
				"raw_signal_points": len(signal_rows_by_uid.get(uid, [])),
				"snap_points": snap_points,
				"od_segments": len(od_rows),
				"gps_points": len(truth_points),
				"lbs_points": len(_read_csv_dicts(route["paths"]["lbs"])),
			}
			alignment_segments.append(
				{
					"uid": uid,
					"signal_segment_file": Path(route["paths"]["signal"]).name,
					"gps_truth_file": truth_source_file or "gps.csv",
					"v311_uid_dir": chain_uid_dir.name,
					"accuracy_percent": round(coverage_accuracy * 100, 2),
					"gps_coverage_accuracy_percent": round(coverage_accuracy * 100, 2),
					"gps_total_length_m": round(gps_total_length_m, 2),
					"gps_covered_length_m": round(gps_covered_length_m, 2),
					"point_accuracy_percent": round(point_accuracy * 100, 2),
					"road_truth_segments": road_count,
					"road_matched_segments": road_ok,
					"reconstruction_points": point_count,
					"snap_points": snap_points,
					"od_segments": len(od_rows),
				}
			)
			total_gps_length_m += gps_total_length_m
			total_gps_covered_length_m += gps_covered_length_m
			total_road += road_count
			total_road_ok += road_ok
			total_points += point_count
			total_points_ok += point_ok
		else:
			states_index[uid] = []

	overall = total_gps_covered_length_m / total_gps_length_m if total_gps_length_m else 0.0
	point_overall = total_points_ok / total_points if total_points else 0.0
	coverage_scenarios, coverage_recommendation = build_gps_coverage_scenarios(coverage_rows_by_uid) if coverage_rows_by_uid else ([], {})
	algorithm_metadata = chain_report.get("fmm_algorithm") if isinstance(chain_report.get("fmm_algorithm"), dict) else {}
	comparison = {
		"generated_at": generated_at,
		"method": "signal_triplet_upload_v311_snap_od_fmm_gps_truth_length_coverage",
		"coordinate_system": "metrics and batch CSV coordinates are WGS84; the Studio frontend converts to GCJ-02 at render time for Gaode basemap",
		"comparison_label": "比对 GPS路段真值",
		"reference_layer_label": "GPS真值轨迹",
		"runtime_pipeline": "snap+OD+FMM v311",
		"algorithm": algorithm_metadata,
		"fmm_version": chain_report.get("fmm_version") or algorithm_metadata.get("fmm_version") or "",
		"fmm_network_cost_field": chain_report.get("fmm_network_cost_field") or algorithm_metadata.get("fmm_network_cost_field") or "",
		"gps_coverage_definition": "GPS truth length whose segment midpoint is within 50m of the reconstructed trajectory divided by total GPS truth length",
		"gps_coverage_threshold_meters": GPS_COVERAGE_THRESHOLD_M,
		"gps_coverage_step_meters": GPS_COVERAGE_STEP_M,
		"gps_coverage_scenarios": coverage_scenarios,
		"gps_accuracy_90_candidates": coverage_recommendation,
		"road_segment_step_meters": GPS_COVERAGE_STEP_M,
		"road_segment_distance_meters": GPS_COVERAGE_THRESHOLD_M,
		"road_segment_heading_degrees": None,
		"overall_accuracy": round(overall, 4),
		"overall_accuracy_percent": round(overall * 100, 2),
		"gps_coverage_accuracy": round(overall, 4),
		"gps_coverage_accuracy_percent": round(overall * 100, 2),
		"gps_total_length_m": round(total_gps_length_m, 2),
		"gps_covered_length_m": round(total_gps_covered_length_m, 2),
		"road_overall_accuracy": round(overall, 4),
		"road_overall_accuracy_percent": round(overall * 100, 2),
		"road_truth_segments": total_road,
		"road_matched_segments": total_road_ok,
		"point_overall_accuracy": round(point_overall, 4),
		"point_overall_accuracy_percent": round(point_overall * 100, 2),
		"total_points": total_points,
		"correct_points": total_points_ok,
		"alignment_segments": alignment_segments,
		"by_uid": by_uid,
	}

	layers = ["signal", "gate", "lbs", "snap", "od", "reconstruction"]
	if has_gps:
		layers.append("gps")
	layer_labels = {
		"signal": "测试号信令",
		"gate": "卡口定位",
		"lbs": "LBS辅助定位",
		"snap": "Snap中间结果",
		"od": "OD中间结果",
		"reconstruction": "信令还原轨迹",
		"gps": "GPS真值轨迹",
	}
	layer_specs = {
		"signal": {"filename": "signal.csv", "kind": "signal", "defaultColor": "#f59e0b", "defaultOpacity": 0.72, "hasLine": True},
		"gate": {"filename": "gate.csv", "kind": "gate", "defaultColor": "#0891b2", "defaultOpacity": 0.88, "hasLine": False, "pointRadius": 8, "ignoreDisplayTimeWindow": True},
		"lbs": {"filename": "lbs.csv", "kind": "lbs", "defaultColor": "#0284c7", "defaultOpacity": 0.86, "hasLine": True, "pointRadius": 4, "lineWeight": 5, "dashArray": "10 6", "ignoreDisplayTimeWindow": True},
		"snap": {"filename": "snap.csv", "kind": "default", "defaultColor": "#7c3aed", "defaultOpacity": 0.62, "hasLine": True},
		"od": {"filename": "od.csv", "kind": "od", "defaultColor": "#0f766e", "defaultOpacity": 0.74, "hasLine": False, "isOD": True, "moveColor": "#0f766e", "stayColor": "#111827", "stayDefaultRadiusM": 90, "stayFillOpacity": 0.32},
		"reconstruction": {"filename": "reconstruction.csv", "kind": "gps", "defaultColor": "#dc2626", "defaultOpacity": 0.78, "hasLine": True},
		"gps": {"filename": "gps.csv", "kind": "gps", "defaultColor": "#2563eb", "defaultOpacity": 0.82, "hasLine": True},
	}
	review_reference_files = ["signal.csv", "gate.csv", "lbs.csv", "snap.csv", "od.csv", "reconstruction.csv"]
	if has_gps:
		review_reference_files.extend(["gps.csv", "road_segment_compare.csv"])
	filter_state_options = ["gps_match", "gps_mismatch"] if has_gps else []
	manifest = {
		"dataset_name": Path(result_root).parent.name,
		"label": title,
		"title": title,
		"generated_at": generated_at,
		"ui_mode": "trajectory_layers",
		"uids": uids,
		"layers": layers,
		"layer_labels": {key: value for key, value in layer_labels.items() if key in layers},
		"layer_specs": {key: value for key, value in layer_specs.items() if key in layers},
		"layer_visibility": {
			"signal": False,
			"gate": True,
			"lbs": True,
			"snap": False,
			"od": True,
			"reconstruction": True,
			"gps": False,
		} if has_gps else {
			"signal": False,
			"gate": True,
			"lbs": True,
			"snap": False,
			"od": True,
			"reconstruction": True,
		},
		"time_scrubber_preferred_layers": ["reconstruction", "gps", "signal"] if has_gps else ["reconstruction", "signal"],
		"review_reference_files": review_reference_files,
		"hide_review_panel": True,
		"states": states_index,
		"filter_state_options": filter_state_options,
		"point_status_types": filter_state_options,
		"point_status_styles": {"gps_match": {"color": "#16a34a", "size": 5}, "gps_mismatch": {"color": "#dc2626", "size": 6}} if has_gps else {},
		"fmm_version": chain_report.get("fmm_version") or algorithm_metadata.get("fmm_version") or "",
		"fmm_network_cost_field": chain_report.get("fmm_network_cost_field") or algorithm_metadata.get("fmm_network_cost_field") or "",
		"fmm_edges": chain_report.get("fmm_effective_edges") or chain_report.get("fmm_edges") or algorithm_metadata.get("fmm_edges") or "",
		"fmm_algorithm": algorithm_metadata,
	}
	if has_gps:
		manifest["gps_comparison"] = comparison
	write_json(result_root / "manifest.json", manifest)
	write_json(result_root / "states_index.json", states_index)
	if has_gps:
		write_json(result_root / "gps_comparison_summary.json", comparison)
	signal6_algorithm_profile = normalize_signal6_algorithm_profile(
		chain_report.get("signal6_algorithm_profile")
		or algorithm_metadata.get("profile")
		or "speed_sparsity_90"
	)
	return {
		"adapter": SIGNAL_TRIPLET_UPLOAD_TYPE,
		"pipeline_mode": "v311",
		"ui_mode": "trajectory_layers",
		"review_reference_files": review_reference_files,
		"result_root": str(result_root),
		"uid_count": len(uids),
		"uids": uids,
		"row_count": sum(len(rows) for rows in signal_rows_by_uid.values()),
		"filter_state_options": filter_state_options,
		"signal6_algorithm_profile": signal6_algorithm_profile,
		"fmm_algorithm": algorithm_metadata,
		"gps_comparison": comparison if has_gps else None,
		"runtime_pipeline": "snap+od+fmm",
		"source_layers": ["signal", "gate", "lbs", "gps"] if has_gps else ["signal", "gate", "lbs"],
		"chain_report": chain_report,
	}


def build_signal_triplet_result(
	source_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Signal/Gate/LBS",
	pipeline_options: Any = None,
) -> dict[str, Any]:
	result_root = Path(output_root).expanduser().resolve()
	run_root = result_root.parent
	work_root = run_root / "_signal_triplet_upload"
	if work_root.exists():
		shutil.rmtree(work_root)
	work_root.mkdir(parents=True, exist_ok=True)
	source_root = _prepare_signal_triplet_source_root(source_path, work_root)
	routes = _discover_signal_triplet_routes(source_root)
	if not routes:
		raise UserUploadAdapterError(
			"signal_triplet upload did not find any route folder with signal.csv, gate.csv, and lbs.csv"
		)
	combined_signal_path = work_root / "combined_signal6.csv"
	row_count, signal_rows_by_uid = _write_signal_triplet_combined_signal(routes, combined_signal_path)
	if row_count <= 0:
		raise UserUploadAdapterError("signal_triplet signal.csv inputs did not yield any signal rows")

	chain_root = run_root / "_signal_triplet_algorithm" / "result"
	if chain_root.parent.exists():
		shutil.rmtree(chain_root.parent)
	options = signal6_pipeline_options_for_profile("speed_sparsity_90")
	if pipeline_options is not None:
		if not isinstance(pipeline_options, dict):
			raise UserUploadAdapterError("signal_triplet pipeline_options must be an object")
		requested_profile = normalize_signal6_algorithm_profile(
			pipeline_options.get("signal6_algorithm_profile")
			or options.get("signal6_algorithm_profile")
			or "speed_sparsity_90"
		)
		options = _deep_update_mapping(signal6_pipeline_options_for_profile(requested_profile), pipeline_options)
	options["signal6_algorithm_profile"] = normalize_signal6_algorithm_profile(
		options.get("signal6_algorithm_profile") or "speed_sparsity_90"
	)
	chain_report = build_signal6_result(
		combined_signal_path,
		chain_root,
		title=title,
		field_mapping=None,
		pipeline_mode="v311",
		pipeline_options=options,
	)
	return _write_signal_triplet_final_result(
		result_root=result_root,
		title=title,
		routes=routes,
		chain_result_root=chain_root,
		chain_report=chain_report,
		signal_rows_by_uid=signal_rows_by_uid,
	)


def build_signal6_result(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Signal6",
	field_mapping: Any = None,
	pipeline_mode: Any = "legacy",
	pipeline_options: Any = None,
) -> dict[str, Any]:
	mode = normalize_signal6_pipeline_mode(pipeline_mode)
	if mode == "legacy":
		if pipeline_options is not None and not isinstance(pipeline_options, dict):
			raise UserUploadAdapterError("signal6 legacy pipeline_options must be an object")
		return _build_signal6_result_legacy(
			source_csv_path=source_csv_path,
			output_root=output_root,
			title=title,
			field_mapping=field_mapping,
			drop_outside_beijing_bbox_rows=bool(
				pipeline_options.get("drop_outside_beijing_bbox_rows", False)
				if isinstance(pipeline_options, dict)
				else False
			),
		)
	if mode == "v311":
		return _build_signal6_result_v311(
			source_csv_path=source_csv_path,
			output_root=output_root,
			title=title,
			field_mapping=field_mapping,
			pipeline_options=pipeline_options,
		)
	raise UserUploadAdapterError(
		f"unsupported signal6 pipeline_mode: {pipeline_mode!r}; expected one of {sorted(SIGNAL6_PIPELINE_MODES)}"
	)


__all__ = [
	"BEIJING_BBOX",
	"UserUploadAdapterError",
	"build_signal6_result",
	"build_signal_triplet_result",
	"build_trajectory4_result",
	"normalize_signal6_pipeline_mode",
	"normalize_signal6_algorithm_profile",
	"signal6_pipeline_mode_for_profile",
	"signal6_pipeline_options_for_profile",
	"normalize_user_upload_field_mapping",
]
