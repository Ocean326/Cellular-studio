from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from ..server_batch_lib import validate_result_root
from ..user_upload_adapter_lib import (
	UserUploadAdapterError,
	build_signal6_result,
	build_trajectory4_result,
)


class UserUploadAdapterLibTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		with open(path, "w", encoding="utf-8", newline="") as handle:
			writer = csv.DictWriter(handle, fieldnames=fieldnames)
			writer.writeheader()
			for row in rows:
				writer.writerow(row)

	def test_build_trajectory4_result_writes_valid_result_root(self) -> None:
		source_csv = self.root / "trajectory4.csv"
		self._write_csv(
			source_csv,
			["uid", "lat", "lon", "timestamp", "state"],
			[
				{"uid": "u1001", "lat": 39.901, "lon": 116.391, "timestamp": "2026-04-17T08:00:01Z", "state": "walking"},
				{"uid": "u1001", "lat": 39.902, "lon": 116.392, "timestamp": "2026-04-17T08:00:00Z", "state": "stay"},
				{"uid": "u1002", "lat": 39.903, "lon": 116.393, "timestamp": "1713340800000", "state": "driving"},
			],
		)

		result_root = self.root / "result_trajectory4"
		payload = build_trajectory4_result(source_csv, result_root, title="Trajectory4 Upload")

		self.assertEqual(payload["adapter"], "trajectory4")
		self.assertEqual(payload["uid_count"], 2)
		self.assertEqual(payload["filter_state_options"], ["walking", "stay", "driving"])
		self.assertTrue((result_root / "u1001" / "gps.csv").exists())

		report = validate_result_root(result_root, require_review_reference=True)
		self.assertTrue(report["ok"], report["errors"])

		manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
		states_index = json.loads((result_root / "states_index.json").read_text(encoding="utf-8"))
		rows = list(csv.DictReader((result_root / "u1001" / "gps.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(manifest["ui_mode"], "trajectory_layers")
		self.assertEqual(manifest["layer_specs"]["gps"]["filename"], "gps.csv")
		self.assertEqual(manifest["review_reference_files"], ["gps.csv"])
		self.assertEqual(states_index["u1001"], ["stay", "walking"])
		self.assertEqual(rows[0]["timestamp_ms"], "1776412800000")
		self.assertEqual(rows[0]["status"], "stay")
		self.assertEqual(rows[1]["status"], "walking")

	def test_build_trajectory4_result_accepts_case_insensitive_headers(self) -> None:
		source_csv = self.root / "trajectory4_casefold.csv"
		self._write_csv(
			source_csv,
			["UID", "Latitude", "Longitude", "TimestampMS", "State"],
			[
				{"UID": "u2001", "Latitude": 39.901, "Longitude": 116.391, "TimestampMS": "1713340800000", "State": "stay"},
				{"UID": "u2001", "Latitude": 39.902, "Longitude": 116.392, "TimestampMS": "1713340860000", "State": "walking"},
			],
		)

		result_root = self.root / "result_trajectory4_casefold"
		payload = build_trajectory4_result(source_csv, result_root, title="Trajectory4 Casefold Upload")
		rows = list(csv.DictReader((result_root / "u2001" / "gps.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(rows[0]["uid"], "u2001")
		self.assertEqual(rows[0]["status"], "stay")
		self.assertEqual(rows[1]["status"], "walking")

	def test_build_trajectory4_result_rejects_missing_timestamp_columns(self) -> None:
		source_csv = self.root / "trajectory4_missing.csv"
		self._write_csv(
			source_csv,
			["uid", "latitude", "longitude"],
			[
				{"uid": "u1001", "latitude": 39.901, "longitude": 116.391},
			],
		)

		with self.assertRaisesRegex(UserUploadAdapterError, "missing required column for timestamp"):
			build_trajectory4_result(source_csv, self.root / "bad_result")

	def test_build_signal6_result_writes_valid_result_root(self) -> None:
		source_csv = self.root / "signal6.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "latitude", "longitude", "start_time", "end_time", "status"],
			[
				{
					"uid": "s2001",
					"cid": "1101",
					"latitude": 39.9042,
					"longitude": 116.4074,
					"start_time": "2026-04-17T08:00:00Z",
					"end_time": "2026-04-17T08:03:00Z",
					"status": "road",
				},
				{
					"uid": "s2001",
					"cid": "1102",
					"latitude": 39.9142,
					"longitude": 116.4174,
					"start_time": "2026-04-17T08:03:00Z",
					"end_time": "2026-04-17T08:05:00Z",
					"status": "subway",
				},
			],
		)

		result_root = self.root / "result_signal6"
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Upload")

		self.assertEqual(payload["adapter"], "signal6")
		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(payload["filter_state_options"], ["road", "subway"])
		self.assertTrue((result_root / "s2001" / "signal.csv").exists())

		report = validate_result_root(result_root, require_review_reference=True)
		self.assertTrue(report["ok"], report["errors"])

		manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
		states_index = json.loads((result_root / "states_index.json").read_text(encoding="utf-8"))
		rows = list(csv.DictReader((result_root / "s2001" / "signal.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(manifest["layers"], ["signal"])
		self.assertEqual(manifest["layer_specs"]["signal"]["kind"], "signal")
		self.assertEqual(states_index["s2001"], ["road", "subway"])
		self.assertEqual(rows[0]["duration_ms"], "180000")
		self.assertEqual(rows[1]["cid"], "1102")

	def test_build_signal6_result_accepts_case_insensitive_headers(self) -> None:
		source_csv = self.root / "signal6_casefold.csv"
		self._write_csv(
			source_csv,
			["UID", "CID", "Lat", "Lon", "TIn", "TOut", "Status"],
			[
				{
					"UID": "s2101",
					"CID": "1101",
					"Lat": 39.9042,
					"Lon": 116.4074,
					"TIn": "2026-04-17T08:00:00Z",
					"TOut": "2026-04-17T08:03:00Z",
					"Status": "road",
				},
			],
		)

		result_root = self.root / "result_signal6_casefold"
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Casefold Upload")
		rows = list(csv.DictReader((result_root / "s2101" / "signal.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(rows[0]["uid"], "s2101")
		self.assertEqual(rows[0]["cid"], "1101")
		self.assertEqual(rows[0]["status"], "road")

	def test_build_signal6_result_accepts_expanded_time_aliases(self) -> None:
		source_csv = self.root / "signal6_time_aliases.csv"
		self._write_csv(
			source_csv,
			["UID", "CID", "Lat", "Lon", "procedureStartTime", "proceduereEndTime", "Status"],
			[
				{
					"UID": "s2201",
					"CID": "1201",
					"Lat": 39.9042,
					"Lon": 116.4074,
					"procedureStartTime": "2026-04-17T08:00:00Z",
					"proceduereEndTime": "2026-04-17T08:03:00Z",
					"Status": "road",
				},
			],
		)

		result_root = self.root / "result_signal6_time_aliases"
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Time Alias Upload")
		rows = list(csv.DictReader((result_root / "s2201" / "signal.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(rows[0]["t_in"], "1776412800000")
		self.assertEqual(rows[0]["t_out"], "1776412980000")

	def test_build_trajectory4_result_accepts_custom_field_mapping(self) -> None:
		source_csv = self.root / "trajectory4_custom_mapping.csv"
		self._write_csv(
			source_csv,
			["trackId", "gpsLat", "gpsLon", "collectTime", "motionLabel"],
			[
				{
					"trackId": "u2401",
					"gpsLat": 39.901,
					"gpsLon": 116.391,
					"collectTime": "1713340800000",
					"motionLabel": "stay",
				},
			],
		)

		result_root = self.root / "result_trajectory4_custom_mapping"
		payload = build_trajectory4_result(
			source_csv,
			result_root,
			title="Trajectory4 Custom Mapping Upload",
			field_mapping={
				"uid": "trackId",
				"latitude": "gpsLat",
				"longitude": "gpsLon",
				"timestamp": "collectTime",
				"status": "motionLabel",
			},
		)
		rows = list(csv.DictReader((result_root / "u2401" / "gps.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(rows[0]["uid"], "u2401")
		self.assertEqual(rows[0]["status"], "stay")

	def test_build_signal6_result_rejects_out_of_beijing_rows(self) -> None:
		source_csv = self.root / "signal6_outside.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "lat", "lon", "t_in", "t_out"],
			[
				{"uid": "s3001", "cid": "2201", "lat": 31.2304, "lon": 121.4737, "t_in": 1, "t_out": 2},
			],
		)

		with self.assertRaisesRegex(UserUploadAdapterError, "outside Beijing bbox"):
			build_signal6_result(source_csv, self.root / "bad_signal_result")

	def test_build_signal6_result_rejects_reverse_time_window(self) -> None:
		source_csv = self.root / "signal6_bad_time.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "lat", "lon", "t_in", "t_out"],
			[
				{"uid": "s3002", "cid": "2202", "lat": 39.9042, "lon": 116.4074, "t_in": 20, "t_out": 10},
			],
		)

		with self.assertRaisesRegex(UserUploadAdapterError, "t_out must be >= t_in"):
			build_signal6_result(source_csv, self.root / "bad_signal_time_result")


if __name__ == "__main__":
	unittest.main()
