#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
	from .server_batch_lib import publish_batch, read_json, resolve_result_root
except ImportError:
	from server_batch_lib import publish_batch, read_json, resolve_result_root  # type: ignore


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Publish a mounted trajectory_annotation_studio batch into the shared published root."
	)
	parser.add_argument("--published-root", required=True, help="Published batches root")
	parser.add_argument("--batch-name", required=True, help="Published batch name")
	parser.add_argument("--source-result-root", default=None, help="Result root to mount")
	parser.add_argument("--source-batch-root", default=None, help="Optional source batch root to derive result root and metadata from")
	parser.add_argument("--label", default="", help="Display label")
	parser.add_argument("--version", default="v1", help="Batch version")
	parser.add_argument("--keywords", default="", help="Comma-separated keywords")
	parser.add_argument("--cohort-id", default="", help="Cohort id for sharded large datasets")
	parser.add_argument("--shard-index", type=int, default=None, help="Shard index")
	parser.add_argument("--shard-count", type=int, default=None, help="Shard count")
	parser.add_argument("--days", default="", help="Comma-separated day list")
	parser.add_argument("--status", default="published", help="Batch publish status")
	parser.add_argument("--force", action="store_true", help="Replace an existing published batch")
	parser.add_argument("--dry-run", action="store_true", help="Print the publish plan without writing")
	parser.add_argument("--skip-validate", action="store_true", help="Skip validation during publish")
	return parser.parse_args()


def _resolve_source(args: argparse.Namespace) -> tuple[Path, dict]:
	if args.source_batch_root:
		source_batch_root = Path(args.source_batch_root).expanduser().resolve()
		meta_path = source_batch_root / "batch_meta.json"
		metadata = read_json(meta_path) if meta_path.exists() else {}
		result_root = resolve_result_root(source_batch_root, metadata)
		return result_root, metadata
	if not args.source_result_root:
		raise SystemExit("either --source-result-root or --source-batch-root is required")
	return Path(args.source_result_root).expanduser().resolve(), {}


def main() -> None:
	args = parse_args()
	source_result_root, source_metadata = _resolve_source(args)
	keywords = [item.strip() for item in str(args.keywords or "").split(",") if item.strip()]
	if not keywords:
		keywords = [str(item).strip() for item in source_metadata.get("keywords", []) if str(item).strip()]
	days = [item.strip() for item in str(args.days or "").split(",") if item.strip()]
	if not days:
		days = [str(item).strip() for item in source_metadata.get("days", []) if str(item).strip()]
	payload = publish_batch(
		published_root=Path(args.published_root).expanduser().resolve(),
		batch_name=args.batch_name,
		source_result_root=source_result_root,
		label=args.label or str(source_metadata.get("label") or ""),
		version=args.version or str(source_metadata.get("version") or "v1"),
		keywords=keywords,
		cohort_id=args.cohort_id or str(source_metadata.get("cohort_id") or ""),
		shard_index=args.shard_index if args.shard_index is not None else source_metadata.get("shard_index"),
		shard_count=args.shard_count if args.shard_count is not None else source_metadata.get("shard_count"),
		days=days,
		status=args.status,
		force=bool(args.force),
		dry_run=bool(args.dry_run),
		validate=not bool(args.skip_validate),
	)
	print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
