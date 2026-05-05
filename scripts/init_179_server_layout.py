#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from server_batch_lib import init_179_server_layout


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Initialize the recommended 179 server directory layout for trajectory_annotation_studio."
	)
	parser.add_argument("--root", required=True, help="Server root, for example /srv/trajectory_annotation_studio")
	parser.add_argument("--release-name", default="bootstrap", help="Initial app release directory name")
	parser.add_argument("--create-current-link", action="store_true", help="Create app/current symlink")
	parser.add_argument("--dry-run", action="store_true", help="Print the planned layout without modifying the filesystem")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	payload = init_179_server_layout(
		Path(args.root).expanduser().resolve(),
		release_name=args.release_name,
		create_current_link=args.create_current_link,
		dry_run=args.dry_run,
	)
	print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
