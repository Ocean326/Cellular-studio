from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8016"
DEFAULT_TIMEOUT_SECONDS = 30.0
VALID_REVIEW_STATUSES = frozenset({"any", "reviewed", "unreviewed"})


def _dedupe_preserve_order(items: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for item in items:
		text = str(item or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		result.append(text)
	return result


def _preview_csv_text(text: str, preview_rows: int) -> tuple[list[dict[str, str]], int]:
	reader = csv.DictReader(io.StringIO(text))
	rows = list(reader)
	return rows[: max(0, int(preview_rows))], len(rows)


class StudioAgentClientError(RuntimeError):
	pass


@dataclass(frozen=True)
class BatchFilePayload:
	relative_path: str
	url: str
	exists: bool
	content_type: str
	text: str | None = None
	json_payload: dict[str, Any] | list[Any] | None = None
	preview_rows: list[dict[str, str]] | None = None
	row_count: int | None = None
	error: str = ""


class StudioAgentClient:
	def __init__(
		self,
		base_url: str = DEFAULT_BASE_URL,
		batch: str | None = None,
		timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
	) -> None:
		self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
		self.batch = str(batch or "").strip() or None
		self.timeout_seconds = float(timeout_seconds)

	def _build_url(self, path: str, query: dict[str, Any] | None = None) -> str:
		parsed = urlparse(f"{self.base_url}{path}")
		existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
		for key, value in (query or {}).items():
			if value is None or value == "":
				continue
			existing[str(key)] = str(value)
		return urlunparse(parsed._replace(query=urlencode(existing)))

	def _request(
		self,
		method: str,
		path: str,
		payload: dict[str, Any] | None = None,
		query: dict[str, Any] | None = None,
	) -> tuple[str, str]:
		body = None
		headers = {}
		if payload is not None:
			body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
			headers["Content-Type"] = "application/json"
		request = Request(
			self._build_url(path, query=query),
			data=body,
			headers=headers,
			method=method,
		)
		try:
			with urlopen(request, timeout=self.timeout_seconds) as response:
				return str(response.headers.get("Content-Type") or ""), response.read().decode("utf-8")
		except HTTPError as exc:
			raw = exc.read().decode("utf-8", errors="replace")
			message = raw
			try:
				message = json.loads(raw).get("error") or raw
			except Exception:
				pass
			raise StudioAgentClientError(f"{method} {path} failed: HTTP {exc.code}: {message}") from exc
		except URLError as exc:
			raise StudioAgentClientError(f"{method} {path} failed: {exc}") from exc

	def _request_json(
		self,
		method: str,
		path: str,
		payload: dict[str, Any] | None = None,
		query: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		_, text = self._request(method, path, payload=payload, query=query)
		try:
			return json.loads(text)
		except json.JSONDecodeError as exc:
			raise StudioAgentClientError(f"{method} {path} returned invalid JSON: {exc}") from exc

	def _effective_batch(self, batch: str | None = None) -> str:
		explicit = str(batch or "").strip() or self.batch
		if explicit:
			return explicit
		payload = self.list_batches()
		current_batch = str(payload.get("current_batch") or "").strip()
		if current_batch:
			return current_batch
		raise StudioAgentClientError("No batch selected and server did not expose a current batch")

	def _batch_query(self, batch: str | None = None) -> dict[str, Any]:
		effective = str(batch or "").strip() or self.batch
		return {"batch": effective} if effective else {}

	def batch_data_url(self, relative_path: str, batch: str | None = None) -> str:
		effective_batch = self._effective_batch(batch=batch)
		parts = [quote(part) for part in str(relative_path).split("/") if str(part).strip()]
		return f"{self.base_url}/batch-data/{quote(effective_batch)}/{'/'.join(parts)}"

	def fetch_batch_text(self, relative_path: str, batch: str | None = None) -> str:
		url = self.batch_data_url(relative_path, batch=batch)
		request = Request(url, method="GET")
		try:
			with urlopen(request, timeout=self.timeout_seconds) as response:
				return response.read().decode("utf-8")
		except HTTPError as exc:
			raise StudioAgentClientError(
				f"GET batch-data/{relative_path} failed for batch {self._effective_batch(batch=batch)}: HTTP {exc.code}"
			) from exc
		except URLError as exc:
			raise StudioAgentClientError(f"GET {url} failed: {exc}") from exc

	def fetch_batch_json(self, relative_path: str, batch: str | None = None) -> dict[str, Any]:
		text = self.fetch_batch_text(relative_path, batch=batch)
		try:
			return json.loads(text)
		except json.JSONDecodeError as exc:
			raise StudioAgentClientError(
				f"batch-data/{relative_path} for batch {self._effective_batch(batch=batch)} is not valid JSON: {exc}"
			) from exc

	def health(self, batch: str | None = None) -> dict[str, Any]:
		return self._request_json("GET", "/api/health", query=self._batch_query(batch=batch))

	def list_batches(self) -> dict[str, Any]:
		return self._request_json("GET", "/api/batches")

	def batch_info(self, batch: str | None = None) -> dict[str, Any]:
		payload = self.list_batches()
		target = str(batch or self.batch or payload.get("current_batch") or "").strip()
		if not target:
			raise StudioAgentClientError("No batch selected and server did not expose a current batch")
		for item in payload.get("batches", []) or []:
			if isinstance(item, dict) and str(item.get("name") or "").strip() == target:
				return dict(item)
		raise StudioAgentClientError(f"Batch not found: {target}")

	def batch_result_root(self, batch: str | None = None) -> Path:
		info = self.batch_info(batch=batch)
		result_root = str(info.get("result_root") or "").strip()
		if not result_root:
			raise StudioAgentClientError(f"Batch {info.get('name') or batch or self.batch} does not expose result_root")
		path = Path(result_root).expanduser().resolve()
		if not path.is_dir():
			raise StudioAgentClientError(f"Batch result_root is not accessible locally: {path}")
		return path

	def read_manifest(self, batch: str | None = None) -> dict[str, Any]:
		return self.fetch_batch_json("manifest.json", batch=batch)

	def list_samples(
		self,
		batch: str | None = None,
		tags: list[str] | None = None,
		limit: int | None = None,
		offset: int = 0,
		review_status: str = "any",
		reviewer_id: str | None = None,
	) -> dict[str, Any]:
		effective_batch = self._effective_batch(batch=batch)
		manifest = self.read_manifest(batch=effective_batch)
		states = manifest.get("states") if isinstance(manifest.get("states"), dict) else {}
		required_tags = {str(tag).strip() for tag in (tags or []) if str(tag).strip()}
		normalized_review_status = str(review_status or "any").strip().lower() or "any"
		if normalized_review_status not in VALID_REVIEW_STATUSES:
			raise StudioAgentClientError(
				f"Unsupported review_status: {review_status!r}. Expected one of {sorted(VALID_REVIEW_STATUSES)}"
			)
		target_reviewer_id = str(reviewer_id or "").strip() or None
		items: list[dict[str, Any]] = []
		for uid in manifest.get("uids", []) or []:
			tags_for_uid = list(states.get(uid) or [])
			if required_tags and required_tags.isdisjoint(tags_for_uid):
				continue
			review_meta: dict[str, Any] = {
				"reviewed": None,
				"reviewed_by_target_reviewer": None,
				"reviewer_count": None,
			}
			if normalized_review_status != "any" or target_reviewer_id:
				aggregate = self.review_aggregate(str(uid), batch=effective_batch).get("aggregate") or {}
				latest_reviews = aggregate.get("latest_reviews") if isinstance(aggregate.get("latest_reviews"), list) else []
				reviewer_ids = {
					str(item.get("reviewer_id") or "").strip()
					for item in latest_reviews
					if isinstance(item, dict) and str(item.get("reviewer_id") or "").strip()
				}
				reviewed = bool(latest_reviews)
				reviewed_by_target = target_reviewer_id in reviewer_ids if target_reviewer_id else reviewed
				review_meta = {
					"reviewed": reviewed,
					"reviewed_by_target_reviewer": reviewed_by_target if target_reviewer_id else None,
					"reviewer_count": int(aggregate.get("reviewer_count") or 0),
				}
				if normalized_review_status == "reviewed" and not reviewed_by_target:
					continue
				if normalized_review_status == "unreviewed" and reviewed_by_target:
					continue
			items.append(
				{
					"uid": str(uid),
					"tags": tags_for_uid,
					**review_meta,
				}
			)
		sliced = items[max(0, int(offset)) :]
		if limit is not None and int(limit) >= 0:
			sliced = sliced[: int(limit)]
		return {
			"batch": effective_batch,
			"total": len(items),
			"offset": max(0, int(offset)),
			"limit": None if limit is None else int(limit),
			"review_status": normalized_review_status,
			"reviewer_id": target_reviewer_id,
			"items": sliced,
		}

	def _read_batch_file(
		self,
		uid: str,
		filename: str,
		batch: str,
		preview_rows: int,
	) -> BatchFilePayload:
		relative_path = f"{uid}/{filename}"
		url = self.batch_data_url(relative_path, batch=batch)
		request = Request(url, method="GET")
		try:
			with urlopen(request, timeout=self.timeout_seconds) as response:
				content_type = str(response.headers.get("Content-Type") or "")
				text = response.read().decode("utf-8")
		except HTTPError as exc:
			return BatchFilePayload(
				relative_path=relative_path,
				url=url,
				exists=False,
				content_type="",
				error=f"HTTP {exc.code}",
			)
		if filename.endswith(".json"):
			try:
				payload = json.loads(text)
			except json.JSONDecodeError as exc:
				return BatchFilePayload(
					relative_path=relative_path,
					url=url,
					exists=True,
					content_type=content_type,
					text=text,
					error=f"invalid json: {exc}",
				)
			return BatchFilePayload(
				relative_path=relative_path,
				url=url,
				exists=True,
				content_type=content_type,
				text=text,
				json_payload=payload,
			)
		if filename.endswith(".csv"):
			preview, row_count = _preview_csv_text(text, preview_rows=preview_rows)
			return BatchFilePayload(
				relative_path=relative_path,
				url=url,
				exists=True,
				content_type=content_type,
				text=text,
				preview_rows=preview,
				row_count=row_count,
			)
		return BatchFilePayload(
			relative_path=relative_path,
			url=url,
			exists=True,
			content_type=content_type,
			text=text,
		)

	def inspect_sample(
		self,
		uid: str,
		batch: str | None = None,
		preview_rows: int = 8,
		include_files: list[str] | None = None,
		include_aggregate: bool = True,
	) -> dict[str, Any]:
		effective_batch = self._effective_batch(batch=batch)
		manifest = self.read_manifest(batch=effective_batch)
		uids = [str(item) for item in (manifest.get("uids") or [])]
		if str(uid) not in uids:
			raise StudioAgentClientError(f"UID {uid} not found in batch {effective_batch}")
		layer_specs = manifest.get("layer_specs") if isinstance(manifest.get("layer_specs"), dict) else {}
		reference_files = list(manifest.get("review_reference_files") or [])
		default_files: list[str] = ["case_manifest.json", "signal.csv", "raw.csv", "snap.csv", "od.csv", "line.csv", "fmm.csv"]
		for spec in layer_specs.values():
			if isinstance(spec, dict):
				default_files.append(str(spec.get("filename") or ""))
		default_files.extend(reference_files)
		selected_files = _dedupe_preserve_order(include_files or default_files)
		file_payloads = [
			self._read_batch_file(str(uid), filename, batch=effective_batch, preview_rows=preview_rows)
			for filename in selected_files
		]
		result = {
			"batch": effective_batch,
			"uid": str(uid),
			"tags": list((manifest.get("states") or {}).get(str(uid)) or []),
			"review_reference_files": reference_files,
			"files": [
				{
					"relative_path": item.relative_path,
					"url": item.url,
					"exists": item.exists,
					"content_type": item.content_type,
					"row_count": item.row_count,
					"preview_rows": item.preview_rows,
					"json_payload": item.json_payload,
					"error": item.error,
				}
				for item in file_payloads
			],
		}
		if include_aggregate:
			result["review_aggregate"] = self.review_aggregate(str(uid), batch=effective_batch).get("aggregate")
			result["timeline_aggregate"] = self.timeline_aggregate(str(uid), batch=effective_batch).get("aggregate")
		return result

	def materialize_sample(
		self,
		uid: str,
		output_dir: str | Path,
		batch: str | None = None,
		preview_rows: int = 8,
		include_files: list[str] | None = None,
	) -> dict[str, Any]:
		payload = self.inspect_sample(
			uid=uid,
			batch=batch,
			preview_rows=preview_rows,
			include_files=include_files,
			include_aggregate=True,
		)
		target_root = Path(output_dir).expanduser().resolve()
		target_root.mkdir(parents=True, exist_ok=True)
		context_path = target_root / "context.json"
		context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
		for item in payload.get("files", []):
			relative_path = str(item.get("relative_path") or "").strip()
			if not relative_path or not item.get("exists"):
				continue
			text = self.fetch_batch_text(relative_path, batch=payload["batch"])
			file_path = target_root / relative_path
			file_path.parent.mkdir(parents=True, exist_ok=True)
			file_path.write_text(text, encoding="utf-8")
		return {
			"batch": payload["batch"],
			"uid": payload["uid"],
			"output_dir": str(target_root),
			"context_path": str(context_path),
		}

	def open_reviewer_session(
		self,
		display_name: str,
		reviewer_id: str | None = None,
		batch: str | None = None,
	) -> dict[str, Any]:
		payload = {"display_name": str(display_name).strip()}
		if reviewer_id:
			payload["reviewer_id"] = str(reviewer_id).strip()
		return self._request_json(
			"POST",
			"/api/reviewers/session",
			payload=payload,
			query=self._batch_query(batch=batch),
		)

	def list_reviewers(self, batch: str | None = None) -> dict[str, Any]:
		return self._request_json("GET", "/api/reviewers", query=self._batch_query(batch=batch))

	def get_review(
		self,
		uid: str,
		reviewer_id: str | None = None,
		batch: str | None = None,
	) -> dict[str, Any]:
		query = self._batch_query(batch=batch)
		query["uid"] = str(uid)
		if reviewer_id:
			query["reviewer_id"] = str(reviewer_id)
		return self._request_json("GET", "/api/reviews", query=query)

	def submit_review(
		self,
		uid: str,
		decision: str,
		reviewer_id: str,
		reviewer_name: str,
		notes: str = "",
		reference_source: str = "",
		trajectory_tags: list[str] | None = None,
		batch: str | None = None,
	) -> dict[str, Any]:
		payload = {
			"uid": str(uid),
			"decision": str(decision).strip().lower(),
			"reviewer_id": str(reviewer_id).strip(),
			"reviewer_name": str(reviewer_name).strip(),
			"notes": str(notes),
			"reference_source": str(reference_source),
			"trajectory_tags": list(trajectory_tags or []),
		}
		return self._request_json(
			"POST",
			"/api/reviews",
			payload=payload,
			query=self._batch_query(batch=batch),
		)

	def review_aggregate(self, uid: str, batch: str | None = None) -> dict[str, Any]:
		query = self._batch_query(batch=batch)
		query["uid"] = str(uid)
		return self._request_json("GET", "/api/reviews/aggregate", query=query)

	def get_timeline(
		self,
		uid: str,
		reviewer_id: str | None = None,
		batch: str | None = None,
	) -> dict[str, Any]:
		query = self._batch_query(batch=batch)
		query["uid"] = str(uid)
		if reviewer_id:
			query["reviewer_id"] = str(reviewer_id)
		return self._request_json("GET", "/api/timeline-annotations", query=query)

	def put_timeline(
		self,
		uid: str,
		reviewer_id: str,
		reviewer_name: str,
		payload: dict[str, Any],
		batch: str | None = None,
	) -> dict[str, Any]:
		merged = dict(payload)
		merged["uid"] = str(uid)
		merged["reviewer_id"] = str(reviewer_id)
		merged["reviewer_name"] = str(reviewer_name)
		return self._request_json(
			"POST",
			"/api/timeline-annotations",
			payload=merged,
			query=self._batch_query(batch=batch),
		)

	def get_track_edits(
		self,
		uid: str,
		reviewer_id: str,
		batch: str | None = None,
	) -> dict[str, Any]:
		query = self._batch_query(batch=batch)
		query["uid"] = str(uid)
		query["reviewer_id"] = str(reviewer_id)
		return self._request_json("GET", "/api/track-edits", query=query)

	def put_track_edits(
		self,
		uid: str,
		reviewer_id: str,
		reviewer_name: str,
		payload: dict[str, Any],
		batch: str | None = None,
	) -> dict[str, Any]:
		merged = dict(payload)
		merged["uid"] = str(uid)
		merged["reviewer_id"] = str(reviewer_id)
		merged["reviewer_name"] = str(reviewer_name)
		return self._request_json(
			"POST",
			"/api/track-edits",
			payload=merged,
			query=self._batch_query(batch=batch),
		)

	def export_track_edits(self, uid: str, reviewer_id: str, batch: str | None = None) -> dict[str, Any]:
		effective_batch = self._effective_batch(batch=batch)
		track_payload = self.get_track_edits(uid, reviewer_id, batch=effective_batch)
		timeline_payload = self.get_timeline(uid, reviewer_id=reviewer_id, batch=effective_batch)
		return {
			"batch": effective_batch,
			"uid": str(uid),
			"reviewer_id": str(reviewer_id),
			"track_edits": track_payload.get("track_edits"),
			"timeline_annotations": timeline_payload.get("annotations"),
		}

	def timeline_aggregate(self, uid: str, batch: str | None = None) -> dict[str, Any]:
		query = self._batch_query(batch=batch)
		query["uid"] = str(uid)
		return self._request_json("GET", "/api/timeline-annotations/aggregate", query=query)

	def export_review_aggregate(self, clean: bool = False, batch: str | None = None) -> dict[str, Any]:
		return self._request_json(
			"POST",
			"/api/export/review-aggregate",
			payload={"clean": bool(clean)},
			query=self._batch_query(batch=batch),
		)

	def export_reviewer_bundle(
		self,
		reviewer_id: str,
		batch: str | None = None,
		clean: bool = False,
		create_zip: bool = False,
		decision_filters: list[str] | None = None,
		uids: list[str] | None = None,
		trajectory_tags: list[str] | None = None,
		export_mode: str = "",
		bundle_name: str | None = None,
		interval_seconds: int | None = None,
		timestamp_unit: str | None = None,
		labeled_span_only: bool = False,
	) -> dict[str, Any]:
		payload = {
			"reviewer_id": str(reviewer_id).strip(),
			"clean": bool(clean),
			"create_zip": bool(create_zip),
			"decisions": list(decision_filters or ["accept", "reject", "skip"]),
			"uids": list(uids or []),
			"trajectory_tags": list(trajectory_tags or []),
		}
		if export_mode:
			payload["export_mode"] = str(export_mode).strip()
		if bundle_name:
			payload["bundle_name"] = str(bundle_name).strip()
		if interval_seconds is not None:
			payload["interval_seconds"] = int(interval_seconds)
		if timestamp_unit is not None and str(timestamp_unit).strip():
			payload["timestamp_unit"] = str(timestamp_unit).strip()
		if labeled_span_only:
			payload["labeled_span_only"] = True
		return self._request_json(
			"POST",
			"/api/export/reviewer-bundle",
			payload=payload,
			query=self._batch_query(batch=batch),
		)
