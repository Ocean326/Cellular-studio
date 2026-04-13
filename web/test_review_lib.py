from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
	sys.path.insert(0, str(THIS_DIR))

from review_lib import export_accepted_assets, resolve_review_paths, write_review


class ReviewLibTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.project_root = Path(self.temp_dir.name)
		self.result_root = self.project_root / "data" / "result"
		self.result_root.mkdir(parents=True, exist_ok=True)
		self.paths = resolve_review_paths(project_root=self.project_root)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_csv(self, path: Path, content: str) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(content, encoding="utf-8")

	def test_write_review_refreshes_latest_index(self) -> None:
		uid_dir = self.result_root / "1001"
		self._write_csv(uid_dir / "raw.csv", "uid,latitude\n1001,39.9\n")
		self._write_csv(uid_dir / "line.csv", "latitude,longitude\n39.9,116.3\n")

		write_review(
			self.paths,
			{
				"uid": "1001",
				"sample_id": "1001",
				"decision": "skip",
				"reviewer": "alice",
				"notes": "first pass",
				"reference_source": "fmm.csv",
			},
		)
		review = write_review(
			self.paths,
			{
				"uid": "1001",
				"sample_id": "1001",
				"decision": "accept",
				"reviewer": "bob",
				"notes": "confirmed",
				"reference_source": "line.csv",
			},
		)

		self.assertEqual(review["decision"], "accept")
		self.assertEqual(review["reviewer"], "bob")

		latest_payload = json.loads(self.paths.latest_path.read_text(encoding="utf-8"))
		self.assertEqual(latest_payload["count"], 1)
		self.assertEqual(latest_payload["counts"]["accept"], 1)
		self.assertEqual(latest_payload["reviews"]["1001"]["notes"], "confirmed")

	def test_export_accepted_assets_prefers_line_then_fmm(self) -> None:
		uid1_dir = self.result_root / "2001"
		uid2_dir = self.result_root / "2002"
		self._write_csv(uid1_dir / "raw.csv", "uid,latitude\n2001,39.9\n")
		self._write_csv(uid1_dir / "line.csv", "latitude,longitude\n39.9,116.3\n")
		self._write_csv(uid1_dir / "fmm.csv", "latitude,longitude\n39.9,116.4\n")
		self._write_csv(uid2_dir / "raw.csv", "uid,latitude\n2002,39.8\n")
		self._write_csv(uid2_dir / "line.csv", "latitude,longitude\n")
		self._write_csv(uid2_dir / "fmm.csv", "latitude,longitude\n39.8,116.2\n")

		write_review(
			self.paths,
			{
				"uid": "2001",
				"decision": "accept",
				"reviewer": "alice",
				"notes": "line available",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "2002",
				"decision": "accept",
				"reviewer": "alice",
				"notes": "fallback to fmm",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "2999",
				"decision": "reject",
				"reviewer": "alice",
				"notes": "should not export",
			},
		)

		manifest = export_accepted_assets(self.paths, clean=True)

		self.assertEqual(manifest["accepted_count"], 2)
		self.assertTrue((self.paths.export_root / "samples" / "2001" / "raw.csv").exists())
		self.assertTrue((self.paths.export_root / "samples" / "2001" / "line.csv").exists())
		self.assertFalse((self.paths.export_root / "samples" / "2001" / "fmm.csv").exists())
		self.assertTrue((self.paths.export_root / "samples" / "2002" / "raw.csv").exists())
		self.assertTrue((self.paths.export_root / "samples" / "2002" / "fmm.csv").exists())

		review_record = json.loads(
			(self.paths.export_root / "samples" / "2002" / "review.json").read_text(encoding="utf-8")
		)
		self.assertEqual(review_record["reference_source"], "fmm.csv")

	def test_write_review_rejects_accept_without_line_or_fmm(self) -> None:
		uid_dir = self.result_root / "3001"
		self._write_csv(uid_dir / "raw.csv", "uid,latitude\n3001,39.7\n")

		with self.assertRaisesRegex(ValueError, "line.csv or fmm.csv"):
			write_review(
				self.paths,
				{
					"uid": "3001",
					"decision": "accept",
					"reviewer": "alice",
					"notes": "raw only should fail",
				},
			)

	def test_export_accepted_assets_rewrites_sample_dir_when_reference_changes(self) -> None:
		uid_dir = self.result_root / "4001"
		self._write_csv(uid_dir / "raw.csv", "uid,latitude\n4001,39.6\n")
		self._write_csv(uid_dir / "line.csv", "latitude,longitude\n39.6,116.1\n")
		self._write_csv(uid_dir / "fmm.csv", "latitude,longitude\n39.6,116.2\n")

		write_review(
			self.paths,
			{
				"uid": "4001",
				"decision": "accept",
				"reviewer": "alice",
				"reference_source": "line.csv",
			},
		)
		export_accepted_assets(self.paths, clean=True)
		self.assertTrue((self.paths.export_root / "samples" / "4001" / "line.csv").exists())

		self._write_csv(uid_dir / "line.csv", "latitude,longitude\n")
		write_review(
			self.paths,
			{
				"uid": "4001",
				"decision": "accept",
				"reviewer": "alice",
				"reference_source": "fmm.csv",
			},
		)
		export_accepted_assets(self.paths, clean=False)

		sample_dir = self.paths.export_root / "samples" / "4001"
		self.assertFalse((sample_dir / "line.csv").exists())
		self.assertTrue((sample_dir / "fmm.csv").exists())
		review_record = json.loads((sample_dir / "review.json").read_text(encoding="utf-8"))
		self.assertEqual(review_record["reference_source"], "fmm.csv")


if __name__ == "__main__":
	unittest.main()
