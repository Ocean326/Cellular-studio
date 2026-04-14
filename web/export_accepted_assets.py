from __future__ import annotations

import argparse
import json

from review_lib import export_accepted_assets, resolve_review_paths


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Export accepted cellular_quality review assets for downstream consumption."
	)
	parser.add_argument("--project-root", default=None, help="cellular_quality project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review ledger root")
	parser.add_argument("--export-root", default=None, help="Override accepted export root")
	parser.add_argument(
		"--reviewer-id",
		default=None,
		help="Reviewer namespace to export from. Required when reviewer namespaces are enabled.",
	)
	parser.add_argument(
		"--clean",
		action="store_true",
		help="Remove the existing export root before writing new accepted assets",
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
	manifest = export_accepted_assets(
		paths,
		clean=args.clean,
		reviewer_id=args.reviewer_id,
	)
	print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
