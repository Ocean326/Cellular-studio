from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_DECISIONS = frozenset({"accept", "reject", "skip"})
VALID_REFERENCE_FILES = frozenset({"line.csv", "fmm.csv"})
DEFAULT_LEDGER_NAME = "ledger.jsonl"
DEFAULT_LATEST_NAME = "latest_reviews.json"
DEFAULT_ACCEPTED_LEDGER_NAME = "accepted_reviews.jsonl"
DEFAULT_ACCEPTED_MANIFEST_NAME = "export_manifest.json"
DEFAULT_TIMELINE_ANNOTATIONS_DIR = "timeline_annotations"
DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME = "ledger.jsonl"


@dataclass(frozen=True)
class ReviewPaths:
	project_root: Path
	result_root: Path
	review_root: Path
	ledger_path: Path
	latest_path: Path
	export_root: Path


@dataclass(frozen=True)
class ReviewEntry:
	uid: str
	sample_id: str
	decision: str
	reviewer: str
	timestamp: str
	notes: str = ""
	reference_source: str = ""


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
		Path(export_root).resolve()
		if export_root
		else resolved_review_root / "accepted_assets"
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


def validate_decision(decision: str) -> str:
	value = str(decision or "").strip().lower()
	if value not in VALID_DECISIONS:
		raise ValueError(
			f"Invalid decision: {decision!r}. Expected one of {sorted(VALID_DECISIONS)}"
		)
	return value


def normalize_uid(uid: Any) -> str:
	value = str(uid or "").strip()
	if not value:
		raise ValueError("uid is required")
	return value


def normalize_review_payload(
	payload: dict[str, Any],
	result_root: str | Path | None = None,
) -> ReviewEntry:
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	decision = validate_decision(payload.get("decision", ""))
	reviewer = str(payload.get("reviewer") or "").strip()
	timestamp = str(payload.get("timestamp") or "").strip() or utc_now_iso()
	notes = str(payload.get("notes") or "").strip()
	reference_source = str(payload.get("reference_source") or "").strip()
	if not reference_source and result_root is not None:
		reference_source = choose_reference_source(Path(result_root) / uid)
	return ReviewEntry(
		uid=uid,
		sample_id=sample_id,
		decision=decision,
		reviewer=reviewer,
		timestamp=timestamp,
		notes=notes,
		reference_source=reference_source,
	)


def _read_json(path: Path) -> dict[str, Any]:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2)


def get_timeline_annotations_dir(paths: ReviewPaths) -> Path:
	return paths.review_root / DEFAULT_TIMELINE_ANNOTATIONS_DIR


def get_timeline_annotation_path(paths: ReviewPaths, uid: str) -> Path:
	return get_timeline_annotations_dir(paths) / f"{normalize_uid(uid)}.json"


def get_timeline_annotation_ledger_path(paths: ReviewPaths) -> Path:
	return get_timeline_annotations_dir(paths) / DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME


def _normalize_timeline_pin(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		return {}
	time_value = parse_numeric_value(item.get("time"))
	if time_value is None:
		return {}
	return {
		"id": str(item.get("id") or f"pin-{round(time_value)}").strip() or f"pin-{round(time_value)}",
		"time": time_value,
		"layerKey": str(item.get("layerKey") or "").strip(),
		"label": str(item.get("label") or "").strip(),
	}


def _normalize_timeline_segment(item: Any) -> dict[str, Any]:
	if not isinstance(item, dict):
		return {}
	start_time = parse_numeric_value(item.get("startTime"))
	end_time = parse_numeric_value(item.get("endTime"))
	if start_time is None or end_time is None:
		return {}
	left_time = min(start_time, end_time)
	right_time = max(start_time, end_time)
	return {
		"id": str(item.get("id") or f"segment-{round(left_time)}-{round(right_time)}").strip()
		or f"segment-{round(left_time)}-{round(right_time)}",
		"categoryId": str(item.get("categoryId") or "").strip(),
		"categoryName": str(item.get("categoryName") or "").strip(),
		"color": str(item.get("color") or "").strip(),
		"startTime": left_time,
		"endTime": right_time,
	}


def parse_numeric_value(value: Any) -> float | None:
	if value is None or value == "":
		return None
	try:
		parsed = float(value)
	except (TypeError, ValueError):
		return None
	return parsed if parsed == parsed else None


def normalize_timeline_annotations_payload(payload: dict[str, Any]) -> dict[str, Any]:
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	pins = [_normalize_timeline_pin(item) for item in payload.get("pins", [])]
	segments = [_normalize_timeline_segment(item) for item in payload.get("segments", [])]
	normalized = {
		"uid": uid,
		"sample_id": sample_id,
		"updated_at": str(payload.get("updated_at") or "").strip() or utc_now_iso(),
		"pins": [item for item in pins if item],
		"segments": [item for item in segments if item],
	}
	return normalized


def read_timeline_annotations(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	path = get_timeline_annotation_path(paths, uid)
	if not path.exists():
		normalized_uid = normalize_uid(uid)
		return {
			"uid": normalized_uid,
			"sample_id": normalized_uid,
			"updated_at": "",
			"pins": [],
			"segments": [],
		}
	return normalize_timeline_annotations_payload(_read_json(path))


def write_timeline_annotations(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	record = normalize_timeline_annotations_payload(payload)
	target_path = get_timeline_annotation_path(paths, record["uid"])
	_write_json(target_path, record)
	ledger_path = get_timeline_annotation_ledger_path(paths)
	ledger_path.parent.mkdir(parents=True, exist_ok=True)
	with open(ledger_path, "a", encoding="utf-8") as handle:
		handle.write(json.dumps(record, ensure_ascii=False) + "\n")
	return record


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


def build_latest_reviews(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
	latest: dict[str, dict[str, Any]] = {}
	for entry in entries:
		uid = normalize_uid(entry.get("uid"))
		latest[uid] = dict(entry)
	return latest


def build_review_index(entries: list[dict[str, Any]]) -> dict[str, Any]:
	reviews = build_latest_reviews(entries)
	counts = {decision: 0 for decision in VALID_DECISIONS}
	for review in reviews.values():
		decision = str(review.get("decision") or "").strip().lower()
		if decision in counts:
			counts[decision] += 1
	return {
		"generated_at": utc_now_iso(),
		"count": len(reviews),
		"counts": counts,
		"reviews": reviews,
	}


def read_latest_reviews(paths: ReviewPaths) -> dict[str, Any]:
	if paths.latest_path.exists():
		return _read_json(paths.latest_path)
	return refresh_latest_reviews(paths)


def refresh_latest_reviews(paths: ReviewPaths) -> dict[str, Any]:
	entries = load_ledger(paths.ledger_path)
	index_payload = build_review_index(entries)
	_write_json(paths.latest_path, index_payload)
	return index_payload


def write_review(paths: ReviewPaths, payload: dict[str, Any]) -> dict[str, Any]:
	entry = normalize_review_payload(payload, result_root=paths.result_root)
	if entry.decision == "accept":
		validate_accept_reference(
			paths.result_root / entry.uid,
			entry.reference_source,
			entry.sample_id,
		)
	paths.review_root.mkdir(parents=True, exist_ok=True)
	with open(paths.ledger_path, "a", encoding="utf-8") as handle:
		handle.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
	index_payload = refresh_latest_reviews(paths)
	return index_payload["reviews"][entry.uid]


def get_review(paths: ReviewPaths, uid: str) -> dict[str, Any] | None:
	index_payload = read_latest_reviews(paths)
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


def choose_reference_source(uid_dir: str | Path) -> str:
	base = Path(uid_dir)
	for candidate in ("line.csv", "fmm.csv"):
		if csv_has_data(base / candidate):
			return candidate
	return ""


def validate_accept_reference(uid_dir: str | Path, reference_source: str, sample_id: str) -> str:
	base = Path(uid_dir)
	chosen = str(reference_source or "").strip()
	if chosen not in VALID_REFERENCE_FILES:
		chosen = choose_reference_source(base)
	if chosen not in VALID_REFERENCE_FILES:
		raise ValueError(
			f"Accepted sample {sample_id} requires a usable line.csv or fmm.csv reference asset."
		)
	if not csv_has_data(base / chosen):
		raise ValueError(
			f"Accepted sample {sample_id} expects reference source {chosen}, but the file is missing or empty."
		)
	return chosen


def _safe_copy(src: Path, dst: Path) -> bool:
	if not src.exists() or not src.is_file():
		return False
	dst.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(src, dst)
	return True


def export_accepted_assets(paths: ReviewPaths, clean: bool = False) -> dict[str, Any]:
	index_payload = read_latest_reviews(paths)
	accepted = [
		review
		for review in index_payload.get("reviews", {}).values()
		if str(review.get("decision") or "").lower() == "accept"
	]

	if clean and paths.export_root.exists():
		shutil.rmtree(paths.export_root)

	samples_root = paths.export_root / "samples"
	samples_root.mkdir(parents=True, exist_ok=True)

	accepted_ledger_path = paths.export_root / DEFAULT_ACCEPTED_LEDGER_NAME
	manifest_path = paths.export_root / DEFAULT_ACCEPTED_MANIFEST_NAME

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
		)
		reference_exported = False
		if reference_name in VALID_REFERENCE_FILES:
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
				"reviewer": review.get("reviewer", ""),
				"timestamp": review.get("timestamp", ""),
				"notes": review.get("notes", ""),
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
		"generated_at": utc_now_iso(),
		"result_root": str(paths.result_root),
		"review_root": str(paths.review_root),
		"export_root": str(paths.export_root),
		"accepted_count": len(exported_samples),
		"samples": exported_samples,
	}
	_write_json(manifest_path, manifest)
	return manifest
