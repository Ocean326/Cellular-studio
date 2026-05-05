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


LAYER_SOURCES = (
	{
		"split_dir": "tier1-clean-physical",
		"layer_key": "tier1",
		"label": "Tier-1 Clean Physical",
		"tier_weight": 0.2,
		"description": "基础真实层，对应 organizer 内部 tier1-clean-physical。",
	},
	{
		"split_dir": "tier2-overlap-ambiguity",
		"layer_key": "tier2",
		"label": "Tier-2 Overlap Ambiguity",
		"tier_weight": 0.3,
		"description": "重叠歧义层，对应 organizer 内部 tier2-overlap-ambiguity。",
	},
	{
		"split_dir": "tier3-raw-like-local-noise",
		"layer_key": "tier3",
		"label": "Tier-3 Raw-like Local Noise",
		"tier_weight": 0.3,
		"description": "本地噪声层，对应 organizer 内部 tier3-raw-like-local-noise。",
	},
	{
		"split_dir": "tier4-closest-to-raw",
		"layer_key": "tier4",
		"label": "Tier-4 Closest To Raw",
		"tier_weight": 0.2,
		"description": "拟真锚点层，对应 organizer 内部 tier4-closest-to-raw。",
	},
)


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Build a trajectory_annotation_studio batch that overlays GPS + V1.5 tier1-4 raw6 layers for the same trajectories."
	)
	parser.add_argument("--dataset-root", required=True, help="Research arena V1.5 dataset root")
	parser.add_argument("--phase", default="dev-public", help="Split phase shared across tiers, or a comma-separated phase list")
	parser.add_argument("--output-batch-root", required=True, help="Target studio batch root")
	parser.add_argument("--limit", type=int, default=0, help="Optional max uid count to export")
	parser.add_argument("--force", action="store_true", help="Replace output batch root if it already exists")
	return parser.parse_args()


def ensure_empty_dir(path: Path, force: bool = False) -> None:
	if path.exists():
		if not force:
			raise FileExistsError(f"output already exists: {path}")
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


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
			if not uid:
				continue
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
		csv_path = split_root / "batches" / csv_file
		rows_by_uid = load_csv_rows_by_uid(csv_path)
		for user in manifest_payload.get("users", []) or []:
			uid = str(user.get("uid") or "").strip()
			sample_id = str(user.get("sample_id") or "").strip()
			if not uid or not sample_id:
				continue
			sample_path = split_root / "samples" / f"{sample_id}.json"
			truth_path = split_root / "truth" / f"{sample_id}.json"
			if not sample_path.exists():
				raise FileNotFoundError(f"sample payload not found: {sample_path}")
			if not truth_path.exists():
				raise FileNotFoundError(f"truth payload not found: {truth_path}")
			records[uid] = {
				"uid": uid,
				"sample_id": sample_id,
				"sample_path": sample_path,
				"truth_path": truth_path,
				"manifest_user": user,
				"batch_id": str(manifest_payload.get("batch_id") or "").strip(),
				"tier_id": str(manifest_payload.get("tier_id") or "").strip(),
				"split_name": str(manifest_payload.get("split_name") or "").strip(),
				"rows": rows_by_uid.get(uid, []),
			}
	return records


def parse_phase_list(phase: str) -> list[str]:
	phases = [token.strip() for token in str(phase or "").split(",") if token.strip()]
	if not phases:
		raise ValueError("expected at least one phase")
	return phases


def build_gps_rows(uid: str, sample_payload: dict[str, Any], truth_payload: dict[str, Any]) -> list[dict[str, Any]]:
	offsets = list(sample_payload.get("time_grid_offsets_sec") or [])
	gps_sequence = list(truth_payload.get("gps_sequence") or [])
	if len(offsets) != len(gps_sequence):
		raise ValueError(
			f"sample {sample_payload.get('sample_id')} has mismatched time grid / gps_sequence lengths: "
			f"{len(offsets)} vs {len(gps_sequence)}"
		)
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
			label=f"{batch_name} GPS+tier1-4",
			version="v15-layered-v1",
			keywords=["annotation-studio", "research-arena", "raw6", "trajectory-layers"],
			status="prepared",
			result_mode="copied",
			uid_count=uid_count,
		),
	)
	write_json(
		batch_root / "source_batch.json",
		{
			"generated_at": utc_now_iso(),
			"source": "research_arena_v15_layer_adapter",
			"dataset_root": str(dataset_root),
		},
	)


def build_layered_batch(
	*,
	dataset_root: Path,
	phase: str,
	output_batch_root: Path,
	limit: int = 0,
	force: bool = False,
) -> dict[str, Any]:
	dataset_root = dataset_root.expanduser().resolve()
	output_batch_root = output_batch_root.expanduser().resolve()
	ensure_empty_dir(output_batch_root, force=force)
	phase_list = parse_phase_list(phase)

	split_records: dict[str, dict[str, dict[str, Any]]] = {}
	for layer_source in LAYER_SOURCES:
		merged_records: dict[str, dict[str, Any]] = {}
		for phase_name in phase_list:
			split_root = dataset_root / "splits" / layer_source["split_dir"] / phase_name
			if not split_root.exists():
				raise FileNotFoundError(f"split root not found: {split_root}")
			for uid, payload in load_split_records(split_root).items():
				if uid in merged_records:
					raise ValueError(f"duplicate uid across requested phases: {uid}")
				merged_records[uid] = payload
		split_records[layer_source["layer_key"]] = merged_records

	common_uids = sorted(
		set.intersection(*(set(records.keys()) for records in split_records.values()))
	) if split_records else []
	if limit and limit > 0:
		common_uids = common_uids[:limit]
	if not common_uids:
		raise ValueError("no common uids were found across requested tier splits")

	initialize_batch_root(output_batch_root, output_batch_root.name, dataset_root, len(common_uids))
	result_root = output_batch_root / "result"
	states_index = {uid: [] for uid in common_uids}
	track_manifest_tracks: list[dict[str, Any]] = []

	for uid in common_uids:
		uid_dir = result_root / uid
		uid_dir.mkdir(parents=True, exist_ok=True)
		first_layer_record = split_records["tier1"][uid]
		sample_payload = read_json(first_layer_record["sample_path"])
		truth_payload = read_json(first_layer_record["truth_path"])
		gps_rows = build_gps_rows(uid, sample_payload, truth_payload)
		write_csv(uid_dir / "gps.csv", ["uid", "point_index", "latitude", "longitude", "timestamp_ms"], gps_rows)

		layer_samples: dict[str, str] = {"gps": str(first_layer_record["sample_id"])}
		row_counts: dict[str, int] = {"gps": len(gps_rows)}
		source_paths: dict[str, str] = {
			"gps_csv": str(uid_dir / "gps.csv"),
			"gps_truth_path": str(first_layer_record["truth_path"]),
		}
		for layer_source in LAYER_SOURCES:
			layer_key = layer_source["layer_key"]
			layer_record = split_records[layer_key][uid]
			layer_rows = copy_raw6_rows(layer_record["rows"])
			write_csv(uid_dir / f"{layer_key}.csv", ["uid", "cid", "lat", "lon", "t_in", "t_out"], layer_rows)
			layer_samples[layer_key] = str(layer_record["sample_id"])
			row_counts[layer_key] = len(layer_rows)
			source_paths[f"{layer_key}_csv"] = str(uid_dir / f"{layer_key}.csv")
			source_paths[f"{layer_key}_source_sample"] = str(layer_record["sample_path"])
		track_manifest_tracks.append(
			{
				"track_id": f"uid:{uid}",
				"uid": uid,
				"sample_id": str(first_layer_record["sample_id"]),
				"phase": str(first_layer_record["split_name"]).split("/")[-1],
				"sample_ids_by_layer": layer_samples,
				"available_layers": ["gps", "tier1", "tier2", "tier3", "tier4"],
				"stats": {"row_counts": row_counts},
				"source_paths": source_paths,
			}
		)

	manifest_payload = {
		"ui_mode": "trajectory_layers",
		"title": f"Research Arena V1.5 GPS + Tier1-4 对照 ({', '.join(phase_list)})",
		"search_placeholder": "搜索 UID / sample_id / tier 样本...",
		"filter_title": "按同轨迹多层对照浏览",
		"filter_source_label": "GPS 真值 + 4 个 raw6 tier",
		"hide_review_panel": True,
		"review_reference_files": [],
		"time_scrubber_preferred_layers": ["gps", "tier4", "tier3", "tier2", "tier1"],
		"uids": common_uids,
		"layers": ["gps", "tier1", "tier2", "tier3", "tier4"],
		"layer_labels": {
			"gps": "GPS 真值",
			"tier1": "Tier-1 Clean Physical",
			"tier2": "Tier-2 Overlap Ambiguity",
			"tier3": "Tier-3 Raw-like Local Noise",
			"tier4": "Tier-4 Closest To Raw",
		},
		"layer_specs": {
			"gps": {
				"filename": "gps.csv",
				"kind": "gps",
				"defaultColor": "#0f766e",
				"defaultOpacity": 0.85,
				"hasLine": True,
			},
			"tier1": {
				"filename": "tier1.csv",
				"kind": "signal",
				"defaultColor": "#475569",
				"defaultOpacity": 0.72,
				"hasLine": True,
			},
			"tier2": {
				"filename": "tier2.csv",
				"kind": "signal",
				"defaultColor": "#2563eb",
				"defaultOpacity": 0.72,
				"hasLine": True,
			},
			"tier3": {
				"filename": "tier3.csv",
				"kind": "signal",
				"defaultColor": "#ea580c",
				"defaultOpacity": 0.78,
				"hasLine": True,
			},
			"tier4": {
				"filename": "tier4.csv",
				"kind": "signal",
				"defaultColor": "#7c3aed",
				"defaultOpacity": 0.82,
				"hasLine": True,
			},
		},
		"layer_visibility": {
			"gps": True,
			"tier1": True,
			"tier2": True,
			"tier3": True,
			"tier4": True,
		},
		"layer_sources": {
			"gps": {
				"source_type": "truth",
				"description": "Organizer GPS truth sequence projected on the fixed time grid.",
			},
			**{
				layer_source["layer_key"]: {
					"source_type": "raw6",
					"split_dir": layer_source["split_dir"],
					"tier_weight": layer_source["tier_weight"],
					"description": layer_source["description"],
				}
				for layer_source in LAYER_SOURCES
			},
		},
	}
	write_json(result_root / "manifest.json", manifest_payload)
	write_json(result_root / "states_index.json", states_index)
	write_json(
		output_batch_root / "track_manifest.json",
		{
			"generated_at": utc_now_iso(),
			"source": "research_arena_v15_layer_adapter",
			"phase": phase,
			"phases": phase_list,
			"count": len(track_manifest_tracks),
			"tracks": track_manifest_tracks,
		},
	)
	source_batch_payload = read_json(output_batch_root / "source_batch.json")
	source_batch_payload["phase"] = phase
	source_batch_payload["phases"] = phase_list
	source_batch_payload["layer_sources"] = [
		{
			"layer_key": layer_source["layer_key"],
			"split_dir": layer_source["split_dir"],
			"tier_weight": layer_source["tier_weight"],
		}
		for layer_source in LAYER_SOURCES
	]
	write_json(output_batch_root / "source_batch.json", source_batch_payload)

	return {
		"generated_at": utc_now_iso(),
		"dataset_root": str(dataset_root),
		"phase": phase,
		"phases": phase_list,
		"output_batch_root": str(output_batch_root),
		"uid_count": len(common_uids),
		"uids": common_uids,
	}


def main() -> int:
	args = parse_args()
	report = build_layered_batch(
		dataset_root=Path(args.dataset_root),
		phase=args.phase,
		output_batch_root=Path(args.output_batch_root),
		limit=max(0, int(args.limit or 0)),
		force=bool(args.force),
	)
	print(json.dumps(report, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
