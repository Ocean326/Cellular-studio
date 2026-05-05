from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ..adapt_research_arena_v15_layers_batch import build_layered_batch


class ResearchArenaV15LayerAdapterTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_json(self, path: Path, payload: dict) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

	def _write_text(self, path: Path, content: str) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(content, encoding="utf-8")

	def _create_split(self, dataset_root: Path, split_dir: str, uid: str) -> None:
		split_root = dataset_root / "splits" / split_dir / "dev-public"
		sample_prefix = {
			"tier1-clean-physical": "tier1",
			"tier2-overlap-ambiguity": "tier2",
			"tier3-raw-like-local-noise": "tier3",
			"tier4-closest-to-raw": "tier4",
		}[split_dir]
		sample_id = f"{sample_prefix}-dev-public-u{uid}"
		batch_id = f"{sample_prefix}-dev-public-0000"
		self._write_text(
			split_root / "batches" / f"{batch_id}.csv",
			f"uid,cid,lat,lon,t_in,t_out\n{uid},101,39.9,116.3,1,2\n{uid},102,39.91,116.31,3,4\n",
		)
		self._write_json(
			split_root / "manifests" / f"{batch_id}.json",
			{
				"batch_id": batch_id,
				"tier_id": split_dir,
				"split_name": f"{split_dir}/dev-public",
				"csv_file": f"{batch_id}.csv",
				"users": [
					{
						"sample_id": sample_id,
						"uid": uid,
						"start_time": "2023-03-01T00:00:00Z",
						"end_time": "2023-03-01T00:02:00Z",
						"time_grid_offsets_sec": [0, 60],
					}
				],
			},
		)
		self._write_json(
			split_root / "samples" / f"{sample_id}.json",
			{
				"sample_id": sample_id,
				"uid": uid,
				"start_time": "2023-03-01T00:00:00Z",
				"end_time": "2023-03-01T00:02:00Z",
				"time_grid_offsets_sec": [0, 60],
				"metadata": {},
			},
		)
		self._write_json(
			split_root / "truth" / f"{sample_id}.json",
			{
				"sample_id": sample_id,
				"gps_sequence": [
					{"lat": 39.9, "lng": 116.3},
					{"lat": 39.91, "lng": 116.31},
				],
				"metadata": {},
			},
		)

	def test_build_layered_batch_outputs_gps_plus_tier_layers(self) -> None:
		dataset_root = self.root / "dataset"
		for split_dir in (
			"tier1-clean-physical",
			"tier2-overlap-ambiguity",
			"tier3-raw-like-local-noise",
			"tier4-closest-to-raw",
		):
			self._create_split(dataset_root, split_dir, "1011509")

		output_batch_root = self.root / "studio_batch"
		report = build_layered_batch(
			dataset_root=dataset_root,
			phase="dev-public",
			output_batch_root=output_batch_root,
			force=True,
		)

		self.assertEqual(report["uid_count"], 1)
		self.assertTrue((output_batch_root / "result" / "1011509" / "gps.csv").exists())
		self.assertTrue((output_batch_root / "result" / "1011509" / "tier1.csv").exists())
		self.assertTrue((output_batch_root / "result" / "1011509" / "tier4.csv").exists())
		manifest = json.loads((output_batch_root / "result" / "manifest.json").read_text(encoding="utf-8"))
		self.assertEqual(manifest["ui_mode"], "trajectory_layers")
		self.assertEqual(manifest["layers"], ["gps", "tier1", "tier2", "tier3", "tier4"])
		self.assertEqual(manifest["layer_specs"]["tier4"]["filename"], "tier4.csv")
		self.assertEqual(manifest["layer_sources"]["tier4"]["split_dir"], "tier4-closest-to-raw")


if __name__ == "__main__":
	unittest.main()
