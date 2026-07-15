#!/usr/bin/env python3
"""Adapter: Research Arena S02-03 职业身份识别 -> trajectory_annotation_studio batch.

This is a **UID-level ranking** task, not sequence labeling. We map it to the
studio's "正轨标签" channel:

  - Each UID carries predicted profession(s) in `state` + `states_index.json`.
  - Reviewers accept/reject/skip the UID via the standard review panel.
  - No timeline segment seeding — the label unit is the whole UID.

Per-UID layers produced:

  - signal.csv   : raw6 cell-tower signals for mobility inspection (kind=signal, optional)
  - profile.csv  : UID-level profile row with profession scores + top prediction
                   (state column = top profession; other columns = scores)

Top-K candidates from each profession CSV are bucketed into the batch with
their predicted profession as `state`. Remaining UIDs carry `state="unknown"`.
If `--signal-csv` is not provided, the adapter builds a profile-only batch.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFS = ("bus_driver", "cab_driver", "delivery")
PROF_LABELS_ZH = {
    "bus_driver": "公交司机",
    "cab_driver": "出租车司机",
    "delivery":   "快递员",
    "unknown":    "未定",
    "multi":      "多职业疑似",
}
PROF_COLORS = {
    "bus_driver": "#2E79B5",
    "cab_driver": "#F0A040",
    "delivery":   "#1F8A65",
    "unknown":    "#8888A8",
    "multi":      "#C85898",
}

SIGNAL_FIELDS = ["uid", "cid", "lat", "lon", "t_in", "t_out"]
PROFILE_FIELDS = [
    "uid",
    "state",
    "top_profession",
    "top_score",
    "bus_driver_score",
    "cab_driver_score",
    "delivery_score",
    "bus_driver_rank",
    "cab_driver_rank",
    "delivery_rank",
    "multi_label",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def ensure_empty_dir(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise FileExistsError(f"output already exists: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def initialize_batch_dirs(batch_root: Path) -> None:
    for rel in (
        "result",
        "review/system",
        "review/reviewers",
        "review/aggregate",
        "accepted_assets/reviewers",
        "review_exports/aggregate",
    ):
        (batch_root / rel).mkdir(parents=True, exist_ok=True)


# ---------- Input readers ----------

def read_signal_csv(path: Path) -> dict[str, list[dict]]:
    per_uid: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            uid = str(row.get("uid") or "").strip()
            if not uid:
                continue
            lat = row.get("lat") or row.get("latitude") or ""
            lon = row.get("lon") or row.get("longitude") or ""
            per_uid[uid].append(
                {
                    "uid": uid,
                    "cid": str(row.get("cid") or "").strip(),
                    "lat": str(lat).strip(),
                    "lon": str(lon).strip(),
                    "t_in": str(row.get("t_in") or row.get("time_in") or row.get("time") or "").strip(),
                    "t_out": str(row.get("t_out") or row.get("time_out") or "").strip(),
                }
            )
    return per_uid


def read_rank_csv(path: Path) -> list[tuple[str, float]]:
    """uid,score  — returned in file order (assumed descending)."""
    ranked: list[tuple[str, float]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        first_line = fh.readline()
    has_header = first_line.lower().strip().startswith("uid")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        if has_header:
            next(reader, None)
        for row in reader:
            if not row:
                continue
            uid = str(row[0]).strip()
            if not uid:
                continue
            try:
                score = float(row[1]) if len(row) > 1 else 0.0
            except (TypeError, ValueError):
                continue
            ranked.append((uid, score))
    return ranked


# ---------- Main ----------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--signal-csv",
        default="",
        help="raw6 signal CSV covering candidate UIDs (optional; if omitted -> profile-only batch).",
    )
    parser.add_argument("--bus-rank-csv", required=True, help="bus_driver.csv with uid,score (descending).")
    parser.add_argument("--cab-rank-csv", required=True, help="cab_driver.csv with uid,score (descending).")
    parser.add_argument("--delivery-rank-csv", required=True, help="delivery.csv with uid,score (descending).")
    parser.add_argument("--top-k", type=int, default=100, help="Top-K per profession to include in the batch.")
    parser.add_argument("--multi-label-threshold-rank", type=int, default=50,
                        help="If a UID appears in top-N of 2+ professions, its state becomes 'multi'.")
    parser.add_argument(
        "--focus-profession",
        choices=PROFS,
        default="",
        help="If set, emit a profession-specific dataset containing only that profession's candidates.",
    )
    parser.add_argument("--output-batch-root", required=True, help="Output batch root.")
    parser.add_argument("--batch-name", default="arena_task03_occupation")
    parser.add_argument("--label", default="S02-03 职业身份识别 · Top-K Review")
    parser.add_argument("--force", action="store_true", help="Replace output batch root if it exists.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_root = Path(args.output_batch_root).expanduser().resolve()
    signal_path = Path(args.signal_csv).expanduser().resolve() if str(args.signal_csv).strip() else None
    rank_paths = {
        "bus_driver": Path(args.bus_rank_csv).expanduser().resolve(),
        "cab_driver": Path(args.cab_rank_csv).expanduser().resolve(),
        "delivery":   Path(args.delivery_rank_csv).expanduser().resolve(),
    }
    focus_profession = str(args.focus_profession).strip()
    inputs: list[Path] = [*rank_paths.values()]
    if signal_path is not None:
        inputs.append(signal_path)
    for p in inputs:
        if not p.exists():
            raise FileNotFoundError(f"input not found: {p}")

    ensure_empty_dir(out_root, force=args.force)
    initialize_batch_dirs(out_root)

    signal_by_uid = read_signal_csv(signal_path) if signal_path is not None else {}
    rankings: dict[str, list[tuple[str, float]]] = {k: read_rank_csv(p) for k, p in rank_paths.items()}

    # Per-UID scores + ranks
    scores: dict[str, dict[str, float]] = defaultdict(lambda: {"bus_driver": 0.0, "cab_driver": 0.0, "delivery": 0.0})
    ranks:  dict[str, dict[str, int]]   = defaultdict(lambda: {"bus_driver": 0,   "cab_driver": 0,   "delivery": 0})
    for prof, rows in rankings.items():
        for idx, (uid, score) in enumerate(rows, start=1):
            scores[uid][prof] = max(scores[uid][prof], score)
            if ranks[uid][prof] == 0 or idx < ranks[uid][prof]:
                ranks[uid][prof] = idx

    # Select Top-K per profession
    selected: dict[str, str] = {}  # uid -> assigned primary profession
    for prof in PROFS:
        for uid, _score in rankings[prof][: args.top_k]:
            if uid not in selected:
                selected[uid] = prof
            else:
                current = selected[uid]
                if scores[uid][prof] > scores[uid].get(current, 0.0):
                    selected[uid] = prof

    if focus_profession:
        base_uids = [uid for uid, _score in rankings[focus_profession][: args.top_k]]
        if signal_path is not None:
            valid_uids = [uid for uid in base_uids if uid in signal_by_uid]
            if not valid_uids:
                raise ValueError(
                    f"no overlap between {focus_profession} top-K UIDs and signal CSV UIDs"
                )
        else:
            valid_uids = [uid for uid in base_uids if uid in scores]
            if not valid_uids:
                raise ValueError(f"no UID selected from {focus_profession} ranking file")
    else:
        # Keep UIDs according to signal availability policy:
        # - with signal-csv: keep only overlapped UIDs (inspectable trajectories)
        # - without signal-csv: keep all selected UIDs (profile-only review)
        if signal_path is not None:
            valid_uids = [uid for uid in selected.keys() if uid in signal_by_uid]
            if not valid_uids:
                raise ValueError("no overlap between ranked top-K UIDs and signal CSV UIDs")
        else:
            valid_uids = sorted(selected.keys())
            if not valid_uids:
                raise ValueError("no UID selected from ranking files")

    # Sort by top score descending
    def _top_score(uid: str) -> float:
        return max(scores[uid].values()) if scores[uid] else 0.0

    valid_uids.sort(key=_top_score, reverse=True)

    result_root = out_root / "result"
    states_index: dict[str, list[str]] = {}
    per_prof_count = {p: 0 for p in PROFS}
    multi_count = 0

    for uid in valid_uids:
        uid_scores = scores[uid]
        uid_ranks = ranks[uid]

        # Multi-label heuristic: UID in top-N of 2+ professions
        in_top_k: list[str] = [
            p for p in PROFS
            if uid_ranks[p] > 0 and uid_ranks[p] <= args.multi_label_threshold_rank
        ]
        multi_label = "true" if len(in_top_k) >= 2 else "false"

        primary = focus_profession or selected[uid]
        if len(in_top_k) >= 2:
            state = "multi"
            multi_count += 1
        else:
            state = primary
            per_prof_count[primary] += 1

        if signal_path is not None and uid in signal_by_uid:
            write_csv(result_root / uid / "signal.csv", SIGNAL_FIELDS, signal_by_uid[uid])
        profile_row = {
            "uid": uid,
            "state": state,
            "top_profession": primary,
            "top_score": f"{_top_score(uid):.6f}",
            "bus_driver_score": f"{uid_scores['bus_driver']:.6f}",
            "cab_driver_score": f"{uid_scores['cab_driver']:.6f}",
            "delivery_score":   f"{uid_scores['delivery']:.6f}",
            "bus_driver_rank":  uid_ranks["bus_driver"] or "",
            "cab_driver_rank":  uid_ranks["cab_driver"] or "",
            "delivery_rank":    uid_ranks["delivery"] or "",
            "multi_label":      multi_label,
        }
        write_csv(result_root / uid / "profile.csv", PROFILE_FIELDS, [profile_row])

        if focus_profession:
            tags = [focus_profession]
            if len(in_top_k) >= 2:
                tags.extend([p for p in in_top_k if p != focus_profession])
        else:
            tags = list(in_top_k) if len(in_top_k) >= 2 else [primary]
        states_index[uid] = tags

    generated_at = utc_now_iso()
    layers = ["profile"] if signal_path is None else ["signal", "profile"]
    layer_labels = {"profile": "UID 画像 + 职业得分"}
    layer_specs: dict[str, dict[str, Any]] = {
        "profile": {
            "filename": "profile.csv",
            "kind": "default",
            "review_reference": True,
        },
    }
    if signal_path is not None:
        layer_labels["signal"] = "原始信令 (raw6)"
        layer_specs["signal"] = {
            "filename": "signal.csv",
            "kind": "signal",
            "hasLine": True,
            "defaultOpacity": 0.8,
        }

    title = "S02-03 职业身份识别 · Top-K Review"
    filter_title = "按预测职业筛选"
    search_placeholder = "搜索 UID / 职业标签..."
    if focus_profession:
        focus_label = PROF_LABELS_ZH[focus_profession]
        title = f"S02-03 职业身份识别 · {focus_label} 专项 Review"
        filter_title = f"按 {focus_label} 候选筛选"
        search_placeholder = f"搜索 UID / {focus_label} 候选..."

    manifest = {
        "ui_mode": "chain2",
        "title": title,
        "search_placeholder": search_placeholder,
        "filter_title": filter_title,
        "dataset_name": args.batch_name,
        "label": args.label,
        "generated_at": generated_at,
        "uids": valid_uids,
        "layers": layers,
        "layer_labels": layer_labels,
        "layer_specs": layer_specs,
        "review_reference_files": ["profile.csv"],
        "time_scrubber_preferred_layers": ["signal"] if signal_path is not None else ["profile"],
        "hide_review_panel": False,
        "states": states_index,
        "state_labels": PROF_LABELS_ZH,
        "state_colors": PROF_COLORS,
        "review_decision_hint": {
            "accept": "确认该 UID 职业预测正确",
            "reject": "该 UID 不属于预测职业",
            "skip":   "证据不足 / 无法判断",
        },
    }
    write_json(result_root / "manifest.json", manifest)
    write_json(result_root / "states_index.json", states_index)
    write_json(
        out_root / "batch_meta.json",
        {
            "name": args.batch_name,
            "label": args.label,
            "version": "v1",
            "created_at": generated_at,
            "keywords": ["arena", "task03", "occupation", "ranking", "weak-supervision"],
            "status": "prepared",
            "result_mode": "copied",
            "source_result_root": str(result_root),
            "uid_count": len(valid_uids),
            "top_k": args.top_k,
            "per_profession_primary_count": per_prof_count,
            "multi_label_count": multi_count,
        },
    )
    write_json(
        out_root / "source_batch.json",
        {
            "generated_at": generated_at,
            "source": "adapters/arena_task03_occupation/build_batch.py",
            "signal_csv": str(signal_path) if signal_path is not None else "",
            "rank_csvs": {k: str(v) for k, v in rank_paths.items()},
            "top_k": args.top_k,
            "multi_label_threshold_rank": args.multi_label_threshold_rank,
            "focus_profession": focus_profession,
        },
    )

    summary = {
        "batch_root": str(out_root),
        "result_root": str(result_root),
        "manifest_path": str(result_root / "manifest.json"),
        "uid_count": len(valid_uids),
        "per_profession_primary_count": per_prof_count,
        "multi_label_count": multi_count,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
