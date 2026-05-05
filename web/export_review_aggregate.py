from __future__ import annotations

import argparse
import json

try:
	from .review_lib import export_review_aggregate, resolve_review_paths
except ImportError:
	from review_lib import export_review_aggregate, resolve_review_paths  # type: ignore


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Export aggregate multi-reviewer review summaries for organizer follow-up."
	)
	parser.add_argument("--project-root", default=None, help="trajectory_annotation_studio project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review root")
	parser.add_argument("--export-root", default=None, help="Optional output root for aggregate export")
	parser.add_argument(
		"--clean",
		action="store_true",
		help="Remove the existing aggregate export root before writing",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	paths = resolve_review_paths(
		project_root=args.project_root,
		result_root=args.result_root,
		review_root=args.review_root,
	)
	manifest = export_review_aggregate(
		paths,
		clean=args.clean,
		output_root=args.export_root,
	)
	print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
