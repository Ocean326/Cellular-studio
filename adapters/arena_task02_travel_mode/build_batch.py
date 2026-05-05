#!/usr/bin/env python3
"""Adapter: Research Arena S02-02 出行语义识别 -> trajectory_annotation_studio batch.

Produces a studio batch with two layers per UID:

  - signal.csv : raw6 cell-tower signals (uid,cid,lat,lon,t_in,t_out)
  - pred.csv   : per-point model prediction (uid,point_index,lat,lon,timestamp_ms,state)

`state` carries the predicted travel mode (subway/bus/highway/other) so the
studio's states_index picks it up as a per-UID tag.

Per-UID timeline segments are pre-seeded (one segment per consecutive-equal
prediction run) into the legacy timeline_annotations path, so reviewers open
a UID and see the model's segmentation already filled in — then split/merge/
relabel freely via the studio UI. This is the "多段+多段" review surface.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE_NAMES: dict[int, str] = {0: "other", 1: "subway", 2: "bus", 3: "highway"}
MODE_LABELS_ZH: dict[str, str] = {
    "other": "其他",
    "subway": "地铁",
    "bus": "公交",
    "highway": "高速",
}
MODE_COLORS: dict[str, str] = {
    "other": "#8888A8",
    "subway": "#2E79B5",
    "bus": "#1F8A65",
    "highway": "#F0A040",
}

SIGNAL_FIELDS = ["uid", "cid", "lat", "lon", "t_in", "t_out"]
PRED_FIELDS = ["uid", "point_index", "latitude", "longitude", "timestamp_ms", "state"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time_to_ms(value: Any) -> int:
    if value is None or value == "":
        return 0
    s = str(value).strip()
    try:
        return int(float(s))
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return int(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    return 0


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
        "review/timeline_annotations",
        "accepted_assets/reviewers",
        "review_exports/aggregate",
    ):
        (batch_root / rel).mkdir(parents=True, exist_ok=True)


# ---------- Input readers ----------

def read_signal_csv(path: Path) -> dict[str, list[dict]]:
    """uid,cid,lon,lat,t_in,t_out  (any column order; also supports lat/lon alt names)."""
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


def read_pred_csv(path: Path) -> dict[str, list[dict]]:
    """uid,(cid),lon,lat,time,prediction  — prediction is 0/1/2/3 int."""
    per_uid: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            uid = str(row.get("uid") or "").strip()
            if not uid:
                continue
            pred_raw = str(row.get("prediction") or row.get("pred") or "").strip()
            try:
                pred_int = int(float(pred_raw))
            except (TypeError, ValueError):
                continue
            state = MODE_NAMES.get(pred_int, "other")
            time_value = row.get("time") or row.get("timestamp") or row.get("t_in") or ""
            timestamp_ms = parse_time_to_ms(time_value)
            lat = row.get("lat") or row.get("latitude") or ""
            lon = row.get("lon") or row.get("longitude") or ""
            per_uid[uid].append(
                {
                    "uid": uid,
                    "latitude": str(lat).strip(),
                    "longitude": str(lon).strip(),
                    "timestamp_ms": timestamp_ms,
                    "state": state,
                    "_time_raw": str(time_value).strip(),
                }
            )
    for uid in list(per_uid.keys()):
        per_uid[uid].sort(key=lambda r: r["timestamp_ms"])
        for idx, rec in enumerate(per_uid[uid]):
            rec["point_index"] = idx
    return per_uid


def read_pred_results_dir(root: Path) -> dict[str, list[dict]]:
    """Load official per-user result files: user_<uid>_result.csv."""
    per_uid: dict[str, list[dict]] = defaultdict(list)
    files = sorted(root.glob("user_*_result.csv"))
    if not files:
        raise ValueError(f"no user_*_result.csv found under: {root}")
    for path in files:
        match = re.match(r"user_(.+)_result\.csv$", path.name)
        uid_from_name = match.group(1) if match else ""
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                uid = str(row.get("uid") or uid_from_name).strip()
                if not uid:
                    continue
                pred_raw = str(row.get("prediction") or row.get("pred") or "").strip()
                try:
                    pred_int = int(float(pred_raw))
                except (TypeError, ValueError):
                    continue
                state = MODE_NAMES.get(pred_int, "other")
                time_value = row.get("time") or row.get("timestamp") or row.get("t_in") or ""
                timestamp_ms = parse_time_to_ms(time_value)
                lat = row.get("lat") or row.get("latitude") or ""
                lon = row.get("lon") or row.get("longitude") or ""
                per_uid[uid].append(
                    {
                        "uid": uid,
                        "latitude": str(lat).strip(),
                        "longitude": str(lon).strip(),
                        "timestamp_ms": timestamp_ms,
                        "state": state,
                        "_time_raw": str(time_value).strip(),
                    }
                )
    for uid in list(per_uid.keys()):
        per_uid[uid].sort(key=lambda r: r["timestamp_ms"])
        for idx, rec in enumerate(per_uid[uid]):
            rec["point_index"] = idx
    return per_uid


# ---------- Timeline segment seeding ----------

def rle_segments(rows: list[dict]) -> list[dict]:
    segs: list[dict] = []
    for r in rows:
        t = int(r["timestamp_ms"] or 0)
        state = r["state"]
        if segs and segs[-1]["state"] == state:
            segs[-1]["end"] = t
        else:
            segs.append({"state": state, "start": t, "end": t})
    return segs


def segments_to_timeline_payload(uid: str, segs: list[dict]) -> dict[str, Any]:
    timeline_segments = []
    for idx, s in enumerate(segs):
        if s["end"] <= s["start"]:
            s["end"] = s["start"] + 1
        cat = s["state"]
        timeline_segments.append(
            {
                "id": f"seed-{uid}-{idx:04d}",
                "categoryId": cat,
                "categoryName": MODE_LABELS_ZH.get(cat, cat),
                "color": MODE_COLORS.get(cat, "#8888A8"),
                "startTime": s["start"],
                "endTime": s["end"],
                "entryMode": "model_seed",
                "segmentScope": "model",
                "sourceLayerKey": "pred",
            }
        )
    return {
        "schema_version": 1,
        "uid": uid,
        "sample_id": uid,
        "reviewer_id": "",
        "reviewer_name": "",
        "reviewer": "",
        "updated_at": utc_now_iso(),
        "pins": [],
        "segments": timeline_segments,
    }


# ---------- Main ----------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-csv", required=True, help="Raw6 signal CSV: uid,cid,lon,lat,t_in,t_out")
    parser.add_argument(
        "--pred-csv",
        default="",
        help="Per-point prediction CSV: uid,(cid,lon,lat,)time,prediction",
    )
    parser.add_argument(
        "--pred-results-dir",
        default="",
        help="Official submission results dir containing user_<uid>_result.csv files.",
    )
    parser.add_argument("--output-batch-root", required=True, help="Output batch root.")
    parser.add_argument("--batch-name", default="arena_task02_travel_mode", help="Batch name written to batch_meta.json")
    parser.add_argument("--label", default="S02-02 出行语义识别 · 多段标签 Review", help="Display label.")
    parser.add_argument("--max-uids", type=int, default=0, help="If > 0, truncate to first N UIDs (debug).")
    parser.add_argument("--force", action="store_true", help="Replace output batch root if it already exists.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signal_path = Path(args.signal_csv).expanduser().resolve()
    pred_csv_arg = str(args.pred_csv).strip()
    pred_results_dir_arg = str(args.pred_results_dir).strip()
    out_root = Path(args.output_batch_root).expanduser().resolve()

    if not signal_path.exists():
        raise FileNotFoundError(f"input not found: {signal_path}")
    if bool(pred_csv_arg) == bool(pred_results_dir_arg):
        raise ValueError("exactly one of --pred-csv or --pred-results-dir must be provided")

    pred_source_kind = ""
    pred_source_path = ""
    if pred_csv_arg:
        pred_path = Path(pred_csv_arg).expanduser().resolve()
        if not pred_path.exists():
            raise FileNotFoundError(f"input not found: {pred_path}")
        pred_source_kind = "pred_csv"
        pred_source_path = str(pred_path)
    else:
        pred_results_dir = Path(pred_results_dir_arg).expanduser().resolve()
        if not pred_results_dir.exists():
            raise FileNotFoundError(f"input not found: {pred_results_dir}")
        pred_source_kind = "pred_results_dir"
        pred_source_path = str(pred_results_dir)

    ensure_empty_dir(out_root, force=args.force)
    initialize_batch_dirs(out_root)

    signal_by_uid = read_signal_csv(signal_path)
    pred_by_uid = read_pred_csv(pred_path) if pred_csv_arg else read_pred_results_dir(pred_results_dir)

    common_uids = sorted(set(signal_by_uid.keys()) & set(pred_by_uid.keys()))
    if args.max_uids and args.max_uids > 0:
        common_uids = common_uids[: args.max_uids]
    if not common_uids:
        raise ValueError("no common UIDs between signal and pred CSVs")

    result_root = out_root / "result"
    timeline_dir = out_root / "review" / "timeline_annotations"

    states_index: dict[str, list[str]] = {}
    layer_counts = {"signal": 0, "pred": 0}

    for uid in common_uids:
        sig_rows = signal_by_uid.get(uid, [])
        pred_rows = pred_by_uid.get(uid, [])

        write_csv(result_root / uid / "signal.csv", SIGNAL_FIELDS, sig_rows)
        pred_rows_for_csv = [
            {
                "uid": r["uid"],
                "point_index": r["point_index"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "timestamp_ms": r["timestamp_ms"],
                "state": r["state"],
            }
            for r in pred_rows
        ]
        write_csv(result_root / uid / "pred.csv", PRED_FIELDS, pred_rows_for_csv)

        layer_counts["signal"] += len(sig_rows)
        layer_counts["pred"] += len(pred_rows)

        states = sorted({r["state"] for r in pred_rows if r["state"]})
        states_index[uid] = states

        segs = rle_segments(pred_rows)
        if segs:
            write_json(timeline_dir / f"{uid}.json", segments_to_timeline_payload(uid, segs))

    generated_at = utc_now_iso()
    manifest = {
        "ui_mode": "chain2",
        "title": "S02-02 出行语义识别 · 多段标签 Review",
        "search_placeholder": "搜索 UID / 出行方式标签...",
        "filter_title": "按出行方式标签筛选",
        "dataset_name": args.batch_name,
        "label": args.label,
        "generated_at": generated_at,
        "uids": common_uids,
        "layers": ["signal", "pred"],
        "layer_labels": {
            "signal": "原始信令 (raw6)",
            "pred": "逐点出行方式预测",
        },
        "layer_specs": {
            "signal": {
                "filename": "signal.csv",
                "kind": "signal",
                "hasLine": True,
                "defaultOpacity": 0.75,
            },
            "pred": {
                "filename": "pred.csv",
                "kind": "default",
                "hasLine": True,
                "review_reference": True,
                "defaultOpacity": 0.9,
            },
        },
        "review_reference_files": ["pred.csv"],
        "time_scrubber_preferred_layers": ["pred", "signal"],
        "states": states_index,
        "state_labels": MODE_LABELS_ZH,
        "state_colors": MODE_COLORS,
        "annotation_categories": [
            {"id": code, "name": MODE_LABELS_ZH[code], "color": MODE_COLORS[code]}
            for code in ("subway", "bus", "highway", "other")
        ],
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
            "keywords": ["arena", "task02", "travel-mode", "sequence-labeling"],
            "status": "prepared",
            "result_mode": "copied",
            "source_result_root": str(result_root),
            "uid_count": len(common_uids),
            "layer_counts": layer_counts,
        },
    )
    write_json(
        out_root / "source_batch.json",
        {
            "generated_at": generated_at,
            "source": "adapters/arena_task02_travel_mode/build_batch.py",
            "signal_csv": str(signal_path),
            pred_source_kind: pred_source_path,
        },
    )

    summary = {
        "batch_root": str(out_root),
        "result_root": str(result_root),
        "manifest_path": str(result_root / "manifest.json"),
        "uid_count": len(common_uids),
        "layer_counts": layer_counts,
        "seeded_timeline_uids": len(common_uids),
        "mode_totals": {
            name: sum(1 for uid in common_uids for r in pred_by_uid[uid] if r["state"] == name)
            for name in ("subway", "bus", "highway", "other")
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
