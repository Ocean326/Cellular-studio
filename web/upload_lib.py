from __future__ import annotations

import json
import re
import secrets
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_UPLOAD_STATUS_NAME = "upload_status.json"
OWNER_ONLY_VISIBILITY = "owner_only"
PUBLIC_VISIBILITY = "public"

ACTOR_ID_HEADER_CANDIDATES = (
	"x-forwarded-user",
	"x-remote-user",
	"remote-user",
	"x-authenticated-user",
	"x-user-id",
	"x-user",
)
DISPLAY_NAME_HEADER_CANDIDATES = (
	"x-display-name",
	"x-forwarded-name",
	"x-user-name",
	"x-real-name",
)
HIDDEN_STATUSES = frozenset(
	{
		"hidden",
		"unpublished",
		"archived",
		"retired",
		"deleting",
		"deleted",
	}
)
DELETED_STATUSES = frozenset({"deleted", "purged"})

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ActorIdentity:
	actor_id: str
	display_name: str
	source_header: str = ""


@dataclass(frozen=True)
class UploadStorageLayout:
	project_root: Path
	catalog_root: Path
	catalog_uploads_root: Path
	catalog_assets_root: Path
	catalog_batches_root: Path
	datasets_root: Path
	user_assets_root: Path
	published_root: Path
	published_private_root: Path
	published_public_root: Path


def resolve_project_root(anchor: str | Path | None = None) -> Path:
	base = Path(anchor) if anchor is not None else Path(__file__).resolve()
	return base.resolve().parents[1]


def resolve_upload_storage_layout(
	project_root: str | Path | None = None,
	*,
	published_root: str | Path | None = None,
) -> UploadStorageLayout:
	root = Path(project_root).resolve() if project_root else resolve_project_root()
	catalog_root = root / "catalog"
	datasets_root = root / "datasets"
	resolved_published_root = (
		Path(published_root).resolve() if published_root is not None else root / "published"
	)
	return UploadStorageLayout(
		project_root=root,
		catalog_root=catalog_root,
		catalog_uploads_root=catalog_root / "uploads",
		catalog_assets_root=catalog_root / "assets",
		catalog_batches_root=catalog_root / "batches",
		datasets_root=datasets_root,
		user_assets_root=datasets_root / "user_assets",
		published_root=resolved_published_root,
		published_private_root=resolved_published_root / "private",
		published_public_root=resolved_published_root / "public",
	)


def utc_now_compact(now: datetime | None = None) -> str:
	moment = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
	return moment.replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")


def normalize_actor_id(value: Any) -> str:
	text = str(value or "").strip()
	if not text:
		return ""
	local = text.split("@", 1)[0].strip()
	normalized = _NON_ALNUM_RE.sub("-", local.lower()).strip("-")
	return normalized[:64]


def normalize_display_name(value: Any) -> str:
	return str(value or "").strip()


def _normalize_header_mapping(headers: Mapping[str, Any] | None) -> dict[str, str]:
	if not headers:
		return {}
	normalized: dict[str, str] = {}
	for key, value in headers.items():
		header_key = str(key or "").strip().lower()
		if not header_key:
			continue
		normalized[header_key] = str(value or "").strip()
	return normalized


def parse_actor_identity_from_headers(headers: Mapping[str, Any] | None) -> ActorIdentity:
	normalized = _normalize_header_mapping(headers)
	actor_source = ""
	actor_raw = ""
	for header_name in ACTOR_ID_HEADER_CANDIDATES:
		value = normalized.get(header_name, "")
		if value:
			actor_source = header_name
			actor_raw = value
			break
	display_name = ""
	for header_name in DISPLAY_NAME_HEADER_CANDIDATES:
		value = normalized.get(header_name, "")
		if value:
			display_name = value
			break
	if not actor_raw and display_name:
		actor_raw = display_name
		actor_source = "derived-display-name"
	actor_id = normalize_actor_id(actor_raw)
	if not display_name:
		display_name = normalize_display_name(actor_raw.split("@", 1)[0] if actor_raw else "")
	return ActorIdentity(
		actor_id=actor_id,
		display_name=display_name,
		source_header=actor_source,
	)


def normalize_visibility_scope(value: Any) -> str:
	text = str(value or "").strip().lower()
	if text in {"", "owner_only", "private", "self", "self_only", "mine"}:
		return OWNER_ONLY_VISIBILITY
	if text in {PUBLIC_VISIBILITY, "shared"}:
		return PUBLIC_VISIBILITY
	raise ValueError(f"Unsupported visibility scope: {value!r}")


def normalize_lifecycle_status(value: Any) -> str:
	return str(value or "").strip().lower()


def is_hidden_status(value: Any) -> bool:
	return normalize_lifecycle_status(value) in HIDDEN_STATUSES


def is_deleted_status(value: Any) -> bool:
	return normalize_lifecycle_status(value) in DELETED_STATUSES


def is_owner(actor_id: Any, owner_actor_id: Any) -> bool:
	resolved_actor_id = normalize_actor_id(actor_id)
	resolved_owner_id = normalize_actor_id(owner_actor_id)
	return bool(resolved_actor_id) and resolved_actor_id == resolved_owner_id


def can_actor_view_batch(metadata: Mapping[str, Any] | None, actor_id: Any) -> bool:
	payload = dict(metadata or {})
	status = payload.get("status", "")
	if payload.get("deleted_at") or is_deleted_status(status):
		return False
	if payload.get("hidden_at") or is_hidden_status(status):
		return False
	if "visibility_scope" not in payload and "visibility" not in payload:
		return True
	visibility = normalize_visibility_scope(payload.get("visibility_scope") or payload.get("visibility"))
	if visibility == PUBLIC_VISIBILITY:
		return True
	owner_actor_id = payload.get("owner_actor_id") or payload.get("owner_user_id")
	return is_owner(actor_id, owner_actor_id)


def _normalize_identifier_component(value: Any, fallback: str) -> str:
	normalized = normalize_actor_id(value)
	if normalized:
		return normalized
	text = _NON_ALNUM_RE.sub("-", str(value or "").strip().lower()).strip("-")
	return text or fallback


def _normalize_token(token: str | None = None, length: int = 8) -> str:
	raw = str(token or secrets.token_hex(max(4, length // 2))).strip().lower()
	normalized = re.sub(r"[^a-z0-9]", "", raw)
	if not normalized:
		normalized = secrets.token_hex(max(4, length // 2))
	return normalized[:length]


def generate_upload_id(
	actor_id: Any = "",
	*,
	now: datetime | None = None,
	token: str | None = None,
) -> str:
	owner_component = _normalize_identifier_component(actor_id, "upload")
	return f"{utc_now_compact(now)}_{owner_component}_{_normalize_token(token)}"


def generate_asset_id(
	asset_kind: Any,
	actor_id: Any = "",
	*,
	now: datetime | None = None,
	token: str | None = None,
) -> str:
	kind_component = _normalize_identifier_component(asset_kind, "asset")
	owner_component = _normalize_identifier_component(actor_id, "asset")
	return f"asset_{kind_component}_{owner_component}_{utc_now_compact(now)}_{_normalize_token(token)}"


def generate_batch_name(
	prefix: Any,
	actor_id: Any = "",
	*,
	now: datetime | None = None,
	token: str | None = None,
) -> str:
	prefix_component = _normalize_identifier_component(prefix, "batch")
	owner_component = _normalize_identifier_component(actor_id, "batch")
	return f"{prefix_component}_{owner_component}_{utc_now_compact(now).lower()}_{_normalize_token(token)}"


def resolve_upload_status_path(upload_root: str | Path) -> Path:
	return Path(upload_root).resolve() / DEFAULT_UPLOAD_STATUS_NAME


def resolve_upload_catalog_path(
	layout_or_root: UploadStorageLayout | str | Path,
	upload_id: str,
) -> Path:
	layout = (
		layout_or_root
		if isinstance(layout_or_root, UploadStorageLayout)
		else resolve_upload_storage_layout(layout_or_root)
	)
	return layout.catalog_uploads_root / f"{upload_id}.json"


def resolve_asset_catalog_path(
	layout_or_root: UploadStorageLayout | str | Path,
	asset_id: str,
) -> Path:
	layout = (
		layout_or_root
		if isinstance(layout_or_root, UploadStorageLayout)
		else resolve_upload_storage_layout(layout_or_root)
	)
	return layout.catalog_assets_root / f"{asset_id}.json"


def resolve_batch_catalog_path(
	layout_or_root: UploadStorageLayout | str | Path,
	batch_name: str,
) -> Path:
	layout = (
		layout_or_root
		if isinstance(layout_or_root, UploadStorageLayout)
		else resolve_upload_storage_layout(layout_or_root)
	)
	return layout.catalog_batches_root / f"{batch_name}.json"


def resolve_user_assets_root(
	layout_or_root: UploadStorageLayout | str | Path,
	owner_actor_id: Any,
) -> Path:
	layout = (
		layout_or_root
		if isinstance(layout_or_root, UploadStorageLayout)
		else resolve_upload_storage_layout(layout_or_root)
	)
	return layout.user_assets_root / _normalize_identifier_component(owner_actor_id, "unknown")


def resolve_asset_dataset_root(
	layout_or_root: UploadStorageLayout | str | Path,
	owner_actor_id: Any,
	asset_id: str,
) -> Path:
	return resolve_user_assets_root(layout_or_root, owner_actor_id) / asset_id


def resolve_published_visibility_root(
	layout_or_root: UploadStorageLayout | str | Path,
	visibility_scope: Any,
	owner_actor_id: Any = "",
) -> Path:
	layout = (
		layout_or_root
		if isinstance(layout_or_root, UploadStorageLayout)
		else resolve_upload_storage_layout(layout_or_root)
	)
	visibility = normalize_visibility_scope(visibility_scope)
	if visibility == PUBLIC_VISIBILITY:
		return layout.published_public_root
	return layout.published_private_root / _normalize_identifier_component(owner_actor_id, "unknown")


def resolve_published_batch_root(
	layout_or_root: UploadStorageLayout | str | Path,
	batch_name: str,
	visibility_scope: Any,
	owner_actor_id: Any = "",
) -> Path:
	return resolve_published_visibility_root(layout_or_root, visibility_scope, owner_actor_id) / batch_name


def read_json_metadata(path: str | Path) -> dict[str, Any]:
	metadata_path = Path(path).resolve()
	if not metadata_path.exists():
		return {}
	with open(metadata_path, encoding="utf-8") as handle:
		return json.load(handle)


def write_json_metadata(path: str | Path, payload: Mapping[str, Any]) -> Path:
	metadata_path = Path(path).resolve()
	metadata_path.parent.mkdir(parents=True, exist_ok=True)
	with tempfile.NamedTemporaryFile(
		"w",
		encoding="utf-8",
		dir=metadata_path.parent,
		delete=False,
		prefix=f"{metadata_path.name}.",
		suffix=".tmp",
	) as handle:
		json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
		handle.write("\n")
		tmp_path = Path(handle.name)
	tmp_path.replace(metadata_path)
	return metadata_path


def read_upload_metadata(upload_root: str | Path) -> dict[str, Any]:
	return read_json_metadata(resolve_upload_status_path(upload_root))


def write_upload_metadata(upload_root: str | Path, payload: Mapping[str, Any]) -> Path:
	return write_json_metadata(resolve_upload_status_path(upload_root), payload)


def read_batch_catalog_metadata(path: str | Path) -> dict[str, Any]:
	return read_json_metadata(path)


def write_batch_catalog_metadata(path: str | Path, payload: Mapping[str, Any]) -> Path:
	return write_json_metadata(path, payload)
