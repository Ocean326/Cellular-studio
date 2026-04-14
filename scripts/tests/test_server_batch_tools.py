from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
	sys.path.insert(0, str(SCRIPTS_DIR))

from server_batch_lib import (
	init_179_server_layout,
	intake_upload_bundle,
	publish_batch,
	validate_batch_root,
	validate_result_root,
)


class ServerBatchToolsTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write_result_tree(self, root: Path) -> None:
		result_root = root / "result"
		result_root.mkdir(parents=True, exist_ok=True)
		(result_root / "manifest.json").write_text(
			'{"uids":["1001","1002"],"layers":["raw","snap","od","fmm","line"],"states":{"1001":["road"],"1002":["stay"]}}\n',
			encoding="utf-8",
		)
		(result_root / "states_index.json").write_text(
			'{"1001":["road"],"1002":["stay"]}\n',
			encoding="utf-8",
		)
		for uid in ("1001", "1002"):
			uid_dir = result_root / uid
			uid_dir.mkdir(parents=True, exist_ok=True)
			for name in ("raw.csv", "snap.csv", "od.csv", "line.csv"):
				(uid_dir / name).write_text("a,b\n1,2\n", encoding="utf-8")

	def test_init_179_server_layout_dry_run(self) -> None:
		report = init_179_server_layout(self.root / "srv", release_name="r1", create_current_link=True, dry_run=True)
		self.assertEqual(report["release_root"], str((self.root / "srv" / "app" / "releases" / "r1")))
		self.assertEqual(report["current_link"]["status"], "planned")

	def test_validate_batch_root_detects_valid_mounted_batch(self) -> None:
		dataset_root = self.root / "datasets" / "cohort1"
		self._write_result_tree(dataset_root)
		batch_root = self.root / "published" / "batch1"
		batch_root.mkdir(parents=True, exist_ok=True)
		(batch_root / "batch_meta.json").write_text(
			f'{{"name":"batch1","source_result_root":"{(dataset_root / "result").resolve()}"}}\n',
			encoding="utf-8",
		)
		report = validate_batch_root(batch_root)
		self.assertTrue(report["ok"])
		self.assertEqual(report["summary"]["manifest_uid_count"], 2)

	def test_publish_batch_creates_published_structure(self) -> None:
		dataset_root = self.root / "datasets" / "cohort2"
		self._write_result_tree(dataset_root)
		published_root = self.root / "shared" / "published"
		payload = publish_batch(
			published_root=published_root,
			batch_name="cohort2_b01of10",
			source_result_root=dataset_root / "result",
			cohort_id="cohort2",
			shard_index=1,
			shard_count=10,
			days=["2023-03-01", "2023-03-02"],
		)
		target_root = published_root / "cohort2_b01of10"
		self.assertTrue(target_root.exists())
		self.assertTrue((target_root / "batch_meta.json").exists())
		self.assertTrue((target_root / "source_batch.json").exists())
		self.assertTrue((target_root / "review" / "reviewers").exists())
		self.assertTrue((target_root / "accepted_assets" / "reviewers").exists())
		self.assertEqual(payload["metadata"]["cohort_id"], "cohort2")

	def test_validate_result_root_detects_missing_manifest(self) -> None:
		result_root = self.root / "bad_result"
		result_root.mkdir(parents=True, exist_ok=True)
		report = validate_result_root(result_root)
		self.assertFalse(report["ok"])
		self.assertIn("manifest.json is required", report["errors"])

	def test_intake_upload_bundle_extracts_and_publishes(self) -> None:
		upload_root = self.root / "incoming" / "20260414T000000Z_abcd1234"
		upload_root.mkdir(parents=True, exist_ok=True)
		(upload_root / "upload_status.json").write_text('{"upload_id":"u1","status":"uploaded"}\n', encoding="utf-8")
		payload_path = upload_root / "payload.zip"
		with zipfile.ZipFile(payload_path, "w") as archive:
			archive.writestr("result/manifest.json", '{"uids":["1001","1002"]}\n')
			archive.writestr("result/states_index.json", '{"1001":["road"],"1002":["stay"]}\n')
			archive.writestr("result/1001/raw.csv", "a,b\n1,2\n")
			archive.writestr("result/1001/line.csv", "a,b\n1,2\n")
			archive.writestr("result/1002/raw.csv", "a,b\n1,2\n")
			archive.writestr("result/1002/fmm.csv", "a,b\n1,2\n")

		report = intake_upload_bundle(
			upload_root=upload_root,
			workspace_root=self.root / "workspaces" / "incoming",
			published_root=self.root / "shared" / "published",
			batch_name="round1_b01of10",
			label="Round 1 B01",
			cohort_id="round1",
			shard_index=1,
			shard_count=10,
			clean_workspace=True,
			require_review_reference=True,
			publish=True,
		)

		self.assertTrue(report["validation"]["ok"])
		self.assertIsNotNone(report["published"])
		self.assertTrue((self.root / "shared" / "published" / "round1_b01of10" / "batch_meta.json").exists())
		self.assertTrue((upload_root / "intake_report.json").exists())


if __name__ == "__main__":
	unittest.main()
