from __future__ import annotations

import argparse
import json
from pathlib import Path

from server_batch_lib import intake_upload_bundle


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Extract, validate, and optionally publish an uploaded zip bundle from shared/incoming."
	)
	parser.add_argument("--upload-root", required=True, help="Incoming upload directory containing payload.zip")
	parser.add_argument("--workspace-root", required=True, help="Workspace root used to extract uploaded bundles")
	parser.add_argument("--published-root", default=None, help="Published batch root; required with --publish")
	parser.add_argument("--batch-name", default=None, help="Batch name to publish as")
	parser.add_argument("--label", default="", help="Batch label")
	parser.add_argument("--version", default="v1", help="Batch version")
	parser.add_argument("--keywords", default="", help="Comma-separated keywords")
	parser.add_argument("--cohort-id", default="", help="Optional cohort id")
	parser.add_argument("--shard-index", type=int, default=None, help="Optional shard index")
	parser.add_argument("--shard-count", type=int, default=None, help="Optional shard count")
	parser.add_argument("--days", default="", help="Comma-separated days carried by this batch")
	parser.add_argument("--force", action="store_true", help="Replace existing published batch if it exists")
	parser.add_argument("--clean-workspace", action="store_true", help="Remove prior extraction workspace before reprocessing")
	parser.add_argument(
		"--require-review-reference",
		action="store_true",
		help="Require every uid to contain line.csv or fmm.csv during validation",
	)
	parser.add_argument("--publish", action="store_true", help="Publish validated result root to published-root")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	report = intake_upload_bundle(
		upload_root=Path(args.upload_root),
		workspace_root=Path(args.workspace_root),
		published_root=Path(args.published_root).expanduser().resolve() if args.published_root else None,
		batch_name=args.batch_name,
		label=args.label,
		version=args.version,
		keywords=[item.strip() for item in args.keywords.split(",") if item.strip()],
		cohort_id=args.cohort_id,
		shard_index=args.shard_index,
		shard_count=args.shard_count,
		days=[item.strip() for item in args.days.split(",") if item.strip()],
		force=args.force,
		clean_workspace=args.clean_workspace,
		require_review_reference=args.require_review_reference,
		publish=args.publish,
	)
	print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
