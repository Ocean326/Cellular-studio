from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


VALID_DECISIONS = frozenset({"accept", "reject", "skip"})
LEGACY_REFERENCE_FILES = ("line.csv", "fmm.csv")

SCHEMA_VERSION = 2

DEFAULT_LEDGER_NAME = "ledger.jsonl"
DEFAULT_LATEST_NAME = "latest_reviews.json"
DEFAULT_ACCEPTED_LEDGER_NAME = "accepted_reviews.jsonl"
DEFAULT_ACCEPTED_MANIFEST_NAME = "export_manifest.json"
DEFAULT_TIMELINE_ANNOTATIONS_DIR = "timeline_annotations"
DEFAULT_TIMELINE_ANNOTATIONS_LEDGER_NAME = "ledger.jsonl"
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
REVIEWER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

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


def _dedupe_preserve_order(items: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for item in items:
		value = str(item or "").strip()
		if not value or value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result


def _read_result_manifest(result_root: str | Path) -> dict[str, Any]:
	manifest_path = Path(result_root) / "manifest.json"
	if not manifest_path.exists():
		return {}
	try:
		return _read_json(manifest_path)
	except Exception:
		return {}


def _normalize_manifest_layer_specs(manifest_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
	layer_order = [
		str(item or "").strip()
		for item in manifest_payload.get("layers", []) or []
		if str(item or "").strip()
	]
	layer_specs = manifest_payload.get("layer_specs") if isinstance(manifest_payload.get("layer_specs"), dict) else {}
	legacy_layer_styles = (
		manifest_payload.get("layer_styles") if isinstance(manifest_payload.get("layer_styles"), dict) else {}
	)
	if not layer_order:
		layer_order = _dedupe_preserve_order([*legacy_layer_styles.keys(), *layer_specs.keys()])
	specs: dict[str, dict[str, Any]] = {}
	for layer in layer_order:
		merged: dict[str, Any] = {}
		if isinstance(legacy_layer_styles.get(layer), dict):
			merged.update(legacy_layer_styles[layer])
		if isinstance(layer_specs.get(layer), dict):
			merged.update(layer_specs[layer])
		filename = str(merged.get("filename") or f"{layer}.csv").strip() or f"{layer}.csv"
		merged["filename"] = filename
		specs[layer] = merged
	return specs


def get_manifest_review_reference_files(result_root: str | Path) -> list[str]:
	manifest_payload = _read_result_manifest(result_root)
	if "review_reference_files" in manifest_payload and isinstance(manifest_payload.get("review_reference_files"), list):
		reference_files = [
			str(item or "").strip()
			for item in manifest_payload.get("review_reference_files", []) or []
			if str(item or "").strip()
		]
		return _dedupe_preserve_order(reference_files)
	specs = _normalize_manifest_layer_specs(manifest_payload)
	reference_layers = {
		str(item or "").strip()
		for item in manifest_payload.get("review_reference_layers", []) or []
		if str(item or "").strip()
	}
	from_specs = [
		str(spec.get("filename") or "").strip()
		for layer, spec in specs.items()
		if spec.get("review_reference") or layer in reference_layers
	]
	if from_specs:
		return _dedupe_preserve_order(from_specs)
	return list(LEGACY_REFERENCE_FILES)


def get_manifest_export_filenames(result_root: str | Path) -> list[str]:
	manifest_payload = _read_result_manifest(result_root)
	specs = _normalize_manifest_layer_specs(manifest_payload)
	declared = [str(spec.get("filename") or "").strip() for spec in specs.values()]
	return _dedupe_preserve_order(
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


def normalize_reviewer_id(display_name: Any, explicit_reviewer_id: Any | None = None) -> str:
	explicit = str(explicit_reviewer_id or "").strip().lower()
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


def normalize_timeline_annotations_payload(
	paths: ReviewPaths,
	payload: dict[str, Any],
) -> dict[str, Any]:
	profile = _reviewer_profile_from_payload(paths, payload)
	uid = normalize_uid(payload.get("uid"))
	sample_id = str(payload.get("sample_id") or uid).strip() or uid
	pins = [_normalize_timeline_pin(item) for item in payload.get("pins", [])]
	segments = [_normalize_timeline_segment(item) for item in payload.get("segments", [])]
	return {
		"schema_version": SCHEMA_VERSION,
		"uid": uid,
		"sample_id": sample_id,
		"reviewer_id": profile["reviewer_id"],
		"reviewer_name": profile["reviewer_name"],
		"reviewer": profile["reviewer_name"],
		"updated_at": str(payload.get("updated_at") or "").strip() or utc_now_iso(),
		"pins": [item for item in pins if item],
		"segments": [item for item in segments if item],
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
		"pins": [],
		"segments": [],
	}


def _read_legacy_timeline_annotations(paths: ReviewPaths, uid: str) -> dict[str, Any]:
	path = get_legacy_timeline_annotation_path(paths, uid)
	if not path.exists():
		return _empty_timeline_annotations(uid)
	payload = _read_json(path)
	normalized = {
		**_empty_timeline_annotations(uid),
		"updated_at": str(payload.get("updated_at") or "").strip(),
		"pins": [_normalize_timeline_pin(item) for item in payload.get("pins", []) if _normalize_timeline_pin(item)],
		"segments": [_normalize_timeline_segment(item) for item in payload.get("segments", []) if _normalize_timeline_segment(item)],
	}
	return normalized


def read_timeline_annotations(
	paths: ReviewPaths,
	uid: str,
	reviewer_id: str | None = None,
) -> dict[str, Any]:
	if reviewer_id:
		profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
		reviewer_paths = resolve_reviewer_paths(paths, profile["reviewer_id"], profile["reviewer_name"])
		path = reviewer_paths.timeline_root / f"{normalize_uid(uid)}.json"
		if not path.exists():
			return _empty_timeline_annotations(uid, profile["reviewer_id"], profile["reviewer_name"])
		payload = _read_json(path)
		return {
			**_empty_timeline_annotations(uid, profile["reviewer_id"], profile["reviewer_name"]),
			"updated_at": str(payload.get("updated_at") or "").strip(),
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
	selected_reviews = [
		review
		for review in index_payload.get("reviews", {}).values()
		if str(review.get("decision") or "").strip().lower() in decision_filter
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
