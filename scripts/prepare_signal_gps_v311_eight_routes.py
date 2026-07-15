#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LOCAL_TIMEZONE = timezone(timedelta(hours=8))
DEFAULT_IMPORT_ROOT = Path("data/imports/linux-zt-cdrom-2026-06-01")
DEFAULT_BASE_ROOT = Path("data/source_uploads/current_two_sources")
DEFAULT_OUTPUT_ROOT = Path("data/source_uploads/signal_gps_eight_routes_20260602")
DEFAULT_NEW_SIGNAL_RAR = DEFAULT_IMPORT_ROOT / "20260602测试.rar"
DEFAULT_KML_TRUTHS = (
	Path("/Users/ocean/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_2hfhpkch5obf22_3b7a/msg/file/2026-06/2026-06-01 1825北京城区海淀区.kml"),
	Path("/Users/ocean/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_2hfhpkch5obf22_3b7a/msg/file/2026-06/2026-06-01 2109北京城区海淀区到朝阳区(1).kml"),
	Path("/Users/ocean/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_2hfhpkch5obf22_3b7a/msg/file/2026-06/2026-06-02 0751北京城区东城区到海淀区(1).kml"),
)
INPUT_FIELDS = [
	"uid",
	"cid",
	"lat",
	"lon",
	"t_in",
	"t_out",
	"source_time",
	"segment_file",
	"declared_window_start",
	"declared_window_end",
	"input_window_start",
	"input_window_end",
]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Prepare the June 2026 signal/GPS demo as eight v311 routes.")
	parser.add_argument("--base-root", type=Path, default=DEFAULT_BASE_ROOT)
	parser.add_argument("--new-signal-rar", type=Path, default=DEFAULT_NEW_SIGNAL_RAR)
	parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
	parser.add_argument("--kml-truth", action="append", type=Path, default=[])
	parser.add_argument("--uid-prefix-start", type=int, default=6)
	parser.add_argument("--input-window-padding-minutes", type=int, default=30)
	parser.add_argument("--force", action="store_true")
	return parser.parse_args()


def parse_local_datetime(value: str) -> datetime:
	text = str(value or "").strip().strip("\t")
	for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
		try:
			return datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TIMEZONE)
		except ValueError:
			continue
	raise ValueError(f"unsupported datetime: {value!r}")


def parse_segment_window(path: Path) -> tuple[datetime, datetime]:
	name = path.name
	prefix = name.split("（", 1)[0]
	day = prefix[:8]
	window = prefix[8:]
	start_hm, end_hm = window.split("-", 1)
	start = datetime.strptime(day + start_hm, "%Y%m%d%H%M").replace(tzinfo=LOCAL_TIMEZONE)
	end = datetime.strptime(day + end_hm, "%Y%m%d%H%M").replace(tzinfo=LOCAL_TIMEZONE) + timedelta(seconds=59)
	if end < start:
		end += timedelta(days=1)
	return start, end


def format_local(value: datetime) -> str:
	return value.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def epoch_ms(value: datetime) -> int:
	return int(value.timestamp() * 1000)


def parse_float(value: Any) -> float | None:
	try:
		return float(str(value).strip().strip("\t"))
	except (TypeError, ValueError):
		return None


def ensure_empty(path: Path, force: bool) -> None:
	if path.exists():
		if not force:
			raise FileExistsError(path)
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def extract_rar(source: Path, target: Path) -> None:
	target.mkdir(parents=True, exist_ok=True)
	subprocess.run(["bsdtar", "-xf", str(source), "-C", str(target)], check=True)


def read_existing_rows(path: Path) -> list[dict[str, Any]]:
	with path.open(encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def find_new_signal_dir(extracted_root: Path) -> Path:
	candidates = [path for path in extracted_root.rglob("*") if path.is_dir() and list(path.glob("202606*.csv"))]
	if not candidates:
		raise FileNotFoundError(f"no extracted 202606 signal segment directory under {extracted_root}")
	return sorted(candidates, key=lambda item: str(item))[0]


def read_new_segment_rows(path: Path, *, route_index: int, padding_minutes: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	start, end = parse_segment_window(path)
	input_start = start - timedelta(minutes=padding_minutes)
	input_end = end + timedelta(minutes=padding_minutes)
	uid = f"route_{route_index:02d}_{path.stem}"
	rows: list[dict[str, Any]] = []
	with path.open(encoding="gbk", newline="") as handle:
		for row in csv.DictReader(handle):
			source_time = str(row.get("开始时间") or "").strip().strip("\t")
			if not source_time:
				continue
			try:
				time_value = parse_local_datetime(source_time)
			except ValueError:
				continue
			if time_value < input_start or time_value > input_end:
				continue
			lon = parse_float(row.get("基站经度"))
			lat = parse_float(row.get("基站纬度"))
			if lon is None or lat is None:
				continue
			cid = str(row.get("用户号码") or "13031180432").strip().strip("\t") or "13031180432"
			t_in = epoch_ms(time_value)
			rows.append(
				{
					"uid": uid,
					"cid": cid,
					"lat": f"{lat:.8f}",
					"lon": f"{lon:.8f}",
					"t_in": t_in,
					"t_out": t_in + 1000,
					"source_time": format_local(time_value),
					"segment_file": path.name,
					"declared_window_start": format_local(start),
					"declared_window_end": format_local(end),
					"input_window_start": format_local(input_start),
					"input_window_end": format_local(input_end),
				}
			)
	rows.sort(key=lambda item: (int(item["t_in"]), str(item["lon"]), str(item["lat"])))
	summary = {
		"uid": uid,
		"segment_file": path.name,
		"rows": len(rows),
		"declared_window_start": format_local(start),
		"declared_window_end": format_local(end),
		"input_window_start": format_local(input_start),
		"input_window_end": format_local(input_end),
		"actual_first_time": rows[0]["source_time"] if rows else "",
		"actual_last_time": rows[-1]["source_time"] if rows else "",
	}
	return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=INPUT_FIELDS)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row.get(field, "") for field in INPUT_FIELDS})


def main() -> int:
	args = parse_args()
	base_root = args.base_root.expanduser().resolve()
	output_root = args.output_root.expanduser().resolve()
	ensure_empty(output_root, bool(args.force))

	signal_dir = output_root / "gps_rar" / "测试号"
	truth_dir = output_root / "gps_truth"
	signal_dir.mkdir(parents=True, exist_ok=True)
	truth_dir.mkdir(parents=True, exist_ok=True)

	for source in sorted((base_root / "gps_rar" / "测试号").glob("202605*.csv")):
		shutil.copy2(source, signal_dir / source.name)
	for source in sorted((base_root / "gps_truth_csv").glob("*.csv")):
		shutil.copy2(source, truth_dir / source.name)

	with tempfile.TemporaryDirectory() as tmp:
		extracted_root = Path(tmp)
		extract_rar(args.new_signal_rar.expanduser().resolve(), extracted_root)
		new_signal_dir = find_new_signal_dir(extracted_root)
		new_segment_paths = sorted(new_signal_dir.glob("202606*.csv"))
		if len(new_segment_paths) != 3:
			raise ValueError(f"expected 3 new signal segment csv files, got {len(new_segment_paths)}")
		new_rows: list[dict[str, Any]] = []
		summary: list[dict[str, Any]] = []
		for offset, source in enumerate(new_segment_paths):
			route_index = int(args.uid_prefix_start) + offset
			target = signal_dir / source.name
			shutil.copy2(source, target)
			rows, item_summary = read_new_segment_rows(
				source,
				route_index=route_index,
				padding_minutes=int(args.input_window_padding_minutes),
			)
			new_rows.extend(rows)
			summary.append(item_summary)

	kml_truths = args.kml_truth or list(DEFAULT_KML_TRUTHS)
	if len(kml_truths) != 3:
		raise ValueError(f"expected 3 KML truth files, got {len(kml_truths)}")
	for source in kml_truths:
		source_path = source.expanduser().resolve()
		if not source_path.exists():
			raise FileNotFoundError(source_path)
		shutil.copy2(source_path, truth_dir / source_path.name)

	existing_rows = read_existing_rows(base_root / "testing_signal6_input.csv")
	merged_rows = existing_rows + new_rows
	write_csv(output_root / "testing_signal6_input.csv", merged_rows)

	(output_root / "prepare_summary.json").write_text(
		json.dumps(
			{
				"base_root": str(base_root),
				"new_signal_rar": str(args.new_signal_rar.expanduser().resolve()),
				"output_root": str(output_root),
				"route_count": 8,
				"input_rows": len(merged_rows),
				"new_input_rows": len(new_rows),
				"new_segments": summary,
				"truth_files": [path.name for path in sorted(truth_dir.iterdir()) if path.is_file()],
				"signal_segment_files": [path.name for path in sorted(signal_dir.iterdir()) if path.is_file()],
			},
			ensure_ascii=False,
			indent=2,
		)
		+ "\n",
		encoding="utf-8",
	)
	print(f"wrote {output_root} with {len(merged_rows)} input rows")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
