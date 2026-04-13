#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STUDIO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_BATCHES_ROOT = STUDIO_ROOT / "data" / "batches"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def symlink_path(target_path: Path, source_path: Path) -> None:
    if target_path.exists() or target_path.is_symlink():
        if target_path.is_dir() and not target_path.is_symlink():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    relative_source = os.path.relpath(source_path, start=target_path.parent)
    os.symlink(relative_source, target_path)


def ensure_review_root(review_root: Path) -> None:
    review_root.mkdir(parents=True, exist_ok=True)
    ledger_path = review_root / "ledger.jsonl"
    latest_path = review_root / "latest_reviews.json"
    if not ledger_path.exists():
        ledger_path.write_text("", encoding="utf-8")
    if not latest_path.exists():
        write_json(
            latest_path,
            {
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "count": 0,
                "counts": {"accept": 0, "reject": 0, "skip": 0},
                "reviews": {},
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expose a cellular_quality review batch inside trajectory_annotation_studio/data/batches."
    )
    parser.add_argument("--source-batch-root", required=True, help="Source review batch root.")
    parser.add_argument(
        "--output-batches-root",
        default=str(DEFAULT_OUTPUT_BATCHES_ROOT),
        help="Studio batches root.",
    )
    parser.add_argument("--batch-name", default="", help="Optional target batch name. Defaults to source batch name.")
    parser.add_argument("--force", action="store_true", help="Overwrite target batch if it already exists.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_batch_root = Path(args.source_batch_root).expanduser().resolve()
    if not source_batch_root.exists():
        raise FileNotFoundError(f"Source batch root not found: {source_batch_root}")

    result_root = source_batch_root / "result"
    if not result_root.exists():
        raise FileNotFoundError(f"Source result root not found: {result_root}")

    output_batches_root = Path(args.output_batches_root).expanduser().resolve()
    batch_name = str(args.batch_name or "").strip() or source_batch_root.name
    target_batch_root = output_batches_root / batch_name

    if target_batch_root.exists():
        if not args.force:
            raise FileExistsError(f"Target studio batch already exists: {target_batch_root}")
        shutil.rmtree(target_batch_root)

    target_batch_root.mkdir(parents=True, exist_ok=True)

    accepted_root = source_batch_root / "accepted_assets"
    review_root = target_batch_root / "review"
    ensure_review_root(review_root)
    symlink_path(target_batch_root / "result", result_root)
    if accepted_root.exists():
        symlink_path(target_batch_root / "accepted_assets", accepted_root)

    source_meta = load_json(source_batch_root / "batch_meta.json") if (source_batch_root / "batch_meta.json").exists() else {}
    manifest_payload = load_json(result_root / "manifest.json")
    batch_meta = {
        "name": batch_name,
        "label": source_meta.get("label") or batch_name,
        "version": "studio-mounted-v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "keywords": sorted(
            {
                "annotation-studio",
                "mounted",
                *[str(item).strip() for item in source_meta.get("keywords", []) if str(item).strip()],
            }
        ),
        "source_batch_name": source_batch_root.name,
        "source_batch_root": str(source_batch_root),
        "source_result_root": str(result_root),
        "uid_count": len(manifest_payload.get("uids", [])),
        "result_mode": "symlink",
        "accepted_mode": "symlink" if accepted_root.exists() else "none",
    }
    write_json(target_batch_root / "batch_meta.json", batch_meta)
    write_json(
        target_batch_root / "source_batch.json",
        {
            "source_batch_root": str(source_batch_root),
            "source_result_root": str(result_root),
            "source_accepted_assets_root": str(accepted_root),
        },
    )
    print(json.dumps({"target_batch_root": str(target_batch_root), "batch_meta": batch_meta}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
