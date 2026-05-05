from __future__ import annotations

import csv
import hashlib
import math
import json
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

try:
	from ..batch_contract import (
		DEFAULT_RESULT_FILES,
		dedupe_preserve_order,
		get_manifest_layer_filenames,
		get_manifest_review_reference_filenames,
	)
except (ImportError, ValueError):
	REPO_ROOT = Path(__file__).resolve().parents[1]
	if str(REPO_ROOT) not in sys.path:
		sys.path.insert(0, str(REPO_ROOT))
	from batch_contract import (  # type: ignore
		DEFAULT_RESULT_FILES,
		dedupe_preserve_order,
		get_manifest_layer_filenames,
		get_manifest_review_reference_filenames,
	)


VALID_DECISIONS = frozenset({"accept", "reject", "skip"})

SCHEMA_VERSION = 2

DEFAULT_LEDGER_NAME = "ledger.jsonl"
DEFAULT_LATEST_NAME = "latest_reviews.json"
DEFAULT_ACCEPTED_LEDGER_NAME = "accepted_reviews.jsonl"
DEFAULT_ACCEPTED_MANIFEST_NAME = "export_manifest.json"
DEFAULT_TIMELINE_ANNOTATIONS_DIR = "timeline_annotations"
DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME = "ledger.jsonl"
DEFAULT_TRACK_EDITS_DIR = "track_edits"
DEFAULT_TRACK_EDITS_LEDGER_NAME = "ledger.jsonl"
DEFAULT_SYSTEM_DIR = "system"
DEFAULT_REVIEWERS_DIR = "reviewers"
DEFAULT_AGGREGATE_DIR = "aggregate"
DEFAULT_AGGREGATE_BY_UID_DIR = "by_uid"
DEFAULT_REVIEW_EXPORTS_DIR = "review_exports"
DEFAULT_REVIEWER_REGISTRY_NAME = "reviewer_registry.json"
DEFAULT_SCHEMA_VERSION_NAME = "schema_version.json"
DEFAULT_AGGREGATE_STATS_NAME = "stats.json"
DEFAULT_REVIEWER_EXPORTS_DIR = "reviewers"
DEFAULT_REVIEWER_BUNDLE_LEDGER_NAME = "ledger.jsonl"
DEFAULT_REVIEWER_BUNDLE_LATEST_NAME = "latest_reviews.json"
DEFAULT_REVIEWER_BUNDLE_MANIFEST_NAME = "bundle_manifest.json"
DEFAULT_SOURCE_MANIFEST_NAME = "source_manifest.json"
DEFAULT_LEGACY_TIMELINE_REVIEWER_ID = "legacy-import"
TRACK_EDITS_SCHEMA_VERSION = 1
REVIEWER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
EXPORT_DATASET_STATUSES = frozenset({
	"subway",
	"road_car",
	"road_bus",
	"road_taxi",
	"road",
	"low_speed",
	"train",
	"stay",
	"flight",
})
EXPORT_STATUS_ALIASES = {
	"地铁": "subway",
	"subway": "subway",
	"road_car": "road_car",
	"驾车": "road_car",
	"road_bus": "road_bus",
	"公交": "road_bus",
	"road_taxi": "road_taxi",
	"出租车": "road_taxi",
	"road": "road",
	"乘车": "road",
	"低速": "low_speed",
	"low_speed": "low_speed",
	"railway": "train",
	"铁路": "train",
	"rail": "train",
	"列车": "train",
	"火车": "train",
	"train": "train",
	"驻留": "stay",
	"stay": "stay",
	"飞机": "flight",
	"flight": "flight",
}
INTERVAL_SEMANTICS_ALIASES = {
	"left_open_right_closed": "left_open_right_closed",
	"closed": "closed_interval",
	"closed_interval": "closed_interval",
}
VALID_INTERVAL_SEMANTICS = frozenset(INTERVAL_SEMANTICS_ALIASES.values())
DEFAULT_INTERVAL_SEMANTICS = "closed_interval"
DEFAULT_SEGMENT_POLICY = {
	"exclusiveMode": False,
	"intervalSemantics": DEFAULT_INTERVAL_SEMANTICS,
}
TIMELINE_SEGMENT_REPLAY_CATEGORY_BY_SEMANTIC_TAG = {
	"matcher:road": {"categoryId": "road", "categoryName": "road", "color": "#4caf50"},
	"road": {"categoryId": "road", "categoryName": "road", "color": "#4caf50"},
	"matcher:subway": {"categoryId": "subway", "categoryName": "subway", "color": "#9c27b0"},
	"subway": {"categoryId": "subway", "categoryName": "subway", "color": "#9c27b0"},
	"matcher:railway": {"categoryId": "railway", "categoryName": "railway", "color": "#795548"},
	"railway": {"categoryId": "railway", "categoryName": "railway", "color": "#795548"},
	"matcher:unmatched": {"categoryId": "unmatch", "categoryName": "unmatch", "color": "#ffd700"},
	"matcher:unmatch": {"categoryId": "unmatch", "categoryName": "unmatch", "color": "#ffd700"},
	"unmatched": {"categoryId": "unmatch", "categoryName": "unmatch", "color": "#ffd700"},
	"unmatch": {"categoryId": "unmatch", "categoryName": "unmatch", "color": "#ffd700"},
	"matcher:stay": {"categoryId": "stay", "categoryName": "stay", "color": "#000000"},
	"stay": {"categoryId": "stay", "categoryName": "stay", "color": "#000000"},
}
TIMELINE_SEGMENT_IGNORED_SEMANTIC_TAG_PREFIXES = frozenset({
	"workflow:",
	"chain:",
	"legacy:ocean0416:",
})

_LOCKS: dict[str, RLock] = {}


@dataclass(frozen=True)
class ReviewPaths:
	project_root: Path
	result_root: Path
	review_root: Path
	ledger_path: Path
	latest_path: Path
	export_root: Path


@dataclass(frozen=True)
class ReviewerPaths:
	reviewer_id: str
	reviewer_name: str
	reviewer_root: Path
	profile_path: Path
	reviews_root: Path
	ledger_path: Path
	latest_path: Path
	timeline_root: Path
	timeline_ledger_path: Path
	track_edits_root: Path
	track_edits_ledger_path: Path
	export_root: Path


@dataclass(frozen=True)
class ReviewEntry:
	uid: str
	sample_id: str
	decision: str
	reviewer_id: str
	reviewer_name: str
	reviewer: str
	timestamp: str
	notes: str = ""
	reference_source: str = ""
	trajectory_tags: list[str] = field(default_factory=list)
	schema_version: int = SCHEMA_VERSION


def resolve_project_root(anchor: Path | None = None) -> Path:
	base = Path(anchor) if anchor is not None else Path(__file__).resolve()
	return base.resolve().parents[1]


def resolve_review_paths(
	project_root: str | Path | None = None,
	result_root: str | Path | None = None,
	review_root: str | Path | None = None,
	export_root: str | Path | None = None,
) -> ReviewPaths:
	root = Path(project_root).resolve() if project_root else resolve_project_root()
	resolved_result_root = Path(result_root).resolve() if result_root else root / "data" / "result"
	resolved_review_root = Path(review_root).resolve() if review_root else root / "data" / "review"
	resolved_export_root = (
		Path(export_root).resolve() if export_root else resolved_review_root / "accepted_assets"
	)
	return ReviewPaths(
		project_root=root,
		result_root=resolved_result_root,
		review_root=resolved_review_root,
		ledger_path=resolved_review_root / DEFAULT_LEDGER_NAME,
		latest_path=resolved_review_root / DEFAULT_LATEST_NAME,
		export_root=resolved_export_root,
	)


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_lock(key: str | Path) -> RLock:
	lock_key = str(key)
	lock = _LOCKS.get(lock_key)
	if lock is None:
		lock = RLock()
		_LOCKS[lock_key] = lock
	return lock


def _read_json(path: Path) -> dict[str, Any]:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with tempfile.NamedTemporaryFile(
		"w",
		encoding="utf-8",
		dir=path.parent,
		delete=False,
		prefix=f"{path.name}.",
		suffix=".tmp",
	) as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2)
		handle.write("\n")
		tmp_path = Path(handle.name)
	tmp_path.replace(path)


def _read_result_manifest(result_root: str | Path) -> dict[str, Any]:
	manifest_path = Path(result_root) / "manifest.json"
	if not manifest_path.exists():
		return {}
	try:
		return _read_json(manifest_path)
	except Exception:
		return {}


def get_manifest_review_reference_files(result_root: str | Path) -> list[str]:
	manifest_payload = _read_result_manifest(result_root)
	return get_manifest_review_reference_filenames(manifest_payload)


def get_manifest_export_filenames(result_root: str | Path) -> list[str]:
	manifest_payload = _read_result_manifest(result_root)
	declared = get_manifest_layer_filenames(manifest_payload)
	return dedupe_preserve_order(
		[
			"raw.csv",
			"snap.csv",
			"od.csv",
			"fmm.csv",
			"line.csv",
			*declared,
		]
	)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "a", encoding="utf-8") as handle:
		handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _safe_copy(src: Path, dst: Path) -> bool:
	if not src.exists() or not src.is_file():
		return False
	dst.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(src, dst)
	return True


def _make_zip_from_directory(src_dir: Path, zip_path: Path) -> Path:
	zip_path.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		for path in sorted(src_dir.rglob("*")):
			if not path.is_file():
				continue
			archive.write(path, arcname=path.relative_to(src_dir))
	return zip_path


def validate_decision(decision: str) -> str:
	value = str(decision or "").strip().lower()
	if value not in VALID_DECISIONS:
		raise ValueError(
			f"Invalid decision: {decision!r}. Expected one of {sorted(VALID_DECISIONS)}"
		)
	return value


def normalize_trajectory_tags(value: Any) -> list[str]:
	if value is None:
		raw_items: list[Any] = []
	elif isinstance(value, (list, tuple, set)):
		raw_items = list(value)
	else:
		raw_items = [value]
	normalized: list[str] = []
	seen: set[str] = set()
	for item in raw_items:
		text = str(item or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		normalized.append(text)
	return normalized


def normalize_string_filters(value: Any) -> list[str]:
	if value is None:
		raw_items: list[Any] = []
	elif isinstance(value, str):
		raw_items = re.split(r"[\s,|]+", value)
	elif isinstance(value, (list, tuple, set)):
		raw_items = list(value)
	else:
		raw_items = [value]
	normalized: list[str] = []
	seen: set[str] = set()
	for item in raw_items:
		text = str(item or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		normalized.append(text)
	return normalized


def _normalize_bool(value: Any, default: bool = False) -> bool:
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	text = str(value).strip().lower()
	if not text:
		return default
	if text in {"1", "true", "yes", "on"}:
		return True
	if text in {"0", "false", "no", "off"}:
		return False
	return bool(value)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
	if not path.exists() or not path.is_file():
		return []
	with open(path, encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def _normalize_time_ms(value: Any) -> int | None:
	text = str(value or "").strip()
	if not text:
		return None
	try:
		number = float(text)
	except (TypeError, ValueError):
		return None
	if abs(number) < 10**11:
		number *= 1000.0
	return int(round(number))


def _normalize_export_status(value: Any) -> str:
	text = str(value or "").strip()
	if not text:
		return ""
	key = text.lower().replace("-", "_").replace(" ", "_")
	return EXPORT_STATUS_ALIASES.get(text, EXPORT_STATUS_ALIASES.get(key, key if key in EXPORT_DATASET_STATUSES else ""))


def _normalize_interval_semantics(value: Any) -> str:
	text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
	if text in INTERVAL_SEMANTICS_ALIASES:
		return INTERVAL_SEMANTICS_ALIASES[text]
	return DEFAULT_INTERVAL_SEMANTICS


def _normalize_segment_policy(value: Any) -> dict[str, Any]:
	raw = value if isinstance(value, dict) else {}
	return {
		"exclusiveMode": _normalize_bool(
			raw.get("exclusiveMode"),
			default=bool(DEFAULT_SEGMENT_POLICY["exclusiveMode"]),
		),
		"intervalSemantics": _normalize_interval_semantics(
			raw.get("intervalSemantics")
		),
	}


def _build_segment_record_with_bounds(
	record: dict[str, Any],
	start_time: float,
	end_time: float,
) -> dict[str, Any] | None:
	left_time = min(start_time, end_time)
	right_time = max(start_time, end_time)
	if right_time <= left_time:
		return None
	category_id = str(record.get("categoryId") or "segment").strip() or "segment"
	return {
		**record,
		"id": f"{category_id}:{round(left_time)}:{round(right_time)}",
		"startTime": left_time,
		"endTime": right_time,
	}


def _canonicalize_timeline_segments(
	segments: list[dict[str, Any]],
	policy: dict[str, Any],
) -> list[dict[str, Any]]:
	if not policy.get("exclusiveMode"):
		return segments
	canonical: list[dict[str, Any]] = []
	for segment in segments:
		if not isinstance(segment, dict):
			continue
		start_time = parse_numeric_value(segment.get("startTime"))
		end_time = parse_numeric_value(segment.get("endTime"))
		if start_time is None or end_time is None:
			continue
		candidate = _build_segment_record_with_bounds(segment, start_time, end_time)
		if not candidate:
			continue
		for existing in canonical:
			if existing["startTime"] < candidate["startTime"] < existing["endTime"]:
				snapped = _build_segment_record_with_bounds(
					candidate,
					existing["endTime"],
					candidate["endTime"],
				)
				candidate = snapped
				break
		if not candidate:
			continue
		trimmed_existing: list[dict[str, Any]] = []
		for existing in canonical:
			if (
				existing["endTime"] <= candidate["startTime"]
				or existing["startTime"] >= candidate["endTime"]
			):
				trimmed_existing.append(existing)
				continue
			left_remainder = _build_segment_record_with_bounds(
				existing,
				existing["startTime"],
				candidate["startTime"],
			)
			if left_remainder:
				trimmed_existing.append(left_remainder)
			right_remainder = _build_segment_record_with_bounds(
				existing,
				candidate["endTime"],
				existing["endTime"],
			)
			if right_remainder:
				trimmed_existing.append(right_remainder)
		trimmed_existing.append(candidate)
		canonical = sorted(
			trimmed_existing,
			key=lambda item: (
				float(item["startTime"]),
				float(item["endTime"]),
				str(item.get("categoryId") or ""),
				str(item.get("id") or ""),
			),
		)
	return canonical


def _build_export_segments(annotations: dict[str, Any]) -> list[dict[str, Any]]:
	segments: list[dict[str, Any]] = []
	for source_order, item in enumerate(annotations.get("segments", [])):
		if not isinstance(item, dict):
			continue
		start_ms = _normalize_time_ms(item.get("startTime"))
		end_ms = _normalize_time_ms(item.get("endTime"))
		if start_ms is None or end_ms is None:
			continue
		status = _normalize_export_status(item.get("categoryName") or item.get("categoryId"))
		if not status:
			continue
		segments.append(
			{
				"id": str(item.get("id") or "").strip(),
				"start_ms": min(start_ms, end_ms),
				"end_ms": max(start_ms, end_ms),
				"status": status,
				"source_order": int(source_order),
			}
		)
	segments.sort(
		key=lambda row: (
			row["start_ms"],
			row["end_ms"],
			int(row.get("source_order", 0)),
			row["status"],
			row["id"],
		)
	)
	return segments


def _canonicalize_export_segments(
	segments: list[dict[str, Any]],
	policy: dict[str, Any],
) -> list[dict[str, Any]]:
	if not policy.get("exclusiveMode"):
		return segments
	canonical: list[dict[str, Any]] = []
	for segment in segments:
		candidate = dict(segment)
		for existing in canonical:
			if existing["start_ms"] < candidate["start_ms"] < existing["end_ms"]:
				candidate["start_ms"] = existing["end_ms"]
				break
		if candidate["end_ms"] <= candidate["start_ms"]:
			continue
		trimmed_existing: list[dict[str, Any]] = []
		for existing in canonical:
			if (
				existing["end_ms"] <= candidate["start_ms"]
				or existing["start_ms"] >= candidate["end_ms"]
			):
				trimmed_existing.append(existing)
				continue
			if existing["start_ms"] < candidate["start_ms"]:
				trimmed_existing.append(
					{
						**existing,
						"id": f"{existing['status']}:{existing['start_ms']}:{candidate['start_ms']}",
						"end_ms": candidate["start_ms"],
					}
				)
			if existing["end_ms"] > candidate["end_ms"]:
				trimmed_existing.append(
					{
						**existing,
						"id": f"{existing['status']}:{candidate['end_ms']}:{existing['end_ms']}",
						"start_ms": candidate["end_ms"],
					}
				)
		trimmed_existing.append(candidate)
		canonical = sorted(
			trimmed_existing,
			key=lambda row: (
				int(row["start_ms"]),
				int(row["end_ms"]),
				str(row["status"]),
				str(row["id"]),
			),
		)
	return canonical


def _segment_contains_timestamp(
	segment: dict[str, Any],
	timestamp_ms: int,
	interval_semantics: str,
) -> bool:
	start_ms = int(segment["start_ms"])
	end_ms = int(segment["end_ms"])
	if start_ms == end_ms:
		return timestamp_ms == end_ms
	if interval_semantics == "left_open_right_closed":
		return start_ms < timestamp_ms <= end_ms
	return start_ms <= timestamp_ms <= end_ms


def _segment_overlaps_interval_positive_measure(
	segment: dict[str, Any],
	pie_lo: int,
	pie_hi: int,
) -> bool:
	s_lo, s_hi = int(segment["start_ms"]), int(segment["end_ms"])
	s_left, s_right = min(s_lo, s_hi), max(s_lo, s_hi)
	left, right = min(int(pie_lo), int(pie_hi)), max(int(pie_lo), int(pie_hi))
	if s_left == s_right:
		return left <= s_left <= right
	if left == right:
		return s_left <= left <= s_right
	return max(s_left, left) < min(s_right, right)


def _resolve_segment_status(
	segments: list[dict[str, Any]],
	timestamp_ms: int,
	fallback: str,
	interval_semantics: str,
) -> str:
	best_order = -1
	best_status: str | None = None
	for segment in segments:
		if not _segment_contains_timestamp(segment, timestamp_ms, interval_semantics):
			continue
		order = int(segment.get("source_order", -1))
		if order >= best_order:
			best_order = order
			best_status = str(segment["status"])
	if best_status is not None:
		return best_status
	return _normalize_export_status(fallback)


def _resolve_interval_status(
	segments: list[dict[str, Any]],
	start_ms: int,
	end_ms: int,
	fallback: str,
	interval_semantics: str,
) -> str:
	left, right = min(int(start_ms), int(end_ms)), max(int(start_ms), int(end_ms))
	if left == right:
		return _resolve_segment_status(segments, left, fallback, interval_semantics)
	best_order = -1
	best_status: str | None = None
	for segment in segments:
		if not _segment_overlaps_interval_positive_measure(segment, left, right):
			continue
		order = int(segment.get("source_order", -1))
		if order >= best_order:
			best_order = order
			best_status = str(segment["status"])
	if best_status is not None:
		return best_status
	probe_ms = end_ms if interval_semantics == "left_open_right_closed" else (start_ms + end_ms) // 2
	return _resolve_segment_status(segments, int(probe_ms), fallback, interval_semantics)


def _split_signal_interval(
	start_ms: int,
	end_ms: int,
	segments: list[dict[str, Any]],
) -> list[tuple[int, int]]:
	left_ms = min(start_ms, end_ms)
	right_ms = max(start_ms, end_ms)
	if left_ms == right_ms:
		return [(left_ms, right_ms)]
	boundaries = sorted(
		{
			int(boundary_ms)
			for segment in segments
			for boundary_ms in (
				int(segment["start_ms"]),
				int(segment["end_ms"]),
			)
			if left_ms < int(boundary_ms) < right_ms
		}
	)
	if not boundaries:
		return [(left_ms, right_ms)]
	points = [left_ms, *boundaries, right_ms]
	return [
		(points[index - 1], points[index])
		for index in range(1, len(points))
	]


def _merge_signal_export_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	merged: list[dict[str, Any]] = []
	for row in rows:
		if not merged:
			merged.append(dict(row))
			continue
		previous = merged[-1]
		if (
			previous.get("uid") == row.get("uid")
			and previous.get("cid") == row.get("cid")
			and previous.get("longitude") == row.get("longitude")
			and previous.get("latitude") == row.get("latitude")
			and previous.get("status") == row.get("status")
			and int(previous.get("t_out") or 0) == int(row.get("t_in") or 0)
		):
			previous["t_out"] = row["t_out"]
			continue
		merged.append(dict(row))
	return merged


def _normalize_export_timestamp_unit(value: Any) -> str:
	text = str(value or "").strip().lower().replace("-", "_")
	if text in ("s", "sec", "second", "seconds"):
		return "seconds"
	return "milliseconds"


def _format_export_epoch_value(ms: int, unit: str) -> int:
	if unit == "seconds":
		return int(round(float(ms) / 1000.0))
	return int(ms)


def _labeled_segments_span_ms(segments: list[dict[str, Any]]) -> tuple[int, int] | None:
	if not segments:
		return None
	return (
		min(int(s["start_ms"]) for s in segments),
		max(int(s["end_ms"]) for s in segments),
	)


def _filter_export_gps_rows_to_span(
	rows: list[dict[str, Any]],
	span: tuple[int, int],
) -> list[dict[str, Any]]:
	lo, hi = span
	return [row for row in rows if lo <= int(row["timestamp"]) <= hi]


def _resolve_export_annotations(
	paths: ReviewPaths,
	uid: str,
	reviewer_id: str,
) -> dict[str, Any]:
	reviewer_annotations = read_timeline_annotations(paths, uid, reviewer_id=reviewer_id)
	reviewer_segments = _build_export_segments(reviewer_annotations)
	if reviewer_segments:
		policy = _normalize_segment_policy(reviewer_annotations.get("segmentPolicy"))
		return {
			"annotations": reviewer_annotations,
			"annotation_source": "reviewer",
			"segment_policy": policy,
			"segments": _canonicalize_export_segments(reviewer_segments, policy),
		}

	legacy_annotations = _read_legacy_timeline_annotations(paths, uid)
	legacy_segments = _build_export_segments(legacy_annotations)
	if legacy_segments:
		policy = _normalize_segment_policy(legacy_annotations.get("segmentPolicy"))
		return {
			"annotations": legacy_annotations,
			"annotation_source": "legacy",
			"segment_policy": policy,
			"segments": _canonicalize_export_segments(legacy_segments, policy),
		}

	return {
		"annotations": reviewer_annotations,
		"annotation_source": "none",
		"segment_policy": _normalize_segment_policy(
			reviewer_annotations.get("segmentPolicy")
		),
		"segments": [],
	}


def _interpolate_segment_points(points: list[tuple[float, float]], ratio: float) -> tuple[float, float]:
	if not points:
		return 0.0, 0.0
	if len(points) == 1:
		return points[0]
	ratio = max(0.0, min(1.0, ratio))
	distances = [0.0]
	for idx in range(1, len(points)):
		prev_lat, prev_lon = points[idx - 1]
		lat, lon = points[idx]
		step = math.hypot(lat - prev_lat, lon - prev_lon)
		distances.append(distances[-1] + step)
	total = distances[-1]
	if total <= 0:
		return points[0]
	target = total * ratio
	for idx in range(1, len(points)):
		if distances[idx] < target:
			continue
		left_d = distances[idx - 1]
		right_d = distances[idx]
		if right_d <= left_d:
			return points[idx]
		local = (target - left_d) / (right_d - left_d)
		left_lat, left_lon = points[idx - 1]
		right_lat, right_lon = points[idx]
		return (
			left_lat + (right_lat - left_lat) * local,
			left_lon + (right_lon - left_lon) * local,
		)
	return points[-1]


def _normalize_float_value(value: Any) -> float | None:
	text = str(value or "").strip()
	if not text:
		return None
	try:
		number = float(text)
	except (TypeError, ValueError):
		return None
	return number if number == number else None


def _first_present_row_value(row: dict[str, Any], *keys: str) -> str:
	for key in keys:
		value = row.get(key)
		if value is None:
			continue
		text = str(value).strip()
		if text:
			return text
	return ""


def _normalize_row_coordinate(row: dict[str, Any]) -> tuple[float, float] | None:
	latitude = _normalize_float_value(
		_first_present_row_value(row, "latitude", "lat")
	)
	longitude = _normalize_float_value(
		_first_present_row_value(row, "longitude", "lon")
	)
	if latitude is None or longitude is None:
		return None
	return (float(latitude), float(longitude))


def _round_half_up(value: float) -> int:
	if value >= 0:
		return int(math.floor(value + 0.5))
	return int(math.ceil(value - 0.5))


def _get_track_edit_row_midpoint_ms(row: dict[str, Any]) -> int | None:
	start_ms = _normalize_time_ms(
		_first_present_row_value(row, "t_in", "start_time", "timestamp_ms", "timestamp")
	)
	end_ms = _normalize_time_ms(
		_first_present_row_value(row, "t_out", "end_time", "timestamp_ms", "timestamp")
	)
	if start_ms is None and end_ms is None:
		return None
	if start_ms is None:
		return int(end_ms)
	if end_ms is None:
		return int(start_ms)
	return _round_half_up((int(start_ms) + int(end_ms)) / 2.0)


def _build_track_edit_point_id(
	uid: str,
	layer_key: str,
	row_index: int,
	timestamp_ms: int | None = None,
) -> str:
	normalized_uid = str(uid or "").strip() or "__none__"
	normalized_layer = str(layer_key or "").strip() or "layer"
	normalized_row_index = max(0, int(row_index))
	normalized_timestamp = "na" if timestamp_ms is None else str(int(timestamp_ms))
	return f"{normalized_layer}:{normalized_uid}:{normalized_timestamp}:{normalized_row_index}"


def _merge_track_edit_patch(
	existing_patch: dict[str, Any] | None,
	incoming_patch: dict[str, Any] | None,
) -> dict[str, Any] | None:
	if not existing_patch:
		return dict(incoming_patch or {}) or None
	if not incoming_patch:
		return dict(existing_patch)
	merged = {
		**existing_patch,
		**incoming_patch,
	}
	if incoming_patch.get("position") is not None:
		merged["position"] = dict(incoming_patch["position"])
	elif existing_patch.get("position") is not None:
		merged["position"] = dict(existing_patch["position"])
	merged["metadata"] = {
		**dict(existing_patch.get("metadata") or {}),
		**dict(incoming_patch.get("metadata") or {}),
	}
	return merged


def _build_track_edit_patch_maps(
	track_edits: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
	patches_by_point_id: dict[str, dict[str, Any]] = {}
	patches_by_layer_row: dict[tuple[str, int], dict[str, Any]] = {}
	for item in (track_edits or {}).get("patches", []):
		patch = _normalize_track_edit_patch(item)
		if not patch:
			continue
		point_id = str(patch.get("pointId") or "").strip()
		layer_key = str(patch.get("layerKey") or "").strip()
		row_index = max(0, int(patch.get("rowIndex") or 0))
		if point_id:
			patches_by_point_id[point_id] = _merge_track_edit_patch(
				patches_by_point_id.get(point_id),
				patch,
			) or dict(patch)
		if layer_key:
			layer_row_key = (layer_key, row_index)
			patches_by_layer_row[layer_row_key] = _merge_track_edit_patch(
				patches_by_layer_row.get(layer_row_key),
				patch,
			) or dict(patch)
	return patches_by_point_id, patches_by_layer_row


def _apply_track_edit_patch_to_row(
	row: dict[str, Any],
	patch: dict[str, Any] | None,
) -> dict[str, Any]:
	if not patch:
		return dict(row)
	next_row = dict(row)
	position = patch.get("position")
	if isinstance(position, dict):
		latitude = _normalize_float_value(position.get("latitude"))
		longitude = _normalize_float_value(position.get("longitude"))
		if latitude is not None:
			lat_keys = [key for key in ("latitude", "start_latitude", "lat") if row.get(key) is not None]
			if not lat_keys:
				lat_keys = ["latitude"]
			for key in lat_keys:
				next_row[key] = float(latitude)
		if longitude is not None:
			lon_keys = [key for key in ("longitude", "start_longitude", "lng", "lon") if row.get(key) is not None]
			if not lon_keys:
				lon_keys = ["longitude"]
			for key in lon_keys:
				next_row[key] = float(longitude)
	for key, value in dict(patch.get("metadata") or {}).items():
		text_key = str(key or "").strip()
		if not text_key or value is None:
			continue
		next_row[text_key] = value
	return next_row


def _apply_track_edits_to_rows(
	uid: str,
	layer_key: str,
	rows: list[dict[str, str]],
	track_edits: dict[str, Any] | None,
) -> list[dict[str, Any]]:
	if not rows:
		return []
	patches_by_point_id, patches_by_layer_row = _build_track_edit_patch_maps(track_edits)
	if not patches_by_point_id and not patches_by_layer_row:
		return [dict(row) for row in rows]
	normalized_layer_key = str(layer_key or "").strip()
	patched_rows: list[dict[str, Any]] = []
	for row_index, row in enumerate(rows):
		row_copy = dict(row)
		point_id = _build_track_edit_point_id(
			uid,
			normalized_layer_key,
			row_index,
			_get_track_edit_row_midpoint_ms(row_copy),
		)
		patch = patches_by_point_id.get(point_id) or patches_by_layer_row.get((normalized_layer_key, row_index))
		patched_rows.append(_apply_track_edit_patch_to_row(row_copy, patch))
	return patched_rows


def _build_grouped_export_source_rows(
	rows: list[dict[str, str]],
) -> list[list[dict[str, str]]]:
	grouped: dict[tuple[str, int | None, int | None, str], list[dict[str, str]]] = {}
	for row_index, row in enumerate(rows):
		segment_start_ms = _normalize_time_ms(
			_first_present_row_value(row, "segment_start_time", "start_time")
		)
		segment_end_ms = _normalize_time_ms(
			_first_present_row_value(row, "segment_end_time", "end_time")
		)
		segment_key = _first_present_row_value(row, "segment_idx", "od_segment_idx")
		if not segment_key:
			segment_key = f"row-{row_index}"
		status_key = _first_present_row_value(row, "match_type", "status")
		grouped.setdefault(
			(segment_key, segment_start_ms, segment_end_ms, status_key),
			[],
		).append(row)
	return sorted(
		grouped.values(),
		key=lambda group_rows: (
			_normalize_time_ms(
				_first_present_row_value(
					group_rows[0],
					"segment_start_time",
					"start_time",
				)
			) or 0,
			_normalize_time_ms(
				_first_present_row_value(
					group_rows[0],
					"segment_end_time",
					"end_time",
				)
			) or 0,
			_first_present_row_value(group_rows[0], "segment_idx", "od_segment_idx"),
			_first_present_row_value(group_rows[0], "match_type", "status"),
		),
	)


def _build_export_source_status_segments(
	rows: list[dict[str, str]],
	*,
	prefix: str,
	source_order: int,
) -> list[dict[str, Any]]:
	segments: list[dict[str, Any]] = []
	for group_rows in _build_grouped_export_source_rows(rows):
		status = _normalize_export_status(
			_first_present_row_value(group_rows[0], "match_type", "status")
		)
		if not status:
			continue
		anchor_times = [
			time_ms
			for time_ms in (
				_normalize_time_ms(
					_first_present_row_value(row, "t_in", "timestamp_ms", "timestamp")
				)
				for row in group_rows
			)
			if time_ms is not None
		]
		start_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_start_time", "start_time")
		)
		end_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_end_time", "end_time")
		)
		if start_ms is None and anchor_times:
			start_ms = min(anchor_times)
		if end_ms is None and anchor_times:
			end_ms = max(anchor_times)
		if start_ms is None or end_ms is None:
			continue
		left_ms, right_ms = min(int(start_ms), int(end_ms)), max(int(start_ms), int(end_ms))
		segment_key = _first_present_row_value(group_rows[0], "segment_idx", "od_segment_idx") or "0"
		segments.append(
			{
				"id": f"{prefix}:{segment_key}:{left_ms}:{right_ms}",
				"start_ms": left_ms,
				"end_ms": right_ms,
				"status": status,
				"source_order": source_order,
			}
		)
	return sorted(
		segments,
		key=lambda row: (
			int(row["start_ms"]),
			int(row["end_ms"]),
			-int(row.get("source_order", 0)),
			str(row["status"]),
			str(row["id"]),
		),
	)


def _build_line_fallback_segments(uid_dir: Path) -> list[dict[str, Any]]:
	return _build_export_source_status_segments(
		_read_csv_rows(uid_dir / "line.csv"),
		prefix="line-fallback",
		source_order=-1,
	)


def _build_fmm_fallback_segments(uid_dir: Path) -> list[dict[str, Any]]:
	return _build_export_source_status_segments(
		_read_csv_rows(uid_dir / "fmm.csv"),
		prefix="fmm-fallback",
		source_order=0,
	)


def _build_interval_coordinate_rows_from_rows(
	rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	intervals: list[dict[str, Any]] = []
	for row in rows:
		coordinate = _normalize_row_coordinate(row)
		start_ms = _normalize_time_ms(
			_first_present_row_value(row, "t_in", "start_time", "timestamp_ms", "timestamp")
		)
		end_ms = _normalize_time_ms(
			_first_present_row_value(row, "t_out", "end_time", "timestamp_ms", "timestamp")
		)
		if coordinate is None or start_ms is None:
			continue
		if end_ms is None:
			end_ms = start_ms
		left_ms, right_ms = min(int(start_ms), int(end_ms)), max(int(start_ms), int(end_ms))
		intervals.append(
			{
				"start_ms": left_ms,
				"end_ms": right_ms,
				"latitude": coordinate[0],
				"longitude": coordinate[1],
			}
		)
	return sorted(
		intervals,
		key=lambda row: (
			int(row["start_ms"]),
			int(row["end_ms"]),
			float(row["latitude"]),
			float(row["longitude"]),
		),
	)


def _build_interval_coordinate_rows(path: Path) -> list[dict[str, Any]]:
	return _build_interval_coordinate_rows_from_rows(_read_csv_rows(path))


def _build_fmm_anchor_segments_from_rows(
	rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	segments: list[dict[str, Any]] = []
	for group_rows in _build_grouped_export_source_rows(rows):
		anchors: list[dict[str, float | int]] = []
		for row in sorted(
			group_rows,
			key=lambda item: (
				_normalize_time_ms(
					_first_present_row_value(item, "t_in", "timestamp_ms", "timestamp")
				) or 0,
				_normalize_float_value(_first_present_row_value(item, "point_order")) or 0.0,
			),
		):
			coordinate = _normalize_row_coordinate(row)
			timestamp_ms = _normalize_time_ms(
				_first_present_row_value(row, "t_in", "timestamp_ms", "timestamp")
			)
			if coordinate is None or timestamp_ms is None:
				continue
			anchors.append(
				{
					"timestamp_ms": int(timestamp_ms),
					"latitude": float(coordinate[0]),
					"longitude": float(coordinate[1]),
				}
			)
		if not anchors:
			continue
		start_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_start_time", "start_time")
		)
		end_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_end_time", "end_time")
		)
		if start_ms is None:
			start_ms = int(anchors[0]["timestamp_ms"])
		if end_ms is None:
			end_ms = int(anchors[-1]["timestamp_ms"])
		segments.append(
			{
				"start_ms": min(int(start_ms), int(end_ms)),
				"end_ms": max(int(start_ms), int(end_ms)),
				"anchors": anchors,
			}
		)
	return sorted(
		segments,
		key=lambda row: (
			int(row["start_ms"]),
			int(row["end_ms"]),
			len(list(row.get("anchors") or [])),
		),
	)


def _build_fmm_anchor_segments(uid_dir: Path) -> list[dict[str, Any]]:
	return _build_fmm_anchor_segments_from_rows(_read_csv_rows(uid_dir / "fmm.csv"))


def _build_line_anchor_segments_from_rows(
	rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	segments: list[dict[str, Any]] = []
	for group_rows in _build_grouped_export_source_rows(rows):
		start_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_start_time", "start_time")
		)
		end_ms = _normalize_time_ms(
			_first_present_row_value(group_rows[0], "segment_end_time", "end_time")
		)
		if start_ms is None or end_ms is None:
			continue
		points = [
			coordinate
			for coordinate in (
				_normalize_row_coordinate(row)
				for row in sorted(
					group_rows,
					key=lambda item: _normalize_float_value(
						_first_present_row_value(item, "point_order")
					) or 0.0,
				)
			)
			if coordinate is not None
		]
		if not points:
			continue
		segments.append(
			{
				"start_ms": min(int(start_ms), int(end_ms)),
				"end_ms": max(int(start_ms), int(end_ms)),
				"points": points,
			}
		)
	return sorted(
		segments,
		key=lambda row: (
			int(row["start_ms"]),
			int(row["end_ms"]),
			len(list(row.get("points") or [])),
		),
	)


def _build_line_anchor_segments(uid_dir: Path) -> list[dict[str, Any]]:
	return _build_line_anchor_segments_from_rows(_read_csv_rows(uid_dir / "line.csv"))


def _merge_export_time_intervals(
	intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
	normalized = sorted(
		[
			(min(int(start_ms), int(end_ms)), max(int(start_ms), int(end_ms)))
			for start_ms, end_ms in intervals
		],
		key=lambda item: (item[0], item[1]),
	)
	merged: list[list[int]] = []
	for start_ms, end_ms in normalized:
		if not merged or start_ms > merged[-1][1]:
			merged.append([start_ms, end_ms])
			continue
		merged[-1][1] = max(merged[-1][1], end_ms)
	return [(item[0], item[1]) for item in merged]


def _build_export_signal_rows(
	uid: str,
	uid_dir: Path,
	segments: list[dict[str, Any]],
	interval_semantics: str,
	clip_span: tuple[int, int] | None = None,
	track_edits: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	line_rows = _apply_track_edits_to_rows(
		uid,
		"line",
		_read_csv_rows(uid_dir / "line.csv"),
		track_edits,
	)
	line_fallback_segments = _build_export_source_status_segments(
		line_rows,
		prefix="line-fallback",
		source_order=-1,
	)

	def export_row_pieces(
		row: dict[str, str],
		fallback_status: str = "",
	) -> list[dict[str, Any]]:
		t_in_ms = _normalize_time_ms(row.get("t_in"))
		t_out_ms = _normalize_time_ms(row.get("t_out"))
		if t_in_ms is None or t_out_ms is None:
			return []
		if clip_span is not None:
			span_lo, span_hi = clip_span
			row_lo, row_hi = min(t_in_ms, t_out_ms), max(t_in_ms, t_out_ms)
			clip_lo = max(row_lo, min(span_lo, span_hi))
			clip_hi = min(row_hi, max(span_lo, span_hi))
			if clip_lo > clip_hi:
				return []
			t_in_ms = clip_lo
			t_out_ms = clip_hi
		pieces = _split_signal_interval(t_in_ms, t_out_ms, segments)
		export_rows: list[dict[str, Any]] = []
		for piece_start_ms, piece_end_ms in pieces:
			piece_fallback_status = _normalize_export_status(fallback_status)
			if not piece_fallback_status and line_fallback_segments:
				piece_fallback_status = _resolve_interval_status(
					line_fallback_segments,
					piece_start_ms,
					piece_end_ms,
					"",
					interval_semantics,
				)
			status = _resolve_interval_status(
				segments,
				piece_start_ms,
				piece_end_ms,
				piece_fallback_status,
				interval_semantics,
			)
			if not status:
				continue
			export_rows.append(
				{
					"uid": uid,
					"cid": str(row.get("CID") or row.get("cid") or "").strip(),
					"longitude": float(row.get("longitude") or row.get("lon") or 0),
					"latitude": float(row.get("latitude") or row.get("lat") or 0),
					"t_in": piece_start_ms,
					"t_out": piece_end_ms,
					"status": status,
				}
			)
		return export_rows

	raw_rows = _apply_track_edits_to_rows(
		uid,
		"raw",
		_read_csv_rows(uid_dir / "raw.csv"),
		track_edits,
	)
	if raw_rows:
		export_rows: list[dict[str, Any]] = []
		for row in raw_rows:
			export_rows.extend(export_row_pieces(row))
		return _merge_signal_export_rows(export_rows)
	signal_rows = _apply_track_edits_to_rows(
		uid,
		"signal",
		_read_csv_rows(uid_dir / "signal.csv"),
		track_edits,
	)
	export_rows: list[dict[str, Any]] = []
	for row in signal_rows:
		export_rows.extend(
			export_row_pieces(
				row,
				fallback_status=str(row.get("status") or row.get("match_type") or ""),
			)
		)
	return _merge_signal_export_rows(export_rows)


def _build_export_gps_rows(
	uid: str,
	uid_dir: Path,
	segments: list[dict[str, Any]],
	interval_semantics: str,
	interval_seconds: int,
	track_edits: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	raw_rows = _apply_track_edits_to_rows(
		uid,
		"raw",
		_read_csv_rows(uid_dir / "raw.csv"),
		track_edits,
	)
	snap_rows = _apply_track_edits_to_rows(
		uid,
		"snap",
		_read_csv_rows(uid_dir / "snap.csv"),
		track_edits,
	)
	fmm_rows = _apply_track_edits_to_rows(
		uid,
		"fmm",
		_read_csv_rows(uid_dir / "fmm.csv"),
		track_edits,
	)
	line_rows = _apply_track_edits_to_rows(
		uid,
		"line",
		_read_csv_rows(uid_dir / "line.csv"),
		track_edits,
	)
	legacy_gps_rows = _apply_track_edits_to_rows(
		uid,
		"gps",
		_read_csv_rows(uid_dir / "gps.csv"),
		track_edits,
	)
	fmm_segments = _build_fmm_anchor_segments_from_rows(fmm_rows)
	line_segments = _build_line_anchor_segments_from_rows(line_rows)
	snap_intervals = _build_interval_coordinate_rows_from_rows(snap_rows)
	raw_intervals = _build_interval_coordinate_rows_from_rows(raw_rows)
	fallback_status_segments = [
		*_build_export_source_status_segments(
			fmm_rows,
			prefix="fmm-fallback",
			source_order=0,
		),
		*_build_export_source_status_segments(
			line_rows,
			prefix="line-fallback",
			source_order=-1,
		),
	]

	def build_legacy_gps_rows() -> list[dict[str, Any]]:
		export_rows: list[dict[str, Any]] = []
		for row in legacy_gps_rows:
			timestamp_ms = _normalize_time_ms(
				_first_present_row_value(row, "timestamp_ms", "timestamp")
			)
			coordinate = _normalize_row_coordinate(row)
			if timestamp_ms is None or coordinate is None:
				continue
			status = _resolve_segment_status(
				segments,
				int(timestamp_ms),
				_first_present_row_value(row, "status"),
				interval_semantics,
			)
			if not status:
				continue
			export_rows.append(
				{
					"uid": uid,
					"longitude": float(coordinate[1]),
					"latitude": float(coordinate[0]),
					"timestamp": int(timestamp_ms),
					"status": status,
				}
			)
		return sorted(export_rows, key=lambda row: row["timestamp"])

	coverage_intervals = _merge_export_time_intervals(
		[
			*((
				int(row["start_ms"]),
				int(row["end_ms"]),
			) for row in raw_intervals),
			*((
				int(row["start_ms"]),
				int(row["end_ms"]),
			) for row in snap_intervals),
			*((
				int(row["start_ms"]),
				int(row["end_ms"]),
			) for row in fmm_segments),
			*((
				int(row["start_ms"]),
				int(row["end_ms"]),
			) for row in line_segments),
		]
	)
	if not coverage_intervals:
		return build_legacy_gps_rows()

	def resolve_interval_coordinate(
		interval_rows: list[dict[str, Any]],
		timestamp_ms: int,
		state: list[int],
	) -> tuple[float, float] | None:
		if not interval_rows:
			return None
		index = min(max(state[0], 0), len(interval_rows) - 1)
		while index < len(interval_rows) and int(interval_rows[index]["end_ms"]) < timestamp_ms:
			index += 1
		state[0] = index
		if index >= len(interval_rows):
			return None
		row = interval_rows[index]
		if int(row["start_ms"]) <= timestamp_ms <= int(row["end_ms"]):
			return (float(row["latitude"]), float(row["longitude"]))
		return None

	def resolve_fmm_coordinate(
		timestamp_ms: int,
		state: list[int],
	) -> tuple[float, float] | None:
		if not fmm_segments:
			return None
		index = min(max(state[0], 0), len(fmm_segments) - 1)
		while index < len(fmm_segments) and int(fmm_segments[index]["end_ms"]) < timestamp_ms:
			index += 1
		state[0] = index
		if index >= len(fmm_segments):
			return None
		segment = fmm_segments[index]
		if int(segment["start_ms"]) > timestamp_ms or int(segment["end_ms"]) < timestamp_ms:
			return None
		anchors = list(segment.get("anchors") or [])
		if not anchors:
			return None
		if len(anchors) == 1:
			return (float(anchors[0]["latitude"]), float(anchors[0]["longitude"]))
		if timestamp_ms <= int(anchors[0]["timestamp_ms"]):
			return (float(anchors[0]["latitude"]), float(anchors[0]["longitude"]))
		for anchor_index in range(1, len(anchors)):
			right = anchors[anchor_index]
			right_ms = int(right["timestamp_ms"])
			if right_ms < timestamp_ms:
				continue
			left = anchors[anchor_index - 1]
			left_ms = int(left["timestamp_ms"])
			if right_ms <= left_ms:
				return (float(right["latitude"]), float(right["longitude"]))
			ratio = (timestamp_ms - left_ms) / max(1, right_ms - left_ms)
			return (
				float(left["latitude"]) + (float(right["latitude"]) - float(left["latitude"])) * ratio,
				float(left["longitude"]) + (float(right["longitude"]) - float(left["longitude"])) * ratio,
			)
		last = anchors[-1]
		return (float(last["latitude"]), float(last["longitude"]))

	def resolve_line_coordinate(
		timestamp_ms: int,
		state: list[int],
	) -> tuple[float, float] | None:
		if not line_segments:
			return None
		index = min(max(state[0], 0), len(line_segments) - 1)
		while index < len(line_segments) and int(line_segments[index]["end_ms"]) < timestamp_ms:
			index += 1
		state[0] = index
		if index >= len(line_segments):
			return None
		segment = line_segments[index]
		start_ms = int(segment["start_ms"])
		end_ms = int(segment["end_ms"])
		if start_ms > timestamp_ms or end_ms < timestamp_ms:
			return None
		points = list(segment.get("points") or [])
		if not points:
			return None
		ratio = 0.0 if end_ms <= start_ms else (timestamp_ms - start_ms) / max(1, end_ms - start_ms)
		return _interpolate_segment_points(points, ratio)

	def resolve_export_status(timestamp_ms: int) -> str:
		return _resolve_segment_status(
			segments,
			timestamp_ms,
			_resolve_segment_status(
				fallback_status_segments,
				timestamp_ms,
				"",
				interval_semantics,
			),
			interval_semantics,
		)

	fmm_state = [0]
	line_state = [0]
	snap_state = [0]
	raw_state = [0]
	step_ms = max(5, int(interval_seconds)) * 1000
	export_rows: list[dict[str, Any]] = []
	seen_timestamps: set[int] = set()
	for start_ms, end_ms in coverage_intervals:
		timestamps = list(range(int(start_ms), int(end_ms) + 1, step_ms))
		if not timestamps or timestamps[-1] != int(end_ms):
			timestamps.append(int(end_ms))
		for timestamp_ms in timestamps:
			if timestamp_ms in seen_timestamps:
				continue
			seen_timestamps.add(timestamp_ms)
			status = resolve_export_status(int(timestamp_ms))
			if not status:
				continue
			if status == "stay":
				coordinate = (
					resolve_interval_coordinate(snap_intervals, int(timestamp_ms), snap_state)
					or resolve_interval_coordinate(raw_intervals, int(timestamp_ms), raw_state)
					or resolve_fmm_coordinate(int(timestamp_ms), fmm_state)
					or resolve_line_coordinate(int(timestamp_ms), line_state)
				)
			else:
				coordinate = (
					resolve_fmm_coordinate(int(timestamp_ms), fmm_state)
					or resolve_interval_coordinate(snap_intervals, int(timestamp_ms), snap_state)
					or resolve_interval_coordinate(raw_intervals, int(timestamp_ms), raw_state)
					or resolve_line_coordinate(int(timestamp_ms), line_state)
				)
			if coordinate is None:
				continue
			export_rows.append(
				{
					"uid": uid,
					"longitude": float(coordinate[1]),
					"latitude": float(coordinate[0]),
					"timestamp": int(timestamp_ms),
					"status": status,
				}
			)
	return sorted(export_rows, key=lambda row: row["timestamp"])


def normalize_uid(uid: Any) -> str:
	value = str(uid or "").strip()
	if not value:
		raise ValueError("uid is required")
	return value


def parse_numeric_value(value: Any) -> float | None:
	if value is None or value == "":
		return None
	try:
		parsed = float(value)
	except (TypeError, ValueError):
		return None
	return parsed if parsed == parsed else None


def _normalize_timeline_epoch_seconds(value: Any) -> float | None:
	parsed = parse_numeric_value(value)
	if parsed is None:
		return None
	return parsed / 1000.0 if abs(parsed) >= 1e12 else parsed


def normalize_reviewer_name(value: Any) -> str:
	name = str(value or "").strip()
	if not name:
		raise ValueError("reviewer display_name is required")
	return name


def _slugify_ascii(text: str) -> str:
	value = re.sub(r"\s+", "-", text.strip().lower())
	value = re.sub(r"[^a-z0-9_-]+", "-", value)
	value = re.sub(r"-{2,}", "-", value).strip("-_")
	if value and not re.match(r"^[a-z0-9]", value):
		value = f"r-{value}"
	return value


def _canonicalize_explicit_reviewer_id(value: Any) -> str:
	explicit = str(value or "").strip().lower()
	if not explicit:
		return ""
	canonical = re.sub(r"[_-]+", "-", explicit).strip("-")
	if canonical and not re.match(r"^[a-z0-9]", canonical):
		canonical = f"r-{canonical}"
	return canonical


def _reviewer_id_aliases(reviewer_id: str) -> list[str]:
	base = _canonicalize_explicit_reviewer_id(reviewer_id) or str(reviewer_id or "").strip().lower()
	candidates = [base]
	underscore_variant = base.replace("-", "_")
	if underscore_variant and underscore_variant not in candidates:
		candidates.append(underscore_variant)
	hyphen_variant = base.replace("_", "-")
	if hyphen_variant and hyphen_variant not in candidates:
		candidates.append(hyphen_variant)
	return [candidate for candidate in candidates if candidate]


def normalize_reviewer_id(display_name: Any, explicit_reviewer_id: Any | None = None) -> str:
	explicit = _canonicalize_explicit_reviewer_id(explicit_reviewer_id)
	if explicit:
		if not REVIEWER_ID_RE.fullmatch(explicit):
			raise ValueError(
				"reviewer_id must match ^[a-z0-9][a-z0-9_-]{0,63}$"
			)
		return explicit

	name = normalize_reviewer_name(display_name)
	slug = _slugify_ascii(name)
	if slug and REVIEWER_ID_RE.fullmatch(slug):
		return slug
	digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
	return f"reviewer-{digest}"


def get_system_dir(paths: ReviewPaths) -> Path:
	return paths.review_root / DEFAULT_SYSTEM_DIR


def get_reviewer_registry_path(paths: ReviewPaths) -> Path:
	return get_system_dir(paths) / DEFAULT_REVIEWER_REGISTRY_NAME


def get_schema_version_path(paths: ReviewPaths) -> Path:
	return get_system_dir(paths) / DEFAULT_SCHEMA_VERSION_NAME


def get_reviewers_dir(paths: ReviewPaths) -> Path:
	return paths.review_root / DEFAULT_REVIEWERS_DIR


def get_aggregate_dir(paths: ReviewPaths) -> Path:
	return paths.review_root / DEFAULT_AGGREGATE_DIR


def get_aggregate_by_uid_dir(paths: ReviewPaths) -> Path:
	return get_aggregate_dir(paths) / DEFAULT_AGGREGATE_BY_UID_DIR


def get_aggregate_uid_path(paths: ReviewPaths, uid: str) -> Path:
	return get_aggregate_by_uid_dir(paths) / f"{normalize_uid(uid)}.json"


def get_aggregate_stats_path(paths: ReviewPaths) -> Path:
	return get_aggregate_dir(paths) / DEFAULT_AGGREGATE_STATS_NAME


def get_legacy_timeline_annotations_dir(paths: ReviewPaths) -> Path:
	return paths.review_root / DEFAULT_TIMELINE_ANNOTATIONS_DIR


def get_legacy_timeline_annotation_path(paths: ReviewPaths, uid: str) -> Path:
	return get_legacy_timeline_annotations_dir(paths) / f"{normalize_uid(uid)}.json"


def get_legacy_timeline_annotation_ledger_path(paths: ReviewPaths) -> Path:
	return get_legacy_timeline_annotations_dir(paths) / DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME


def resolve_reviewer_paths(
	paths: ReviewPaths,
	reviewer_id: str,
	reviewer_name: str = "",
) -> ReviewerPaths:
	normalized_id = normalize_reviewer_id(reviewer_name or reviewer_id, reviewer_id)
	root = get_reviewers_dir(paths) / normalized_id
	reviews_root = root / "reviews"
	timeline_root = root / DEFAULT_TIMELINE_ANNOTATIONS_DIR
	track_edits_root = root / DEFAULT_TRACK_EDITS_DIR
	return ReviewerPaths(
		reviewer_id=normalized_id,
		reviewer_name=reviewer_name or normalized_id,
		reviewer_root=root,
		profile_path=root / "profile.json",
		reviews_root=reviews_root,
		ledger_path=reviews_root / DEFAULT_LEDGER_NAME,
		latest_path=reviews_root / DEFAULT_LATEST_NAME,
		timeline_root=timeline_root,
		timeline_ledger_path=timeline_root / DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME,
		track_edits_root=track_edits_root,
		track_edits_ledger_path=track_edits_root / DEFAULT_TRACK_EDITS_LEDGER_NAME,
		export_root=paths.export_root / DEFAULT_REVIEWER_EXPORTS_DIR / normalized_id,
	)


def _ensure_schema_version(paths: ReviewPaths) -> None:
	with _get_lock(get_system_dir(paths)):
		get_system_dir(paths).mkdir(parents=True, exist_ok=True)
		_write_json(
			get_schema_version_path(paths),
			{
				"schema_version": SCHEMA_VERSION,
				"updated_at": utc_now_iso(),
			},
		)


def _read_reviewer_registry(paths: ReviewPaths) -> dict[str, Any]:
	path = get_reviewer_registry_path(paths)
	if path.exists():
		payload = _read_json(path)
		reviewers = payload.get("reviewers")
		if isinstance(reviewers, list):
			return payload
	return {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"count": 0,
		"reviewers": [],
	}


def _write_reviewer_registry(paths: ReviewPaths, reviewers: list[dict[str, Any]]) -> dict[str, Any]:
	ordered = sorted(reviewers, key=lambda item: str(item.get("reviewer_id") or ""))
	payload = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"count": len(ordered),
		"reviewers": ordered,
	}
	_write_json(get_reviewer_registry_path(paths), payload)
	return payload


def _normalize_registry_profile(raw: dict[str, Any]) -> dict[str, Any]:
	reviewer_name = normalize_reviewer_name(
		raw.get("reviewer_name") or raw.get("display_name") or raw.get("reviewer") or raw.get("reviewer_id")
	)
	reviewer_id = normalize_reviewer_id(reviewer_name, raw.get("reviewer_id"))
	created_at = str(raw.get("created_at") or "").strip() or utc_now_iso()
	last_seen_at = str(raw.get("last_seen_at") or "").strip() or created_at
	return {
		"schema_version": SCHEMA_VERSION,
		"reviewer_id": reviewer_id,
		"reviewer_name": reviewer_name,
		"display_name": reviewer_name,
		"created_at": created_at,
		"last_seen_at": last_seen_at,
		"status": str(raw.get("status") or "active").strip() or "active",
	}


def list_reviewers(paths: ReviewPaths) -> list[dict[str, Any]]:
	registry = _read_reviewer_registry(paths)
	by_id = {
		item["reviewer_id"]: _normalize_registry_profile(item)
		for item in registry.get("reviewers", [])
		if isinstance(item, dict)
	}
	reviewers_root = get_reviewers_dir(paths)
	if reviewers_root.exists():
		for child in reviewers_root.iterdir():
			if not child.is_dir():
				continue
			profile_path = child / "profile.json"
			if not profile_path.exists():
				continue
			try:
				normalized = _normalize_registry_profile(_read_json(profile_path))
			except Exception:
				continue
			by_id[normalized["reviewer_id"]] = normalized
	return sorted(by_id.values(), key=lambda item: item["reviewer_id"])


def _append_missing_jsonl_lines(src: Path, dst: Path) -> None:
	dst.parent.mkdir(parents=True, exist_ok=True)
	existing_lines: set[str] = set()
	if dst.exists():
		with open(dst, encoding="utf-8") as handle:
			existing_lines = {line.rstrip("\n") for line in handle if line.strip()}
	with open(src, encoding="utf-8") as src_handle, open(dst, "a", encoding="utf-8") as dst_handle:
		for line in src_handle:
			text = line.rstrip("\n")
			if not text or text in existing_lines:
				continue
			dst_handle.write(text + "\n")
			existing_lines.add(text)


def _merge_reviewer_namespace_tree(src_root: Path, dst_root: Path) -> None:
	if not src_root.exists() or src_root.resolve() == dst_root.resolve():
		return
	dst_root.mkdir(parents=True, exist_ok=True)
	for child in src_root.iterdir():
		target = dst_root / child.name
		if child.is_dir():
			if not target.exists():
				shutil.move(str(child), str(target))
				continue
			_merge_reviewer_namespace_tree(child, target)
			if child.exists():
				shutil.rmtree(child)
			continue
		if child.suffix == ".jsonl" and target.exists():
			_append_missing_jsonl_lines(child, target)
			child.unlink(missing_ok=True)
			continue
		if child.name == "profile.json":
			child.unlink(missing_ok=True)
			continue
		if not target.exists():
			shutil.move(str(child), str(target))
		else:
			child.unlink(missing_ok=True)
	if src_root.exists():
		shutil.rmtree(src_root)


def _migrate_reviewer_namespace_aliases(
	paths: ReviewPaths,
	canonical_id: str,
	reviewer_name: str,
) -> None:
	reviewers_root = get_reviewers_dir(paths)
	canonical_paths = resolve_reviewer_paths(paths, canonical_id, reviewer_name)
	canonical_root = canonical_paths.reviewer_root
	aliases = [alias for alias in _reviewer_id_aliases(canonical_id) if alias != canonical_id]
	for alias in aliases:
		alias_root = reviewers_root / alias
		if not alias_root.exists():
			continue
		if not canonical_root.exists():
			canonical_root.parent.mkdir(parents=True, exist_ok=True)
			shutil.move(str(alias_root), str(canonical_root))
			break
		_merge_reviewer_namespace_tree(alias_root, canonical_root)
	for alias in aliases:
		alias_export_root = paths.export_root / DEFAULT_REVIEWER_EXPORTS_DIR / alias
		canonical_export_root = canonical_paths.export_root
		if not alias_export_root.exists():
			continue
		if not canonical_export_root.exists():
			canonical_export_root.parent.mkdir(parents=True, exist_ok=True)
			shutil.move(str(alias_export_root), str(canonical_export_root))
			continue
		_merge_reviewer_namespace_tree(alias_export_root, canonical_export_root)


def ensure_reviewer_profile(
	paths: ReviewPaths,
	display_name: str | None = None,
	reviewer_id: str | None = None,
) -> dict[str, Any]:
	_ensure_schema_version(paths)
	name_value = str(display_name or "").strip()
	if not name_value and not reviewer_id:
		raise ValueError("display_name or reviewer_id is required")
	normalized_name = name_value or reviewer_id or ""
	normalized_id = normalize_reviewer_id(normalized_name, reviewer_id)
	lock = _get_lock(get_system_dir(paths))
	with lock:
		_migrate_reviewer_namespace_aliases(paths, normalized_id, normalize_reviewer_name(normalized_name))
		registry = _read_reviewer_registry(paths)
		reviewers = [
			_normalize_registry_profile(item)
			for item in registry.get("reviewers", [])
			if isinstance(item, dict)
		]
		by_id = {item["reviewer_id"]: item for item in reviewers}
		existing = by_id.get(normalized_id)
		now = utc_now_iso()
		if existing:
			if name_value and existing["reviewer_name"] != name_value:
				raise ValueError(
					f"reviewer_id '{normalized_id}' is already registered as '{existing['reviewer_name']}'."
				)
			profile = {
				**existing,
				"last_seen_at": now,
			}
		else:
			profile = {
				"schema_version": SCHEMA_VERSION,
				"reviewer_id": normalized_id,
				"reviewer_name": normalize_reviewer_name(normalized_name),
				"display_name": normalize_reviewer_name(normalized_name),
				"created_at": now,
				"last_seen_at": now,
				"status": "active",
			}
		by_id[normalized_id] = profile
		reviewer_paths = resolve_reviewer_paths(paths, normalized_id, profile["reviewer_name"])
		reviewer_paths.reviewer_root.mkdir(parents=True, exist_ok=True)
		_write_json(reviewer_paths.profile_path, profile)
		_write_reviewer_registry(paths, list(by_id.values()))
	return profile


def find_reviewer_profile(
	paths: ReviewPaths,
	display_name: str | None = None,
	reviewer_id: str | None = None,
) -> dict[str, Any] | None:
	name_value = str(display_name or "").strip()
	if not name_value and not reviewer_id:
		raise ValueError("display_name or reviewer_id is required")
	normalized_name = name_value or reviewer_id or ""
	normalized_id = normalize_reviewer_id(normalized_name, reviewer_id)
	registry = _read_reviewer_registry(paths)
	reviewers = [
		_normalize_registry_profile(item)
		for item in registry.get("reviewers", [])
		if isinstance(item, dict)
	]
	by_id = {item["reviewer_id"]: item for item in reviewers}
	for alias in _reviewer_id_aliases(normalized_id):
		existing = by_id.get(alias)
		if existing:
			return existing
		profile_path = get_reviewers_dir(paths) / alias / "profile.json"
		if not profile_path.exists():
			continue
		try:
			return _normalize_registry_profile(_read_json(profile_path))
		except Exception:
			continue
	return None


def load_ledger(ledger_path: str | Path) -> list[dict[str, Any]]:
	path = Path(ledger_path)
	if not path.exists():
		return []
	rows: list[dict[str, Any]] = []
	with open(path, encoding="utf-8") as handle:
		for line in handle:
			line = line.strip()
			if not line:
				continue
			rows.append(json.loads(line))
	return rows


def _normalize_review_record(raw: dict[str, Any]) -> dict[str, Any]:
	uid = normalize_uid(raw.get("uid"))
	sample_id = str(raw.get("sample_id") or uid).strip() or uid
	reviewer_name = str(
		raw.get("reviewer_name") or raw.get("reviewer") or raw.get("display_name") or ""
	).strip()
	reviewer_name = reviewer_name or DEFAULT_LEGACY_TIMELINE_REVIEWER_ID
	reviewer_id = normalize_reviewer_id(reviewer_name, raw.get("reviewer_id"))
	record = {
		"schema_version": int(raw.get("schema_version") or SCHEMA_VERSION),
		"uid": uid,
		"sample_id": sample_id,
		"decision": validate_decision(raw.get("decision", "")),
		"reviewer_id": reviewer_id,
		"reviewer_name": reviewer_name,
		"reviewer": reviewer_name,
		"timestamp": str(raw.get("timestamp") or "").strip() or utc_now_iso(),
		"notes": str(raw.get("notes") or "").strip(),
		"reference_source": str(raw.get("reference_source") or "").strip(),
		"trajectory_tags": normalize_trajectory_tags(
			raw.get("trajectory_tags", raw.get("tags", raw.get("tag")))
		),
	}
	return record


def build_latest_reviews(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
	latest: dict[str, dict[str, Any]] = {}
	for entry in entries:
		record = _normalize_review_record(entry)
		latest[record["uid"]] = record
	return latest


def _has_reviewer_namespaces(paths: ReviewPaths) -> bool:
	reviewers_root = get_reviewers_dir(paths)
	if not reviewers_root.exists():
		return False
	return any(child.is_dir() for child in reviewers_root.iterdir())


def _legacy_review_index(paths: ReviewPaths) -> dict[str, Any]:
	if paths.latest_path.exists():
		try:
			payload = _read_json(paths.latest_path)
			if isinstance(payload.get("reviews"), dict):
				return {
					**payload,
					"schema_version": int(payload.get("schema_version") or 1),
					"mode": "legacy",
					"aggregate_counts_by_uid": {
						str(uid): 1 for uid in payload.get("reviews", {}).keys()
					},
					"reviewer_profile": None,
				}
		except Exception:
			pass
	return _refresh_legacy_latest_reviews(paths)


def _refresh_legacy_latest_reviews(paths: ReviewPaths) -> dict[str, Any]:
	entries = load_ledger(paths.ledger_path)
	reviews = build_latest_reviews(entries)
	counts = {decision: 0 for decision in VALID_DECISIONS}
	for review in reviews.values():
		decision = str(review.get("decision") or "").strip().lower()
		if decision in counts:
			counts[decision] += 1
	payload = {
		"schema_version": 1,
		"generated_at": utc_now_iso(),
		"mode": "legacy",
		"count": len(reviews),
		"counts": counts,
		"reviews": reviews,
		"aggregate_counts_by_uid": {uid: 1 for uid in reviews},
		"reviewer_profile": None,
	}
	_write_json(paths.latest_path, payload)
	return payload


def _reviewer_index_from_latest(
	latest_payload: dict[str, Any],
	reviewer_profile: dict[str, Any],
	aggregate_counts_by_uid: dict[str, int] | None = None,
) -> dict[str, Any]:
	return {
		"schema_version": SCHEMA_VERSION,
		"generated_at": str(latest_payload.get("generated_at") or "").strip() or utc_now_iso(),
		"mode": "reviewer_namespace",
		"reviewer_profile": reviewer_profile,
		"count": int(latest_payload.get("count") or 0),
		"counts": dict(latest_payload.get("counts") or {decision: 0 for decision in VALID_DECISIONS}),
		"reviews": dict(latest_payload.get("reviews") or {}),
		"aggregate_counts_by_uid": dict(aggregate_counts_by_uid or {}),
	}


def _refresh_reviewer_latest_reviews(paths: ReviewPaths, reviewer_id: str) -> dict[str, Any]:
	profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
	reviewer_paths = resolve_reviewer_paths(paths, profile["reviewer_id"], profile["reviewer_name"])
	lock = _get_lock(reviewer_paths.reviewer_root)
	with lock:
		entries = load_ledger(reviewer_paths.ledger_path)
		reviews = build_latest_reviews(entries)
		counts = {decision: 0 for decision in VALID_DECISIONS}
		for review in reviews.values():
			decision = str(review.get("decision") or "").strip().lower()
			if decision in counts:
				counts[decision] += 1
		latest_payload = {
			"schema_version": SCHEMA_VERSION,
			"generated_at": utc_now_iso(),
			"count": len(reviews),
			"counts": counts,
			"reviews": reviews,
		}
		_write_json(reviewer_paths.latest_path, latest_payload)
	aggregate_stats = read_aggregate_stats(paths)
	return _reviewer_index_from_latest(
		latest_payload,
		profile,
		aggregate_counts_by_uid=aggregate_stats.get("reviewer_counts_by_uid", {}),
	)


def read_latest_reviews(paths: ReviewPaths, reviewer_id: str | None = None) -> dict[str, Any]:
	if reviewer_id:
		profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
		reviewer_paths = resolve_reviewer_paths(paths, profile["reviewer_id"], profile["reviewer_name"])
		if reviewer_paths.latest_path.exists():
			latest_payload = _read_json(reviewer_paths.latest_path)
		else:
			return _refresh_reviewer_latest_reviews(paths, reviewer_id)
		aggregate_stats = read_aggregate_stats(paths)
		return _reviewer_index_from_latest(
			latest_payload,
			profile,
			aggregate_counts_by_uid=aggregate_stats.get("reviewer_counts_by_uid", {}),
		)
	if _has_reviewer_namespaces(paths):
		aggregate_stats = read_aggregate_stats(paths)
		return {
			"schema_version": SCHEMA_VERSION,
			"generated_at": utc_now_iso(),
			"mode": "reviewer_namespace",
			"count": 0,
			"counts": {decision: 0 for decision in VALID_DECISIONS},
			"reviews": {},
			"reviewer_profile": None,
			"aggregate_counts_by_uid": aggregate_stats.get("reviewer_counts_by_uid", {}),
		}
	return _legacy_review_index(paths)


def refresh_latest_reviews(paths: ReviewPaths, reviewer_id: str | None = None) -> dict[str, Any]:
	if reviewer_id:
		return _refresh_reviewer_latest_reviews(paths, reviewer_id)
	if _has_reviewer_namespaces(paths):
		return read_latest_reviews(paths, reviewer_id=None)
	return _refresh_legacy_latest_reviews(paths)


def get_review(paths: ReviewPaths, uid: str, reviewer_id: str | None = None) -> dict[str, Any] | None:
	index_payload = read_latest_reviews(paths, reviewer_id=reviewer_id)
	return index_payload.get("reviews", {}).get(str(uid))


def csv_has_data(path: str | Path) -> bool:
	file_path = Path(path)
	if not file_path.exists() or not file_path.is_file():
		return False
	try:
		with open(file_path, encoding="utf-8", newline="") as handle:
			reader = csv.reader(handle)
			next(reader, None)
			return next(reader, None) is not None
	except OSError:
		return False


def choose_reference_source(uid_dir: str | Path, result_root: str | Path | None = None) -> str:
	base = Path(uid_dir)
	candidates = get_manifest_review_reference_files(result_root or base.parent)
	for candidate in candidates:
		if csv_has_data(base / candidate):
			return candidate
	return ""


def validate_accept_reference(
	uid_dir: str | Path,
	reference_source: str,
	sample_id: str,
	result_root: str | Path | None = None,
) -> str:
	base = Path(uid_dir)
	candidates = get_manifest_review_reference_files(result_root or base.parent)
	chosen = str(reference_source or "").strip()
	if chosen not in candidates:
		chosen = choose_reference_source(base, result_root=result_root)
	if chosen not in candidates:
		expected = " or ".join(candidates) if candidates else "a usable reference CSV"
		raise ValueError(
			f"Accepted sample {sample_id} requires a usable {expected} reference asset."
		)
	if not csv_has_data(base / chosen):
		raise ValueError(
			f"Accepted sample {sample_id} expects reference source {chosen}, but the file is missing or empty."
		)
	return chosen


def _reviewer_profile_from_payload(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	display_name = (
		payload.get("reviewer_name")
		or payload.get("reviewer")
		or payload.get("display_name")
		or ""
	)
	reviewer_id = payload.get("reviewer_id")
	return ensure_reviewer_profile(paths, display_name=display_name, reviewer_id=reviewer_id)


def normalize_review_payload(
	paths: ReviewPaths,
	payload: dict[str, Any],
) -> ReviewEntry:
	profile = _reviewer_profile_from_payload(paths, payload)
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	decision = validate_decision(payload.get("decision", ""))
	timestamp = str(payload.get("timestamp") or "").strip() or utc_now_iso()
	notes = str(payload.get("notes") or "").strip()
	reference_source = str(payload.get("reference_source") or "").strip()
	trajectory_tags = normalize_trajectory_tags(
		payload.get("trajectory_tags", payload.get("tags", payload.get("tag")))
	)
	if not reference_source:
		reference_source = choose_reference_source(paths.result_root / uid, result_root=paths.result_root)
	return ReviewEntry(
		uid=uid,
		sample_id=sample_id,
		decision=decision,
		reviewer_id=profile["reviewer_id"],
		reviewer_name=profile["reviewer_name"],
		reviewer=profile["reviewer_name"],
		timestamp=timestamp,
		notes=notes,
		reference_source=reference_source,
		trajectory_tags=trajectory_tags,
	)


def _normalize_timeline_pin(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		return {}
	time_value = _normalize_timeline_epoch_seconds(item.get("time"))
	if time_value is None:
		return {}
	return {
		"id": str(item.get("id") or f"pin-{round(time_value)}").strip() or f"pin-{round(time_value)}",
		"time": time_value,
		"layerKey": str(item.get("layerKey") or "").strip(),
		"label": str(item.get("label") or "").strip(),
	}


_TIMELINE_SEGMENT_VNEXT_STRING_KEYS = frozenset(
	{
		"chainType",
		"chainTypeName",
		"travelMode",
		"reconstructionQuality",
		"accuracyLabel",
		"notes",
	}
)
_TIMELINE_SEGMENT_VNEXT_TAG_LIST_KEYS = frozenset({"semanticTags", "errorTypes"})
_TIMELINE_SEGMENT_VNEXT_REF_LIST_KEYS = frozenset({"visualEvidenceRefs", "trackEditRefs"})


def _normalize_timeline_segment_tag_list(value: Any) -> list[str]:
	if not isinstance(value, list):
		return []
	normalized: list[str] = []
	seen: set[str] = set()
	for entry in value:
		text = str(entry or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		normalized.append(text)
	return normalized


def _normalize_timeline_segment_ref_list(value: Any) -> list[str]:
	if not isinstance(value, list):
		return []
	normalized: list[str] = []
	seen: set[str] = set()
	for entry in value:
		text = str(entry or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		normalized.append(text)
	return normalized


def _normalize_timeline_segment_evidence_value(value: Any, depth: int = 0) -> Any | None:
	if depth > 6:
		return None
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		if isinstance(value, float) and not math.isfinite(value):
			return None
		return value
	if isinstance(value, str):
		stripped = value.strip()
		return stripped if stripped else None
	if isinstance(value, list):
		items: list[Any] = []
		for entry in value:
			nested = _normalize_timeline_segment_evidence_value(entry, depth + 1)
			if nested is not None:
				items.append(nested)
		return items if items else None
	if isinstance(value, dict):
		return _normalize_timeline_segment_evidence_dict(value, depth + 1)
	return None


def _normalize_timeline_segment_evidence_dict(raw: Any, depth: int = 0) -> dict[str, Any] | None:
	if not isinstance(raw, dict) or depth > 6:
		return None
	out: dict[str, Any] = {}
	for raw_key, raw_val in raw.items():
		key = str(raw_key or "").strip()
		if not key:
			continue
		val = _normalize_timeline_segment_evidence_value(raw_val, depth + 1)
		if val is not None:
			out[key] = val
	return out if out else None


def _merge_vnext_timeline_segment_fields(item: dict[str, Any], record: dict[str, Any]) -> None:
	for key in _TIMELINE_SEGMENT_VNEXT_STRING_KEYS:
		if key not in item:
			continue
		text = str(item.get(key) or "").strip()
		if text:
			record[key] = text
	for key in _TIMELINE_SEGMENT_VNEXT_TAG_LIST_KEYS:
		if key not in item:
			continue
		tags = _normalize_timeline_segment_tag_list(item.get(key))
		if tags:
			record[key] = tags
	for key in _TIMELINE_SEGMENT_VNEXT_REF_LIST_KEYS:
		if key not in item:
			continue
		refs = _normalize_timeline_segment_ref_list(item.get(key))
		if refs:
			record[key] = refs
	if "evidence" in item:
		evidence = _normalize_timeline_segment_evidence_dict(item.get("evidence"), 0)
		if evidence:
			record["evidence"] = evidence
	if "confidence" in item:
		confidence = parse_numeric_value(item.get("confidence"))
		if confidence is not None and math.isfinite(confidence):
			record["confidence"] = confidence
	if "needsHumanReview" in item:
		record["needsHumanReview"] = _normalize_bool(item.get("needsHumanReview"))


def _infer_timeline_segment_category_fields(record: dict[str, Any]) -> None:
	if all(str(record.get(key) or "").strip() for key in ("categoryId", "categoryName", "color")):
		return
	semantic_tags = record.get("semanticTags")
	if not isinstance(semantic_tags, list):
		return
	inferred: dict[str, str] | None = None
	for raw_tag in semantic_tags:
		tag = str(raw_tag or "").strip().lower()
		if (
			not tag
			or any(tag.startswith(prefix) for prefix in TIMELINE_SEGMENT_IGNORED_SEMANTIC_TAG_PREFIXES)
		):
			continue
		inferred = TIMELINE_SEGMENT_REPLAY_CATEGORY_BY_SEMANTIC_TAG.get(tag)
		if inferred:
			break
	if not inferred:
		return
	for key, value in inferred.items():
		if not str(record.get(key) or "").strip():
			record[key] = value


def _normalize_timeline_segment(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		return {}
	start_time = _normalize_timeline_epoch_seconds(item.get("startTime"))
	end_time = _normalize_timeline_epoch_seconds(item.get("endTime"))
	if start_time is None or end_time is None:
		return {}
	left_time = min(start_time, end_time)
	right_time = max(start_time, end_time)
	record = {
		"id": str(item.get("id") or f"segment-{round(left_time)}-{round(right_time)}").strip()
		or f"segment-{round(left_time)}-{round(right_time)}",
		"categoryId": str(item.get("categoryId") or "").strip(),
		"categoryName": str(item.get("categoryName") or "").strip(),
		"color": str(item.get("color") or "").strip(),
		"startTime": left_time,
		"endTime": right_time,
	}
	entry_mode = str(item.get("entryMode") or "").strip()
	segment_scope = str(item.get("segmentScope") or "").strip()
	window_start_day = str(item.get("windowStartDay") or "").strip()
	window_end_day = str(item.get("windowEndDay") or "").strip()
	source_layer_key = str(item.get("sourceLayerKey") or "").strip()
	fixed_span_days = parse_numeric_value(item.get("fixedSpanDays"))
	if entry_mode:
		record["entryMode"] = entry_mode
	if segment_scope:
		record["segmentScope"] = segment_scope
	if window_start_day:
		record["windowStartDay"] = window_start_day
	if window_end_day:
		record["windowEndDay"] = window_end_day
	if source_layer_key:
		record["sourceLayerKey"] = source_layer_key
	if fixed_span_days is not None:
		record["fixedSpanDays"] = max(0, int(round(fixed_span_days)))
	_merge_vnext_timeline_segment_fields(item, record)
	_infer_timeline_segment_category_fields(record)
	return record


def normalize_timeline_annotations_payload(
	paths: ReviewPaths,
	payload: dict[str, Any],
) -> dict[str, Any]:
	profile = _reviewer_profile_from_payload(paths, payload)
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	segment_policy = _normalize_segment_policy(payload.get("segmentPolicy"))
	pins = [_normalize_timeline_pin(item) for item in payload.get("pins", [])]
	segments = [_normalize_timeline_segment(item) for item in payload.get("segments", [])]
	canonical_segments = _canonicalize_timeline_segments(
		[item for item in segments if item],
		segment_policy,
	)
	return {
		"schema_version": SCHEMA_VERSION,
		"uid": uid,
		"sample_id": sample_id,
		"reviewer_id": profile["reviewer_id"],
		"reviewer_name": profile["reviewer_name"],
		"reviewer": profile["reviewer_name"],
		"updated_at": str(payload.get("updated_at") or "").strip() or utc_now_iso(),
		"segmentPolicy": segment_policy,
		"pins": [item for item in pins if item],
		"segments": canonical_segments,
	}


def _empty_timeline_annotations(uid: str, reviewer_id: str = "", reviewer_name: str = "") -> dict[str, Any]:
	normalized_uid = normalize_uid(uid)
	return {
		"schema_version": SCHEMA_VERSION,
		"uid": normalized_uid,
		"sample_id": normalized_uid,
		"reviewer_id": reviewer_id,
		"reviewer_name": reviewer_name,
		"reviewer": reviewer_name,
		"updated_at": "",
		"segmentPolicy": dict(DEFAULT_SEGMENT_POLICY),
		"pins": [],
		"segments": [],
	}


def _normalize_track_edit_patch(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		return {}
	point_id = str(item.get("pointId") or "").strip()
	layer_key = str(item.get("layerKey") or "").strip()
	row_index = parse_numeric_value(item.get("rowIndex"))
	timestamp = parse_numeric_value(item.get("timestamp"))
	position = item.get("position")
	if (
		not point_id
		or not layer_key
		or row_index is None
		or timestamp is None
	):
		return {}
	metadata = item.get("metadata")
	normalized: dict[str, Any] = {
		"pointId": point_id,
		"layerKey": layer_key,
		"rowIndex": max(0, int(round(row_index))),
		"timestamp": timestamp,
		"metadata": dict(metadata) if isinstance(metadata, dict) else {},
	}
	if isinstance(position, dict):
		latitude = parse_numeric_value(position.get("latitude"))
		longitude = parse_numeric_value(position.get("longitude"))
		if latitude is not None and longitude is not None:
			normalized["position"] = {
				"latitude": latitude,
				"longitude": longitude,
			}
	if "position" not in normalized and not normalized["metadata"]:
		return {}
	return normalized


def normalize_track_edits_payload(
	paths: ReviewPaths,
	payload: dict[str, Any],
) -> dict[str, Any]:
	profile = _reviewer_profile_from_payload(paths, payload)
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	patches = [
		_normalize_track_edit_patch(item)
		for item in payload.get("pointPatches", payload.get("patches", payload.get("trackEdits", [])))
	]
	return {
		"schema_version": TRACK_EDITS_SCHEMA_VERSION,
		"uid": uid,
		"sample_id": sample_id,
		"reviewer_id": profile["reviewer_id"],
		"reviewer_name": profile["reviewer_name"],
		"reviewer": profile["reviewer_name"],
		"updated_at": str(payload.get("updated_at") or "").strip() or utc_now_iso(),
		"patches": [item for item in patches if item],
	}


def _with_track_edit_patch_aliases(payload: dict[str, Any]) -> dict[str, Any]:
	patches = [
		_normalize_track_edit_patch(item)
		for item in payload.get("patches", payload.get("pointPatches", payload.get("trackEdits", [])))
		if _normalize_track_edit_patch(item)
	]
	return {
		**payload,
		"patches": patches,
		"pointPatches": patches,
	}


def _empty_track_edits(uid: str, reviewer_id: str = "", reviewer_name: str = "") -> dict[str, Any]:
	normalized_uid = normalize_uid(uid)
	return {
		"schema_version": TRACK_EDITS_SCHEMA_VERSION,
		"uid": normalized_uid,
		"sample_id": normalized_uid,
		"reviewer_id": reviewer_id,
		"reviewer_name": reviewer_name,
		"reviewer": reviewer_name,
		"updated_at": "",
		"patches": [],
	}


def read_track_edits(
	paths: ReviewPaths,
	uid: str,
	reviewer_id: str,
) -> dict[str, Any]:
	profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
	reviewer_paths = resolve_reviewer_paths(paths, profile["reviewer_id"], profile["reviewer_name"])
	path = reviewer_paths.track_edits_root / f"{normalize_uid(uid)}.json"
	if not path.exists():
		return _with_track_edit_patch_aliases(_empty_track_edits(uid, profile["reviewer_id"], profile["reviewer_name"]))
	payload = _read_json(path)
	return _with_track_edit_patch_aliases({
		**_empty_track_edits(uid, profile["reviewer_id"], profile["reviewer_name"]),
		"updated_at": str(payload.get("updated_at") or "").strip(),
		"patches": payload.get("patches", payload.get("pointPatches", payload.get("trackEdits", []))),
	})


def _read_legacy_timeline_annotations(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	path = get_legacy_timeline_annotation_path(paths, uid)
	if not path.exists():
		return _empty_timeline_annotations(uid)
	payload = _read_json(path)
	normalized = {
		**_empty_timeline_annotations(uid),
		"updated_at": str(payload.get("updated_at") or "").strip(),
		"segmentPolicy": _normalize_segment_policy(payload.get("segmentPolicy")),
		"pins": [_normalize_timeline_pin(item) for item in payload.get("pins", []) if _normalize_timeline_pin(item)],
		"segments": [_normalize_timeline_segment(item) for item in payload.get("segments", []) if _normalize_timeline_segment(item)],
	}
	return normalized


def read_timeline_annotations(
	paths: ReviewPaths,
	uid: str,
	reviewer_id: str | None = None,
	read_only: bool = False,
) -> dict[str, Any]:
	if reviewer_id:
		profile = find_reviewer_profile(paths, reviewer_id=reviewer_id) if read_only else ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
		effective_reviewer_id = str(
			profile.get("reviewer_id") if profile else normalize_reviewer_id(reviewer_id, reviewer_id)
		).strip()
		effective_reviewer_name = str(
			profile.get("reviewer_name") if profile else reviewer_id or effective_reviewer_id
		).strip() or effective_reviewer_id
		reviewer_paths = resolve_reviewer_paths(paths, effective_reviewer_id, effective_reviewer_name)
		path = reviewer_paths.timeline_root / f"{normalize_uid(uid)}.json"
		if read_only and not path.exists():
			for alias in _reviewer_id_aliases(effective_reviewer_id):
				candidate_paths = resolve_reviewer_paths(paths, alias, effective_reviewer_name)
				candidate_path = candidate_paths.timeline_root / f"{normalize_uid(uid)}.json"
				if not candidate_path.exists():
					continue
				reviewer_paths = candidate_paths
				path = candidate_path
				break
		if not path.exists():
			return _empty_timeline_annotations(uid, reviewer_paths.reviewer_id, reviewer_paths.reviewer_name)
		payload = _read_json(path)
		return {
			**_empty_timeline_annotations(uid, reviewer_paths.reviewer_id, reviewer_paths.reviewer_name),
			"updated_at": str(payload.get("updated_at") or "").strip(),
			"segmentPolicy": _normalize_segment_policy(payload.get("segmentPolicy")),
			"pins": [_normalize_timeline_pin(item) for item in payload.get("pins", []) if _normalize_timeline_pin(item)],
			"segments": [
				_normalize_timeline_segment(item)
				for item in payload.get("segments", [])
				if _normalize_timeline_segment(item)
			],
		}
	if _has_reviewer_namespaces(paths):
		return _empty_timeline_annotations(uid)
	return _read_legacy_timeline_annotations(paths, uid)


def _summarize_timeline_annotations(payload: dict[str, Any]) -> dict[str, Any]:
	segments = payload.get("segments", [])
	window_quick_segment_count = sum(
		1
		for item in segments
		if isinstance(item, dict)
		and str(item.get("entryMode") or "").strip() == "window_quick"
		and str(item.get("segmentScope") or "").strip() == "date_window"
	)
	category_names = sorted(
		{
			str(item.get("categoryName") or "").strip()
			for item in segments
			if isinstance(item, dict) and str(item.get("categoryName") or "").strip()
		}
	)
	return {
		"reviewer_id": str(payload.get("reviewer_id") or "").strip(),
		"reviewer_name": str(payload.get("reviewer_name") or payload.get("reviewer") or "").strip(),
		"updated_at": str(payload.get("updated_at") or "").strip(),
		"pin_count": len(payload.get("pins", []) or []),
		"segment_count": len(segments or []),
		"window_quick_segment_count": window_quick_segment_count,
		"categories": category_names,
	}


def _write_uid_aggregate(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	normalized_uid = normalize_uid(uid)
	reviews: list[dict[str, Any]] = []
	timeline_summary: list[dict[str, Any]] = []
	if _has_reviewer_namespaces(paths):
		for profile in list_reviewers(paths):
			reviewer_paths = resolve_reviewer_paths(
				paths, profile["reviewer_id"], profile["reviewer_name"]
			)
			if reviewer_paths.latest_path.exists():
				try:
					latest_payload = _read_json(reviewer_paths.latest_path)
				except Exception:
					latest_payload = {}
				review = dict(latest_payload.get("reviews", {}).get(normalized_uid) or {})
				if review:
					reviews.append(review)
			annotation_path = reviewer_paths.timeline_root / f"{normalized_uid}.json"
			if annotation_path.exists():
				try:
					annotations = _read_json(annotation_path)
				except Exception:
					annotations = {}
				if annotations:
					timeline_summary.append(_summarize_timeline_annotations(annotations))
	else:
		legacy_index = _legacy_review_index(paths)
		review = dict(legacy_index.get("reviews", {}).get(normalized_uid) or {})
		if review:
			reviews.append(review)
		legacy_annotations = _read_legacy_timeline_annotations(paths, normalized_uid)
		if legacy_annotations.get("pins") or legacy_annotations.get("segments"):
			timeline_summary.append(_summarize_timeline_annotations(legacy_annotations))

	decision_counts = {decision: 0 for decision in VALID_DECISIONS}
	for review in reviews:
		decision = str(review.get("decision") or "").strip().lower()
		if decision in decision_counts:
			decision_counts[decision] += 1
	reviewer_ids = {
		str(review.get("reviewer_id") or "").strip()
		for review in reviews
		if str(review.get("reviewer_id") or "").strip()
	}
	reviewer_ids.update(
		str(item.get("reviewer_id") or "").strip()
		for item in timeline_summary
		if str(item.get("reviewer_id") or "").strip()
	)
	sample_id = (
		str(reviews[0].get("sample_id") or "").strip()
		if reviews
		else normalized_uid
	)
	aggregate = {
		"schema_version": SCHEMA_VERSION,
		"uid": normalized_uid,
		"sample_id": sample_id or normalized_uid,
		"generated_at": utc_now_iso(),
		"reviewer_count": len(reviewer_ids),
		"decision_counts": decision_counts,
		"latest_reviews": sorted(
			reviews,
			key=lambda row: (
				str(row.get("timestamp") or ""),
				str(row.get("reviewer_id") or ""),
			),
			reverse=True,
		),
		"timeline_annotation_summary": sorted(
			timeline_summary,
			key=lambda row: (
				str(row.get("updated_at") or ""),
				str(row.get("reviewer_id") or ""),
			),
			reverse=True,
		),
	}
	with _get_lock(get_aggregate_dir(paths)):
		_write_json(get_aggregate_uid_path(paths, normalized_uid), aggregate)
	return aggregate


def get_uid_review_aggregate(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	path = get_aggregate_uid_path(paths, uid)
	if path.exists():
		try:
			payload = _read_json(path)
			if normalize_uid(payload.get("uid")) == normalize_uid(uid):
				return payload
		except Exception:
			pass
	return _write_uid_aggregate(paths, uid)


def get_timeline_annotation_aggregate(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	aggregate = get_uid_review_aggregate(paths, uid)
	return {
		"schema_version": SCHEMA_VERSION,
		"uid": aggregate.get("uid"),
		"sample_id": aggregate.get("sample_id"),
		"generated_at": aggregate.get("generated_at"),
		"annotations": aggregate.get("timeline_annotation_summary", []),
	}


def refresh_aggregate_stats(paths: ReviewPaths) -> dict[str, Any]:
	reviewer_counts_by_uid: dict[str, int] = {}
	conflict_uids: list[str] = []
	total_reviewed_uids = 0
	if get_aggregate_by_uid_dir(paths).exists():
		for child in get_aggregate_by_uid_dir(paths).iterdir():
			if child.suffix != ".json":
				continue
			try:
				payload = _read_json(child)
			except Exception:
				continue
			uid = str(payload.get("uid") or child.stem).strip()
			latest_reviews = payload.get("latest_reviews", [])
			reviewer_counts_by_uid[uid] = len(latest_reviews or [])
			if latest_reviews:
				total_reviewed_uids += 1
				decisions = {
					str(item.get("decision") or "").strip().lower()
					for item in latest_reviews
					if str(item.get("decision") or "").strip()
				}
				if len(decisions) > 1:
					conflict_uids.append(uid)
	reviewers = list_reviewers(paths) if _has_reviewer_namespaces(paths) else []
	payload = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"reviewer_count": len(reviewers),
		"reviewed_uid_count": total_reviewed_uids,
		"conflict_uid_count": len(conflict_uids),
		"conflict_uids": sorted(conflict_uids),
		"reviewer_counts_by_uid": reviewer_counts_by_uid,
		"reviewers": reviewers,
	}
	with _get_lock(get_aggregate_dir(paths)):
		_write_json(get_aggregate_stats_path(paths), payload)
	return payload


def read_aggregate_stats(paths: ReviewPaths) -> dict[str, Any]:
	path = get_aggregate_stats_path(paths)
	if path.exists():
		try:
			return _read_json(path)
		except Exception:
			pass
	if _has_reviewer_namespaces(paths):
		return refresh_aggregate_stats(paths)
	legacy_index = _legacy_review_index(paths)
	return {
		"schema_version": 1,
		"generated_at": utc_now_iso(),
		"reviewer_count": 0,
		"reviewed_uid_count": legacy_index.get("count", 0),
		"conflict_uid_count": 0,
		"conflict_uids": [],
		"reviewer_counts_by_uid": legacy_index.get("aggregate_counts_by_uid", {}),
		"reviewers": [],
	}


def write_review(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	entry = normalize_review_payload(paths, payload)
	if entry.decision == "accept":
		validate_accept_reference(
			paths.result_root / entry.uid,
			entry.reference_source,
			entry.sample_id,
			result_root=paths.result_root,
		)
	reviewer_paths = resolve_reviewer_paths(paths, entry.reviewer_id, entry.reviewer_name)
	reviewer_lock = _get_lock(reviewer_paths.reviewer_root)
	with reviewer_lock:
		reviewer_paths.reviews_root.mkdir(parents=True, exist_ok=True)
		_append_jsonl(reviewer_paths.ledger_path, asdict(entry))
	_refresh_reviewer_latest_reviews(paths, entry.reviewer_id)
	_write_uid_aggregate(paths, entry.uid)
	refresh_aggregate_stats(paths)
	return get_review(paths, entry.uid, reviewer_id=entry.reviewer_id) or asdict(entry)


def write_timeline_annotations(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	record = normalize_timeline_annotations_payload(paths, payload)
	reviewer_paths = resolve_reviewer_paths(
		paths, record["reviewer_id"], record["reviewer_name"]
	)
	reviewer_lock = _get_lock(reviewer_paths.reviewer_root)
	with reviewer_lock:
		target_path = reviewer_paths.timeline_root / f"{record['uid']}.json"
		_write_json(target_path, record)
		_append_jsonl(reviewer_paths.timeline_ledger_path, record)
	_write_uid_aggregate(paths, record["uid"])
	refresh_aggregate_stats(paths)
	return record


def write_track_edits(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	record = normalize_track_edits_payload(paths, payload)
	reviewer_paths = resolve_reviewer_paths(
		paths, record["reviewer_id"], record["reviewer_name"]
	)
	reviewer_lock = _get_lock(reviewer_paths.reviewer_root)
	with reviewer_lock:
		target_path = reviewer_paths.track_edits_root / f"{record['uid']}.json"
		_write_json(target_path, record)
		_append_jsonl(reviewer_paths.track_edits_ledger_path, record)
	return _with_track_edit_patch_aliases(record)


def export_accepted_assets(
	paths: ReviewPaths,
	clean: bool = False,
	reviewer_id: str | None = None,
) -> dict[str, Any]:
	if _has_reviewer_namespaces(paths):
		if not reviewer_id:
			raise ValueError("reviewer_id is required for accepted export when reviewer namespaces are enabled.")
		index_payload = read_latest_reviews(paths, reviewer_id=reviewer_id)
		profile = index_payload.get("reviewer_profile") or ensure_reviewer_profile(
			paths, reviewer_id=reviewer_id
		)
		target_export_root = resolve_reviewer_paths(
			paths, profile["reviewer_id"], profile["reviewer_name"]
		).export_root
	else:
		index_payload = read_latest_reviews(paths)
		profile = index_payload.get("reviewer_profile")
		target_export_root = paths.export_root

	accepted = [
		review
		for review in index_payload.get("reviews", {}).values()
		if str(review.get("decision") or "").lower() == "accept"
	]

	if clean and target_export_root.exists():
		shutil.rmtree(target_export_root)

	samples_root = target_export_root / "samples"
	samples_root.mkdir(parents=True, exist_ok=True)

	accepted_ledger_path = target_export_root / DEFAULT_ACCEPTED_LEDGER_NAME
	manifest_path = target_export_root / DEFAULT_ACCEPTED_MANIFEST_NAME

	exported_samples: list[dict[str, Any]] = []
	for review in sorted(accepted, key=lambda row: (row.get("uid", ""), row.get("timestamp", ""))):
		uid = normalize_uid(review.get("uid"))
		sample_id = str(review.get("sample_id") or uid).strip() or uid
		uid_dir = paths.result_root / uid
		target_dir = samples_root / sample_id
		if target_dir.exists():
			shutil.rmtree(target_dir)
		target_dir.mkdir(parents=True, exist_ok=True)

		raw_exported = _safe_copy(uid_dir / "raw.csv", target_dir / "raw.csv")
		reference_name = validate_accept_reference(
			uid_dir,
			str(review.get("reference_source") or "").strip(),
			sample_id,
			result_root=paths.result_root,
		)
		reference_exported = False
		if reference_name:
			reference_exported = _safe_copy(uid_dir / reference_name, target_dir / reference_name)

		review_record = dict(review)
		review_record["exported_at"] = utc_now_iso()
		review_record["export_uid_dir"] = str(uid_dir)
		review_record["reference_source"] = reference_name
		_write_json(target_dir / "review.json", review_record)

		exported_samples.append(
			{
				"uid": uid,
				"sample_id": sample_id,
				"decision": review.get("decision"),
				"reviewer_id": review.get("reviewer_id", ""),
				"reviewer_name": review.get("reviewer_name") or review.get("reviewer", ""),
				"reviewer": review.get("reviewer_name") or review.get("reviewer", ""),
				"timestamp": review.get("timestamp", ""),
				"notes": review.get("notes", ""),
				"trajectory_tags": normalize_trajectory_tags(review.get("trajectory_tags")),
				"reference_source": reference_name,
				"raw_exported": raw_exported,
				"reference_exported": reference_exported,
				"sample_dir": str(target_dir),
			}
		)

	with open(accepted_ledger_path, "w", encoding="utf-8") as handle:
		for row in exported_samples:
			handle.write(json.dumps(row, ensure_ascii=False) + "\n")

	manifest = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"result_root": str(paths.result_root),
		"review_root": str(paths.review_root),
		"export_root": str(target_export_root),
		"reviewer_profile": profile,
		"accepted_count": len(exported_samples),
		"samples": exported_samples,
	}
	_write_json(manifest_path, manifest)
	return manifest


def export_review_aggregate(
	paths: ReviewPaths,
	clean: bool = False,
	output_root: str | Path | None = None,
) -> dict[str, Any]:
	target_root = (
		Path(output_root).expanduser().resolve()
		if output_root
		else paths.review_root / DEFAULT_REVIEW_EXPORTS_DIR / "aggregate"
	)
	if clean and target_root.exists():
		shutil.rmtree(target_root)
	target_root.mkdir(parents=True, exist_ok=True)

	by_uid_records: list[dict[str, Any]] = []
	if get_aggregate_by_uid_dir(paths).exists():
		for child in sorted(get_aggregate_by_uid_dir(paths).iterdir(), key=lambda item: item.name):
			if child.suffix != ".json":
				continue
			try:
				by_uid_records.append(_read_json(child))
			except Exception:
				continue
	elif not _has_reviewer_namespaces(paths):
		legacy_index = _legacy_review_index(paths)
		for uid in legacy_index.get("reviews", {}):
			by_uid_records.append(get_uid_review_aggregate(paths, uid))

	by_reviewer_stats: dict[str, dict[str, Any]] = {}
	conflict_records: list[dict[str, Any]] = []
	for record in by_uid_records:
		latest_reviews = record.get("latest_reviews", []) or []
		decisions = {
			str(item.get("decision") or "").strip().lower()
			for item in latest_reviews
			if str(item.get("decision") or "").strip()
		}
		if len(decisions) > 1:
			conflict_records.append(record)
		for review in latest_reviews:
			reviewer_id = str(review.get("reviewer_id") or "").strip()
			if not reviewer_id:
				continue
			stats = by_reviewer_stats.setdefault(
				reviewer_id,
				{
					"reviewer_id": reviewer_id,
					"reviewer_name": str(review.get("reviewer_name") or review.get("reviewer") or "").strip(),
					"reviewed_uid_count": 0,
					"accept_count": 0,
					"reject_count": 0,
					"skip_count": 0,
				},
			)
			stats["reviewed_uid_count"] += 1
			decision = str(review.get("decision") or "").strip().lower()
			if decision == "accept":
				stats["accept_count"] += 1
			elif decision == "reject":
				stats["reject_count"] += 1
			elif decision == "skip":
				stats["skip_count"] += 1

	by_uid_path = target_root / "by_uid.jsonl"
	by_reviewer_path = target_root / "by_reviewer.jsonl"
	conflicts_path = target_root / "conflicts.jsonl"
	manifest_path = target_root / DEFAULT_ACCEPTED_MANIFEST_NAME

	with open(by_uid_path, "w", encoding="utf-8") as handle:
		for row in by_uid_records:
			handle.write(json.dumps(row, ensure_ascii=False) + "\n")
	with open(by_reviewer_path, "w", encoding="utf-8") as handle:
		for row in sorted(by_reviewer_stats.values(), key=lambda item: item["reviewer_id"]):
			handle.write(json.dumps(row, ensure_ascii=False) + "\n")
	with open(conflicts_path, "w", encoding="utf-8") as handle:
		for row in conflict_records:
			handle.write(json.dumps(row, ensure_ascii=False) + "\n")

	manifest = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"review_root": str(paths.review_root),
		"output_root": str(target_root),
		"uid_count": len(by_uid_records),
		"reviewer_count": len(by_reviewer_stats),
		"conflict_uid_count": len(conflict_records),
	}
	_write_json(manifest_path, manifest)
	return manifest


def export_reviewer_bundle(
	paths: ReviewPaths,
	reviewer_id: str,
	output_root: str | Path | None = None,
	bundle_name: str | None = None,
	clean: bool = False,
	decisions: list[str] | tuple[str, ...] | None = None,
	uids: list[str] | tuple[str, ...] | None = None,
	trajectory_tags: list[str] | tuple[str, ...] | None = None,
	create_zip: bool = False,
) -> dict[str, Any]:
	profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
	reviewer_paths = resolve_reviewer_paths(paths, profile["reviewer_id"], profile["reviewer_name"])
	index_payload = read_latest_reviews(paths, reviewer_id=profile["reviewer_id"])
	decision_filter = tuple(
		sorted(
			{
				str(value or "").strip().lower()
				for value in (decisions or ("accept", "reject", "skip"))
				if str(value or "").strip()
			}
		)
	)
	if not decision_filter:
		raise ValueError("decisions must include at least one value")
	uid_filter = {normalize_uid(value) for value in normalize_string_filters(uids)}
	tag_filter = {
		str(value or "").strip()
		for value in normalize_string_filters(trajectory_tags)
		if str(value or "").strip()
	}
	selected_reviews = [
		review
		for review in index_payload.get("reviews", {}).values()
		if str(review.get("decision") or "").strip().lower() in decision_filter
	]
	if uid_filter:
		selected_reviews = [
			review
			for review in selected_reviews
			if normalize_uid(review.get("uid")) in uid_filter
		]
	if tag_filter:
		selected_reviews = [
			review
			for review in selected_reviews
			if tag_filter.intersection(normalize_trajectory_tags(review.get("trajectory_tags")))
		]
	selected_reviews = sorted(
		selected_reviews,
		key=lambda row: (
			str(row.get("timestamp") or ""),
			str(row.get("uid") or row.get("sample_id") or ""),
		),
		reverse=True,
	)
	target_root = (
		Path(output_root).expanduser().resolve()
		if output_root
		else paths.review_root
		/ DEFAULT_REVIEW_EXPORTS_DIR
		/ DEFAULT_REVIEWER_EXPORTS_DIR
		/ profile["reviewer_id"]
		/ (
			bundle_name
			or f"bundle_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
		)
	)
	if clean and target_root.exists():
		shutil.rmtree(target_root)
	target_root.mkdir(parents=True, exist_ok=True)

	reviews_root = target_root / "reviews"
	timeline_root = target_root / DEFAULT_TIMELINE_ANNOTATIONS_DIR
	samples_root = target_root / "samples"
	reviews_root.mkdir(parents=True, exist_ok=True)
	timeline_root.mkdir(parents=True, exist_ok=True)
	samples_root.mkdir(parents=True, exist_ok=True)

	selected_uids = {normalize_uid(review.get("uid")) for review in selected_reviews}
	filtered_latest_payload = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"decision_filter": list(decision_filter),
		"uid_filter": sorted(uid_filter),
		"trajectory_tag_filter": sorted(tag_filter),
		"reviewer_profile": profile,
		"count": len(selected_reviews),
		"reviews": {normalize_uid(review.get("uid")): review for review in selected_reviews},
	}
	_write_json(reviews_root / DEFAULT_REVIEWER_BUNDLE_LATEST_NAME, filtered_latest_payload)
	with open(reviews_root / DEFAULT_REVIEWER_BUNDLE_LEDGER_NAME, "w", encoding="utf-8") as handle:
		for record in load_ledger(reviewer_paths.ledger_path):
			uid = normalize_uid(record.get("uid"))
			if uid not in selected_uids:
				continue
			handle.write(json.dumps(record, ensure_ascii=False) + "\n")

	batch_root = paths.review_root.parent
	batch_meta_path = batch_root / "batch_meta.json"
	batch_meta = _read_json(batch_meta_path) if batch_meta_path.exists() else {}

	exported_samples: list[dict[str, Any]] = []
	export_filenames = get_manifest_export_filenames(paths.result_root)
	for review in selected_reviews:
		uid = normalize_uid(review.get("uid"))
		sample_id = str(review.get("sample_id") or uid).strip() or uid
		uid_dir = paths.result_root / uid
		target_sample_dir = samples_root / sample_id
		target_sample_dir.mkdir(parents=True, exist_ok=True)

		copied_files: dict[str, bool] = {}
		for filename in export_filenames:
			copied_files[filename] = _safe_copy(uid_dir / filename, target_sample_dir / filename)

		review_record = dict(review)
		review_record["exported_at"] = utc_now_iso()
		review_record["export_uid_dir"] = str(uid_dir)
		_write_json(target_sample_dir / "review.json", review_record)

		annotations = read_timeline_annotations(paths, uid, reviewer_id=profile["reviewer_id"])
		_write_json(target_sample_dir / "timeline_annotations.json", annotations)
		_write_json(timeline_root / f"{uid}.json", annotations)

		source_manifest = {
			"schema_version": SCHEMA_VERSION,
			"generated_at": utc_now_iso(),
			"batch_name": str(batch_meta.get("name") or batch_root.name).strip() or batch_root.name,
			"batch_label": str(batch_meta.get("label") or batch_root.name).strip() or batch_root.name,
			"batch_version": str(batch_meta.get("version") or "").strip(),
			"batch_keywords": list(batch_meta.get("keywords") or []),
			"cohort_id": str(batch_meta.get("cohort_id") or "").strip(),
			"days": list(batch_meta.get("days") or []),
			"uid": uid,
			"sample_id": sample_id,
			"reviewer_id": profile["reviewer_id"],
			"reviewer_name": profile["reviewer_name"],
			"source_result_root": str(paths.result_root),
			"source_review_root": str(paths.review_root),
			"source_uid_dir": str(uid_dir),
			"source_review_json": str(target_sample_dir / "review.json"),
			"source_timeline_json": str(target_sample_dir / "timeline_annotations.json"),
			"copied_files": copied_files,
		}
		_write_json(target_sample_dir / DEFAULT_SOURCE_MANIFEST_NAME, source_manifest)
		exported_samples.append(
			{
				"uid": uid,
				"sample_id": sample_id,
				"decision": str(review.get("decision") or ""),
				"timestamp": str(review.get("timestamp") or ""),
				"notes": str(review.get("notes") or ""),
				"trajectory_tags": normalize_trajectory_tags(review.get("trajectory_tags")),
				"reviewer_id": profile["reviewer_id"],
				"reviewer_name": profile["reviewer_name"],
				"sample_dir": str(target_sample_dir),
				"timeline_annotation_path": str(timeline_root / f"{uid}.json"),
				"copied_files": copied_files,
			}
		)

	manifest = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"bundle_name": target_root.name,
		"bundle_root": str(target_root),
		"reviewer_profile": profile,
		"decision_filter": list(decision_filter),
		"uid_filter": sorted(uid_filter),
		"trajectory_tag_filter": sorted(tag_filter),
		"result_root": str(paths.result_root),
		"review_root": str(paths.review_root),
		"batch_meta": batch_meta,
		"sample_count": len(exported_samples),
		"samples": exported_samples,
	}
	zip_path = None
	if create_zip:
		zip_path = target_root.parent / f"{target_root.name}.zip"
		_make_zip_from_directory(target_root, zip_path)
		manifest["zip_path"] = str(zip_path)
	_write_json(target_root / DEFAULT_REVIEWER_BUNDLE_MANIFEST_NAME, manifest)
	return manifest


def export_segment_label_dataset(
	paths: ReviewPaths,
	reviewer_id: str,
	output_root: str | Path | None = None,
	bundle_name: str | None = None,
	clean: bool = False,
	decisions: list[str] | tuple[str, ...] | None = None,
	uids: list[str] | tuple[str, ...] | None = None,
	trajectory_tags: list[str] | tuple[str, ...] | None = None,
	create_zip: bool = False,
	interval_seconds: int = 5,
	timestamp_unit: str = "ms",
	labeled_span_only: bool = False,
) -> dict[str, Any]:
	profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
	base_manifest = export_reviewer_bundle(
		paths,
		reviewer_id=profile["reviewer_id"],
		output_root=output_root,
		bundle_name=bundle_name,
		clean=clean,
		decisions=decisions,
		uids=uids,
		trajectory_tags=trajectory_tags,
		create_zip=False,
	)
	target_root = Path(base_manifest["bundle_root"])
	interval_seconds = max(5, int(interval_seconds or 5))
	ts_unit = _normalize_export_timestamp_unit(timestamp_unit)
	span_only = bool(labeled_span_only)
	dataset_name = f"{target_root.name}_dataset"
	dataset_root = target_root / dataset_name
	if dataset_root.exists():
		shutil.rmtree(dataset_root)
	dataset_root.mkdir(parents=True, exist_ok=True)

	exported_files: list[dict[str, Any]] = []
	for sample in base_manifest.get("samples", []):
		uid = normalize_uid(sample.get("uid"))
		if not uid:
			continue
		track_edits = read_track_edits(
			paths,
			uid,
			reviewer_id=profile["reviewer_id"],
		)
		resolved_annotations = _resolve_export_annotations(
			paths,
			uid,
			profile["reviewer_id"],
		)
		interval_semantics = str(
			resolved_annotations["segment_policy"].get("intervalSemantics")
			or DEFAULT_INTERVAL_SEMANTICS
		)
		uid_dir = paths.result_root / uid
		export_segments = resolved_annotations["segments"]
		span = _labeled_segments_span_ms(export_segments) if span_only else None
		if span_only and not export_segments:
			signal_rows = []
			gps_rows = []
		else:
			signal_rows = _build_export_signal_rows(
				uid,
				uid_dir,
				export_segments,
				interval_semantics,
				clip_span=span,
				track_edits=track_edits,
			)
			gps_rows = _build_export_gps_rows(
				uid,
				uid_dir,
				export_segments,
				interval_semantics,
				interval_seconds,
				track_edits=track_edits,
			)
			if span:
				gps_rows = _filter_export_gps_rows_to_span(gps_rows, span)
		signal_path = dataset_root / f"{uid}_signal.csv"
		gps_path = dataset_root / f"{uid}_gps.csv"
		with open(signal_path, "w", encoding="utf-8", newline="") as handle:
			writer = csv.DictWriter(handle, fieldnames=["uid", "cid", "longitude", "latitude", "t_in", "t_out", "status"])
			writer.writeheader()
			for row in signal_rows:
				writer.writerow({
					**row,
					"t_in": _format_export_epoch_value(int(row["t_in"]), ts_unit),
					"t_out": _format_export_epoch_value(int(row["t_out"]), ts_unit),
				})
		with open(gps_path, "w", encoding="utf-8", newline="") as handle:
			writer = csv.DictWriter(handle, fieldnames=["uid", "longitude", "latitude", "timestamp", "status"])
			writer.writeheader()
			for row in gps_rows:
				writer.writerow({
					**row,
					"timestamp": _format_export_epoch_value(int(row["timestamp"]), ts_unit),
				})
		exported_files.append({
			"uid": uid,
			"signal_csv": str(signal_path),
			"gps_csv": str(gps_path),
			"signal_count": len(signal_rows),
			"gps_count": len(gps_rows),
			"annotation_source": resolved_annotations["annotation_source"],
			"interval_semantics": interval_semantics,
		})

	annotation_sources = sorted({str(item.get("annotation_source") or "") for item in exported_files if str(item.get("annotation_source") or "")})
	interval_semantics_values = sorted({str(item.get("interval_semantics") or "") for item in exported_files if str(item.get("interval_semantics") or "")})
	manifest = {
		"schema_version": SCHEMA_VERSION,
		"generated_at": utc_now_iso(),
		"bundle_name": target_root.name,
		"dataset_name": dataset_name,
		"bundle_root": str(target_root),
		"dataset_root": str(dataset_root),
		"reviewer_profile": profile,
		"interval_seconds": interval_seconds,
		"timestamp_unit": ts_unit,
		"labeled_span_only": span_only,
		"decision_filter": base_manifest.get("decision_filter", []),
		"uid_filter": base_manifest.get("uid_filter", []),
		"trajectory_tag_filter": base_manifest.get("trajectory_tag_filter", []),
		"annotation_sources": annotation_sources,
		"uses_legacy_fallback": "legacy" in annotation_sources,
		"interval_semantics": interval_semantics_values[0] if len(interval_semantics_values) == 1 else "mixed",
		"sample_count": len(exported_files),
		"samples": exported_files,
	}
	zip_path = None
	if create_zip:
		zip_path = target_root.parent / f"{target_root.name}.zip"
		zip_path.parent.mkdir(parents=True, exist_ok=True)
		with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
			for path in sorted(dataset_root.rglob("*")):
				if not path.is_file():
					continue
				archive.write(path, arcname=Path(dataset_name) / path.relative_to(dataset_root))
		manifest["zip_path"] = str(zip_path)
		manifest["download_name"] = f"{dataset_name}.zip"
	_write_json(target_root / "segment_label_dataset_manifest.json", manifest)
	return manifest
