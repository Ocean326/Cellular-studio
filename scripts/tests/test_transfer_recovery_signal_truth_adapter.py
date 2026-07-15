from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TransferRecoverySignalTruthAdapterTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name)
		self.repo_root = Path(__file__).resolve().parents[2]
		self.script_path = (
			self.repo_root
			/ "adapters"
			/ "transfer_recovery_signal_truth_layers"
			/ "build_batch.py"
		)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_text(self, path: Path, text: str) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text, encoding="utf-8")

	def _make_dalian_sample(self) -> tuple[Path, Path]:
		signal_path = self.root / "dalian" / "processed" / "sim_signal" / "dalian_00000_signal.csv"
		gps_path = self.root / "dalian" / "processed" / "gps_native" / "dalian_00000_trajectory.csv"
		truth_path = self.root / "dalian" / "processed" / "internal_truth" / "sim_signal" / "dalian_00000.json"
		self._write_text(
			signal_path,
			"uid,cid,lon,lat,t_in,t_out\n"
			"dalian_00000,C001,121.51,38.85,1729600455,1729600476\n",
		)
		self._write_text(
			gps_path,
			"timestamp_ms,longitude,latitude,cid\n"
			"1729600455000,121.51,38.85,C001\n",
		)
		self._write_text(
			truth_path,
			json.dumps(
				{
					"gps_truth_sequence": [
						{"ts": 1729600455.0, "lon": 121.51, "lat": 38.85},
						{"ts": 1729600485.0, "lon": 121.52, "lat": 38.86},
					]
				}
			)
			+ "\n",
		)
		inventory_path = self.root / "dalian_inventory.json"
		self._write_text(
			inventory_path,
			json.dumps(
				{
					"export_report": {
						"samples": [
							{
								"uid": "dalian_00000",
								"signal_path": str(signal_path),
								"truth_path": str(truth_path),
								"signal_rows": 1,
								"truth_points": 2,
							}
						]
					}
				}
			)
			+ "\n",
		)
		return inventory_path, gps_path

	def _make_chania_sample(self) -> Path:
		signal_path = self.root / "chania" / "processed" / "sim_signal" / "chania_00001_signal.csv"
		gps_path = self.root / "chania" / "processed" / "gps_native" / "chania_00001_trajectory.csv"
		truth_path = self.root / "chania" / "processed" / "internal_truth" / "sim_signal" / "chania_00001.json"
		self._write_text(
			signal_path,
			"uid,cid,lon,lat,t_in,t_out,rssi,raw_lon,raw_lat,kalman_lon,kalman_lat,kalman_dt_s,kalman_missing_input\n"
			"chania_00001,60561,24.03,35.51,1365111107,1365111112,-73,24.03,35.51,24.03,35.51,1.0,0\n",
		)
		self._write_text(
			gps_path,
			"timestamp,lat,lon,cid,rssi,is_moving\n"
			"2013-04-04T21:31:47+00:00,35.51,24.03,60561,-73,0\n",
		)
		self._write_text(
			truth_path,
			json.dumps(
				{
					"gps_truth_sequence": [
						{"ts": 1365111107.0, "lon": 24.03, "lat": 35.51},
						{"ts": 1365111112.0, "lon": 24.04, "lat": 35.52},
					]
				}
			)
			+ "\n",
		)
		inventory_path = self.root / "chania_inventory.json"
		self._write_text(
			inventory_path,
			json.dumps(
				{
					"export_report": {
						"samples": [
							{
								"uid": "chania_00001",
								"signal_path": str(signal_path),
								"truth_path": str(truth_path),
								"gps_native_path": str(gps_path),
								"signal_rows": 1,
								"truth_points": 2,
								"input_is_kalman_filtered": True,
							}
						]
					}
				}
			)
			+ "\n",
		)
		return inventory_path

	def test_adapter_builds_layered_batch(self) -> None:
		dalian_inventory, _ = self._make_dalian_sample()
		chania_inventory = self._make_chania_sample()
		output_root = self.root / "batch"

		result = subprocess.run(
			[
				sys.executable,
				str(self.script_path),
				"--dalian-inventory",
				str(dalian_inventory),
				"--chania-inventory",
				str(chania_inventory),
				"--output-batch-root",
				str(output_root),
				"--batch-name",
				"transferrec_demo",
			],
			check=True,
			capture_output=True,
			text=True,
		)

		payload = json.loads(result.stdout)
		manifest = json.loads((output_root / "result" / "manifest.json").read_text(encoding="utf-8"))
		states_index = json.loads((output_root / "result" / "states_index.json").read_text(encoding="utf-8"))
		batch_meta = json.loads((output_root / "batch_meta.json").read_text(encoding="utf-8"))

		self.assertEqual(payload["uid_count"], 2)
		self.assertEqual(manifest["ui_mode"], "trajectory_layers")
		self.assertEqual(manifest["review_reference_files"], ["gps_truth.csv"])
		self.assertEqual(manifest["layers"], ["gps_truth", "gps_native", "signal_raw"])
		self.assertEqual(manifest["dataset_summary"]["sample_count_by_dataset"]["chania"], 1)
		self.assertEqual(manifest["dataset_summary"]["sample_count_by_dataset"]["dalian"], 1)
		self.assertIn("dataset:dalian_fingerprint", states_index["dalian_00000"])
		self.assertIn("signal:kalman_filtered", states_index["chania_00001"])
		self.assertEqual(batch_meta["name"], "transferrec_demo")
		self.assertEqual(batch_meta["annotation_mode"], "read_only")
		self.assertTrue((output_root / "result" / "dalian_00000" / "signal_raw.csv").exists())
		self.assertTrue((output_root / "result" / "chania_00001" / "gps_native.csv").exists())
		self.assertTrue((output_root / "track_manifest.json").exists())


if __name__ == "__main__":
	unittest.main()
