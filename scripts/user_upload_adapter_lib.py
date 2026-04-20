from __future__ import annotations

import csv
import json
import re
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


class UserUploadAdapterError(ValueError):
	pass


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


def build_signal6_result(
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
		"result_root": str(result_root),
		"uid_count": len(uids),
		"uids": uids,
		"row_count": len(rows),
		"filter_state_options": filter_state_options,
		"beijing_bbox": dict(BEIJING_BBOX),
	}


__all__ = [
	"BEIJING_BBOX",
	"UserUploadAdapterError",
	"build_signal6_result",
	"build_trajectory4_result",
]
