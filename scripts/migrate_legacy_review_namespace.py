#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = SCRIPT_ROOT / "web"

import sys

if str(WEB_ROOT) not in sys.path:
	sys.path.insert(0, str(WEB_ROOT))

from review_lib import (
	get_aggregate_dir,
	get_legacy_timeline_annotations_dir,
	get_reviewers_dir,
	load_ledger,
	resolve_review_paths,
	write_review,
	write_timeline_annotations,
)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Migrate legacy single-root review files into reviewer namespaces without deleting the legacy source."
	)
	parser.add_argument("--project-root", default=None, help="trajectory_annotation_studio project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review root")
	parser.add_argument("--export-root", default=None, help="Override export root")
	parser.add_argument(
		"--timeline-reviewer",
		default="legacy-import",
		help="Reviewer name used when importing legacy timeline annotations that have no reviewer dimension.",
	)
	parser.add_argument(
		"--clean-target",
		action="store_true",
		help="Remove review/reviewers and review/aggregate before importing. Legacy source files stay untouched.",
	)
	parser.add_argument(
		"--skip-reviews",
		action="store_true",
		help="Skip migrating legacy ledger.jsonl reviews.",
	)
	parser.add_argument(
		"--skip-timeline",
		action="store_true",
		help="Skip migrating legacy timeline annotations.",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	paths = resolve_review_paths(
		project_root=args.project_root,
		result_root=args.result_root,
		review_root=args.review_root,
		export_root=args.export_root,
	)
	reviewers_root = get_reviewers_dir(paths)
	aggregate_root = get_aggregate_dir(paths)
	if args.clean_target:
		if reviewers_root.exists():
			shutil.rmtree(reviewers_root)
		if aggregate_root.exists():
			shutil.rmtree(aggregate_root)
	elif reviewers_root.exists():
		raise FileExistsError(
			f"Target reviewer namespace root already exists: {reviewers_root}. Use --clean-target to rebuild."
		)

	imported_reviews = 0
	imported_timeline = 0

	if not args.skip_reviews and paths.ledger_path.exists():
		for entry in load_ledger(paths.ledger_path):
			write_review(paths, entry)
			imported_reviews += 1

	if not args.skip_timeline:
		legacy_timeline_dir = get_legacy_timeline_annotations_dir(paths)
		if legacy_timeline_dir.exists():
			for child in sorted(legacy_timeline_dir.iterdir(), key=lambda item: item.name):
				if child.suffix != ".json":
					continue
				payload = json.loads(child.read_text(encoding="utf-8"))
				write_timeline_annotations(
					paths,
					{
						"uid": payload.get("uid") or child.stem,
						"sample_id": payload.get("sample_id") or child.stem,
						"reviewer": args.timeline_reviewer,
						"updated_at": payload.get("updated_at"),
						"pins": payload.get("pins", []),
						"segments": payload.get("segments", []),
					},
				)
				imported_timeline += 1

	print(
		json.dumps(
			{
				"review_root": str(paths.review_root),
				"reviewers_root": str(reviewers_root),
				"aggregate_root": str(aggregate_root),
				"imported_reviews": imported_reviews,
				"imported_timeline_files": imported_timeline,
				"timeline_reviewer": args.timeline_reviewer,
			},
			ensure_ascii=False,
			indent=2,
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
