from __future__ import annotations

import argparse
import json
import posixpath
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from review_lib import (
	ReviewPaths,
	export_accepted_assets,
	get_review,
	read_latest_reviews,
	read_timeline_annotations,
	resolve_review_paths,
	write_timeline_annotations,
	write_review,
)

DEFAULT_BATCH_META_NAME = "batch_meta.json"
DEFAULT_BATCH_NAME = "current"


@dataclass(frozen=True)
class ReviewBatch:
	name: str
	label: str
	batch_root: Path
	paths: ReviewPaths
	metadata: dict
	data_base: str


def _read_json(path: Path) -> dict:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


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
		**kwargs,
	):
		self.review_paths = review_paths
		self.batches_root = Path(batches_root).resolve() if batches_root else None
		self.batches = batches or {}
		self.batch_order = batch_order or list(self.batches.keys())
		self.default_batch = default_batch or (self.batch_order[0] if self.batch_order else None)
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
		if parsed.path == "/api/reviews":
			try:
				_, paths = self._resolve_review_paths(parsed)
			except ValueError as exc:
				self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
				return
			query = parse_qs(parsed.query)
			uid = query.get("uid", [None])[0]
			if uid:
				self._send_json({"review": get_review(paths, uid)})
				return
			self._send_json(read_latest_reviews(paths))
			return
		if parsed.path == "/api/timeline-annotations":
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
			self._send_json({"annotations": read_timeline_annotations(paths, uid)})
			return
		super().do_GET()

	def do_POST(self) -> None:
		parsed = urlparse(self.path)
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

		if parsed.path == "/api/export/accepted":
			try:
				_, paths = self._resolve_review_paths(parsed, payload)
				manifest = export_accepted_assets(
					paths,
					clean=bool(payload.get("clean", False)),
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
	default_batch = batch_order[0] if batch_order else DEFAULT_BATCH_NAME
	handler = lambda *handler_args, **handler_kwargs: ReviewRequestHandler(
		*handler_args,
		directory=str(paths.project_root),
		review_paths=paths,
		batches_root=Path(args.batches_root).expanduser().resolve() if args.batches_root else None,
		batches=batches,
		batch_order=batch_order,
		default_batch=default_batch,
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
