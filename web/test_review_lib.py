from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
	sys.path.insert(0, str(THIS_DIR))

from review_lib import (
	ensure_reviewer_profile,
	export_accepted_assets,
	export_reviewer_bundle,
	export_review_aggregate,
	get_uid_review_aggregate,
	read_latest_reviews,
	read_timeline_annotations,
	resolve_review_paths,
	write_review,
	write_timeline_annotations,
)


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

	def _write_manifest(self, payload: dict) -> None:
		(self.result_root / "manifest.json").write_text(
			json.dumps(payload, ensure_ascii=False) + "\n",
			encoding="utf-8",
		)

	def _write_uid_assets(self, uid: str, *, line: bool = True, fmm: bool = False) -> None:
		uid_dir = self.result_root / uid
		self._write_csv(uid_dir / "raw.csv", f"uid,latitude\n{uid},39.9\n")
		self._write_csv(uid_dir / "snap.csv", f"uid,latitude\n{uid},39.91\n")
		self._write_csv(uid_dir / "od.csv", "uid,is_stationary,start_time,end_time\n1001,false,1,2\n")
		if line:
			self._write_csv(uid_dir / "line.csv", "latitude,longitude\n39.9,116.3\n")
		if fmm:
			self._write_csv(uid_dir / "fmm.csv", "latitude,longitude\n39.9,116.4\n")

	def test_reviewer_namespace_keeps_separate_latest_views(self) -> None:
		self._write_uid_assets("1001", line=True, fmm=True)

		write_review(
			self.paths,
			{
				"uid": "1001",
				"decision": "skip",
				"reviewer": "Alice",
				"notes": "first pass",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "1001",
				"decision": "accept",
				"reviewer": "Bob",
				"notes": "confirmed",
				"reference_source": "line.csv",
			},
		)

		alice_index = read_latest_reviews(self.paths, reviewer_id="alice")
		bob_index = read_latest_reviews(self.paths, reviewer_id="bob")
		aggregate = get_uid_review_aggregate(self.paths, "1001")

		self.assertEqual(alice_index["reviews"]["1001"]["decision"], "skip")
		self.assertEqual(bob_index["reviews"]["1001"]["decision"], "accept")
		self.assertEqual(alice_index["reviewer_profile"]["reviewer_name"], "Alice")
		self.assertEqual(bob_index["reviewer_profile"]["reviewer_name"], "Bob")
		self.assertEqual(len(aggregate["latest_reviews"]), 2)
		self.assertEqual(aggregate["decision_counts"]["accept"], 1)
		self.assertEqual(aggregate["decision_counts"]["skip"], 1)

	def test_review_tags_round_trip_through_latest_and_aggregate(self) -> None:
		self._write_uid_assets("1003", line=True, fmm=True)

		review = write_review(
			self.paths,
			{
				"uid": "1003",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
				"trajectory_tags": ["高优", "需复核", "高优"],
			},
		)

		latest = read_latest_reviews(self.paths, reviewer_id="alice")
		aggregate = get_uid_review_aggregate(self.paths, "1003")

		self.assertEqual(review["trajectory_tags"], ["高优", "需复核"])
		self.assertEqual(latest["reviews"]["1003"]["trajectory_tags"], ["高优", "需复核"])
		self.assertEqual(aggregate["latest_reviews"][0]["trajectory_tags"], ["高优", "需复核"])

	def test_timeline_annotations_are_isolated_per_reviewer(self) -> None:
		ensure_reviewer_profile(self.paths, display_name="Alice")
		ensure_reviewer_profile(self.paths, display_name="Bob")

		write_timeline_annotations(
			self.paths,
			{
				"uid": "2001",
				"reviewer": "Alice",
				"pins": [{"id": "p1", "time": 10, "layerKey": "raw", "label": "A"}],
				"segments": [{"id": "s1", "categoryId": "focus", "categoryName": "重点段", "color": "#fff", "startTime": 10, "endTime": 20}],
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "2001",
				"reviewer": "Bob",
				"pins": [{"id": "p2", "time": 30, "layerKey": "raw", "label": "B"}],
				"segments": [{"id": "s2", "categoryId": "review", "categoryName": "待复核", "color": "#000", "startTime": 30, "endTime": 40}],
			},
		)

		alice = read_timeline_annotations(self.paths, "2001", reviewer_id="alice")
		bob = read_timeline_annotations(self.paths, "2001", reviewer_id="bob")
		aggregate = get_uid_review_aggregate(self.paths, "2001")

		self.assertEqual(len(alice["pins"]), 1)
		self.assertEqual(alice["pins"][0]["label"], "A")
		self.assertEqual(len(bob["pins"]), 1)
		self.assertEqual(bob["pins"][0]["label"], "B")
		self.assertEqual(len(aggregate["timeline_annotation_summary"]), 2)
		self.assertEqual(
			{item["reviewer_id"] for item in aggregate["timeline_annotation_summary"]},
			{"alice", "bob"},
		)

	def test_export_accepted_assets_is_scoped_per_reviewer(self) -> None:
		self._write_uid_assets("3001", line=True, fmm=True)
		self._write_uid_assets("3002", line=False, fmm=True)

		write_review(
			self.paths,
			{
				"uid": "3001",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "3002",
				"decision": "accept",
				"reviewer": "Bob",
				"reference_source": "fmm.csv",
			},
		)

		alice_manifest = export_accepted_assets(self.paths, clean=True, reviewer_id="alice")
		bob_manifest = export_accepted_assets(self.paths, clean=True, reviewer_id="bob")

		self.assertEqual(alice_manifest["accepted_count"], 1)
		self.assertEqual(bob_manifest["accepted_count"], 1)
		self.assertTrue(
			(self.paths.export_root / "reviewers" / "alice" / "samples" / "3001" / "line.csv").exists()
		)
		self.assertFalse(
			(self.paths.export_root / "reviewers" / "alice" / "samples" / "3002").exists()
		)
		self.assertTrue(
			(self.paths.export_root / "reviewers" / "bob" / "samples" / "3002" / "fmm.csv").exists()
		)

	def test_write_review_rejects_accept_without_line_or_fmm(self) -> None:
		uid_dir = self.result_root / "4001"
		self._write_csv(uid_dir / "raw.csv", "uid,latitude\n4001,39.7\n")

		with self.assertRaisesRegex(ValueError, "line.csv or fmm.csv"):
			write_review(
				self.paths,
				{
					"uid": "4001",
					"decision": "accept",
					"reviewer": "Alice",
					"notes": "raw only should fail",
				},
			)

	def test_write_review_accepts_manifest_declared_reference_file(self) -> None:
		self._write_manifest(
			{
				"uids": ["4101"],
				"layers": ["gps", "tier4"],
				"layer_specs": {
					"gps": {"filename": "gps.csv", "kind": "gps"},
					"tier4": {"filename": "tier4.csv", "kind": "signal", "review_reference": True},
				},
			}
		)
		uid_dir = self.result_root / "4101"
		self._write_csv(uid_dir / "raw.csv", "uid,latitude\n4101,39.7\n")
		self._write_csv(uid_dir / "tier4.csv", "uid,cid,lat,lon,t_in,t_out\n4101,1,39.7,116.3,1,2\n")

		review = write_review(
			self.paths,
			{
				"uid": "4101",
				"decision": "accept",
				"reviewer": "Alice",
			},
		)
		self.assertEqual(review["reference_source"], "tier4.csv")

		manifest = export_reviewer_bundle(
			self.paths,
			reviewer_id="alice",
			clean=True,
			bundle_name="tier4_bundle",
		)
		self.assertEqual(manifest["sample_count"], 1)
		self.assertTrue(
			(self.paths.review_root / "review_exports" / "reviewers" / "alice" / "tier4_bundle" / "samples" / "4101" / "tier4.csv").exists()
		)

	def test_export_review_aggregate_outputs_conflicts(self) -> None:
		self._write_uid_assets("5001", line=True, fmm=True)
		self._write_uid_assets("5002", line=True, fmm=True)

		write_review(
			self.paths,
			{
				"uid": "5001",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "5001",
				"decision": "reject",
				"reviewer": "Bob",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "5002",
				"decision": "skip",
				"reviewer": "Bob",
			},
		)

		manifest = export_review_aggregate(self.paths, clean=True)
		aggregate_root = self.paths.review_root / "review_exports" / "aggregate"

		self.assertEqual(manifest["uid_count"], 2)
		self.assertEqual(manifest["reviewer_count"], 2)
		self.assertEqual(manifest["conflict_uid_count"], 1)
		conflict_lines = (aggregate_root / "conflicts.jsonl").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(len(conflict_lines), 1)
		conflict_record = json.loads(conflict_lines[0])
		self.assertEqual(conflict_record["uid"], "5001")

	def test_export_reviewer_bundle_includes_annotations_and_sample_files(self) -> None:
		self._write_uid_assets("7001", line=True, fmm=True)
		self._write_uid_assets("7002", line=False, fmm=True)

		write_review(
			self.paths,
			{
				"uid": "7001",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_review(
			self.paths,
			{
				"uid": "7002",
				"decision": "skip",
				"reviewer": "Alice",
				"reference_source": "fmm.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "7001",
				"reviewer": "Alice",
				"pins": [{"id": "p1", "time": 11, "layerKey": "raw", "label": "pin"}],
				"segments": [{"id": "s1", "categoryId": "focus", "categoryName": "重点段", "color": "#fff", "startTime": 11, "endTime": 22}],
			},
		)

		output_root = self.project_root / "bundle_out"
		manifest = export_reviewer_bundle(
			self.paths,
			reviewer_id="alice",
			output_root=output_root,
			bundle_name="alice_bundle",
			clean=True,
			create_zip=True,
		)

		bundle_root = output_root
		self.assertEqual(manifest["sample_count"], 2)
		self.assertTrue((bundle_root / "bundle_manifest.json").exists())
		self.assertTrue((bundle_root / "reviews" / "latest_reviews.json").exists())
		self.assertTrue((bundle_root / "reviews" / "ledger.jsonl").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "raw.csv").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "snap.csv").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "od.csv").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "line.csv").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "review.json").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "timeline_annotations.json").exists())
		self.assertTrue((bundle_root / "samples" / "7001" / "source_manifest.json").exists())
		self.assertTrue((bundle_root / "samples" / "7002" / "fmm.csv").exists())
		self.assertTrue(Path(manifest["zip_path"]).exists())


if __name__ == "__main__":
	unittest.main()
