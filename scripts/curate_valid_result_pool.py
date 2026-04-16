#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
CELLULAR_QUALITY_SRC = REPO_ROOT / "my_history_methods" / "cellular_quality" / "src"
if str(CELLULAR_QUALITY_SRC) not in sys.path:
	sys.path.insert(0, str(CELLULAR_QUALITY_SRC))

from pipeline_utils.utils import build_web_manifest


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Curate strict-valid UID shards from a cellular_quality result pool."
	)
	parser.add_argument("--source-result-root", required=True, help="Source result root with manifest.json + validation_report.json")
	parser.add_argument("--output-root", required=True, help="Directory that will receive curated shard roots")
	parser.add_argument("--batch-prefix", required=True, help="Batch name prefix for generated shards")
	parser.add_argument("--shard-size", type=int, required=True, help="UID count per curated shard")
	parser.add_argument("--shard-count", type=int, required=True, help="How many curated shards to generate")
	parser.add_argument("--max-uids", type=int, default=0, help="Optional cap on how many valid UIDs to consume")
	parser.add_argument("--link-mode", choices=["symlink", "copy"], default="symlink", help="How to materialize UID directories")
	parser.add_argument("--version", default="v1", help="Version label written to batch_meta.json")
	parser.add_argument("--cohort-id", default="", help="Optional cohort id")
	parser.add_argument("--keywords", default="", help="Comma-separated keywords")
	parser.add_argument("--days", default="", help="Comma-separated day tokens")
	parser.add_argument("--force", action="store_true", help="Replace existing curated shard roots")
	return parser.parse_args()


def _link_or_copy(src: Path, dst: Path, link_mode: str) -> dict[str, str]:
	if dst.exists() or dst.is_symlink():
		if dst.is_symlink() or dst.is_file():
			dst.unlink()
		else:
			shutil.rmtree(dst)
	if link_mode == "copy":
		shutil.copytree(src, dst)
		return {"mode": "copy", "path": str(dst)}
	dst.symlink_to(src, target_is_directory=True)
	return {"mode": "symlink", "path": str(dst), "target": str(src)}


def _load_valid_uids(source_result_root: Path) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
	manifest_path = source_result_root / "manifest.json"
	validation_path = source_result_root / "validation_report.json"
	if not manifest_path.exists():
		raise FileNotFoundError(f"manifest.json not found under {source_result_root}")
	if not validation_path.exists():
		raise FileNotFoundError(f"validation_report.json not found under {source_result_root}")
	manifest = read_json(manifest_path)
	validation = read_json(validation_path)
	uids = [str(uid).strip() for uid in manifest.get("uids") or [] if str(uid).strip()]
	by_uid = validation.get("uids") or {}
	valid_uids = [uid for uid in uids if not bool((by_uid.get(uid) or {}).get("invalid_for_review"))]
	return valid_uids, manifest, validation


def _slice_chunks(items: list[str], shard_size: int, shard_count: int) -> list[list[str]]:
	chunks: list[list[str]] = []
	for index in range(shard_count):
		start = index * shard_size
		end = start + shard_size
		chunk = items[start:end]
		if len(chunk) != shard_size:
			raise ValueError(f"not enough valid uids for shard {index + 1}: expected {shard_size}, got {len(chunk)}")
		chunks.append(chunk)
	return chunks


def _keywords_from_arg(raw: str) -> list[str]:
	return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def curate_valid_pool(args: argparse.Namespace) -> dict[str, Any]:
	source_result_root = Path(args.source_result_root).expanduser().resolve()
	output_root = Path(args.output_root).expanduser().resolve()
	valid_uids, source_manifest, source_validation = _load_valid_uids(source_result_root)
	if args.max_uids and args.max_uids > 0:
		valid_uids = valid_uids[: args.max_uids]

	required = int(args.shard_size) * int(args.shard_count)
	if len(valid_uids) < required:
		raise ValueError(f"only {len(valid_uids)} strict-valid uids available, but {required} are required")

	selected = valid_uids[:required]
	chunks = _slice_chunks(selected, int(args.shard_size), int(args.shard_count))
	keywords = _keywords_from_arg(args.keywords)
	days = _keywords_from_arg(args.days)
	if not days:
		days = [str(item).strip() for item in source_manifest.get("days", []) if str(item).strip()]

	output_root.mkdir(parents=True, exist_ok=True)
	records: list[dict[str, Any]] = []
	for index, chunk in enumerate(chunks, start=1):
		batch_name = f"{args.batch_prefix}_b{index:02d}of{len(chunks):02d}_u{len(chunk)}"
		batch_root = output_root / batch_name
		result_root = batch_root / "result"
		if batch_root.exists():
			if not args.force:
				raise FileExistsError(f"curated shard already exists: {batch_root}")
			shutil.rmtree(batch_root)
		result_root.mkdir(parents=True, exist_ok=True)

		link_records: list[dict[str, str]] = []
		for uid in chunk:
			src_uid_dir = source_result_root / uid
			if not src_uid_dir.is_dir():
				raise FileNotFoundError(f"missing source uid dir: {src_uid_dir}")
			link_records.append(_link_or_copy(src_uid_dir, result_root / uid, args.link_mode))

		manifest = build_web_manifest(result_root)
		batch_meta = {
			"name": batch_name,
			"label": f"{args.batch_prefix} shard {index}/{len(chunks)}",
			"status": "curated",
			"version": args.version,
			"cohort_id": args.cohort_id,
			"keywords": keywords,
			"days": days,
			"shard_index": index,
			"shard_count": len(chunks),
			"source_result_root": str(source_result_root),
			"curated_from_result_root": str(source_result_root),
			"curated_at": utc_now_iso(),
			"selection_mode": "strict_valid",
			"selection_summary": {
				"selected_uid_count": len(chunk),
				"source_valid_uid_count": len(valid_uids),
				"source_uid_count": len(source_manifest.get("uids") or []),
				"source_invalid_uid_count": int((source_validation.get("summary") or {}).get("invalid_for_review_uid_count", 0)),
			},
			"uids": chunk,
		}
		write_json(batch_root / "batch_meta.json", batch_meta)
		(batch_root / "selected_uids.txt").write_text("".join(f"{uid}\n" for uid in chunk), encoding="utf-8")
		records.append(
			{
				"batch_name": batch_name,
				"batch_root": str(batch_root),
				"result_root": str(result_root),
				"uid_count": len(chunk),
				"validation_summary": manifest.get("validation_summary") or {},
				"link_mode": args.link_mode,
				"link_records_sample": link_records[:5],
			}
		)

	report = {
		"generated_at": utc_now_iso(),
		"source_result_root": str(source_result_root),
		"output_root": str(output_root),
		"selection_mode": "strict_valid",
		"source_uid_count": len(source_manifest.get("uids") or []),
		"source_valid_uid_count": len(valid_uids),
		"selected_uid_count": len(selected),
		"shard_size": int(args.shard_size),
		"shard_count": int(args.shard_count),
		"batches": records,
	}
	write_json(output_root / f"{args.batch_prefix}_curation_report.json", report)
	return report


def main() -> None:
	args = parse_args()
	report = curate_valid_pool(args)
	print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
