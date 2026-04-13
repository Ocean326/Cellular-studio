#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


STUDIO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDIO_ROOT.parent
DEFAULT_BATCHES_ROOT = REPO_ROOT / "project_data" / "cellular_quality_review_round1" / "workspace" / "review_batches"
DEFAULT_PORT = 8016


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start trajectory_annotation_studio against the shared cellular_quality review_batches root."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port.")
    parser.add_argument(
        "--project-root",
        default=str(STUDIO_ROOT),
        help="trajectory_annotation_studio project root.",
    )
    parser.add_argument(
        "--batches-root",
        default=str(DEFAULT_BATCHES_ROOT),
        help="Shared review batch root. Newest batch becomes the default preview batch.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    batches_root = Path(args.batches_root).expanduser().resolve()
    review_server = project_root / "web" / "review_server.py"
    if not review_server.exists():
        raise FileNotFoundError(f"review_server.py not found: {review_server}")
    if not batches_root.exists():
        raise FileNotFoundError(f"Batches root not found: {batches_root}")

    cmd = [
        sys.executable,
        str(review_server),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--project-root",
        str(project_root),
        "--batches-root",
        str(batches_root),
    ]
    print(
        f"Starting trajectory_annotation_studio on http://{args.host}:{args.port}/web/index.html "
        f"(batches_root={batches_root})",
        flush=True,
    )
    os.execv(sys.executable, cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
