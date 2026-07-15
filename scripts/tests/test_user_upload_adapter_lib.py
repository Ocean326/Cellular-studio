from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from ..server_batch_lib import validate_result_root
from .. import user_upload_adapter_lib
from ..user_upload_adapter_lib import (
	UserUploadAdapterError,
	build_signal6_result,
	build_signal_triplet_result,
	build_trajectory4_result,
	detect_user_upload_type,
	normalize_signal6_algorithm_profile,
	signal6_pipeline_mode_for_profile,
	signal6_pipeline_options_for_profile,
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

	def test_detect_user_upload_type_identifies_trajectory4(self) -> None:
		source_csv = self.root / "trajectory4_detect.csv"
		self._write_csv(
			source_csv,
			["UID", "Latitude", "Longitude", "TimestampMS", "State"],
			[
				{"UID": "u2001", "Latitude": 39.901, "Longitude": 116.391, "TimestampMS": "1713340800000", "State": "stay"},
			],
		)

		self.assertEqual(detect_user_upload_type(source_csv), "trajectory4")

	def test_detect_user_upload_type_identifies_signal6_even_if_requested_type_is_trajectory4(self) -> None:
		source_csv = self.root / "signal6_detect.csv"
		self._write_csv(
			source_csv,
			["UID", "CID", "Lat", "Lon", "TIn", "TOut", "Status"],
			[
				{"UID": "s2101", "CID": "1101", "Lat": 39.9042, "Lon": 116.4074, "TIn": "1713340800000", "TOut": "1713340980000", "Status": "road"},
			],
		)

		self.assertEqual(detect_user_upload_type(source_csv, requested_upload_type="trajectory4"), "signal6")

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
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Upload", pipeline_mode="legacy")

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
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Casefold Upload", pipeline_mode="legacy")
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
		payload = build_signal6_result(source_csv, result_root, title="Signal6 Time Alias Upload", pipeline_mode="legacy")
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
			build_signal6_result(source_csv, self.root / "bad_signal_result", pipeline_mode="legacy")

	def test_build_signal6_result_can_drop_out_of_beijing_rows_for_preview(self) -> None:
		source_csv = self.root / "signal6_preview_outside.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "lat", "lon", "t_in", "t_out", "status"],
			[
				{"uid": "s3001", "cid": "2201", "lat": 39.9042, "lon": 116.4074, "t_in": 1, "t_out": 2, "status": "road"},
				{"uid": "s3001", "cid": "bad0", "lat": 0, "lon": 0, "t_in": 3, "t_out": 4, "status": "road"},
			],
		)

		result_root = self.root / "signal6_preview_result"
		payload = build_signal6_result(
			source_csv,
			result_root,
			pipeline_mode="legacy",
			pipeline_options={"drop_outside_beijing_bbox_rows": True},
		)
		rows = list(csv.DictReader((result_root / "s3001" / "signal.csv").read_text(encoding="utf-8").splitlines()))

		self.assertEqual(payload["uid_count"], 1)
		self.assertEqual(payload["outside_beijing_bbox_row_count"], 1)
		self.assertEqual(payload["dropped_outside_beijing_bbox_rows"], 1)
		self.assertEqual([row["cid"] for row in rows], ["2201"])

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
			build_signal6_result(source_csv, self.root / "bad_signal_time_result", pipeline_mode="legacy")

	def test_build_signal6_result_dispatches_to_v311_pipeline(self) -> None:
		source_csv = self.root / "signal6_v311_dispatch.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "latitude", "longitude", "t_in", "t_out"],
			[
				{"uid": "s9001", "cid": "1101", "latitude": 39.9042, "longitude": 116.4074, "t_in": 1, "t_out": 2},
			],
		)
		result_root = self.root / "result_signal6_v311_dispatch"
		with mock.patch.object(
			user_upload_adapter_lib,
			"_build_signal6_result_v311",
			return_value={"adapter": "signal6", "pipeline_mode": "v311", "uids": ["s9001"]},
		) as mock_v311:
			pipeline_options = {"fmm_variant_params": {"road": {"r": 0.01}}}
			payload = build_signal6_result(
				source_csv,
				result_root,
				pipeline_mode="v311",
				pipeline_options=pipeline_options,
			)
		self.assertEqual(payload["pipeline_mode"], "v311")
		mock_v311.assert_called_once_with(
			source_csv_path=source_csv,
			output_root=result_root,
			title="Uploaded Signal6",
			field_mapping=None,
			pipeline_options=pipeline_options,
		)

	def test_signal6_algorithm_profile_options_are_productized(self) -> None:
		self.assertEqual(normalize_signal6_algorithm_profile("demo90"), "speed_sparsity_90")
		self.assertEqual(normalize_signal6_algorithm_profile("mainroad"), "mainroad_weighted")

		baseline = signal6_pipeline_options_for_profile("baseline_v311")
		mainroad = signal6_pipeline_options_for_profile("mainroad_weighted")
		speed_sparsity = signal6_pipeline_options_for_profile("speed_sparsity_90")

		self.assertEqual(baseline["signal6_algorithm_profile"], "baseline_v311")
		self.assertEqual(mainroad["fmm_version"], "mainroad")
		self.assertEqual(mainroad["fmm_variant_params"]["subway"]["r"], -1.0)
		self.assertTrue(speed_sparsity["speed_sparsity_hybrid"])
		self.assertEqual(speed_sparsity["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertEqual(signal6_pipeline_mode_for_profile("legacy", "speed_sparsity_90"), "v311")
		self.assertEqual(signal6_pipeline_mode_for_profile("legacy", "mainroad_weighted"), "v311")
		self.assertEqual(signal6_pipeline_mode_for_profile("legacy", "baseline_v311"), "legacy")

	def test_detect_user_upload_type_identifies_signal_triplet_directory_and_zip(self) -> None:
		route_dir = self.root / "route_01"
		self._write_csv(
			route_dir / "signal.csv",
			["uid", "cid", "latitude", "longitude", "t_in", "t_out"],
			[
				{"uid": "route_01（测试）", "cid": "1101", "latitude": 39.9042, "longitude": 116.4074, "t_in": 1713340800000, "t_out": 1713340860000},
			],
		)
		self._write_csv(route_dir / "gate.csv", ["uid", "latitude", "longitude", "timestamp_ms"], [{"uid": "route_01（测试）", "latitude": 39.9042, "longitude": 116.4074, "timestamp_ms": 1713340800000}])
		self._write_csv(route_dir / "lbs.csv", ["uid", "segment_id", "point_index", "latitude", "longitude", "timestamp_ms"], [{"uid": "route_01（测试）", "segment_id": "LBS-01", "point_index": 0, "latitude": 39.9042, "longitude": 116.4074, "timestamp_ms": 1713340800000}])

		self.assertEqual(detect_user_upload_type(self.root, requested_upload_type="auto"), "signal_triplet")

		zip_path = self.root / "signal_triplet.zip"
		with zipfile.ZipFile(zip_path, "w") as archive:
			for csv_path in route_dir.glob("*.csv"):
				archive.write(csv_path, arcname=f"route_01/{csv_path.name}")
		self.assertEqual(detect_user_upload_type(zip_path, requested_upload_type="auto"), "signal_triplet")

	def test_build_signal_triplet_result_wraps_v311_chain_output(self) -> None:
		route_dir = self.root / "route_01"
		uid = "route_01（测试）"
		self._write_csv(
			route_dir / "signal.csv",
			["uid", "cid", "latitude", "longitude", "t_in", "t_out", "status"],
			[
				{"uid": uid, "cid": "1101", "latitude": 39.9042, "longitude": 116.4074, "t_in": 1713340800000, "t_out": 1713340801000, "status": "testing_signal"},
				{"uid": uid, "cid": "1102", "latitude": 39.9052, "longitude": 116.4084, "t_in": 1713340860000, "t_out": 1713340920000, "status": "testing_signal"},
			],
		)
		self._write_csv(route_dir / "gate.csv", ["uid", "gate_id", "latitude", "longitude", "timestamp_ms", "status"], [{"uid": uid, "gate_id": "GATE-01", "latitude": 39.9042, "longitude": 116.4074, "timestamp_ms": 1713340800000, "status": "gate_location"}])
		self._write_csv(route_dir / "lbs.csv", ["uid", "segment_id", "point_index", "latitude", "longitude", "timestamp_ms", "status"], [{"uid": uid, "segment_id": "LBS-01", "point_index": 0, "latitude": 39.9042, "longitude": 116.4074, "timestamp_ms": 1713340800000, "status": "lbs_assist"}])

		def fake_build_signal6_result(source_csv_path, output_root, **kwargs):
			uid_dir = Path(output_root) / "route_01_safe"
			self._write_csv(uid_dir / "snap.csv", ["uid", "cid", "latitude", "longitude", "t_in", "t_out"], [{"uid": uid, "cid": "1101", "latitude": 39.9042, "longitude": 116.4074, "t_in": 1713340800, "t_out": 1713340860}])
			self._write_csv(uid_dir / "line.csv", ["uid", "latitude", "longitude", "t_in", "t_out"], [{"uid": uid, "latitude": 39.9042, "longitude": 116.4074, "t_in": 1713340800, "t_out": 1713340860}])
			self._write_csv(uid_dir / "od.csv", ["start_latitude", "start_longitude", "end_latitude", "end_longitude", "start_time", "end_time", "time_diff", "speed", "is_stationary"], [{"start_latitude": 39.9042, "start_longitude": 116.4074, "end_latitude": 39.9052, "end_longitude": 116.4084, "start_time": 1713340800, "end_time": 1713340860, "time_diff": 60, "speed": 1.0, "is_stationary": "False"}])
			(Path(output_root) / "manifest.json").write_text(json.dumps({"uids": ["route_01_safe"]}) + "\n", encoding="utf-8")
			return {
				"adapter": "signal6",
				"pipeline_mode": "v311",
				"ui_mode": "chain2",
				"fmm_version": "mainroad",
				"fmm_network_cost_field": "fmm_cost",
				"fmm_algorithm": {"profile": "speed_sparsity_90", "fmm_version": "mainroad"},
			}

		result_root = self.root / "signal_triplet_result"
		with mock.patch.object(user_upload_adapter_lib, "build_signal6_result", side_effect=fake_build_signal6_result) as mock_chain:
			payload = build_signal_triplet_result(self.root, result_root, title="Signal Triplet Upload")

		self.assertEqual(payload["adapter"], "signal_triplet")
		self.assertEqual(payload["ui_mode"], "trajectory_layers")
		self.assertEqual(payload["review_reference_files"], ["signal.csv", "gate.csv", "lbs.csv", "snap.csv", "od.csv", "reconstruction.csv"])
		self.assertTrue((result_root / uid / "signal.csv").exists())
		self.assertTrue((result_root / uid / "reconstruction.csv").exists())
		manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
		self.assertEqual(manifest["layers"], ["signal", "gate", "lbs", "snap", "od", "reconstruction"])
		self.assertEqual(manifest["layer_specs"]["gate"]["ignoreDisplayTimeWindow"], True)
		self.assertEqual(manifest["time_scrubber_preferred_layers"], ["reconstruction", "signal"])
		signal_rows = list(csv.DictReader((result_root / uid / "signal.csv").read_text(encoding="utf-8").splitlines()))
		self.assertEqual(signal_rows[0]["t_out"], "1713340801000")
		self.assertEqual(signal_rows[0]["display_t_out"], "1713340860000")
		self.assertEqual(signal_rows[0]["display_duration_ms"], "60000")
		self.assertEqual(signal_rows[0]["display_duration_source"], "next_signal_t_in")
		self.assertEqual(signal_rows[1]["display_duration_source"], "source_t_out")
		report = validate_result_root(result_root, require_review_reference=True)
		self.assertTrue(report["ok"], report["errors"])
		mock_chain.assert_called_once()

	def test_route02_startfix_guard_uses_sparse_start_profile(self) -> None:
		route02_profile = {
			"snap_points": 16,
			"sparsity_score": 0.7918,
			"p75_gap_s": 353.5,
			"p85_step_m": 1376.46,
		}
		self.assertTrue(
			user_upload_adapter_lib._should_apply_signal6_route02_startfix_guard(
				"route_02_202605292018-2036_2",
				route02_profile,
			)
		)
		self.assertFalse(
			user_upload_adapter_lib._should_apply_signal6_route02_startfix_guard(
				"route_03_202605292140-2220_3",
				route02_profile,
			)
		)
		self.assertFalse(
			user_upload_adapter_lib._should_apply_signal6_route02_startfix_guard(
				"route_02_dense",
				{"snap_points": 31, "sparsity_score": 1.0, "p75_gap_s": 400.0, "p85_step_m": 2000.0},
			)
		)

	@unittest.skipUnless(
		os.environ.get("RUN_SIGNAL6_V311_SMOKE") == "1",
		"Set RUN_SIGNAL6_V311_SMOKE=1 to run real signal6 v311 smoke test.",
	)
	def test_build_signal6_result_v311_smoke(self) -> None:
		source_csv = self.root / "signal6_v311_smoke.csv"
		self._write_csv(
			source_csv,
			["uid", "cid", "latitude", "longitude", "t_in", "t_out"],
			[
				{"uid": "91001", "cid": "1101", "latitude": 39.9042, "longitude": 116.4074, "t_in": 1713340800000, "t_out": 1713340980000},
				{"uid": "91001", "cid": "1102", "latitude": 39.9052, "longitude": 116.4084, "t_in": 1713340980000, "t_out": 1713341160000},
				{"uid": "91002", "cid": "1201", "latitude": 39.9142, "longitude": 116.4174, "t_in": 1713340800000, "t_out": 1713341100000},
			],
		)
		result_root = self.root / "result_signal6_v311_smoke"
		payload = build_signal6_result(source_csv, result_root, title="Signal6 V311 Smoke", pipeline_mode="v311")
		self.assertEqual(payload["pipeline_mode"], "v311")
		self.assertEqual(payload["ui_mode"], "chain2")
		self.assertTrue((result_root / "91001" / "line.csv").exists())
		self.assertTrue((result_root / "manifest.json").exists())


if __name__ == "__main__":
	unittest.main()
