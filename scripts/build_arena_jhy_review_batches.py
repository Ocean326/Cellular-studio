#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TASK02_BUILDER = REPO_ROOT / "trajectory_annotation_studio" / "adapters" / "arena_task02_travel_mode" / "build_batch.py"
TASK03_BUILDER = REPO_ROOT / "trajectory_annotation_studio" / "adapters" / "arena_task03_occupation" / "build_batch.py"

DEFAULT_TASK02_RESULTS_DIR = REPO_ROOT / "research_arena_personal" / "final_submission_payloads" / "20260421" / "task-26-TG-S02-02" / "姜海洋-BY2406213" / "results"
DEFAULT_TASK02_SIGNAL_CSV = REPO_ROOT / "research_arena_personal" / "server_sync" / "20260421" / "task-26-TG-S02-02" / "codex-staging-v3" / "results_merged_task02_signal.csv"
DEFAULT_TASK03_RESULTS_DIR = REPO_ROOT / "research_arena_personal" / "final_submission_payloads" / "20260421" / "task-26-TG-S02-03" / "姜海洋-BY2406213" / "results"
DEFAULT_BATCHS_ROOT = REPO_ROOT / "trajectory_annotation_studio" / "data" / "batches"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build JHY Arena S02-02 / S02-03 studio review batches.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_BATCHS_ROOT),
        help="Directory under which batches will be created.",
    )
    parser.add_argument(
        "--task02-results-dir",
        default=str(DEFAULT_TASK02_RESULTS_DIR),
        help="Task02 final submission results dir containing user_*_result.csv.",
    )
    parser.add_argument(
        "--task02-signal-csv",
        default=str(DEFAULT_TASK02_SIGNAL_CSV),
        help="Task02 raw signal CSV aligned with the final submission UIDs.",
    )
    parser.add_argument(
        "--task03-results-dir",
        default=str(DEFAULT_TASK03_RESULTS_DIR),
        help="Task03 final submission results dir containing bus/cab/delivery CSVs.",
    )
    parser.add_argument(
        "--tag",
        default="20260424_jhy",
        help="Suffix used in generated batch names.",
    )
    parser.add_argument("--task03-top-k", type=int, default=300, help="Top-K per profession for Task03 review batches.")
    parser.add_argument(
        "--task03-multi-label-threshold-rank",
        type=int,
        default=120,
        help="Task03 multi-label threshold rank.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).expanduser().resolve()
    task02_results_dir = Path(args.task02_results_dir).expanduser().resolve()
    task02_signal_csv = Path(args.task02_signal_csv).expanduser().resolve()
    task03_results_dir = Path(args.task03_results_dir).expanduser().resolve()

    output_root.mkdir(parents=True, exist_ok=True)

    task02_batch = output_root / f"arena_{args.tag}_task02_jhy_submission_review"
    run(
        [
            sys.executable,
            str(TASK02_BUILDER),
            "--signal-csv",
            str(task02_signal_csv),
            "--pred-results-dir",
            str(task02_results_dir),
            "--output-batch-root",
            str(task02_batch),
            "--batch-name",
            task02_batch.name,
            "--label",
            "S02-02 姜海洋正式提交 · 多段着色 Review",
            "--force",
        ]
    )

    task03_files = {
        "bus_driver": task03_results_dir / "bus_driver.csv",
        "cab_driver": task03_results_dir / "cab_driver.csv",
        "delivery": task03_results_dir / "delivery.csv",
    }
    for profession, label in (
        ("bus_driver", "公交司机"),
        ("cab_driver", "出租车司机"),
        ("delivery", "快递员"),
    ):
        batch_root = output_root / f"arena_{args.tag}_task03_{profession}_review"
        run(
            [
                sys.executable,
                str(TASK03_BUILDER),
                "--bus-rank-csv",
                str(task03_files["bus_driver"]),
                "--cab-rank-csv",
                str(task03_files["cab_driver"]),
                "--delivery-rank-csv",
                str(task03_files["delivery"]),
                "--top-k",
                str(args.task03_top_k),
                "--multi-label-threshold-rank",
                str(args.task03_multi_label_threshold_rank),
                "--focus-profession",
                profession,
                "--output-batch-root",
                str(batch_root),
                "--batch-name",
                batch_root.name,
                "--label",
                f"S02-03 姜海洋正式提交 · {label}专项 Review",
                "--force",
            ]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
