from __future__ import annotations

import argparse
import json

from review_lib import export_reviewer_bundle, resolve_review_paths


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Export one reviewer's reviews, annotations, and source sample files as a portable bundle."
	)
	parser.add_argument("--project-root", default=None, help="trajectory_annotation_studio project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review root")
	parser.add_argument("--export-root", default=None, help="Override output root for this bundle")
	parser.add_argument("--reviewer-id", required=True, help="Reviewer namespace to export")
	parser.add_argument("--bundle-name", default=None, help="Optional bundle directory name")
	parser.add_argument(
		"--decisions",
		default="accept,reject,skip",
		help="Comma-separated latest decision set to include. Default: accept,reject,skip",
	)
	parser.add_argument(
		"--clean",
		action="store_true",
		help="Remove the target bundle directory before writing",
	)
	parser.add_argument(
		"--zip",
		action="store_true",
		help="Also create a zip archive next to the exported bundle directory",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	paths = resolve_review_paths(
		project_root=args.project_root,
		result_root=args.result_root,
		review_root=args.review_root,
	)
	decisions = [item.strip() for item in str(args.decisions or "").split(",") if item.strip()]
	manifest = export_reviewer_bundle(
		paths,
		reviewer_id=args.reviewer_id,
		output_root=args.export_root,
		bundle_name=args.bundle_name,
		clean=args.clean,
		decisions=decisions,
		create_zip=bool(args.zip),
	)
	print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
