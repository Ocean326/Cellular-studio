from __future__ import annotations

import csv
import json
import os
import re
import sys
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
}

AUTO_UPLOAD_TYPE = "auto"
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
) -> dict[str, Any]:
	rows, _fieldnames = read_csv_rows(source_csv_path, field_mapping=field_mapping, upload_type="signal6")
	result_root = Path(output_root).expanduser().resolve()
	result_root.mkdir(parents=True, exist_ok=True)

	grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
	global_states: list[str] = []

	for row_number, row in enumerate(rows, start=2):
		uid = require_column(row, ("uid",), row_number=row_number, label="uid")
		cid = require_column(row, ("cid",), row_number=row_number, label="cid")
		lat = parse_float(require_column(row, ("latitude", "lat"), row_number=row_number, label="latitude"), row_number=row_number, label="latitude")
		lon = parse_float(require_column(row, ("longitude", "lon"), row_number=row_number, label="longitude"), row_number=row_number, label="longitude")
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
	}


def _signal6_repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _signal6_v311_default_assets(repo_root: Path) -> dict[str, Path]:
	return {
		"fmm_edges": repo_root / "project_data" / "map_assets" / "beijing" / "edges.shp",
		"fmm_cmd": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "fmm",
		"fmm_ubodt_cmd": repo_root / "my_history_methods" / "map_matching" / "vendor" / "fmm" / "build" / "ubodt_gen",
	}


def _ensure_signal6_v311_assets(assets: dict[str, Path]) -> None:
	missing = [f"{name}={path}" for name, path in assets.items() if not path.exists()]
	if not missing:
		return
	raise UserUploadAdapterError(
		"signal6 v311 runtime asset missing: "
		+ "; ".join(missing)
		+ ". expected local snap+OD+fmm runtime under project_data/map_assets and my_history_methods/map_matching/vendor/fmm/build"
	)


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


def _build_signal6_result_v311(
	source_csv_path: str | Path,
	output_root: str | Path,
	*,
	title: str = "Uploaded Signal6",
	field_mapping: Any = None,
	pipeline_options: Any = None,
) -> dict[str, Any]:
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
	_ensure_signal6_v311_assets(assets)

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
		"runtime_pipeline": "snap+od+fmm",
	}


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
		return _build_signal6_result_legacy(
			source_csv_path=source_csv_path,
			output_root=output_root,
			title=title,
			field_mapping=field_mapping,
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
	"build_trajectory4_result",
	"normalize_signal6_pipeline_mode",
	"normalize_user_upload_field_mapping",
]
