#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


RAW_FIELDNAMES = ["uid", "point_index", "latitude", "longitude", "timestamp_ms", "state"]


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Build a minimal trajectory_annotation_studio batch from simple point records."
	)
	parser.add_argument("--input-json", required=True, help="Input JSON file following adapters/template examples")
	parser.add_argument("--output-batch-root", required=True, help="Output batch root")
	parser.add_argument("--batch-name", default="template_batch", help="Batch name written to batch_meta.json")
	parser.add_argument("--label", default="", help="Optional display label")
	parser.add_argument("--force", action="store_true", help="Replace output batch root if it already exists")
	return parser.parse_args()


def read_json(path: Path) -> dict:
	with open(path, encoding="utf-8") as handle:
		return json.load(handle)


def write_json(path: Path, payload: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(payload, handle, ensure_ascii=False, indent=2)
		handle.write("\n")


def write_csv(path: Path, rows: list[dict]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=RAW_FIELDNAMES)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in RAW_FIELDNAMES})


def ensure_empty_dir(path: Path, force: bool = False) -> None:
	if path.exists():
		if not force:
			raise FileExistsError(f"output already exists: {path}")
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def dedupe_preserve_order(items: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for item in items:
		value = str(item or "").strip()
		if not value or value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result


def normalize_samples(payload: dict) -> list[dict]:
	samples = payload.get("samples")
	if not isinstance(samples, list) or not samples:
		raise ValueError("input JSON must contain a non-empty samples array")
	normalized: list[dict] = []
	for index, sample in enumerate(samples, start=1):
		if not isinstance(sample, dict):
			raise ValueError(f"samples[{index - 1}] must be an object")
		uid = str(sample.get("uid") or "").strip()
		points = sample.get("points")
		if not uid:
			raise ValueError(f"samples[{index - 1}] is missing uid")
		if not isinstance(points, list) or not points:
			raise ValueError(f"samples[{index - 1}] must contain a non-empty points array")
		normalized.append({"uid": uid, "points": points})
	return normalized


def point_to_row(uid: str, point_index: int, point: dict) -> dict:
	latitude = point.get("latitude")
	if latitude is None:
		latitude = point.get("lat", "")
	longitude = point.get("longitude")
	if longitude is None:
		longitude = point.get("lon", "")
	return {
		"uid": uid,
		"point_index": point_index,
		"latitude": latitude,
		"longitude": longitude,
		"timestamp_ms": point.get("timestamp_ms", ""),
		"state": str(point.get("state") or "").strip(),
	}


def initialize_batch_dirs(batch_root: Path) -> None:
	for relative in (
		Path("result"),
		Path("review/system"),
		Path("review/reviewers"),
		Path("review/aggregate"),
		Path("accepted_assets/reviewers"),
		Path("review_exports/aggregate"),
	):
		(batch_root / relative).mkdir(parents=True, exist_ok=True)


def main() -> int:
	args = parse_args()
	input_path = Path(args.input_json).expanduser().resolve()
	output_batch_root = Path(args.output_batch_root).expanduser().resolve()
	if not input_path.exists():
		raise FileNotFoundError(f"input JSON not found: {input_path}")

	payload = read_json(input_path)
	samples = normalize_samples(payload)
	ensure_empty_dir(output_batch_root, force=bool(args.force))
	initialize_batch_dirs(output_batch_root)

	result_root = output_batch_root / "result"
	uids: list[str] = []
	states_index: dict[str, list[str]] = {}

	for sample in samples:
		uid = sample["uid"]
		points = sample["points"]
		uids.append(uid)
		rows = [point_to_row(uid, index, point) for index, point in enumerate(points)]
		write_csv(result_root / uid / "raw.csv", rows)
		states_index[uid] = dedupe_preserve_order([row["state"] for row in rows])

	generated_at = utc_now_iso()
	label = str(args.label or payload.get("label") or args.batch_name).strip() or args.batch_name
	manifest = {
		"dataset_name": str(payload.get("dataset_name") or args.batch_name).strip() or args.batch_name,
		"label": label,
		"generated_at": generated_at,
		"ui_mode": "chain2",
		"uids": uids,
		"layers": ["raw"],
		"layer_specs": {
			"raw": {
				"filename": "raw.csv",
				"kind": "default",
				"label": "Raw Points",
				"review_reference": True,
			}
		},
		"review_reference_files": ["raw.csv"],
		"states": states_index,
	}
	write_json(result_root / "manifest.json", manifest)
	write_json(result_root / "states_index.json", states_index)
	write_json(
		output_batch_root / "batch_meta.json",
		{
			"name": args.batch_name,
			"label": label,
			"version": "v1",
			"created_at": generated_at,
			"keywords": ["adapter-template"],
			"status": "prepared",
			"result_mode": "copied",
			"source_result_root": str(result_root),
			"uid_count": len(uids),
		},
	)
	write_json(
		output_batch_root / "source_batch.json",
		{
			"generated_at": generated_at,
			"source": "adapters/template/build_batch.py",
			"input_json": str(input_path),
		},
	)

	print(
		json.dumps(
			{
				"batch_root": str(output_batch_root),
				"result_root": str(result_root),
				"manifest_path": str(result_root / "manifest.json"),
				"uid_count": len(uids),
			},
			ensure_ascii=False,
			indent=2,
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
