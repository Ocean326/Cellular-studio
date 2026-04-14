from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RESULT_FILES = ("raw.csv", "snap.csv", "od.csv", "fmm.csv", "line.csv")


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
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


def ensure_dir(path: Path, dry_run: bool = False) -> dict[str, str]:
	record = {"path": str(path), "status": "planned" if dry_run else "created"}
	if not dry_run:
		path.mkdir(parents=True, exist_ok=True)
	return record


def resolve_result_root(batch_root: Path, metadata: dict[str, Any] | None = None) -> Path:
	metadata = metadata or {}
	local_result = batch_root / "result"
	if local_result.exists():
		return local_result.resolve()
	source_result_root = metadata.get("source_result_root")
	if source_result_root:
		candidate = Path(str(source_result_root)).expanduser().resolve()
		if candidate.exists():
			return candidate
	raise FileNotFoundError(f"Could not resolve result root for batch: {batch_root}")


def summarize_result_root(result_root: Path) -> dict[str, Any]:
	manifest_path = result_root / "manifest.json"
	states_index_path = result_root / "states_index.json"
	manifest_payload = read_json(manifest_path) if manifest_path.exists() else {}
	uids = list(manifest_payload.get("uids") or [])
	uid_dirs = sorted(path.name for path in result_root.iterdir() if path.is_dir()) if result_root.exists() else []
	file_counts = {name: 0 for name in DEFAULT_RESULT_FILES}
	for uid in uid_dirs:
		uid_dir = result_root / uid
		for name in DEFAULT_RESULT_FILES:
			if (uid_dir / name).exists():
				file_counts[name] += 1
	return {
		"result_root": str(result_root),
		"manifest_exists": manifest_path.exists(),
		"states_index_exists": states_index_path.exists(),
		"manifest_uid_count": len(uids),
		"uid_dir_count": len(uid_dirs),
		"uid_sample": uid_dirs[:10],
		"file_counts": file_counts,
	}


def validate_result_root(
	result_root: Path,
	require_states_index: bool = True,
	require_manifest: bool = True,
	require_review_reference: bool = False,
) -> dict[str, Any]:
	result_root = result_root.expanduser().resolve()
	errors: list[str] = []
	warnings: list[str] = []
	summary = summarize_result_root(result_root)
	if require_manifest and not summary["manifest_exists"]:
		errors.append("manifest.json is required")
	if require_states_index and not summary["states_index_exists"]:
		errors.append("states_index.json is required")
	if summary["manifest_exists"]:
		manifest_payload = read_json(result_root / "manifest.json")
		uids = [str(item).strip() for item in manifest_payload.get("uids") or [] if str(item).strip()]
		if not uids:
			errors.append("manifest.json.uids must be non-empty")
		for uid in uids:
			if not (result_root / uid).is_dir():
				errors.append(f"missing uid directory for manifest uid: {uid}")
		if summary["uid_dir_count"] and summary["manifest_uid_count"] != summary["uid_dir_count"]:
			warnings.append(
				f"manifest uid count {summary['manifest_uid_count']} differs from result dir count {summary['uid_dir_count']}"
			)
		if require_review_reference:
			for uid in uids:
				uid_dir = result_root / uid
				if not (uid_dir / "line.csv").exists() and not (uid_dir / "fmm.csv").exists():
					errors.append(f"uid {uid} is missing both line.csv and fmm.csv")
	else:
		if summary["uid_dir_count"] == 0:
			errors.append("result root does not contain any uid directories")
	return {
		"ok": not errors,
		"result_root": str(result_root),
		"errors": errors,
		"warnings": warnings,
		"summary": summary,
	}


def validate_batch_root(
	batch_root: Path,
	require_states_index: bool = True,
	require_manifest: bool = True,
	require_review_reference: bool = False,
) -> dict[str, Any]:
	metadata_path = batch_root / "batch_meta.json"
	metadata = read_json(metadata_path) if metadata_path.exists() else {}
	errors: list[str] = []
	warnings: list[str] = []
	try:
		result_root = resolve_result_root(batch_root, metadata)
	except Exception as exc:
		return {
			"ok": False,
			"batch_root": str(batch_root),
			"errors": [str(exc)],
			"warnings": [],
			"summary": {},
		}

	result_validation = validate_result_root(
		result_root,
		require_states_index=require_states_index,
		require_manifest=require_manifest,
		require_review_reference=require_review_reference,
	)
	errors.extend(result_validation["errors"])
	warnings.extend(result_validation["warnings"])
	summary = result_validation["summary"]

	return {
		"ok": not errors,
		"batch_root": str(batch_root),
		"metadata_path": str(metadata_path),
		"metadata": metadata,
		"errors": errors,
		"warnings": warnings,
		"summary": summary,
	}


def _iter_candidate_result_roots(root: Path) -> list[Path]:
	candidates: list[Path] = []
	for candidate in (
		root / "result",
		root,
	):
		if candidate.exists():
			candidates.append(candidate)
	children = [child for child in root.iterdir() if child.is_dir()] if root.exists() else []
	if len(children) == 1:
		child = children[0]
		for candidate in (child / "result", child):
			if candidate.exists():
				candidates.append(candidate)
	seen: set[Path] = set()
	unique_candidates: list[Path] = []
	for candidate in candidates:
		resolved = candidate.resolve()
		if resolved in seen:
			continue
		seen.add(resolved)
		unique_candidates.append(resolved)
	return unique_candidates


def resolve_uploaded_result_root(extracted_root: Path) -> Path:
	for candidate in _iter_candidate_result_roots(extracted_root.expanduser().resolve()):
		if (candidate / "manifest.json").exists():
			return candidate
	raise FileNotFoundError(
		f"Could not resolve uploaded result root under {extracted_root}; expected manifest.json in root or result/"
	)


def extract_upload_zip(
	zip_path: Path,
	destination_root: Path,
	*,
	clean: bool = False,
) -> dict[str, Any]:
	zip_path = zip_path.expanduser().resolve()
	destination_root = destination_root.expanduser().resolve()
	if not zip_path.exists():
		raise FileNotFoundError(f"upload zip not found: {zip_path}")
	if clean and destination_root.exists():
		shutil.rmtree(destination_root)
	destination_root.mkdir(parents=True, exist_ok=True)
	extracted_files = 0
	with zipfile.ZipFile(zip_path) as archive:
		for member in archive.infolist():
			member_path = Path(member.filename)
			if member_path.is_absolute() or ".." in member_path.parts:
				raise ValueError(f"unsafe zip member path: {member.filename}")
			target_path = destination_root / member_path
			if member.is_dir():
				target_path.mkdir(parents=True, exist_ok=True)
				continue
			target_path.parent.mkdir(parents=True, exist_ok=True)
			with archive.open(member) as src, open(target_path, "wb") as dst:
				shutil.copyfileobj(src, dst)
			extracted_files += 1
	return {
		"zip_path": str(zip_path),
		"destination_root": str(destination_root),
		"extracted_files": extracted_files,
	}


def intake_upload_bundle(
	*,
	upload_root: Path,
	workspace_root: Path,
	published_root: Path | None = None,
	batch_name: str | None = None,
	label: str = "",
	version: str = "v1",
	keywords: list[str] | None = None,
	cohort_id: str = "",
	shard_index: int | None = None,
	shard_count: int | None = None,
	days: list[str] | None = None,
	force: bool = False,
	clean_workspace: bool = False,
	require_review_reference: bool = False,
	publish: bool = False,
) -> dict[str, Any]:
	upload_root = upload_root.expanduser().resolve()
	workspace_root = workspace_root.expanduser().resolve()
	status_path = upload_root / "upload_status.json"
	payload = read_json(status_path) if status_path.exists() else {}
	payload_path = upload_root / "payload.zip"
	if not payload_path.exists():
		raise FileNotFoundError(f"payload.zip not found under upload root: {upload_root}")
	upload_id = str(payload.get("upload_id") or upload_root.name).strip() or upload_root.name
	extract_root = workspace_root / upload_id / "extracted"
	extraction = extract_upload_zip(payload_path, extract_root, clean=clean_workspace)
	result_root = resolve_uploaded_result_root(extract_root)
	validation = validate_result_root(
		result_root,
		require_states_index=True,
		require_manifest=True,
		require_review_reference=require_review_reference,
	)
	report = {
		"generated_at": utc_now_iso(),
		"upload_id": upload_id,
		"upload_root": str(upload_root),
		"status_path": str(status_path),
		"payload_path": str(payload_path),
		"workspace_root": str(workspace_root),
		"extract_root": extraction["destination_root"],
		"result_root": str(result_root),
		"validation": validation,
		"published": None,
	}
	if publish:
		if not published_root:
			raise ValueError("published_root is required when publish=True")
		if not batch_name:
			raise ValueError("batch_name is required when publish=True")
		if not validation["ok"]:
			raise ValueError(f"cannot publish invalid upload bundle: {validation['errors']}")
		report["published"] = publish_batch(
			published_root=published_root,
			batch_name=batch_name,
			source_result_root=result_root,
			label=label,
			version=version,
			keywords=keywords,
			cohort_id=cohort_id,
			shard_index=shard_index,
			shard_count=shard_count,
			days=days,
			force=force,
			validate=True,
		)
	incoming_report_path = upload_root / "intake_report.json"
	write_json(incoming_report_path, report)
	if status_path.exists():
		status_payload = dict(payload)
		status_payload["intake"] = {
			"processed_at": report["generated_at"],
			"extract_root": report["extract_root"],
			"result_root": report["result_root"],
			"validation_ok": validation["ok"],
			"report_path": str(incoming_report_path),
			"published_batch": report["published"]["metadata"]["name"] if report["published"] else "",
		}
		write_json(status_path, status_payload)
	report["report_path"] = str(incoming_report_path)
	return report


def init_179_server_layout(
	root: Path,
	release_name: str = "bootstrap",
	create_current_link: bool = False,
	dry_run: bool = False,
) -> dict[str, Any]:
	release_root = root / "app" / "releases" / release_name
	layout_paths = [
		release_root,
		root / "datasets" / "cellular_quality",
		root / "shared" / "published",
		root / "shared" / "incoming",
		root / "shared" / "exports",
		root / "runtime" / "logs",
		root / "runtime" / "tmp",
		root / "runtime" / "uploads",
		root / "workspaces",
	]
	records = [ensure_dir(path, dry_run=dry_run) for path in layout_paths]
	current_link = root / "app" / "current"
	link_record = {
		"path": str(current_link),
		"target": str(release_root),
		"status": "skipped",
	}
	if create_current_link:
		link_record["status"] = "planned" if dry_run else "created"
		if not dry_run:
			if current_link.exists() or current_link.is_symlink():
				if current_link.is_dir() and not current_link.is_symlink():
					shutil.rmtree(current_link)
				else:
					current_link.unlink()
			relative_target = os.path.relpath(release_root, start=current_link.parent)
			current_link.symlink_to(relative_target)
	return {
		"generated_at": utc_now_iso(),
		"root": str(root),
		"release_root": str(release_root),
		"directories": records,
		"current_link": link_record,
	}


def build_batch_metadata(
	*,
	batch_name: str,
	source_result_root: Path,
	label: str = "",
	version: str = "v1",
	keywords: list[str] | None = None,
	cohort_id: str = "",
	shard_index: int | None = None,
	shard_count: int | None = None,
	days: list[str] | None = None,
	status: str = "published",
	result_mode: str = "mounted",
	uid_count: int | None = None,
) -> dict[str, Any]:
	payload = {
		"name": batch_name,
		"label": label or batch_name,
		"version": version,
		"created_at": utc_now_iso(),
		"keywords": keywords or [],
		"cohort_id": cohort_id,
		"days": days or [],
		"status": status,
		"result_mode": result_mode,
		"source_result_root": str(source_result_root),
	}
	if shard_index is not None:
		payload["shard_index"] = int(shard_index)
	if shard_count is not None:
		payload["shard_count"] = int(shard_count)
	if uid_count is not None:
		payload["uid_count"] = int(uid_count)
	return payload


def publish_batch(
	*,
	published_root: Path,
	batch_name: str,
	source_result_root: Path,
	label: str = "",
	version: str = "v1",
	keywords: list[str] | None = None,
	cohort_id: str = "",
	shard_index: int | None = None,
	shard_count: int | None = None,
	days: list[str] | None = None,
	status: str = "published",
	force: bool = False,
	dry_run: bool = False,
	validate: bool = True,
) -> dict[str, Any]:
	source_result_root = source_result_root.expanduser().resolve()
	if not source_result_root.exists():
		raise FileNotFoundError(f"source result root not found: {source_result_root}")
	summary = summarize_result_root(source_result_root)
	target_root = published_root / batch_name
	stage_root = published_root / f".{batch_name}.staging"
	if target_root.exists() and not force:
		raise FileExistsError(f"published batch already exists: {target_root}")
	if dry_run:
		return {
			"generated_at": utc_now_iso(),
			"dry_run": True,
			"published_root": str(published_root),
			"target_root": str(target_root),
			"source_result_root": str(source_result_root),
			"summary": summary,
		}
	metadata = build_batch_metadata(
		batch_name=batch_name,
		source_result_root=source_result_root,
		label=label,
		version=version,
		keywords=keywords,
		cohort_id=cohort_id,
		shard_index=shard_index,
		shard_count=shard_count,
		days=days,
		status=status,
		result_mode="mounted",
		uid_count=summary["manifest_uid_count"] or summary["uid_dir_count"],
	)
	if stage_root.exists():
		shutil.rmtree(stage_root)
	stage_root.mkdir(parents=True, exist_ok=True)
	write_json(stage_root / "batch_meta.json", metadata)
	write_json(
		stage_root / "source_batch.json",
		{
			"generated_at": utc_now_iso(),
			"batch_name": batch_name,
			"source_result_root": str(source_result_root),
			"summary": summary,
		},
	)
	for relative in (
		Path("review/system"),
		Path("review/reviewers"),
		Path("review/aggregate"),
		Path("accepted_assets/reviewers"),
		Path("review_exports/aggregate"),
	):
		(stage_root / relative).mkdir(parents=True, exist_ok=True)
	if validate:
		report = validate_batch_root(stage_root)
		write_json(stage_root / "validation_report.json", report)
		if not report["ok"]:
			raise ValueError(f"published batch validation failed: {report['errors']}")
	if target_root.exists():
		shutil.rmtree(target_root)
	stage_root.rename(target_root)
	return {
		"generated_at": utc_now_iso(),
		"published_root": str(published_root),
		"target_root": str(target_root),
		"metadata": metadata,
		"summary": summary,
	}
