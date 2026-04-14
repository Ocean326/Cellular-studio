#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from server_batch_lib import validate_batch_root


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Validate a published or to-be-published trajectory_annotation_studio batch root."
	)
	parser.add_argument("--batch-root", required=True, help="Batch root containing batch_meta.json or result/")
	parser.add_argument("--allow-missing-states-index", action="store_true", help="Do not fail if states_index.json is absent")
	parser.add_argument("--allow-missing-manifest", action="store_true", help="Do not fail if manifest.json is absent")
	parser.add_argument("--require-review-reference", action="store_true", help="Require every UID to have line.csv or fmm.csv")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	report = validate_batch_root(
		Path(args.batch_root).expanduser().resolve(),
		require_states_index=not args.allow_missing_states_index,
		require_manifest=not args.allow_missing_manifest,
		require_review_reference=bool(args.require_review_reference),
	)
	print(json.dumps(report, ensure_ascii=False, indent=2))
	if not report["ok"]:
		raise SystemExit(1)


if __name__ == "__main__":
	main()
