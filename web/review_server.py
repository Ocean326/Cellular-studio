from __future__ import annotations

import argparse
import json
import posixpath
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import uuid4

try:
	from .review_lib import (
		ReviewPaths,
		ensure_reviewer_profile,
		export_accepted_assets,
		export_segment_label_dataset,
		export_reviewer_bundle,
		export_review_aggregate,
		get_review,
		get_timeline_annotation_aggregate,
		get_uid_review_aggregate,
		list_reviewers,
		read_latest_reviews,
		read_track_edits,
		read_timeline_annotations,
		resolve_review_paths,
		write_track_edits,
		write_timeline_annotations,
		write_review,
	)
	from .upload_lib import (
		ActorIdentity,
		can_actor_view_batch,
		generate_asset_id,
		generate_batch_name,
		generate_upload_id,
		normalize_visibility_scope,
		parse_actor_identity_from_headers,
		read_batch_catalog_metadata,
		read_json_metadata,
		read_upload_metadata,
		resolve_asset_catalog_path,
		resolve_asset_dataset_root,
		resolve_batch_catalog_path,
		resolve_published_batch_root,
		resolve_upload_catalog_path,
		resolve_upload_storage_layout,
		write_batch_catalog_metadata,
		write_json_metadata,
		write_upload_metadata,
	)
	from .offline_tile_lib import OfflineTileService
except ImportError:
	from review_lib import (  # type: ignore
		ReviewPaths,
		ensure_reviewer_profile,
		export_accepted_assets,
		export_segment_label_dataset,
		export_reviewer_bundle,
		export_review_aggregate,
		get_review,
		get_timeline_annotation_aggregate,
		get_uid_review_aggregate,
		list_reviewers,
		read_latest_reviews,
		read_track_edits,
		read_timeline_annotations,
		resolve_review_paths,
		write_track_edits,
		write_timeline_annotations,
		write_review,
	)
	from upload_lib import (  # type: ignore
		ActorIdentity,
		can_actor_view_batch,
		generate_asset_id,
		generate_batch_name,
		generate_upload_id,
		normalize_visibility_scope,
		parse_actor_identity_from_headers,
		read_batch_catalog_metadata,
		read_json_metadata,
		read_upload_metadata,
		resolve_asset_catalog_path,
		resolve_asset_dataset_root,
		resolve_batch_catalog_path,
		resolve_published_batch_root,
		resolve_upload_catalog_path,
		resolve_upload_storage_layout,
		write_batch_catalog_metadata,
		write_json_metadata,
		write_upload_metadata,
	)
	try:
		from offline_tile_lib import OfflineTileService  # type: ignore
	except ImportError:  # pragma: no cover
		OfflineTileService = None  # type: ignore

try:
	from ..scripts.server_batch_lib import publish_batch
	from ..scripts.user_upload_adapter_lib import (
		UserUploadAdapterError,
		build_signal6_result,
		build_trajectory4_result,
		detect_user_upload_type,
		normalize_signal6_pipeline_mode,
		normalize_user_upload_field_mapping,
	)
except ImportError:
	from scripts.server_batch_lib import publish_batch  # type: ignore
	from scripts.user_upload_adapter_lib import (  # type: ignore
		UserUploadAdapterError,
		build_signal6_result,
		build_trajectory4_result,
		detect_user_upload_type,
		normalize_signal6_pipeline_mode,
		normalize_user_upload_field_mapping,
	)

DEFAULT_BATCH_META_NAME = "batch_meta.json"
DEFAULT_BATCH_NAME = "current"
DEFAULT_UPLOAD_MAX_BYTES = 2 * 1024 * 1024 * 1024
UPLOAD_STATUS_NAME = "upload_status.json"
UPLOAD_FILE_NAME = "payload.zip"
SAFE_UPLOAD_RE = re.compile(r"[^A-Za-z0-9._-]+")
SAFE_SOURCE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
USER_UPLOAD_TYPES = frozenset({"trajectory4", "signal6", "auto"})
ANNOTATION_MODES = frozenset({"annotatable", "view_only"})
DEFAULT_LOCAL_ACTOR_ID = "local-dev"
DEFAULT_LOCAL_ACTOR_NAME = "Local Dev"


@dataclass(frozen=True)
class ReviewBatch:
	name: str
	label: str
	batch_root: Path
	paths: ReviewPaths
	metadata: dict
	data_base: str


@dataclass(frozen=True)
class AdminUploadItem:
	upload_id: str
	upload_root: Path
	status_path: Path
	payload: dict


def _read_json(path: Path) -> dict:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def _utc_now() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_relative_to(path: Path, parent: Path) -> bool:
	try:
		path.relative_to(parent)
		return True
	except ValueError:
		return False


def _sanitize_upload_name(raw_name: str) -> str:
	name = Path(raw_name.strip()).name
	if not name:
		raise ValueError("upload name is required")
	suffix = Path(name).suffix.lower()
	if suffix != ".zip":
		raise ValueError("only .zip uploads are supported")
	stem = Path(name).stem
	safe_stem = SAFE_UPLOAD_RE.sub("_", stem).strip("._-")
	if not safe_stem:
		raise ValueError("upload name must contain letters or numbers")
	return f"{safe_stem}.zip"


def _sanitize_source_name(raw_name: str) -> str:
	name = Path(raw_name.strip()).name
	if not name:
		raise ValueError("source file name is required")
	suffix = Path(name).suffix.lower()
	if suffix != ".csv":
		raise ValueError("only .csv uploads are currently supported")
	stem = Path(name).stem
	safe_stem = SAFE_SOURCE_NAME_RE.sub("_", stem).strip("._-")
	if not safe_stem:
		raise ValueError("source file name must contain letters or numbers")
	return f"{safe_stem}.csv"


def _resolve_runtime_root(project_root: Path, batches_root: Path | None) -> Path:
	if batches_root is not None:
		return batches_root.resolve().parent
	return project_root.resolve()


def _iter_candidate_batch_roots(batches_root: Path) -> list[Path]:
	if not batches_root.exists():
		return []
	seen: set[Path] = set()
	candidates: list[Path] = []

	def register(path: Path) -> None:
		if not path.is_dir():
			return
		resolved = path.resolve()
		if resolved in seen:
			return
		if not ((path / DEFAULT_BATCH_META_NAME).exists() or (path / "result").exists()):
			return
		seen.add(resolved)
		candidates.append(path)

	for child in sorted(batches_root.iterdir()):
		if not child.is_dir():
			continue
		if child.name == "public":
			for batch_root in sorted(child.iterdir()):
				register(batch_root)
			continue
		if child.name == "private":
			for owner_root in sorted(child.iterdir()):
				if not owner_root.is_dir():
					continue
				for batch_root in sorted(owner_root.iterdir()):
					register(batch_root)
			continue
		register(child)
	return candidates


def _write_json(path: Path, payload: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2)
		handle.write("\n")


def _read_upload_item(upload_root: Path) -> AdminUploadItem | None:
	status_path = upload_root / UPLOAD_STATUS_NAME
	if not status_path.exists():
		return None
	try:
		payload = _read_json(status_path)
	except Exception:
		return None
	upload_id = str(payload.get("upload_id") or upload_root.name).strip() or upload_root.name
	return AdminUploadItem(upload_id=upload_id, upload_root=upload_root, status_path=status_path, payload=payload)


def _list_incoming_items(incoming_root: Path) -> list[dict]:
	items: list[dict] = []
	if not incoming_root.exists():
		return items
	for child in incoming_root.iterdir():
		if not child.is_dir():
			continue
		item = _read_upload_item(child)
		if item is None:
			continue
		payload = dict(item.payload)
		payload.setdefault("upload_id", item.upload_id)
		payload.setdefault("upload_root", str(item.upload_root))
		items.append(payload)
	items.sort(
		key=lambda payload: (
			str(payload.get("created_at") or ""),
			str(payload.get("upload_id") or ""),
		),
		reverse=True,
	)
	return items


def _safe_uid_count(result_root: Path) -> int | None:
	manifest_path = result_root / "manifest.json"
	if not manifest_path.exists():
		return None
	try:
		payload = _read_json(manifest_path)
	except Exception:
		return None
	uids = payload.get("uids")
	return len(uids) if isinstance(uids, list) else None


def _build_batch_payload(batch: ReviewBatch) -> dict:
	uid_count = _safe_uid_count(batch.paths.result_root)
	ui_config = batch.metadata.get("ui_config")
	if not isinstance(ui_config, dict):
		ui_config = {}
	visibility_scope = str(batch.metadata.get("visibility_scope") or batch.metadata.get("visibility") or "public").strip() or "public"
	annotation_mode = str(batch.metadata.get("annotation_mode") or "annotatable").strip() or "annotatable"
	return {
		"name": batch.name,
		"label": batch.label,
		"data_base": batch.data_base,
		"batch_root": str(batch.batch_root),
		"result_root": str(batch.paths.result_root),
		"review_root": str(batch.paths.review_root),
		"export_root": str(batch.paths.export_root),
		"created_at": batch.metadata.get("created_at") or batch.metadata.get("generated_at") or "",
		"version": batch.metadata.get("version") or "",
		"keywords": batch.metadata.get("keywords") or [],
		"status": batch.metadata.get("status") or "published",
		"visibility_scope": visibility_scope,
		"annotation_mode": annotation_mode,
		"owner_actor_id": batch.metadata.get("owner_actor_id") or "",
		"uid_count": uid_count,
		"ui_config": ui_config,
	}


def build_single_batch(paths: ReviewPaths) -> ReviewBatch:
	name = DEFAULT_BATCH_NAME
	return ReviewBatch(
		name=name,
		label=paths.result_root.name or name,
		batch_root=paths.result_root.parent,
		paths=paths,
		metadata={},
		data_base=f"/batch-data/{name}",
	)


def discover_batches(
	project_root: Path,
	batches_root: Path,
	batch_catalog_root: Path | None = None,
) -> tuple[dict[str, ReviewBatch], list[str]]:
	batches: dict[str, ReviewBatch] = {}
	order: list[tuple[str, str]] = []
	if not batches_root.exists():
		return batches, []

	for child in _iter_candidate_batch_roots(batches_root):
		result_root = child / "result"
		metadata = {}
		meta_path = child / DEFAULT_BATCH_META_NAME
		if meta_path.exists():
			try:
				metadata = _read_json(meta_path)
			except Exception:
				metadata = {}
		if not result_root.exists():
			source_result_root = metadata.get("source_result_root")
			if source_result_root:
				candidate = Path(str(source_result_root)).expanduser().resolve()
				if candidate.exists():
					result_root = candidate
		if not result_root.exists():
			continue
		if batch_catalog_root is not None:
			preferred_name = str(metadata.get("name") or metadata.get("batch_name") or child.name).strip() or child.name
			catalog_metadata = read_batch_catalog_metadata(batch_catalog_root / f"{preferred_name}.json")
			if catalog_metadata:
				merged_metadata = dict(metadata)
				merged_metadata.update(catalog_metadata)
				metadata = merged_metadata
		name = str(metadata.get("name") or metadata.get("batch_name") or child.name).strip() or child.name
		label = str(metadata.get("label") or name).strip() or name
		review_root = child / "review"
		export_root = child / "accepted_assets"
		paths = resolve_review_paths(
			project_root=project_root,
			result_root=result_root,
			review_root=review_root,
			export_root=export_root,
		)
		batches[name] = ReviewBatch(
			name=name,
			label=label,
			batch_root=child,
			paths=paths,
			metadata=metadata,
			data_base=f"/batch-data/{name}",
		)
		sort_key = str(metadata.get("created_at") or metadata.get("generated_at") or child.name)
		order.append((sort_key, name))

	order.sort(key=lambda item: (item[0], item[1]), reverse=True)
	return batches, [name for _, name in order]


class ReviewRequestHandler(SimpleHTTPRequestHandler):
	server_version = "CellularQualityReviewServer/0.1"

	def __init__(
		self,
		*args,
		directory: str | None = None,
		review_paths=None,
		batches_root: Path | None = None,
		batches: dict[str, ReviewBatch] | None = None,
		batch_order: list[str] | None = None,
		default_batch: str | None = None,
		incoming_root: Path | None = None,
			runtime_root: Path | None = None,
			offline_tile_cache_root: Path | None = None,
			upload_max_bytes: int = DEFAULT_UPLOAD_MAX_BYTES,
			signal6_pipeline_mode: str = "v311",
			**kwargs,
		):
		self.review_paths = review_paths
		self.batches_root = Path(batches_root).resolve() if batches_root else None
		self.runtime_root = (
			Path(runtime_root).resolve()
			if runtime_root is not None
			else _resolve_runtime_root(self.review_paths.project_root, self.batches_root)
		)
		published_root = self.batches_root if self.batches_root is not None else self.runtime_root / "published"
		self.upload_layout = resolve_upload_storage_layout(
			self.runtime_root,
			published_root=published_root,
		)
		self.batch_catalog_root = self.upload_layout.catalog_batches_root
		self.batches = batches or {}
		self.batch_order = batch_order or list(self.batches.keys())
		self.default_batch = default_batch or (self.batch_order[0] if self.batch_order else None)
		self.incoming_root = (
			Path(incoming_root).resolve()
			if incoming_root is not None
			else (self.runtime_root / "incoming").resolve()
		)
		self.offline_tile_cache_root = (
			Path(offline_tile_cache_root).resolve()
			if offline_tile_cache_root is not None
			else (self.runtime_root / "offline_tiles_cache").resolve()
		)
		self._offline_tile_service = None
		self.upload_max_bytes = max(int(upload_max_bytes or DEFAULT_UPLOAD_MAX_BYTES), 1)
		self.signal6_pipeline_mode = normalize_signal6_pipeline_mode(signal6_pipeline_mode)
		super().__init__(*args, directory=directory, **kwargs)

	def end_headers(self) -> None:
		self.send_header("Cache-Control", "no-store")
		super().end_headers()

	def log_message(self, format: str, *args) -> None:
		super().log_message(format, *args)

	def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
		body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _send_error_json(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
		self._send_json({"error": message}, status=status)

	def _send_png(self, payload: bytes, status: int = HTTPStatus.OK) -> None:
		self.send_response(status)
		self.send_header("Content-Type", "image/png")
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)

	def _send_file(
		self,
		path: Path,
		*,
		content_type: str = "application/octet-stream",
		download_name: str | None = None,
		status: int = HTTPStatus.OK,
	) -> None:
		payload = path.read_bytes()
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(payload)))
		if download_name:
			self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
		self.end_headers()
		self.wfile.write(payload)

	def _get_offline_tile_service(self):
		if self._offline_tile_service is not None:
			return self._offline_tile_service
		if OfflineTileService is None:
			raise RuntimeError("offline tile service is unavailable; missing offline_tile_lib dependencies")
		self._offline_tile_service = OfflineTileService(
			project_root=self.review_paths.project_root,
			runtime_root=self.runtime_root,
			cache_root=self.offline_tile_cache_root,
		)
		return self._offline_tile_service

	def _send_admin_error(
		self,
		code: str,
		message: str,
		status: int = HTTPStatus.BAD_REQUEST,
		**details,
	) -> None:
		payload = {"status": "error", "code": code, "error": message}
		payload.update(details)
		self._send_json(payload, status=status)

	def _incoming_enabled(self) -> bool:
		return self.incoming_root is not None

	def _current_actor(self) -> ActorIdentity:
		identity = parse_actor_identity_from_headers(self.headers)
		if identity.actor_id:
			display_name = identity.display_name or identity.actor_id
			return ActorIdentity(
				actor_id=identity.actor_id,
				display_name=display_name,
				source_header=identity.source_header,
			)
		return ActorIdentity(
			actor_id=DEFAULT_LOCAL_ACTOR_ID,
			display_name=DEFAULT_LOCAL_ACTOR_NAME,
			source_header="local-default",
		)

	def _current_actor_role(self) -> str:
		return (
			str(
				self.headers.get("X-Actor-Role")
				or self.headers.get("X-Forwarded-Role")
				or self.headers.get("X-Role")
				or "developer"
			).strip()
			or "developer"
		)

	def _actor_payload(self) -> dict:
		actor = self._current_actor()
		return {
			"actor_id": actor.actor_id,
			"display_name": actor.display_name,
			"role": self._current_actor_role(),
			"source_header": actor.source_header,
		}

	def _incoming_state_payload(self) -> dict:
		return {
			"enabled": self._incoming_enabled(),
			"incoming_root": str(self.incoming_root) if self.incoming_root else "",
			"upload_max_bytes": self.upload_max_bytes,
			"items": _list_incoming_items(self.incoming_root) if self.incoming_root else [],
		}

	def _refresh_batches(self) -> None:
		if not self.batches_root:
			return
		batches, batch_order = discover_batches(
			self.review_paths.project_root,
			self.batches_root,
			batch_catalog_root=self.batch_catalog_root,
		)
		self.batches = batches
		self.batch_order = batch_order
		if self.default_batch not in self.batches:
			self.default_batch = batch_order[0] if batch_order else None

	def _read_json_body(self) -> dict:
		content_length = int(self.headers.get("Content-Length", "0") or "0")
		if content_length <= 0:
			return {}
		raw_body = self.rfile.read(content_length)
		if not raw_body:
			return {}
		return json.loads(raw_body.decode("utf-8"))

	def _read_raw_body(self) -> bytes:
		content_length = int(self.headers.get("Content-Length", "0") or "0")
		if content_length <= 0:
			raise ValueError("Content-Length must be a positive integer")
		if content_length > self.upload_max_bytes:
			raise ValueError(f"upload exceeds max size of {self.upload_max_bytes} bytes")
		raw_body = self.rfile.read(content_length)
		if len(raw_body) != content_length:
			raise ValueError(f"expected {content_length} bytes but received {len(raw_body)}")
		return raw_body

	def _visible_batch_names(self, actor_id: str) -> list[str]:
		return [
			name
			for name in self.batch_order
			if name in self.batches and can_actor_view_batch(self.batches[name].metadata, actor_id)
		]

	def _resolve_batch_name(
		self,
		parsed,
		payload: dict | None = None,
		actor: ActorIdentity | None = None,
	) -> str:
		self._refresh_batches()
		if not self.batches:
			return DEFAULT_BATCH_NAME
		actor_identity = actor or self._current_actor()
		visible_batch_names = self._visible_batch_names(actor_identity.actor_id)
		query = parse_qs(parsed.query)
		if payload and payload.get("batch"):
			batch_name = str(payload.get("batch")).strip()
			if batch_name:
				if batch_name not in self.batches:
					raise ValueError(f"Unknown batch: {batch_name}")
				if batch_name not in visible_batch_names:
					raise PermissionError(f"Access denied for batch: {batch_name}")
				return batch_name
		if query.get("batch"):
			batch_name = str(query["batch"][0]).strip()
			if batch_name:
				if batch_name not in self.batches:
					raise ValueError(f"Unknown batch: {batch_name}")
				if batch_name not in visible_batch_names:
					raise PermissionError(f"Access denied for batch: {batch_name}")
				return batch_name
		if self.default_batch and self.default_batch in visible_batch_names:
			return self.default_batch
		if visible_batch_names:
			return visible_batch_names[0]
		raise PermissionError("No visible batch for current actor")

	def _resolve_review_paths(
		self,
		parsed,
		payload: dict | None = None,
		actor: ActorIdentity | None = None,
	) -> tuple[str, ReviewPaths]:
		# Refresh per-request so endpoints keep working after operator publishes batches at runtime.
		self._refresh_batches()
		if not self.batches:
			return DEFAULT_BATCH_NAME, self.review_paths
		batch_name = self._resolve_batch_name(parsed, payload, actor=actor)
		batch = self.batches.get(batch_name)
		if batch is None:
			raise ValueError(f"Unknown batch: {batch_name}")
		return batch_name, batch.paths

	def _batch_list_payload(self, actor: ActorIdentity | None = None) -> dict:
		self._refresh_batches()
		if not self.batches:
			batch = build_single_batch(self.review_paths)
			return {
				"current_batch": batch.name,
				"batches": [_build_batch_payload(batch)],
			}
		actor_identity = actor or self._current_actor()
		visible_batch_names = self._visible_batch_names(actor_identity.actor_id)
		current_batch = self.default_batch if self.default_batch in visible_batch_names else (visible_batch_names[0] if visible_batch_names else None)
		return {
			"current_batch": current_batch,
			"batches": [_build_batch_payload(self.batches[name]) for name in visible_batch_names],
		}

	def _send_upload_error(
		self,
		code: str,
		message: str,
		status: int = HTTPStatus.BAD_REQUEST,
		**details,
	) -> None:
		payload = {"status": "error", "code": code, "error": message}
		payload.update(details)
		self._send_json(payload, status=status)

	def _normalize_upload_type(self, value) -> str:
		upload_type = str(value or "").strip().lower()
		if upload_type not in USER_UPLOAD_TYPES:
			raise ValueError(f"Unsupported upload_type: {value!r}")
		return upload_type

	def _resolve_actual_upload_type(self, source_path: Path, payload: dict) -> str:
		requested_upload_type = self._normalize_upload_type(payload.get("upload_type"))
		field_mapping = payload.get("field_mapping")
		if requested_upload_type != "auto":
			try:
				return detect_user_upload_type(
					source_path,
					requested_upload_type=requested_upload_type,
					field_mapping=field_mapping,
				)
			except Exception:
				return requested_upload_type
		return detect_user_upload_type(
			source_path,
			requested_upload_type=requested_upload_type,
			field_mapping=field_mapping,
		)

	def _normalize_annotation_mode(self, value) -> str:
		annotation_mode = str(value or "annotatable").strip().lower() or "annotatable"
		if annotation_mode not in ANNOTATION_MODES:
			raise ValueError(f"Unsupported annotation_mode: {value!r}")
		return annotation_mode

	def _resolve_upload_record(self, upload_id: str) -> tuple[Path, Path, dict]:
		upload_root = self.incoming_root / upload_id
		catalog_path = resolve_upload_catalog_path(self.upload_layout, upload_id)
		payload = read_json_metadata(catalog_path)
		if not payload:
			payload = read_upload_metadata(upload_root)
		if not payload:
			raise FileNotFoundError(f"upload not found: {upload_id}")
		payload = dict(payload)
		payload.setdefault("upload_id", upload_id)
		payload.setdefault("upload_root", str(upload_root))
		return upload_root, catalog_path, payload

	def _persist_upload_record(self, upload_root: Path, catalog_path: Path, payload: dict) -> dict:
		record = dict(payload)
		record["upload_id"] = str(record.get("upload_id") or upload_root.name).strip() or upload_root.name
		record["upload_root"] = str(upload_root)
		record["updated_at"] = _utc_now()
		write_upload_metadata(upload_root, record)
		write_json_metadata(catalog_path, record)
		return record

	def _list_upload_items(self, actor: ActorIdentity) -> list[dict]:
		items: list[dict] = []
		root = self.upload_layout.catalog_uploads_root
		if not root.exists():
			return items
		for metadata_path in root.glob("*.json"):
			payload = read_json_metadata(metadata_path)
			if not payload:
				continue
			owner_actor_id = str(payload.get("owner_actor_id") or "").strip()
			if owner_actor_id and owner_actor_id != actor.actor_id:
				continue
			payload = dict(payload)
			payload.setdefault("upload_id", metadata_path.stem)
			items.append(payload)
		items.sort(
			key=lambda payload: (
				str(payload.get("created_at") or ""),
				str(payload.get("upload_id") or ""),
			),
			reverse=True,
		)
		return items

	def _resolve_upload_source_path(self, upload_root: Path, payload: dict) -> Path:
		source_path = str(payload.get("source_path") or "").strip()
		if source_path:
			resolved = Path(source_path).expanduser().resolve()
			if resolved.exists():
				return resolved
		for child in sorted(upload_root.iterdir()) if upload_root.exists() else []:
			if child.name in {UPLOAD_STATUS_NAME, "payload.zip", "payload.zip.part", "intake_report.json"}:
				continue
			if child.is_file() and child.suffix.lower() == ".csv":
				return child.resolve()
		raise FileNotFoundError(f"source file not found for upload: {payload.get('upload_id') or upload_root.name}")

	def _ensure_upload_owner(self, payload: dict, actor: ActorIdentity) -> None:
		owner_actor_id = str(payload.get("owner_actor_id") or "").strip()
		if owner_actor_id and owner_actor_id != actor.actor_id:
			raise PermissionError(f"upload does not belong to actor {actor.actor_id}")

	def _upsert_batch_catalog_metadata(self, batch_name: str, metadata: dict) -> Path:
		catalog_path = resolve_batch_catalog_path(self.upload_layout, batch_name)
		record = dict(metadata)
		record.setdefault("batch_name", batch_name)
		write_batch_catalog_metadata(catalog_path, record)
		return catalog_path

	def _mark_batch_deleted(self, batch_name: str) -> None:
		catalog_path = resolve_batch_catalog_path(self.upload_layout, batch_name)
		catalog_payload = read_batch_catalog_metadata(catalog_path)
		if catalog_payload:
			catalog_payload = dict(catalog_payload)
			catalog_payload["status"] = "deleted"
			catalog_payload["hidden_at"] = catalog_payload.get("hidden_at") or _utc_now()
			catalog_payload["deleted_at"] = _utc_now()
			write_batch_catalog_metadata(catalog_path, catalog_payload)
		self._refresh_batches()
		batch = self.batches.get(batch_name)
		if batch is None:
			return
		meta_path = batch.batch_root / DEFAULT_BATCH_META_NAME
		meta_payload = _read_json(meta_path) if meta_path.exists() else {}
		meta_payload["status"] = "deleted"
		meta_payload["hidden_at"] = meta_payload.get("hidden_at") or _utc_now()
		meta_payload["deleted_at"] = _utc_now()
		_write_json(meta_path, meta_payload)
		self._refresh_batches()

	def _publish_upload_preview(self, upload_root: Path, catalog_path: Path, payload: dict, actor: ActorIdentity) -> dict:
		self._ensure_upload_owner(payload, actor)
		annotation_mode = self._normalize_annotation_mode(payload.get("annotation_mode"))
		visibility_scope = normalize_visibility_scope(payload.get("visibility_scope"))
		source_path = self._resolve_upload_source_path(upload_root, payload)
		upload_type = self._resolve_actual_upload_type(source_path, payload)
		field_mapping = normalize_user_upload_field_mapping(upload_type, payload.get("field_mapping"))
		asset_id = str(payload.get("asset_id") or "").strip() or generate_asset_id(upload_type, actor.actor_id)
		batch_name = str(payload.get("batch_name") or "").strip() or generate_batch_name(upload_type, actor.actor_id)
		asset_root = resolve_asset_dataset_root(self.upload_layout, actor.actor_id, asset_id)
		asset_version_root = asset_root / "v001"
		result_root = asset_version_root / "result"
		published_batch_root = resolve_published_batch_root(
			self.upload_layout,
			batch_name,
			visibility_scope,
			actor.actor_id,
		)
		if asset_version_root.exists():
			shutil.rmtree(asset_version_root)
		asset_version_root.mkdir(parents=True, exist_ok=True)

		title = str(payload.get("display_name") or payload.get("original_name") or batch_name).strip() or batch_name
		if upload_type == "trajectory4":
			adapter_report = build_trajectory4_result(source_path, result_root, title=title, field_mapping=field_mapping)
			ui_mode = "trajectory_layers"
			review_reference_files = ["gps.csv"]
		else:
			adapter_report = build_signal6_result(
				source_path,
				result_root,
				title=title,
				field_mapping=field_mapping,
				pipeline_mode="legacy",
			)
			ui_mode = "trajectory_layers"
			review_reference_files = ["signal.csv"]

		ui_config = {
			"ui_mode": ui_mode,
			"annotation_enabled": annotation_mode == "annotatable",
			"hide_review_panel": annotation_mode != "annotatable",
			"review_reference_files": review_reference_files,
			"filter_state_options": adapter_report.get("filter_state_options") or [],
			"point_status_types": adapter_report.get("filter_state_options") or [],
		}
		extra_metadata = {
			"owner_actor_id": actor.actor_id,
			"owner_display_name": actor.display_name,
			"visibility_scope": visibility_scope,
			"annotation_mode": annotation_mode,
			"field_mapping": field_mapping,
			"source_upload_id": str(payload.get("upload_id") or upload_root.name),
			"source_asset_id": asset_id,
			"ui_config": ui_config,
			"preview_only": True,
		}
		publish_report = publish_batch(
			published_root=published_batch_root.parent,
			batch_name=batch_name,
			source_result_root=result_root,
			label=title,
			version="user-upload-preview-v1",
			keywords=["user-upload", upload_type, visibility_scope, annotation_mode, "preview"],
			status="preview_ready",
			force=True,
			validate=True,
			extra_metadata=extra_metadata,
		)
		batch_catalog_payload = dict(publish_report["metadata"])
		batch_catalog_payload["batch_name"] = batch_name
		batch_catalog_payload["batch_root"] = str(published_batch_root)
		batch_catalog_payload["source_path"] = str(source_path)
		self._upsert_batch_catalog_metadata(batch_name, batch_catalog_payload)

		write_json_metadata(
			resolve_asset_catalog_path(self.upload_layout, asset_id),
			{
				"asset_id": asset_id,
				"owner_actor_id": actor.actor_id,
				"source_upload_id": str(payload.get("upload_id") or upload_root.name),
				"upload_type": upload_type,
				"asset_root": str(asset_root),
				"asset_version_root": str(asset_version_root),
				"result_root": str(result_root),
				"batch_name": batch_name,
				"generated_at": _utc_now(),
				"preview_only": True,
			},
		)
		return {
			"status": "preview_ready",
			"upload_type": upload_type,
			"asset_id": asset_id,
			"batch_name": batch_name,
			"published_batch_name": batch_name,
			"asset_root": str(asset_root),
			"result_root": str(result_root),
			"published_batch_root": str(published_batch_root),
			"published_at": _utc_now(),
			"filter_state_options": adapter_report.get("filter_state_options") or [],
			"review_reference_files": review_reference_files,
			"ui_mode": ui_mode,
			"error": "",
			"error_summary": "",
			"note": "仅上传已生成原始预览，可直接打开；后续仍可触发正式处理。",
			"preview_only": True,
		}

	def _process_upload(self, upload_root: Path, catalog_path: Path, payload: dict, actor: ActorIdentity) -> dict:
		self._ensure_upload_owner(payload, actor)
		annotation_mode = self._normalize_annotation_mode(payload.get("annotation_mode"))
		visibility_scope = normalize_visibility_scope(payload.get("visibility_scope"))
		source_path = self._resolve_upload_source_path(upload_root, payload)
		upload_type = self._resolve_actual_upload_type(source_path, payload)
		field_mapping = normalize_user_upload_field_mapping(upload_type, payload.get("field_mapping"))
		asset_id = str(payload.get("asset_id") or "").strip() or generate_asset_id(upload_type, actor.actor_id)
		batch_name = str(payload.get("batch_name") or "").strip() or generate_batch_name(upload_type, actor.actor_id)
		asset_root = resolve_asset_dataset_root(self.upload_layout, actor.actor_id, asset_id)
		asset_version_root = asset_root / "v001"
		result_root = asset_version_root / "result"
		published_batch_root = resolve_published_batch_root(
			self.upload_layout,
			batch_name,
			visibility_scope,
			actor.actor_id,
		)
		if asset_version_root.exists():
			shutil.rmtree(asset_version_root)
		asset_version_root.mkdir(parents=True, exist_ok=True)

		record = dict(payload)
		record["status"] = "processing"
		record["error"] = ""
		record["error_summary"] = ""
		record["upload_type"] = upload_type
		record["asset_id"] = asset_id
		record["batch_name"] = batch_name
		record["field_mapping"] = field_mapping
		record = self._persist_upload_record(upload_root, catalog_path, record)

		title = str(record.get("display_name") or record.get("original_name") or batch_name).strip() or batch_name
		if upload_type == "trajectory4":
			adapter_report = build_trajectory4_result(source_path, result_root, title=title, field_mapping=field_mapping)
			ui_mode = "trajectory_layers"
			review_reference_files = ["gps.csv"]
		else:
			adapter_report = build_signal6_result(
				source_path,
				result_root,
				title=title,
				field_mapping=field_mapping,
				pipeline_mode=self.signal6_pipeline_mode,
			)
			ui_mode = str(adapter_report.get("ui_mode") or ("chain2" if self.signal6_pipeline_mode == "v311" else "trajectory_layers"))
			review_reference_files = list(adapter_report.get("review_reference_files") or [])
			if not review_reference_files:
				review_reference_files = ["line.csv", "fmm.csv"] if ui_mode == "chain2" else ["signal.csv"]

		ui_config = {
			"ui_mode": ui_mode,
			"annotation_enabled": annotation_mode == "annotatable",
			"hide_review_panel": annotation_mode != "annotatable",
			"review_reference_files": review_reference_files,
			"filter_state_options": adapter_report.get("filter_state_options") or [],
			"point_status_types": adapter_report.get("filter_state_options") or [],
		}
		extra_metadata = {
			"owner_actor_id": actor.actor_id,
			"owner_display_name": actor.display_name,
			"visibility_scope": visibility_scope,
			"annotation_mode": annotation_mode,
			"field_mapping": field_mapping,
			"source_upload_id": record["upload_id"],
			"source_asset_id": asset_id,
			"ui_config": ui_config,
		}
		publish_report = publish_batch(
			published_root=published_batch_root.parent,
			batch_name=batch_name,
			source_result_root=result_root,
			label=title,
			version="user-upload-v1",
			keywords=["user-upload", upload_type, visibility_scope, annotation_mode],
			status="published",
			force=True,
			validate=True,
			extra_metadata=extra_metadata,
		)
		batch_catalog_payload = dict(publish_report["metadata"])
		batch_catalog_payload["batch_name"] = batch_name
		batch_catalog_payload["batch_root"] = str(published_batch_root)
		batch_catalog_payload["source_path"] = str(source_path)
		self._upsert_batch_catalog_metadata(batch_name, batch_catalog_payload)

		write_json_metadata(
			resolve_asset_catalog_path(self.upload_layout, asset_id),
			{
				"asset_id": asset_id,
				"owner_actor_id": actor.actor_id,
				"source_upload_id": record["upload_id"],
				"upload_type": upload_type,
				"asset_root": str(asset_root),
				"asset_version_root": str(asset_version_root),
				"result_root": str(result_root),
				"batch_name": batch_name,
				"generated_at": _utc_now(),
			},
		)

		record.update(
			{
				"status": "published",
				"asset_id": asset_id,
				"batch_name": batch_name,
				"published_batch_name": batch_name,
				"asset_root": str(asset_root),
				"result_root": str(result_root),
				"published_batch_root": str(published_batch_root),
					"published_at": _utc_now(),
					"filter_state_options": adapter_report.get("filter_state_options") or [],
					"review_reference_files": review_reference_files,
					"ui_mode": ui_mode,
					"error": "",
					"error_summary": "",
				}
			)
		record = self._persist_upload_record(upload_root, catalog_path, record)
		self._refresh_batches()
		return record

	def do_GET(self) -> None:
		parsed = urlparse(self.path)
		actor = self._current_actor()
		offline_tile_match = re.fullmatch(r"/offline_tiles/beijing/(\d+)/(\d+)/(\d+)\.png", parsed.path)
		if offline_tile_match:
			try:
				z = int(offline_tile_match.group(1))
				x = int(offline_tile_match.group(2))
				y = int(offline_tile_match.group(3))
				payload = self._get_offline_tile_service().render_png(z, x, y)
			except FileNotFoundError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.NOT_FOUND)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_png(payload)
			return
		if parsed.path == "/":
			self.send_response(HTTPStatus.FOUND)
			self.send_header("Location", "/web/index.html")
			self.end_headers()
			return
		if parsed.path == "/api/me":
			self._send_json({"actor": self._actor_payload()})
			return
		if parsed.path == "/api/uploads":
			self._send_json({"items": self._list_upload_items(actor)})
			return
		if parsed.path == "/api/batches":
			self._send_json(self._batch_list_payload(actor))
			return
		if parsed.path == "/api/health":
			try:
				batch_name, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			self._send_json(
				{
					"status": "ok",
					"project_root": str(paths.project_root),
					"result_root": str(paths.result_root),
					"review_root": str(paths.review_root),
					"export_root": str(paths.export_root),
					"batch": batch_name,
				}
			)
			return
		if parsed.path == "/api/admin/incoming":
			if not self._incoming_enabled():
				self._send_admin_error(
					"admin_upload_disabled",
					"incoming upload area is not configured",
					status=HTTPStatus.SERVICE_UNAVAILABLE,
				)
				return
			self._send_json(self._incoming_state_payload())
			return
		if parsed.path == "/api/reviewers":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			self._send_json({"reviewers": list_reviewers(paths)})
			return
		if parsed.path == "/api/reviews":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			reviewer_id = query.get("reviewer_id", [None])[0]
			if uid:
				self._send_json({"review": get_review(paths, uid, reviewer_id=reviewer_id)})
				return
			self._send_json(read_latest_reviews(paths, reviewer_id=reviewer_id))
			return
		if parsed.path == "/api/reviews/aggregate":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"aggregate": get_uid_review_aggregate(paths, uid)})
			return
		if parsed.path == "/api/timeline-annotations":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			reviewer_id = query.get("reviewer_id", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"annotations": read_timeline_annotations(paths, uid, reviewer_id=reviewer_id, read_only=True)})
			return
		if parsed.path == "/api/track-edits":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			reviewer_id = query.get("reviewer_id", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			if not reviewer_id:
				self._send_error_json("reviewer_id is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"track_edits": read_track_edits(paths, uid, reviewer_id=reviewer_id)})
			return
		if parsed.path == "/api/timeline-annotations/aggregate":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"aggregate": get_timeline_annotation_aggregate(paths, uid)})
			return
		if parsed.path == "/api/export/reviewer-bundle/download":
			try:
				_, paths = self._resolve_review_paths(parsed, actor=actor)
				query = parse_qs(parsed.query)
				reviewer_id = str(query.get("reviewer_id", [""])[0]).strip()
				bundle_name = Path(str(query.get("bundle_name", [""])[0]).strip()).name
				if not reviewer_id:
					self._send_error_json("reviewer_id is required", status=HTTPStatus.BAD_REQUEST)
					return
				if not bundle_name:
					self._send_error_json("bundle_name is required", status=HTTPStatus.BAD_REQUEST)
					return
				profile = ensure_reviewer_profile(paths, reviewer_id=reviewer_id)
				zip_path = (
					paths.review_root
					/ "review_exports"
					/ "reviewers"
					/ profile["reviewer_id"]
					/ f"{bundle_name}.zip"
				)
				if not zip_path.exists() or not zip_path.is_file():
					self._send_error_json("bundle zip not found", status=HTTPStatus.NOT_FOUND)
					return
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			self._send_file(
				zip_path,
				content_type="application/zip",
				download_name=zip_path.name,
			)
			return
		super().do_GET()

	def do_POST(self) -> None:
		parsed = urlparse(self.path)
		actor = self._current_actor()
		path_parts = [part for part in parsed.path.split("/") if part]
		if parsed.path == "/api/uploads":
			self._handle_create_upload(actor)
			return
		if len(path_parts) == 4 and path_parts[:2] == ["api", "uploads"] and path_parts[3] == "blob":
			self._handle_upload_blob(path_parts[2], actor)
			return
		if len(path_parts) == 4 and path_parts[:2] == ["api", "uploads"] and path_parts[3] == "process":
			self._handle_process_upload(path_parts[2], actor)
			return
		if parsed.path == "/api/admin/incoming/upload":
			self._handle_admin_upload(parsed)
			return
		try:
			payload = self._read_json_body()
		except json.JSONDecodeError as exc:
			self._send_error_json(f"Invalid JSON body: {exc}", status=HTTPStatus.BAD_REQUEST)
			return

		if parsed.path == "/api/reviews":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				review = write_review(paths, payload)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"review": review})
			return

		if parsed.path == "/api/reviewers/session":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				profile = ensure_reviewer_profile(
					paths,
					display_name=str(payload.get("display_name") or payload.get("reviewer_name") or payload.get("reviewer") or "").strip(),
					reviewer_id=str(payload.get("reviewer_id") or "").strip() or None,
				)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"reviewer": profile})
			return

		if parsed.path == "/api/export/accepted":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				manifest = export_accepted_assets(
					paths,
					clean=bool(payload.get("clean", False)),
					reviewer_id=str(payload.get("reviewer_id") or "").strip() or None,
				)
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/export/review-aggregate":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				manifest = export_review_aggregate(
					paths,
					clean=bool(payload.get("clean", False)),
				)
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/export/reviewer-bundle":
			try:
				batch_name, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				decisions = payload.get("decisions")
				if decisions is None:
					decisions = ["accept", "reject", "skip"]
				export_mode = str(payload.get("export_mode") or "").strip().lower()
				export_args = {
					"paths": paths,
					"reviewer_id": str(payload.get("reviewer_id") or "").strip(),
					"output_root": str(payload.get("output_root") or "").strip() or None,
					"bundle_name": str(payload.get("bundle_name") or "").strip() or None,
					"clean": bool(payload.get("clean", False)),
					"decisions": list(decisions),
					"uids": list(payload.get("uids") or []),
					"trajectory_tags": list(payload.get("trajectory_tags") or []),
					"create_zip": bool(payload.get("create_zip", False)),
				}
				if export_mode == "segment_label_dataset":
					manifest = export_segment_label_dataset(
						interval_seconds=int(payload.get("interval_seconds") or 5),
						timestamp_unit=str(payload.get("timestamp_unit") or "ms"),
						labeled_span_only=bool(payload.get("labeled_span_only", False)),
						**export_args,
					)
				else:
					manifest = export_reviewer_bundle(**export_args)
				manifest["export_mode"] = export_mode or "reviewer_bundle"
				if manifest.get("zip_path") and manifest.get("bundle_name"):
					manifest["batch"] = batch_name
					manifest["download_url"] = (
						f"/api/export/reviewer-bundle/download?batch={quote(batch_name)}"
						f"&reviewer_id={quote(str(manifest.get('reviewer_profile', {}).get('reviewer_id') or payload.get('reviewer_id') or ''))}"
						f"&bundle_name={quote(str(manifest.get('bundle_name') or ''))}"
					)
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/timeline-annotations":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				annotations = write_timeline_annotations(paths, payload)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"annotations": annotations})
			return

		if parsed.path == "/api/track-edits":
			try:
				_, paths = self._resolve_review_paths(parsed, payload, actor=actor)
				track_edits = write_track_edits(paths, payload)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except PermissionError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.FORBIDDEN)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"track_edits": track_edits})
			return

		self._send_error_json("Unknown API endpoint", status=HTTPStatus.NOT_FOUND)

	def do_DELETE(self) -> None:
		parsed = urlparse(self.path)
		actor = self._current_actor()
		path_parts = [part for part in parsed.path.split("/") if part]
		if len(path_parts) == 3 and path_parts[:2] == ["api", "uploads"]:
			upload_id = path_parts[2]
			try:
				upload_root, catalog_path, payload = self._resolve_upload_record(upload_id)
				self._ensure_upload_owner(payload, actor)
			except FileNotFoundError as exc:
				self._send_upload_error("upload_not_found", str(exc), status=HTTPStatus.NOT_FOUND)
				return
			except PermissionError as exc:
				self._send_upload_error("upload_forbidden", str(exc), status=HTTPStatus.FORBIDDEN)
				return
			record = dict(payload)
			record["status"] = "deleted"
			record["hidden_at"] = record.get("hidden_at") or _utc_now()
			record["deleted_at"] = _utc_now()
			if record.get("batch_name"):
				self._mark_batch_deleted(str(record.get("batch_name")))
			record = self._persist_upload_record(upload_root, catalog_path, record)
			self._send_json({"status": "deleted", "upload": record})
			return
		self._send_error_json("Unknown API endpoint", status=HTTPStatus.NOT_FOUND)

	def _handle_create_upload(self, actor: ActorIdentity) -> None:
		try:
			payload = self._read_json_body()
			upload_type = self._normalize_upload_type(payload.get("upload_type"))
			visibility_scope = normalize_visibility_scope(payload.get("visibility_scope"))
			annotation_mode = self._normalize_annotation_mode(payload.get("annotation_mode"))
			field_mapping = normalize_user_upload_field_mapping("trajectory4" if upload_type == "auto" else upload_type, payload.get("field_mapping")) if payload.get("field_mapping") else {}
		except json.JSONDecodeError as exc:
			self._send_upload_error("invalid_json", f"Invalid JSON body: {exc}", status=HTTPStatus.BAD_REQUEST)
			return
		except ValueError as exc:
			self._send_upload_error("invalid_upload_request", str(exc), status=HTTPStatus.BAD_REQUEST)
			return

		upload_id = generate_upload_id(actor.actor_id)
		upload_root = self.incoming_root / upload_id
		catalog_path = resolve_upload_catalog_path(self.upload_layout, upload_id)
		upload_root.mkdir(parents=True, exist_ok=False)
		display_name = (
			str(payload.get("display_name") or payload.get("original_name") or "").strip()
			or f"{upload_type} upload"
		)
		record = {
			"upload_id": upload_id,
			"status": "created",
			"created_at": _utc_now(),
			"owner_actor_id": actor.actor_id,
			"owner_display_name": actor.display_name,
			"owner_role": self._current_actor_role(),
			"upload_type": upload_type,
			"visibility_scope": visibility_scope,
			"annotation_mode": annotation_mode,
			"display_name": display_name,
			"original_name": str(payload.get("original_name") or "").strip(),
			"field_mapping": field_mapping,
			"errors": [],
		}
		record = self._persist_upload_record(upload_root, catalog_path, record)
		self._send_json({"status": "created", "upload": record}, status=HTTPStatus.CREATED)

	def _handle_upload_blob(self, upload_id: str, actor: ActorIdentity) -> None:
		try:
			upload_root, catalog_path, payload = self._resolve_upload_record(upload_id)
			self._ensure_upload_owner(payload, actor)
			raw_body = self._read_raw_body()
			upload_name = str(self.headers.get("X-Upload-Filename") or payload.get("original_name") or "").strip()
			safe_name = _sanitize_source_name(upload_name or f"{payload.get('upload_type') or 'upload'}_{upload_id}.csv")
		except FileNotFoundError as exc:
			self._send_upload_error("upload_not_found", str(exc), status=HTTPStatus.NOT_FOUND)
			return
		except PermissionError as exc:
			self._send_upload_error("upload_forbidden", str(exc), status=HTTPStatus.FORBIDDEN)
			return
		except ValueError as exc:
			self._send_upload_error("invalid_upload_blob", str(exc), status=HTTPStatus.BAD_REQUEST)
			return

		for child in upload_root.glob("*.csv"):
			if child.name != safe_name:
				child.unlink(missing_ok=True)
		tmp_path = upload_root / f"{safe_name}.part"
		target_path = upload_root / safe_name
		with open(tmp_path, "wb") as handle:
			handle.write(raw_body)
		tmp_path.replace(target_path)

		record = dict(payload)
		record.update(
			{
				"status": "uploaded",
				"original_name": upload_name or safe_name,
				"safe_name": safe_name,
				"content_type": str(self.headers.get("Content-Type") or "application/octet-stream"),
				"size_bytes": len(raw_body),
				"source_path": str(target_path),
				"error": "",
				"error_summary": "",
			}
		)
		record = self._persist_upload_record(upload_root, catalog_path, record)
		try:
			record.update(self._publish_upload_preview(upload_root, catalog_path, record, actor))
			record = self._persist_upload_record(upload_root, catalog_path, record)
			self._refresh_batches()
		except (FileNotFoundError, UserUploadAdapterError, ValueError) as exc:
			record["note"] = f"文件已上传，但原始预览生成失败：{exc}"
			record = self._persist_upload_record(upload_root, catalog_path, record)
		self._send_json({"status": record.get("status") or "uploaded", "upload": record}, status=HTTPStatus.CREATED)

	def _handle_process_upload(self, upload_id: str, actor: ActorIdentity) -> None:
		try:
			upload_root, catalog_path, payload = self._resolve_upload_record(upload_id)
		except FileNotFoundError as exc:
			self._send_upload_error("upload_not_found", str(exc), status=HTTPStatus.NOT_FOUND)
			return
		try:
			record = self._process_upload(upload_root, catalog_path, payload, actor)
		except PermissionError as exc:
			self._send_upload_error("upload_forbidden", str(exc), status=HTTPStatus.FORBIDDEN)
			return
		except (FileNotFoundError, UserUploadAdapterError, ValueError) as exc:
			_, _, latest_payload = self._resolve_upload_record(upload_id)
			failed_record = dict(latest_payload)
			failed_record["status"] = "failed"
			failed_record["error"] = str(exc)
			failed_record["error_summary"] = str(exc)
			failed_record = self._persist_upload_record(upload_root, catalog_path, failed_record)
			self._send_upload_error(
				"upload_process_failed",
				str(exc),
				status=HTTPStatus.BAD_REQUEST,
				upload=failed_record,
			)
			return
		except Exception as exc:
			_, _, latest_payload = self._resolve_upload_record(upload_id)
			failed_record = dict(latest_payload)
			failed_record["status"] = "failed"
			failed_record["error"] = str(exc)
			failed_record["error_summary"] = str(exc)
			failed_record = self._persist_upload_record(upload_root, catalog_path, failed_record)
			self._send_upload_error(
				"upload_process_internal_error",
				str(exc),
				status=HTTPStatus.INTERNAL_SERVER_ERROR,
				upload=failed_record,
			)
			return
		self._send_json({"status": "published", "upload": record})

	def _handle_admin_upload(self, parsed) -> None:
		if not self._incoming_enabled():
			self._send_admin_error(
				"admin_upload_disabled",
				"incoming upload area is not configured",
				status=HTTPStatus.SERVICE_UNAVAILABLE,
			)
			return
		query = parse_qs(parsed.query)
		upload_name = str(query.get("name", [""])[0]).strip() or str(self.headers.get("X-Upload-Filename") or "").strip()
		try:
			safe_name = _sanitize_upload_name(upload_name)
		except ValueError as exc:
			self._send_admin_error("invalid_upload_name", str(exc), status=HTTPStatus.BAD_REQUEST)
			return
		try:
			content_length = int(self.headers.get("Content-Length", "0") or "0")
		except ValueError:
			content_length = 0
		if content_length <= 0:
			self._send_admin_error("invalid_content_length", "Content-Length must be a positive integer", status=HTTPStatus.LENGTH_REQUIRED)
			return
		if content_length > self.upload_max_bytes:
			self._send_admin_error(
				"upload_too_large",
				f"upload exceeds max size of {self.upload_max_bytes} bytes",
				status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
				upload_max_bytes=self.upload_max_bytes,
				content_length=content_length,
			)
			return

		upload_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
		upload_root = self.incoming_root / upload_id
		payload_path = upload_root / UPLOAD_FILE_NAME
		tmp_path = upload_root / f"{UPLOAD_FILE_NAME}.part"
		upload_root.mkdir(parents=True, exist_ok=False)

		received = 0
		with open(tmp_path, "wb") as handle:
			remaining = content_length
			while remaining > 0:
				chunk = self.rfile.read(min(1024 * 1024, remaining))
				if not chunk:
					break
				handle.write(chunk)
				received += len(chunk)
				remaining -= len(chunk)

		if received != content_length:
			tmp_path.unlink(missing_ok=True)
			self._send_admin_error(
				"incomplete_upload",
				f"expected {content_length} bytes but received {received}",
				status=HTTPStatus.BAD_REQUEST,
				content_length=content_length,
				received_bytes=received,
			)
			return

		tmp_path.rename(payload_path)
		status_payload = {
			"upload_id": upload_id,
			"status": "uploaded",
			"created_at": _utc_now(),
			"original_name": upload_name,
			"safe_name": safe_name,
			"content_type": str(self.headers.get("Content-Type") or "application/octet-stream"),
			"size_bytes": received,
			"upload_root": str(upload_root),
			"payload_path": str(payload_path),
			"errors": [],
		}
		_write_json(upload_root / UPLOAD_STATUS_NAME, status_payload)
		self._send_json(
			{
				"status": "uploaded",
				"item": status_payload,
			},
			status=HTTPStatus.CREATED,
		)

	def translate_path(self, path: str) -> str:
		self._refresh_batches()
		parsed_path = urlparse(path).path
		relative = parsed_path.lstrip("/")
		if relative.startswith("batch-data/"):
			parts = [part for part in posixpath.normpath(unquote(relative)).split("/") if part and part not in {".", ".."}]
			if len(parts) >= 2:
				batch_name = parts[1]
				actor = self._current_actor()
				if self.batches:
					batch = self.batches.get(batch_name)
					if batch is None:
						return str(Path(self.directory) / "__missing_batch__")
					if not can_actor_view_batch(batch.metadata, actor.actor_id):
						return str(Path(self.directory) / "__forbidden_batch__")
					resolved = batch.paths.result_root
				else:
					resolved = self.review_paths.result_root
				for part in parts[2:]:
					resolved /= part
				return str(resolved)
		if relative in {"", "."}:
			relative = "web/index.html"
		elif relative == "web":
			relative = "web/index.html"
		elif relative.startswith("web/"):
			relative = relative

		normalized = posixpath.normpath(unquote(relative))
		parts = [part for part in normalized.split("/") if part and part not in {".", ".."}]
		resolved = Path(self.directory)
		for part in parts:
			resolved /= part
		return str(resolved)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Local stdlib-only review server for trajectory_annotation_studio workflows."
	)
	parser.add_argument("--host", default="127.0.0.1", help="Bind host")
	parser.add_argument("--port", type=int, default=8000, help="Bind port")
	parser.add_argument("--project-root", default=None, help="trajectory_annotation_studio project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review ledger root")
	parser.add_argument("--export-root", default=None, help="Override accepted export root")
	parser.add_argument("--batches-root", default=None, help="Optional root containing named review batches")
	parser.add_argument("--incoming-root", default=None, help="Optional incoming upload root outside batches-root")
	parser.add_argument(
		"--upload-max-bytes",
		type=int,
		default=DEFAULT_UPLOAD_MAX_BYTES,
		help="Maximum accepted admin upload size in bytes",
	)
	parser.add_argument(
		"--signal6-pipeline-mode",
		default="v311",
		help="Signal6 processing mode: legacy or v311 (snap+OD+fmm).",
	)
	parser.add_argument(
		"--offline-tile-cache-root",
		default=None,
		help="Optional cache root for generated offline vector tiles.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	paths = resolve_review_paths(
		project_root=args.project_root,
		result_root=args.result_root,
		review_root=args.review_root,
		export_root=args.export_root,
	)
	batches: dict[str, ReviewBatch] = {}
	batch_order: list[str] = []
	resolved_batches_root = Path(args.batches_root).expanduser().resolve() if args.batches_root else None
	runtime_root = _resolve_runtime_root(paths.project_root, resolved_batches_root)
	upload_layout = resolve_upload_storage_layout(
		runtime_root,
		published_root=resolved_batches_root if resolved_batches_root is not None else runtime_root / "published",
	)
	if args.batches_root:
		batches, batch_order = discover_batches(
			paths.project_root,
			resolved_batches_root,
			batch_catalog_root=upload_layout.catalog_batches_root,
		)
	incoming_root = (
		Path(args.incoming_root).expanduser().resolve()
		if args.incoming_root
		else (runtime_root / "incoming").resolve()
	)
	if incoming_root and resolved_batches_root:
		if incoming_root == resolved_batches_root or _is_relative_to(incoming_root, resolved_batches_root):
			raise SystemExit("--incoming-root must be outside --batches-root")
	signal6_pipeline_mode = normalize_signal6_pipeline_mode(args.signal6_pipeline_mode)
	default_batch = batch_order[0] if batch_order else DEFAULT_BATCH_NAME
	handler = lambda *handler_args, **handler_kwargs: ReviewRequestHandler(
		*handler_args,
		directory=str(paths.project_root),
		review_paths=paths,
		batches_root=resolved_batches_root,
		batches=batches,
			batch_order=batch_order,
			default_batch=default_batch,
			incoming_root=incoming_root,
			runtime_root=runtime_root,
			offline_tile_cache_root=Path(args.offline_tile_cache_root).expanduser().resolve() if args.offline_tile_cache_root else None,
			upload_max_bytes=args.upload_max_bytes,
			signal6_pipeline_mode=signal6_pipeline_mode,
			**handler_kwargs,
		)
	with ThreadingHTTPServer((args.host, args.port), handler) as httpd:
		print(
			f"Serving review UI on http://{args.host}:{args.port}/web/index.html "
			f"(result_root={paths.result_root}, review_root={paths.review_root}, batches={len(batch_order) or 1})"
		)
		httpd.serve_forever()


if __name__ == "__main__":
	main()
