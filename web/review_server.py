from __future__ import annotations

import argparse
import json
import posixpath
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from review_lib import (
	ReviewPaths,
	ensure_reviewer_profile,
	export_accepted_assets,
	export_reviewer_bundle,
	export_review_aggregate,
	get_review,
	get_timeline_annotation_aggregate,
	get_uid_review_aggregate,
	list_reviewers,
	read_latest_reviews,
	read_timeline_annotations,
	resolve_review_paths,
	write_timeline_annotations,
	write_review,
)

DEFAULT_BATCH_META_NAME = "batch_meta.json"
DEFAULT_BATCH_NAME = "current"
DEFAULT_UPLOAD_MAX_BYTES = 2 * 1024 * 1024 * 1024
UPLOAD_STATUS_NAME = "upload_status.json"
UPLOAD_FILE_NAME = "payload.zip"
SAFE_UPLOAD_RE = re.compile(r"[^A-Za-z0-9._-]+")


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


def discover_batches(project_root: Path, batches_root: Path) -> tuple[dict[str, ReviewBatch], list[str]]:
	batches: dict[str, ReviewBatch] = {}
	order: list[tuple[str, str]] = []
	if not batches_root.exists():
		return batches, []

	for child in batches_root.iterdir():
		if not child.is_dir():
			continue
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
		name = str(metadata.get("name") or child.name).strip() or child.name
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
		upload_max_bytes: int = DEFAULT_UPLOAD_MAX_BYTES,
		**kwargs,
	):
		self.review_paths = review_paths
		self.batches_root = Path(batches_root).resolve() if batches_root else None
		self.batches = batches or {}
		self.batch_order = batch_order or list(self.batches.keys())
		self.default_batch = default_batch or (self.batch_order[0] if self.batch_order else None)
		self.incoming_root = Path(incoming_root).resolve() if incoming_root else None
		self.upload_max_bytes = max(int(upload_max_bytes or DEFAULT_UPLOAD_MAX_BYTES), 1)
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
		batches, batch_order = discover_batches(self.review_paths.project_root, self.batches_root)
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

	def _resolve_batch_name(self, parsed, payload: dict | None = None) -> str:
		self._refresh_batches()
		if not self.batches:
			return DEFAULT_BATCH_NAME
		query = parse_qs(parsed.query)
		if payload and payload.get("batch"):
			batch_name = str(payload.get("batch")).strip()
			if batch_name:
				return batch_name
		if query.get("batch"):
			batch_name = str(query["batch"][0]).strip()
			if batch_name:
				return batch_name
		if self.default_batch:
			return self.default_batch
		raise ValueError("No batch configured")

	def _resolve_review_paths(self, parsed, payload: dict | None = None) -> tuple[str, ReviewPaths]:
		# Refresh per-request so endpoints keep working after operator publishes batches at runtime.
		self._refresh_batches()
		if not self.batches:
			return DEFAULT_BATCH_NAME, self.review_paths
		batch_name = self._resolve_batch_name(parsed, payload)
		batch = self.batches.get(batch_name)
		if batch is None:
			raise ValueError(f"Unknown batch: {batch_name}")
		return batch_name, batch.paths

	def _batch_list_payload(self) -> dict:
		self._refresh_batches()
		if not self.batches:
			batch = build_single_batch(self.review_paths)
			return {
				"current_batch": batch.name,
				"batches": [_build_batch_payload(batch)],
			}
		return {
			"current_batch": self.default_batch,
			"batches": [_build_batch_payload(self.batches[name]) for name in self.batch_order if name in self.batches],
		}

	def do_GET(self) -> None:
		parsed = urlparse(self.path)
		if parsed.path == "/":
			self.send_response(HTTPStatus.FOUND)
			self.send_header("Location", "/web/index.html")
			self.end_headers()
			return
		if parsed.path == "/api/batches":
			self._send_json(self._batch_list_payload())
			return
		if parsed.path == "/api/health":
			try:
				batch_name, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
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
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"reviewers": list_reviewers(paths)})
			return
		if parsed.path == "/api/reviews":
			try:
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
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
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
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
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			reviewer_id = query.get("reviewer_id", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"annotations": read_timeline_annotations(paths, uid, reviewer_id=reviewer_id)})
			return
		if parsed.path == "/api/timeline-annotations/aggregate":
			try:
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			if not uid:
				self._send_error_json("uid is required", status=HTTPStatus.BAD_REQUEST)
				return
			self._send_json({"aggregate": get_timeline_annotation_aggregate(paths, uid)})
			return
		super().do_GET()

	def do_POST(self) -> None:
		parsed = urlparse(self.path)
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
				_, paths = self._resolve_review_paths(parsed, payload)
				review = write_review(paths, payload)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"review": review})
			return

		if parsed.path == "/api/reviewers/session":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				profile = ensure_reviewer_profile(
					paths,
					display_name=str(payload.get("display_name") or payload.get("reviewer_name") or payload.get("reviewer") or "").strip(),
					reviewer_id=str(payload.get("reviewer_id") or "").strip() or None,
				)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"reviewer": profile})
			return

		if parsed.path == "/api/export/accepted":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				manifest = export_accepted_assets(
					paths,
					clean=bool(payload.get("clean", False)),
					reviewer_id=str(payload.get("reviewer_id") or "").strip() or None,
				)
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/export/review-aggregate":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				manifest = export_review_aggregate(
					paths,
					clean=bool(payload.get("clean", False)),
				)
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/export/reviewer-bundle":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				decisions = payload.get("decisions")
				if decisions is None:
					decisions = ["accept", "reject", "skip"]
				manifest = export_reviewer_bundle(
					paths,
					reviewer_id=str(payload.get("reviewer_id") or "").strip(),
					output_root=str(payload.get("output_root") or "").strip() or None,
					bundle_name=str(payload.get("bundle_name") or "").strip() or None,
					clean=bool(payload.get("clean", False)),
					decisions=list(decisions),
					create_zip=bool(payload.get("create_zip", False)),
				)
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json(manifest)
			return

		if parsed.path == "/api/timeline-annotations":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				annotations = write_timeline_annotations(paths, payload)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			except Exception as exc:
				self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)
				return
			self._send_json({"annotations": annotations})
			return

		self._send_error_json("Unknown API endpoint", status=HTTPStatus.NOT_FOUND)

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
				if self.batches:
					batch = self.batches.get(batch_name)
					if batch is None:
						return str(Path(self.directory) / "__missing_batch__")
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
		description="Local stdlib-only review server for cellular_quality organizer workflow."
	)
	parser.add_argument("--host", default="127.0.0.1", help="Bind host")
	parser.add_argument("--port", type=int, default=8000, help="Bind port")
	parser.add_argument("--project-root", default=None, help="cellular_quality project root")
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
	if args.batches_root:
		batches_root = Path(args.batches_root).expanduser().resolve()
		batches, batch_order = discover_batches(paths.project_root, batches_root)
	incoming_root = Path(args.incoming_root).expanduser().resolve() if args.incoming_root else None
	if incoming_root and args.batches_root:
		batches_root = Path(args.batches_root).expanduser().resolve()
		if incoming_root == batches_root or _is_relative_to(incoming_root, batches_root):
			raise SystemExit("--incoming-root must be outside --batches-root")
	default_batch = batch_order[0] if batch_order else DEFAULT_BATCH_NAME
	handler = lambda *handler_args, **handler_kwargs: ReviewRequestHandler(
		*handler_args,
		directory=str(paths.project_root),
		review_paths=paths,
		batches_root=Path(args.batches_root).expanduser().resolve() if args.batches_root else None,
		batches=batches,
		batch_order=batch_order,
		default_batch=default_batch,
		incoming_root=incoming_root,
		upload_max_bytes=args.upload_max_bytes,
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
