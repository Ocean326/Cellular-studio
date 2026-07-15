#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from scripts.server_batch_lib import build_batch_metadata, write_json  # type: ignore


DEFAULT_DALIAN_INVENTORY = Path(
	"/home/ocean/Transfer_Recovery/applications/signal_reconstruction/manifests/dalian_fingerprint_inventory.json"
)
DEFAULT_CHANIA_INVENTORY = Path(
	"/home/ocean/Transfer_Recovery/applications/signal_reconstruction/manifests/mysignals_chania_inventory.json"
)
DEFAULT_BATCH_NAME = "transferrec_dalian_chania_signal_truth_v1"
SIGNAL_FIELDNAMES = [
	"uid",
	"cid",
	"lat",
	"lon",
	"t_in",
	"t_out",
	"rssi",
	"raw_lon",
	"raw_lat",
	"kalman_lon",
	"kalman_lat",
	"kalman_dt_s",
	"kalman_missing_input",
	"source_city",
	"source_dataset",
]
GPS_FIELDNAMES = [
	"uid",
	"point_index",
	"latitude",
	"longitude",
	"timestamp_ms",
	"cid",
	"rssi",
	"is_moving",
	"source_city",
	"source_dataset",
]
TRUTH_FIELDNAMES = [
	"uid",
	"point_index",
	"latitude",
	"longitude",
	"timestamp_ms",
	"source_city",
	"source_dataset",
]
DATASET_SPECS = {
	"dalian": {
		"inventory": DEFAULT_DALIAN_INVENTORY,
		"dataset_label": "dalian_fingerprint",
		"city_label": "Dalian",
	},
	"chania": {
		"inventory": DEFAULT_CHANIA_INVENTORY,
		"dataset_label": "mysignals_chania",
		"city_label": "Chania, Greece",
	},
}


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Build a trajectory_annotation batch for Transfer_Recovery Dalian + Chania raw signal and GPS truth visualization."
	)
	parser.add_argument("--dalian-inventory", default=str(DEFAULT_DALIAN_INVENTORY), help="Dalian inventory manifest")
	parser.add_argument("--chania-inventory", default=str(DEFAULT_CHANIA_INVENTORY), help="Chania inventory manifest")
	parser.add_argument("--output-batch-root", required=True, help="Target batch root for the studio")
	parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME, help="Batch name written to batch metadata")
	parser.add_argument(
		"--datasets",
		default="dalian,chania",
		help="Comma-separated dataset keys to include: dalian, chania",
	)
	parser.add_argument("--limit-per-dataset", type=int, default=0, help="Optional per-dataset sample cap")
	parser.add_argument("--force", action="store_true", help="Replace output batch root if it already exists")
	return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def ensure_empty_dir(path: Path, force: bool = False) -> None:
	if path.exists():
		if not force:
			raise FileExistsError(f"output already exists: {path}")
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def ensure_batch_dirs(batch_root: Path) -> None:
	for relative in (
		Path("result"),
		Path("review/system"),
		Path("review/reviewers"),
		Path("review/aggregate"),
		Path("accepted_assets/reviewers"),
		Path("review_exports/aggregate"),
	):
		(batch_root / relative).mkdir(parents=True, exist_ok=True)


def parse_dataset_list(text: str) -> list[str]:
	tokens = [token.strip().lower() for token in str(text or "").split(",") if token.strip()]
	if not tokens:
		raise ValueError("expected at least one dataset key")
	unknown = [token for token in tokens if token not in DATASET_SPECS]
	if unknown:
		raise ValueError(f"unknown dataset keys: {', '.join(sorted(unknown))}")
	return tokens


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in fieldnames})


def normalize_timestamp_ms(value: Any) -> int:
	if value is None:
		raise ValueError("timestamp value is required")
	if isinstance(value, (int, float)):
		number = float(value)
	else:
		text = str(value).strip()
		if not text:
			raise ValueError("timestamp value is required")
		if text.endswith("Z"):
			text = text[:-1] + "+00:00"
		try:
			dt = datetime.fromisoformat(text)
		except ValueError:
			number = float(text)
		else:
			if dt.tzinfo is None:
				dt = dt.replace(tzinfo=timezone.utc)
			return int(dt.timestamp() * 1000)
	if abs(number) < 10_000_000_000:
		return int(number * 1000)
	return int(number)


def infer_gps_native_path(sample: dict[str, Any], signal_path: Path) -> Path:
	explicit = str(sample.get("gps_native_path") or "").strip()
	if explicit:
		return Path(explicit).expanduser().resolve()
	uid = str(sample.get("uid") or signal_path.stem.replace("_signal", "")).strip()
	candidate = signal_path.parents[1] / "gps_native" / f"{uid}_trajectory.csv"
	return candidate.resolve()


def load_inventory_samples(inventory_path: Path, *, dataset_key: str, limit: int = 0) -> list[dict[str, Any]]:
	payload = read_json(inventory_path.expanduser().resolve())
	samples = list(((payload.get("export_report") or {}).get("samples")) or [])
	if limit > 0:
		samples = samples[:limit]
	normalized: list[dict[str, Any]] = []
	for sample in samples:
		uid = str(sample.get("uid") or "").strip()
		signal_path_text = str(sample.get("signal_path") or "").strip()
		truth_path_text = str(sample.get("truth_path") or "").strip()
		if not uid or not signal_path_text or not truth_path_text:
			continue
		signal_path = Path(signal_path_text).expanduser().resolve()
		truth_path = Path(truth_path_text).expanduser().resolve()
		gps_native_path = infer_gps_native_path(sample, signal_path)
		if not signal_path.exists():
			raise FileNotFoundError(f"signal path not found for {uid}: {signal_path}")
		if not truth_path.exists():
			raise FileNotFoundError(f"truth path not found for {uid}: {truth_path}")
		if not gps_native_path.exists():
			raise FileNotFoundError(f"gps native path not found for {uid}: {gps_native_path}")
		normalized.append(
			{
				"uid": uid,
				"dataset_key": dataset_key,
				"dataset_label": DATASET_SPECS[dataset_key]["dataset_label"],
				"city_label": DATASET_SPECS[dataset_key]["city_label"],
				"signal_path": signal_path,
				"truth_path": truth_path,
				"gps_native_path": gps_native_path,
				"signal_rows": int(sample.get("signal_rows") or 0),
				"truth_points": int(sample.get("truth_points") or 0),
				"input_is_kalman_filtered": bool(sample.get("input_is_kalman_filtered")),
			}
		)
	return normalized


def load_signal_rows(sample: dict[str, Any]) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	with open(sample["signal_path"], encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			rows.append(
				{
					"uid": str(row.get("uid") or sample["uid"]).strip(),
					"cid": str(row.get("cid") or "").strip(),
					"lat": str(row.get("lat") or row.get("latitude") or "").strip(),
					"lon": str(row.get("lon") or row.get("longitude") or "").strip(),
					"t_in": str(row.get("t_in") or row.get("timestamp_ms") or row.get("timestamp") or "").strip(),
					"t_out": str(row.get("t_out") or row.get("timestamp_ms") or row.get("timestamp") or "").strip(),
					"rssi": str(row.get("rssi") or "").strip(),
					"raw_lon": str(row.get("raw_lon") or "").strip(),
					"raw_lat": str(row.get("raw_lat") or "").strip(),
					"kalman_lon": str(row.get("kalman_lon") or "").strip(),
					"kalman_lat": str(row.get("kalman_lat") or "").strip(),
					"kalman_dt_s": str(row.get("kalman_dt_s") or "").strip(),
					"kalman_missing_input": str(row.get("kalman_missing_input") or "").strip(),
					"source_city": sample["city_label"],
					"source_dataset": sample["dataset_label"],
				}
			)
	return rows


def load_gps_native_rows(sample: dict[str, Any]) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	with open(sample["gps_native_path"], encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		for index, row in enumerate(reader):
			rows.append(
				{
					"uid": sample["uid"],
					"point_index": index,
					"latitude": str(row.get("latitude") or row.get("lat") or "").strip(),
					"longitude": str(row.get("longitude") or row.get("lon") or "").strip(),
					"timestamp_ms": normalize_timestamp_ms(
						row.get("timestamp_ms") or row.get("timestamp") or row.get("t_in")
					),
					"cid": str(row.get("cid") or "").strip(),
					"rssi": str(row.get("rssi") or "").strip(),
					"is_moving": str(row.get("is_moving") or "").strip(),
					"source_city": sample["city_label"],
					"source_dataset": sample["dataset_label"],
				}
			)
	return rows


def load_gps_truth_rows(sample: dict[str, Any]) -> list[dict[str, Any]]:
	payload = read_json(sample["truth_path"])
	sequence = list(payload.get("gps_truth_sequence") or [])
	rows: list[dict[str, Any]] = []
	for index, point in enumerate(sequence):
		rows.append(
			{
				"uid": sample["uid"],
				"point_index": index,
				"latitude": point.get("lat", ""),
				"longitude": point.get("lon", ""),
				"timestamp_ms": normalize_timestamp_ms(point.get("ts")),
				"source_city": sample["city_label"],
				"source_dataset": sample["dataset_label"],
			}
		)
	return rows


def build_states_index(samples: list[dict[str, Any]]) -> dict[str, list[str]]:
	return {
		sample["uid"]: [
			f"city:{sample['city_label'].lower().replace(', ', '_').replace(' ', '_')}",
			f"dataset:{sample['dataset_label']}",
			"signal:kalman_filtered" if sample.get("input_is_kalman_filtered") else "signal:raw_like",
		]
		for sample in samples
	}


def build_track_manifest(samples: list[dict[str, Any]], result_root: Path) -> dict[str, Any]:
	return {
		"generated_at": utc_now_iso(),
		"source": "Transfer_Recovery signal/gps layered adapter",
		"count": len(samples),
		"tracks": [
			{
				"uid": sample["uid"],
				"dataset_key": sample["dataset_key"],
				"dataset_label": sample["dataset_label"],
				"city_label": sample["city_label"],
				"signal_path": str(sample["signal_path"]),
				"truth_path": str(sample["truth_path"]),
				"gps_native_path": str(sample["gps_native_path"]),
				"result_uid_dir": str(result_root / sample["uid"]),
				"signal_rows": sample["signal_rows"],
				"truth_points": sample["truth_points"],
				"input_is_kalman_filtered": sample["input_is_kalman_filtered"],
			}
			for sample in samples
		],
	}


def build_manifest(samples: list[dict[str, Any]]) -> dict[str, Any]:
	return {
		"ui_mode": "trajectory_layers",
		"title": "Transfer_Recovery Dalian + Chania Raw Signal / GPS Truth",
		"search_placeholder": "Search UID / city / dataset...",
		"filter_title": "Browse raw cellular signal against GPS layers",
		"filter_source_label": "Transfer_Recovery cross-city signal truth visualization",
		"hide_review_panel": True,
		"review_reference_files": ["gps_truth.csv"],
		"time_scrubber_preferred_layers": ["gps_truth", "gps_native", "signal_raw"],
		"uids": [sample["uid"] for sample in samples],
		"layers": ["gps_truth", "gps_native", "signal_raw"],
		"layer_labels": {
			"gps_truth": "GPS Truth",
			"gps_native": "Native GPS",
			"signal_raw": "Raw Signal",
		},
		"layer_specs": {
			"gps_truth": {
				"filename": "gps_truth.csv",
				"kind": "gps",
				"defaultColor": "#0f766e",
				"defaultOpacity": 0.92,
				"hasLine": True,
				"review_reference": True,
			},
			"gps_native": {
				"filename": "gps_native.csv",
				"kind": "gps",
				"defaultColor": "#2563eb",
				"defaultOpacity": 0.7,
				"hasLine": True,
				"dashArray": "4,4",
			},
			"signal_raw": {
				"filename": "signal_raw.csv",
				"kind": "signal",
				"defaultColor": "#ea580c",
				"defaultOpacity": 0.78,
				"hasLine": True,
			},
		},
		"layer_visibility": {
			"gps_truth": True,
			"gps_native": True,
			"signal_raw": True,
		},
		"layer_sources": {
			"gps_truth": {"source_type": "truth_json"},
			"gps_native": {"source_type": "gps_native_csv"},
			"signal_raw": {"source_type": "sim_signal_csv"},
		},
		"dataset_summary": {
			"sample_count_total": len(samples),
			"sample_count_by_dataset": {
				dataset_key: len([sample for sample in samples if sample["dataset_key"] == dataset_key])
				for dataset_key in sorted({sample["dataset_key"] for sample in samples})
			},
		},
	}


def build_batch(
	*,
	datasets: list[str],
	dalian_inventory: Path,
	chania_inventory: Path,
	output_batch_root: Path,
	batch_name: str,
	limit_per_dataset: int = 0,
	force: bool = False,
) -> dict[str, Any]:
	inventory_map = {
		"dalian": dalian_inventory.expanduser().resolve(),
		"chania": chania_inventory.expanduser().resolve(),
	}
	ensure_empty_dir(output_batch_root, force=force)
	ensure_batch_dirs(output_batch_root)
	result_root = output_batch_root / "result"

	samples: list[dict[str, Any]] = []
	for dataset_key in datasets:
		samples.extend(
			load_inventory_samples(
				inventory_map[dataset_key],
				dataset_key=dataset_key,
				limit=max(0, int(limit_per_dataset or 0)),
			)
		)
	if not samples:
		raise ValueError("no samples loaded from the requested datasets")

	for sample in samples:
		uid_dir = result_root / sample["uid"]
		uid_dir.mkdir(parents=True, exist_ok=True)
		write_csv(uid_dir / "signal_raw.csv", SIGNAL_FIELDNAMES, load_signal_rows(sample))
		write_csv(uid_dir / "gps_native.csv", GPS_FIELDNAMES, load_gps_native_rows(sample))
		write_csv(uid_dir / "gps_truth.csv", TRUTH_FIELDNAMES, load_gps_truth_rows(sample))

	manifest_payload = build_manifest(samples)
	states_index = build_states_index(samples)
	write_json(result_root / "manifest.json", manifest_payload)
	write_json(result_root / "states_index.json", states_index)
	write_json(output_batch_root / "track_manifest.json", build_track_manifest(samples, result_root))
	write_json(
		output_batch_root / "source_batch.json",
		{
			"generated_at": utc_now_iso(),
			"source": "adapters/transfer_recovery_signal_truth_layers/build_batch.py",
			"datasets": datasets,
			"dalian_inventory": str(dalian_inventory.expanduser().resolve()),
			"chania_inventory": str(chania_inventory.expanduser().resolve()),
		},
	)
	write_json(
		output_batch_root / "batch_meta.json",
		build_batch_metadata(
			batch_name=batch_name,
			source_result_root=result_root,
			label="Transfer_Recovery Dalian + Chania Signal Truth",
			version="transferrec-signal-truth-v1",
			keywords=[
				"transfer_recovery",
				"signal_reconstruction",
				"trajectory_layers",
				"dalian",
				"chania",
			],
			status="prepared",
			result_mode="copied",
			uid_count=len(samples),
			extra_metadata={
				"annotation_mode": "read_only",
				"visibility_scope": "public",
				"datasets": datasets,
			},
		),
	)
	return {
		"generated_at": utc_now_iso(),
		"batch_root": str(output_batch_root),
		"result_root": str(result_root),
		"batch_name": batch_name,
		"uid_count": len(samples),
		"datasets": datasets,
		"counts_by_dataset": {
			dataset_key: len([sample for sample in samples if sample["dataset_key"] == dataset_key])
			for dataset_key in datasets
		},
	}


def main() -> int:
	args = parse_args()
	report = build_batch(
		datasets=parse_dataset_list(args.datasets),
		dalian_inventory=Path(args.dalian_inventory),
		chania_inventory=Path(args.chania_inventory),
		output_batch_root=Path(args.output_batch_root).expanduser().resolve(),
		batch_name=str(args.batch_name).strip() or DEFAULT_BATCH_NAME,
		limit_per_dataset=max(0, int(args.limit_per_dataset or 0)),
		force=bool(args.force),
	)
	print(json.dumps(report, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
