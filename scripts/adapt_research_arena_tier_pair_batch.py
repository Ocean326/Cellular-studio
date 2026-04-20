#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .server_batch_lib import build_batch_metadata, read_json, write_json
except ImportError:
    from server_batch_lib import build_batch_metadata, read_json, write_json  # type: ignore


TIER_SOURCES = {
    "tier1": {
        "split_dir": "tier1-clean-physical",
        "label": "Tier-1 Clean Physical",
        "tier_weight": 0.2,
        "description": "基础真实层，对应 organizer 内部 tier1-clean-physical。",
        "color": "#475569",
    },
    "tier2": {
        "split_dir": "tier2-overlap-ambiguity",
        "label": "Tier-2 Overlap Ambiguity",
        "tier_weight": 0.3,
        "description": "重叠歧义层，对应 organizer 内部 tier2-overlap-ambiguity。",
        "color": "#2563eb",
    },
    "tier3": {
        "split_dir": "tier3-raw-like-local-noise",
        "label": "Tier-3 Raw-like Local Noise",
        "tier_weight": 0.3,
        "description": "本地噪声层，对应 organizer 内部 tier3-raw-like-local-noise。",
        "color": "#ea580c",
    },
    "tier4": {
        "split_dir": "tier4-closest-to-raw",
        "label": "Tier-4 Closest To Raw",
        "tier_weight": 0.2,
        "description": "拟真锚点层，对应 organizer 内部 tier4-closest-to-raw。",
        "color": "#7c3aed",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a trajectory_annotation_studio batch with GPS truth + one selected raw6 tier."
    )
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--tier-key", required=True, choices=sorted(TIER_SOURCES))
    parser.add_argument("--phase", default="train-public,dev-public")
    parser.add_argument("--output-batch-root", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def ensure_empty_dir(path: Path, force: bool = False) -> None:
    if path.exists():
        if not force:
            raise FileExistsError(f"output already exists: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def parse_phase_list(phase: str) -> list[str]:
    phases = [token.strip() for token in str(phase or "").split(",") if token.strip()]
    if not phases:
        raise ValueError("expected at least one phase")
    return phases


def iso_to_unix_seconds(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("expected non-empty ISO timestamp")
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_csv_rows_by_uid(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    rows_by_uid: dict[str, list[dict[str, str]]] = {}
    with open(csv_path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            uid = str(row.get("uid") or "").strip()
            if uid:
                rows_by_uid.setdefault(uid, []).append(row)
    return rows_by_uid


def load_split_records(split_root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    manifest_dir = split_root / "manifests"
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest_payload = read_json(manifest_path)
        csv_file = str(manifest_payload.get("csv_file") or "").strip()
        if not csv_file:
            raise ValueError(f"missing csv_file in {manifest_path}")
        rows_by_uid = load_csv_rows_by_uid(split_root / "batches" / csv_file)
        for user in manifest_payload.get("users", []) or []:
            uid = str(user.get("uid") or "").strip()
            sample_id = str(user.get("sample_id") or "").strip()
            if not uid or not sample_id:
                continue
            records[uid] = {
                "uid": uid,
                "sample_id": sample_id,
                "sample_path": split_root / "samples" / f"{sample_id}.json",
                "truth_path": split_root / "truth" / f"{sample_id}.json",
                "rows": rows_by_uid.get(uid, []),
                "split_name": str(manifest_payload.get("split_name") or "").strip(),
            }
    return records


def build_gps_rows(uid: str, sample_payload: dict[str, Any], truth_payload: dict[str, Any]) -> list[dict[str, Any]]:
    offsets = list(sample_payload.get("time_grid_offsets_sec") or [])
    gps_sequence = list(truth_payload.get("gps_sequence") or [])
    if len(offsets) != len(gps_sequence):
        raise ValueError(f"{sample_payload.get('sample_id')} has mismatched time grid and gps sequence lengths")
    start_time_sec = iso_to_unix_seconds(str(sample_payload.get("start_time") or ""))
    rows: list[dict[str, Any]] = []
    for index, (offset_sec, point) in enumerate(zip(offsets, gps_sequence)):
        rows.append(
            {
                "uid": uid,
                "point_index": index,
                "latitude": point.get("lat", ""),
                "longitude": point.get("lng", ""),
                "timestamp_ms": int((start_time_sec + int(offset_sec)) * 1000),
            }
        )
    return rows


def copy_raw6_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "uid": str(row.get("uid") or "").strip(),
            "cid": str(row.get("cid") or "").strip(),
            "lat": str(row.get("lat") or "").strip(),
            "lon": str(row.get("lon") or "").strip(),
            "t_in": str(row.get("t_in") or "").strip(),
            "t_out": str(row.get("t_out") or "").strip(),
        }
        for row in rows
    ]


def initialize_batch_root(batch_root: Path, batch_name: str, dataset_root: Path, uid_count: int) -> None:
    for relative in (
        Path("result"),
        Path("review/system"),
        Path("review/reviewers"),
        Path("review/aggregate"),
        Path("accepted_assets/reviewers"),
        Path("review_exports/aggregate"),
    ):
        (batch_root / relative).mkdir(parents=True, exist_ok=True)
    write_json(
        batch_root / "batch_meta.json",
        build_batch_metadata(
            batch_name=batch_name,
            source_result_root=batch_root / "result",
            label=f"{batch_name} GPS+signal",
            version="tier-pair-v1",
            keywords=["annotation-studio", "research-arena", "raw6", "gps-signal-pair"],
            status="prepared",
            result_mode="copied",
            uid_count=uid_count,
        ),
    )
    write_json(
        batch_root / "source_batch.json",
        {
            "generated_at": utc_now_iso(),
            "source": "research_arena_tier_pair_adapter",
            "dataset_root": str(dataset_root),
        },
    )


def build_tier_pair_batch(
    *,
    dataset_root: Path,
    tier_key: str,
    phase: str,
    output_batch_root: Path,
    limit: int = 0,
    force: bool = False,
) -> dict[str, Any]:
    dataset_root = dataset_root.expanduser().resolve()
    output_batch_root = output_batch_root.expanduser().resolve()
    ensure_empty_dir(output_batch_root, force=force)
    phase_list = parse_phase_list(phase)
    tier_source = TIER_SOURCES[tier_key]

    merged_records: dict[str, dict[str, Any]] = {}
    for phase_name in phase_list:
        split_root = dataset_root / "splits" / tier_source["split_dir"] / phase_name
        if not split_root.exists():
            raise FileNotFoundError(f"split root not found: {split_root}")
        for uid, payload in load_split_records(split_root).items():
            if uid in merged_records:
                raise ValueError(f"duplicate uid across requested phases: {uid}")
            merged_records[uid] = payload

    uids = sorted(merged_records)
    if limit and limit > 0:
        uids = uids[:limit]
    if not uids:
        raise ValueError("no uids found for requested tier/phase selection")

    initialize_batch_root(output_batch_root, output_batch_root.name, dataset_root, len(uids))
    result_root = output_batch_root / "result"
    states_index = {uid: [] for uid in uids}
    track_manifest_tracks: list[dict[str, Any]] = []

    for uid in uids:
        record = merged_records[uid]
        uid_dir = result_root / uid
        uid_dir.mkdir(parents=True, exist_ok=True)

        sample_payload = read_json(record["sample_path"])
        truth_payload = read_json(record["truth_path"])
        sample_metadata = dict(sample_payload.get("metadata", {}))
        gps_rows = build_gps_rows(uid, sample_payload, truth_payload)
        signal_rows = copy_raw6_rows(record["rows"])
        write_csv(uid_dir / "gps.csv", ["uid", "point_index", "latitude", "longitude", "timestamp_ms"], gps_rows)
        write_csv(uid_dir / "signal.csv", ["uid", "cid", "lat", "lon", "t_in", "t_out"], signal_rows)

        track_manifest_tracks.append(
            {
                "track_id": f"uid:{uid}",
                "uid": uid,
                "sample_id": str(record["sample_id"]),
                "phase": str(record["split_name"]).split("/")[-1],
                "tier_key": tier_key,
                "tier_label": tier_source["label"],
                "trajectory_class": sample_metadata.get("trajectory_class"),
                "trajectory_class_metrics": sample_metadata.get("trajectory_class_metrics"),
                "benchmark_sampling": sample_metadata.get("benchmark_sampling"),
                "available_layers": ["gps", "signal"],
                "stats": {
                    "row_counts": {
                        "gps": len(gps_rows),
                        "signal": len(signal_rows),
                    }
                },
                "source_paths": {
                    "gps_csv": str(uid_dir / "gps.csv"),
                    "signal_csv": str(uid_dir / "signal.csv"),
                    "sample_path": str(record["sample_path"]),
                    "truth_path": str(record["truth_path"]),
                },
            }
        )

    manifest_payload = {
        "ui_mode": "trajectory_layers",
        "title": f"{tier_source['label']} GPS + Signal 对照",
        "search_placeholder": "搜索 UID / sample_id / class ...",
        "filter_title": "按单个 tier 浏览 GPS 与模拟信令",
        "filter_source_label": f"GPS 真值 + {tier_source['label']}",
        "hide_review_panel": True,
        "review_reference_files": [],
        "time_scrubber_preferred_layers": ["gps", "signal"],
        "uids": uids,
        "layers": ["gps", "signal"],
        "layer_labels": {
            "gps": "GPS 真值",
            "signal": tier_source["label"],
        },
        "layer_specs": {
            "gps": {
                "filename": "gps.csv",
                "kind": "gps",
                "defaultColor": "#0f766e",
                "defaultOpacity": 0.88,
                "hasLine": True,
            },
            "signal": {
                "filename": "signal.csv",
                "kind": "signal",
                "defaultColor": tier_source["color"],
                "defaultOpacity": 0.80,
                "hasLine": True,
            },
        },
        "layer_visibility": {
            "gps": True,
            "signal": True,
        },
        "layer_sources": {
            "gps": {
                "source_type": "truth",
                "description": "Organizer GPS truth sequence projected on the fixed time grid.",
            },
            "signal": {
                "source_type": "raw6",
                "split_dir": tier_source["split_dir"],
                "tier_weight": tier_source["tier_weight"],
                "description": tier_source["description"],
            },
        },
    }
    write_json(result_root / "manifest.json", manifest_payload)
    write_json(result_root / "states_index.json", states_index)
    write_json(
        output_batch_root / "track_manifest.json",
        {
            "generated_at": utc_now_iso(),
            "source": "research_arena_tier_pair_adapter",
            "phase": phase,
            "phases": phase_list,
            "tier_key": tier_key,
            "count": len(track_manifest_tracks),
            "tracks": track_manifest_tracks,
        },
    )
    source_batch_payload = read_json(output_batch_root / "source_batch.json")
    source_batch_payload["phase"] = phase
    source_batch_payload["phases"] = phase_list
    source_batch_payload["tier_key"] = tier_key
    source_batch_payload["split_dir"] = tier_source["split_dir"]
    write_json(output_batch_root / "source_batch.json", source_batch_payload)

    return {
        "generated_at": utc_now_iso(),
        "dataset_root": str(dataset_root),
        "tier_key": tier_key,
        "phase": phase,
        "phases": phase_list,
        "output_batch_root": str(output_batch_root),
        "uid_count": len(uids),
        "uids": uids,
    }


def main() -> int:
    args = parse_args()
    report = build_tier_pair_batch(
        dataset_root=Path(args.dataset_root),
        tier_key=args.tier_key,
        phase=args.phase,
        output_batch_root=Path(args.output_batch_root),
        limit=max(0, int(args.limit or 0)),
        force=bool(args.force),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
