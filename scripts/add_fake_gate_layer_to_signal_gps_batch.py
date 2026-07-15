from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


GATE_FIELDS = [
	"uid",
	"gate_id",
	"latitude",
	"longitude",
	"timestamp_ms",
	"source_gps_index",
	"source_file",
	"status",
]


def read_json(path: Path) -> dict[str, Any]:
	return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
	with path.open(encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=GATE_FIELDS)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in GATE_FIELDS})


def sample_indices(count: int, target_count: int) -> list[int]:
	if count <= 0:
		return []
	if count <= target_count:
		return list(range(count))
	if target_count <= 1:
		return [count // 2]
	last = count - 1
	indices: list[int] = []
	for index in range(target_count):
		candidate = round(index * last / (target_count - 1))
		if not indices or indices[-1] != candidate:
			indices.append(candidate)
	return indices


def build_gate_rows(uid: str, gps_rows: list[dict[str, str]], *, target_count: int) -> list[dict[str, Any]]:
	valid: list[tuple[int, dict[str, str]]] = []
	for row_index, row in enumerate(gps_rows):
		lat = row.get("latitude") or row.get("lat")
		lon = row.get("longitude") or row.get("lon")
		if not lat or not lon:
			continue
		try:
			float(lat)
			float(lon)
		except ValueError:
			continue
		valid.append((row_index, row))
	gate_rows = []
	for gate_index, valid_index in enumerate(sample_indices(len(valid), target_count), start=1):
		source_index, row = valid[valid_index]
		gate_rows.append(
			{
				"uid": uid,
				"gate_id": f"GATE-{gate_index:02d}",
				"latitude": row.get("latitude") or row.get("lat") or "",
				"longitude": row.get("longitude") or row.get("lon") or "",
				"timestamp_ms": row.get("timestamp_ms") or row.get("time") or row.get("t") or "",
				"source_gps_index": row.get("point_index") or source_index,
				"source_file": row.get("source_file") or "gps.csv",
				"status": "gate_location",
			}
		)
	return gate_rows


def ensure_gate_metadata(payload: dict[str, Any]) -> None:
	layers = payload.get("layers")
	if isinstance(layers, list):
		layers[:] = [layer for layer in layers if layer != "gate"]
		try:
			insert_at = layers.index("signal") + 1
		except ValueError:
			insert_at = 0
		layers.insert(insert_at, "gate")
	layer_labels = payload.setdefault("layer_labels", {})
	if isinstance(layer_labels, dict):
		layer_labels["gate"] = "卡口定位"
	layer_specs = payload.setdefault("layer_specs", {})
	if isinstance(layer_specs, dict):
		layer_specs["gate"] = {
			"filename": "gate.csv",
			"kind": "gate",
			"defaultColor": "#0891b2",
			"defaultOpacity": 0.88,
			"hasLine": False,
			"pointRadius": 8,
		}
	layer_visibility = payload.setdefault("layer_visibility", {})
	if isinstance(layer_visibility, dict):
		layer_visibility.setdefault("gate", True)
	review_reference_files = payload.get("review_reference_files")
	if isinstance(review_reference_files, list) and "gate.csv" not in review_reference_files:
		try:
			insert_at = review_reference_files.index("signal.csv") + 1
		except ValueError:
			insert_at = 0
		review_reference_files.insert(insert_at, "gate.csv")


def patch_batch(batch_root: Path, *, target_count: int) -> dict[str, Any]:
	result_root = batch_root / "result"
	manifest_path = result_root / "manifest.json"
	manifest = read_json(manifest_path)
	uids = list(manifest.get("uids") or [])
	written: dict[str, int] = {}
	for uid in uids:
		uid_dir = result_root / uid
		gps_path = uid_dir / "gps.csv"
		if not gps_path.exists():
			continue
		gate_rows = build_gate_rows(uid, read_csv_rows(gps_path), target_count=target_count)
		write_csv_rows(uid_dir / "gate.csv", gate_rows)
		written[uid] = len(gate_rows)

	ensure_gate_metadata(manifest)
	write_json(manifest_path, manifest)

	batch_meta_path = batch_root / "batch_meta.json"
	if batch_meta_path.exists():
		batch_meta = read_json(batch_meta_path)
		ui_config = batch_meta.setdefault("ui_config", {})
		if isinstance(ui_config, dict):
			ensure_gate_metadata(ui_config)
		write_json(batch_meta_path, batch_meta)

	return {"batch_root": str(batch_root), "uids": len(uids), "gate_rows_by_uid": written}


def main() -> int:
	parser = argparse.ArgumentParser(description="Add a fake gate-location layer to a signal/GPS demo batch using sampled GPS truth points.")
	parser.add_argument("--batch-root", required=True, type=Path)
	parser.add_argument("--target-count", type=int, default=8)
	args = parser.parse_args()
	report = patch_batch(args.batch_root.expanduser().resolve(), target_count=max(1, args.target_count))
	print(json.dumps(report, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
