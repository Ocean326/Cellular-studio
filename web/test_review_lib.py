from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from .review_lib import (
	ensure_reviewer_profile,
	export_accepted_assets,
	export_segment_label_dataset,
	export_reviewer_bundle,
	export_review_aggregate,
	get_uid_review_aggregate,
	read_latest_reviews,
	read_track_edits,
	read_timeline_annotations,
	normalize_track_edits_payload,
	resolve_review_paths,
	write_review,
	write_track_edits,
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

	def test_timeline_annotations_normalize_millisecond_timestamps(self) -> None:
		record = write_timeline_annotations(
			self.paths,
			{
				"uid": "2002",
				"reviewer": "Alice",
				"pins": [{"id": "p1", "time": 1710000030000, "layerKey": "raw", "label": "A"}],
				"segments": [
					{
						"id": "s1",
						"categoryId": "focus",
						"categoryName": "重点段",
						"color": "#fff",
						"startTime": 1710000000000,
						"endTime": 1710000060000,
					}
				],
			},
		)

		loaded = read_timeline_annotations(self.paths, "2002", reviewer_id="alice")

		self.assertEqual(record["pins"][0]["time"], 1710000030)
		self.assertEqual(record["segments"][0]["startTime"], 1710000000)
		self.assertEqual(record["segments"][0]["endTime"], 1710000060)
		self.assertEqual(loaded["pins"][0]["time"], 1710000030)
		self.assertEqual(loaded["segments"][0]["startTime"], 1710000000)
		self.assertEqual(loaded["segments"][0]["endTime"], 1710000060)

	def test_track_edits_are_isolated_per_reviewer(self) -> None:
		ensure_reviewer_profile(self.paths, display_name="Alice")
		ensure_reviewer_profile(self.paths, display_name="Bob")

		write_track_edits(
			self.paths,
			{
				"uid": "2101",
				"reviewer": "Alice",
				"patches": [
					{
						"pointId": "raw:1",
						"layerKey": "raw",
						"rowIndex": 1,
						"timestamp": 1710000001,
						"position": {"latitude": 39.91, "longitude": 116.31},
						"metadata": {"status": "alice"},
					},
				],
			},
		)
		write_track_edits(
			self.paths,
			{
				"uid": "2101",
				"reviewer": "Bob",
				"patches": [
					{
						"pointId": "raw:2",
						"layerKey": "raw",
						"rowIndex": 2,
						"timestamp": 1710000002,
						"position": {"latitude": 39.92, "longitude": 116.32},
						"metadata": {"status": "bob"},
					},
				],
			},
		)

		alice = read_track_edits(self.paths, "2101", reviewer_id="alice")
		bob = read_track_edits(self.paths, "2101", reviewer_id="bob")

		self.assertEqual(alice["reviewer_id"], "alice")
		self.assertEqual(bob["reviewer_id"], "bob")
		self.assertEqual(len(alice["patches"]), 1)
		self.assertEqual(len(bob["patches"]), 1)
		self.assertEqual(alice["patches"][0]["metadata"]["status"], "alice")
		self.assertEqual(bob["patches"][0]["metadata"]["status"], "bob")
		self.assertEqual(alice["patches"][0]["pointId"], "raw:1")
		self.assertEqual(bob["patches"][0]["pointId"], "raw:2")

	def test_reviewer_id_alias_migrates_legacy_underscore_namespace(self) -> None:
		self._write_uid_assets("2401", line=True, fmm=True)
		legacy_root = self.paths.review_root / "reviewers" / "codex_probe"
		(legacy_root / "reviews").mkdir(parents=True, exist_ok=True)
		(legacy_root / "timeline_annotations").mkdir(parents=True, exist_ok=True)
		(legacy_root / "profile.json").write_text(
			json.dumps(
				{
					"schema_version": 2,
					"reviewer_id": "codex_probe",
					"reviewer_name": "Codex Probe",
					"display_name": "Codex Probe",
					"created_at": "2026-04-28T00:00:00Z",
					"last_seen_at": "2026-04-28T00:00:00Z",
					"status": "active",
				}
			)
			+ "\n",
			encoding="utf-8",
		)
		(legacy_root / "reviews" / "ledger.jsonl").write_text(
			json.dumps(
				{
					"schema_version": 2,
					"uid": "2401",
					"sample_id": "2401",
					"decision": "accept",
					"reviewer_id": "codex_probe",
					"reviewer_name": "Codex Probe",
					"reviewer": "Codex Probe",
					"timestamp": "2026-04-28T00:00:00Z",
					"notes": "legacy underscore namespace",
					"reference_source": "line.csv",
					"trajectory_tags": ["home_candidate"],
				}
			)
			+ "\n",
			encoding="utf-8",
		)
		(legacy_root / "timeline_annotations" / "2401.json").write_text(
			json.dumps(
				{
					"schema_version": 2,
					"uid": "2401",
					"sample_id": "2401",
					"reviewer_id": "codex_probe",
					"reviewer_name": "Codex Probe",
					"reviewer": "Codex Probe",
					"updated_at": "2026-04-28T00:00:00Z",
					"segmentPolicy": {"exclusiveMode": False, "intervalSemantics": "closed_interval"},
					"pins": [],
					"segments": [
						{
							"id": "seg1",
							"categoryId": "stay",
							"categoryName": "驻留",
							"startTime": 1,
							"endTime": 2,
						}
					],
				}
			)
			+ "\n",
			encoding="utf-8",
		)

		profile = ensure_reviewer_profile(self.paths, display_name="Codex Probe")
		latest = read_latest_reviews(self.paths, reviewer_id="codex_probe")
		annotations = read_timeline_annotations(self.paths, "2401", reviewer_id="codex_probe")

		self.assertEqual(profile["reviewer_id"], "codex-probe")
		self.assertFalse(legacy_root.exists())
		self.assertTrue((self.paths.review_root / "reviewers" / "codex-probe" / "reviews" / "ledger.jsonl").exists())
		self.assertEqual(latest["reviewer_profile"]["reviewer_id"], "codex-probe")
		self.assertEqual(latest["reviews"]["2401"]["decision"], "accept")
		self.assertEqual(annotations["reviewer_id"], "codex-probe")
		self.assertEqual(len(annotations["segments"]), 1)

	def test_track_edits_patch_round_trip_and_normalize(self) -> None:
		normalized = normalize_track_edits_payload(
			self.paths,
			{
				"uid": "2102",
				"reviewer": "Alice",
				"patches": [
					{
						"pointId": "raw:7",
						"layerKey": "line",
						"rowIndex": "7",
						"timestamp": "1710000123.5",
						"position": {"latitude": "39.95", "longitude": "116.35"},
						"metadata": {"reason": "drag"},
					},
					{
						"pointId": "invalid",
						"layerKey": "line",
						"rowIndex": 9,
						"position": {"latitude": 39.96, "longitude": 116.36},
					},
				],
			},
		)

		self.assertEqual(normalized["schema_version"], 1)
		self.assertEqual(normalized["reviewer_id"], "alice")
		self.assertEqual(len(normalized["patches"]), 1)
		self.assertEqual(normalized["patches"][0]["rowIndex"], 7)
		self.assertEqual(normalized["patches"][0]["timestamp"], 1710000123.5)
		self.assertEqual(normalized["patches"][0]["position"]["latitude"], 39.95)
		self.assertEqual(normalized["patches"][0]["metadata"]["reason"], "drag")

		record = write_track_edits(self.paths, normalized)
		loaded = read_track_edits(self.paths, "2102", reviewer_id="alice")

		self.assertEqual(record, loaded)
		self.assertEqual(loaded["patches"][0]["pointId"], "raw:7")
		self.assertEqual(loaded["patches"][0]["layerKey"], "line")

	def test_track_edits_metadata_only_patch_round_trip(self) -> None:
		normalized = normalize_track_edits_payload(
			self.paths,
			{
				"uid": "2103",
				"reviewer": "Alice",
				"patches": [
					{
						"pointId": "line:2103:1710000200000:3",
						"layerKey": "line",
						"rowIndex": 3,
						"timestamp": 1710000200,
						"metadata": {"match_type": "railway"},
					},
				],
			},
		)

		self.assertEqual(len(normalized["patches"]), 1)
		self.assertEqual(normalized["patches"][0]["metadata"]["match_type"], "railway")
		self.assertNotIn("position", normalized["patches"][0])

		record = write_track_edits(self.paths, normalized)
		loaded = read_track_edits(self.paths, "2103", reviewer_id="alice")

		self.assertEqual(record, loaded)
		self.assertEqual(loaded["patches"][0]["metadata"]["match_type"], "railway")
		self.assertNotIn("position", loaded["patches"][0])

	def test_window_quick_segment_metadata_round_trips_and_is_summarized(self) -> None:
		ensure_reviewer_profile(self.paths, display_name="Alice")

		write_timeline_annotations(
			self.paths,
			{
				"uid": "2002",
				"reviewer": "Alice",
				"segments": [
					{
						"id": "window:2026-04-10:2026-04-12",
						"categoryId": "focus",
						"categoryName": "重点段",
						"color": "#60a5fa",
						"startTime": 100,
						"endTime": 200,
						"entryMode": "window_quick",
						"segmentScope": "date_window",
						"windowStartDay": "2026-04-10",
						"windowEndDay": "2026-04-12",
						"fixedSpanDays": 2,
						"sourceLayerKey": "line",
					},
				],
			},
		)

		annotations = read_timeline_annotations(self.paths, "2002", reviewer_id="alice")
		aggregate = get_uid_review_aggregate(self.paths, "2002")
		segment = annotations["segments"][0]

		self.assertEqual(segment["entryMode"], "window_quick")
		self.assertEqual(segment["segmentScope"], "date_window")
		self.assertEqual(segment["windowStartDay"], "2026-04-10")
		self.assertEqual(segment["windowEndDay"], "2026-04-12")
		self.assertEqual(segment["fixedSpanDays"], 2)
		self.assertEqual(segment["sourceLayerKey"], "line")
		self.assertEqual(aggregate["timeline_annotation_summary"][0]["window_quick_segment_count"], 1)

	def test_timeline_segment_vnext_fields_roundtrip_write_read_export(self) -> None:
		ensure_reviewer_profile(self.paths, display_name="Alice")
		self._write_uid_assets("2005", line=True, fmm=True)
		write_review(
			self.paths,
			{
				"uid": "2005",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		expected_evidence = {
			"source": "map_match",
			"score": 0.9,
			"nested": {"flag": True},
			"mixed": ["a", 2],
		}
		segment = {
			"id": "s-vnext",
			"categoryId": "road_car",
			"categoryName": "驾车",
			"color": "#222",
			"startTime": 100,
			"endTime": 200,
			"entryMode": "window_quick",
			"segmentScope": "date_window",
			"chainType": "trip",
			"chainTypeName": "行程链",
			"travelMode": "car",
			"semanticTags": ["alpha", "beta", "alpha"],
			"reconstructionQuality": "high",
			"accuracyLabel": "likely",
			"errorTypes": ["gap", "noise"],
			"confidence": 0.85,
			"evidence": expected_evidence,
			"visualEvidenceRefs": ["cap-1", "cap-2"],
			"trackEditRefs": ["te-1"],
			"needsHumanReview": True,
			"notes": "复核点",
			"unknownPassthrough": "must_drop",
			"noiseConfidence": "nan",
		}

		write_timeline_annotations(
			self.paths,
			{"uid": "2005", "reviewer": "Alice", "segments": [segment]},
		)

		loaded = read_timeline_annotations(self.paths, "2005", reviewer_id="alice")
		seg = loaded["segments"][0]

		self.assertEqual(seg["semanticTags"], ["alpha", "beta"])
		self.assertEqual(seg["evidence"], expected_evidence)
		self.assertEqual(seg["confidence"], 0.85)
		self.assertTrue(seg["needsHumanReview"])
		self.assertEqual(seg["travelMode"], "car")
		self.assertEqual(seg["chainType"], "trip")
		self.assertEqual(seg["chainTypeName"], "行程链")
		self.assertEqual(seg["reconstructionQuality"], "high")
		self.assertEqual(seg["accuracyLabel"], "likely")
		self.assertEqual(seg["errorTypes"], ["gap", "noise"])
		self.assertEqual(seg["visualEvidenceRefs"], ["cap-1", "cap-2"])
		self.assertEqual(seg["trackEditRefs"], ["te-1"])
		self.assertEqual(seg["notes"], "复核点")
		self.assertEqual(seg["entryMode"], "window_quick")
		self.assertEqual(seg["segmentScope"], "date_window")
		self.assertNotIn("unknownPassthrough", seg)
		self.assertNotIn("noiseConfidence", seg)

		output_root = self.project_root / "bundle_vnext"
		export_reviewer_bundle(
			self.paths,
			reviewer_id="alice",
			output_root=output_root,
			bundle_name="vnext_bundle",
			clean=True,
			create_zip=False,
		)
		exported = json.loads(
			(output_root / "samples" / "2005" / "timeline_annotations.json").read_text(encoding="utf-8")
		)
		exp_seg = exported["segments"][0]
		self.assertEqual(exp_seg["semanticTags"], ["alpha", "beta"])
		self.assertEqual(exp_seg["evidence"], expected_evidence)
		self.assertEqual(exp_seg["confidence"], 0.85)
		self.assertNotIn("unknownPassthrough", exp_seg)

	def test_timeline_segment_semantic_tags_infer_replay_category_fields(self) -> None:
		ensure_reviewer_profile(self.paths, display_name="Alice")

		write_timeline_annotations(
			self.paths,
			{
				"uid": "2006",
				"reviewer": "Alice",
				"segments": [
					{
						"id": "replay-infer",
						"startTime": 100,
						"endTime": 200,
						"semanticTags": ["workflow:segment", "matcher:road", "chain:trip"],
					},
					{
						"id": "replay-explicit",
						"categoryId": "manual-focus",
						"categoryName": "重点人工段",
						"color": "#123456",
						"startTime": 220,
						"endTime": 320,
						"semanticTags": ["matcher:stay"],
					},
				],
			},
		)

		loaded = read_timeline_annotations(self.paths, "2006", reviewer_id="alice")
		inferred = loaded["segments"][0]
		explicit = loaded["segments"][1]

		self.assertEqual(inferred["semanticTags"], ["workflow:segment", "matcher:road", "chain:trip"])
		self.assertEqual(inferred["categoryId"], "road")
		self.assertEqual(inferred["categoryName"], "road")
		self.assertEqual(inferred["color"], "#4caf50")
		self.assertEqual(explicit["categoryId"], "manual-focus")
		self.assertEqual(explicit["categoryName"], "重点人工段")
		self.assertEqual(explicit["color"], "#123456")

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

	def test_export_segment_label_dataset_uses_reviewer_segments_and_min_interval(self) -> None:
		uid_dir = self.result_root / "5201"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5201,cell_a,116.30,39.90,1710000000,1710000030",
					"5201,cell_b,116.32,39.91,1710000030,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5201,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5201,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
					"5201,cell_b,39.92,116.32,road_car,1,0,1710000060,1710000120",
					"5201,cell_b,39.93,116.33,road_car,1,1,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5201",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5201",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "s1", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
					{"id": "s2", "categoryId": "road_car", "categoryName": "驾车", "startTime": 1710000060, "endTime": 1710000120},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_bundle",
			clean=True,
			create_zip=True,
			interval_seconds=1,
		)

		self.assertEqual(manifest["interval_seconds"], 5)
		self.assertEqual(manifest["interval_semantics"], "left_open_right_closed")
		self.assertEqual(manifest["samples"][0]["annotation_source"], "reviewer")
		dataset_root = Path(manifest["dataset_root"])
		self.assertTrue((dataset_root / "5201_signal.csv").exists())
		self.assertTrue((dataset_root / "5201_gps.csv").exists())
		signal_rows = (dataset_root / "5201_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		gps_rows = (dataset_root / "5201_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertIn("uid,cid,longitude,latitude,t_in,t_out,status", signal_rows[0])
		self.assertIn("5201,cell_a,116.3,39.9,1710000000000,1710000030000,stay", signal_rows[1])
		self.assertIn("5201,cell_b,116.32,39.91,1710000030000,1710000060000,stay", signal_rows[2])
		self.assertIn("uid,longitude,latitude,timestamp,status", gps_rows[0])
		self.assertGreaterEqual(len(gps_rows), 4)
		self.assertTrue(any(row.endswith(",stay") for row in gps_rows[1:]))
		self.assertTrue(any(row.endswith(",road_car") for row in gps_rows[1:]))
		self.assertTrue(any(row.startswith("5201,116.32,39.91,1710000060000,stay") for row in gps_rows[1:]))
		with zipfile.ZipFile(manifest["zip_path"]) as archive:
			names = set(archive.namelist())
		self.assertIn("dataset_bundle_dataset/5201_signal.csv", names)
		self.assertIn("dataset_bundle_dataset/5201_gps.csv", names)

	def test_export_segment_label_dataset_applies_signal_track_edit_positions(self) -> None:
		self._write_manifest(
			{
				"review_reference_files": ["signal.csv"],
				"layers": [{"filename": "signal.csv"}],
			}
		)
		uid_dir = self.result_root / "5210"
		self._write_csv(
			uid_dir / "signal.csv",
			"\n".join(
				[
					"uid,cid,longitude,latitude,t_in,t_out,status",
					"5210,cell_a,116.30,39.90,1710000000,1710000060,road",
					"5210,cell_b,116.32,39.91,1710000060,1710000120,stay",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5210",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "signal.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5210",
				"reviewer": "Alice",
				"segments": [
					{"id": "road", "categoryId": "road", "categoryName": "乘车", "startTime": 1710000000, "endTime": 1710000060},
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000060, "endTime": 1710000120},
				],
			},
		)
		write_track_edits(
			self.paths,
			{
				"uid": "5210",
				"reviewer": "Alice",
				"patches": [
					{
						"pointId": "signal:5210:1710000030000:0",
						"layerKey": "signal",
						"rowIndex": 0,
						"timestamp": 1710000030,
						"position": {"latitude": 40.12, "longitude": 120.34},
						"metadata": {},
					},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_signal_track_edits",
			clean=True,
			create_zip=False,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5210_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "5210,cell_a,120.34,40.12,1710000000000,1710000060000,road")
		self.assertEqual(signal_rows[2], "5210,cell_b,116.32,39.91,1710000060000,1710000120000,stay")

	def test_export_segment_label_dataset_prefers_fmm_geometry_for_non_stay_gps_rows(self) -> None:
		uid_dir = self.result_root / "5211"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5211,cell_a,9.00,9.00,1710000000,1710000030",
					"5211,cell_b,9.50,9.50,1710000030,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "fmm.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,t_in,is_stationary,match_type,segment_idx,od_segment_idx,point_order,segment_start_time,segment_end_time",
					"5211,-1,40.00,120.00,1710000000,false,road,0,0,0,1710000000,1710000060",
					"5211,-1,40.00,120.03,1710000030,false,road,0,0,1,1710000000,1710000060",
					"5211,-1,40.00,120.06,1710000060,false,road,0,0,2,1710000000,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5211,cell_a,10.00,10.00,road,0,0,1710000000,1710000060",
					"5211,cell_b,10.00,10.06,road,0,1,1710000000,1710000060",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5211",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "fmm.csv",
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_fmm_geometry_priority",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)

		gps_rows = (Path(manifest["dataset_root"]) / "5211_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertTrue(any(row.startswith("5211,120.03,40.0,1710000030000,road") for row in gps_rows[1:]))
		self.assertFalse(any(row.startswith("5211,10.") for row in gps_rows[1:]))

	def test_export_segment_label_dataset_prefers_snap_geometry_for_labeled_stay_gps_rows(self) -> None:
		uid_dir = self.result_root / "5212"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5212,cell_a,9.00,9.00,1710000020,1710000040",
					"5212,cell_b,9.10,9.10,1710000040,1710000080",
					"5212,cell_c,8.00,8.00,1710000080,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "snap.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5212,cell_a,1.00,1.00,1710000020,1710000040",
					"5212,cell_b,1.10,1.10,1710000040,1710000080",
					"5212,cell_c,4.00,4.00,1710000080,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "fmm.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,t_in,is_stationary,match_type,segment_idx,od_segment_idx,point_order,segment_start_time,segment_end_time",
					"5212,-1,1.00,1.00,1710000020,false,road,0,0,0,1710000020,1710000120",
					"5212,-1,3.00,3.00,1710000080,false,road,0,0,1,1710000020,1710000120",
					"5212,-1,5.00,5.00,1710000120,false,road,0,0,2,1710000020,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5212,cell_a,10.00,10.00,road,0,0,1710000020,1710000120",
					"5212,cell_b,10.00,10.10,road,0,1,1710000020,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5212",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "fmm.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5212",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000020, "endTime": 1710000080},
					{"id": "road", "categoryId": "road", "categoryName": "乘车", "startTime": 1710000080, "endTime": 1710000120},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_stay_snap_priority",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)

		gps_rows = (Path(manifest["dataset_root"]) / "5212_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		stay_rows = [row for row in gps_rows[1:] if row.endswith(",stay")]
		road_rows = [row for row in gps_rows[1:] if row.endswith(",road")]
		self.assertTrue(stay_rows)
		self.assertTrue(road_rows)
		self.assertTrue(all(",1." in row for row in stay_rows))
		self.assertTrue(any(",3." in row or ",5." in row for row in road_rows))
		self.assertFalse(any(",9." in row or ",10." in row for row in stay_rows))

	def test_export_segment_label_dataset_keeps_snap_geometry_until_stay_boundary_even_if_fmm_switches_early(self) -> None:
		uid_dir = self.result_root / "5213"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5213,cell_a,1.00,1.00,1710000020,1710000060",
					"5213,cell_b,1.10,1.10,1710000060,1710000090",
					"5213,cell_c,2.00,2.00,1710000090,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "snap.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5213,cell_a,1.00,1.00,1710000020,1710000060",
					"5213,cell_b,1.10,1.10,1710000060,1710000090",
					"5213,cell_c,2.00,2.00,1710000090,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "fmm.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,t_in,is_stationary,match_type,segment_idx,od_segment_idx,point_order,segment_start_time,segment_end_time",
					"5213,-1,30.00,130.00,1710000020,false,railway,0,0,0,1710000020,1710000060",
					"5213,-1,30.00,130.06,1710000060,false,railway,0,0,1,1710000020,1710000060",
					"5213,-1,40.00,140.00,1710000060,false,road,1,1,0,1710000060,1710000120",
					"5213,-1,40.00,140.12,1710000120,false,road,1,1,1,1710000060,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5213,cell_a,10.00,10.00,road,0,0,1710000020,1710000120",
					"5213,cell_b,10.10,10.10,road,0,1,1710000020,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5213",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "fmm.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5213",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000020, "endTime": 1710000090},
					{"id": "road", "categoryId": "road", "categoryName": "乘车", "startTime": 1710000090, "endTime": 1710000120},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_stay_boundary_priority",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)

		with open(Path(manifest["dataset_root"]) / "5213_gps.csv", encoding="utf-8") as handle:
			rows = list(csv.DictReader(handle))
		stay_rows_after_fmm_switch = [
			row
			for row in rows
			if row["status"] == "stay" and int(row["timestamp"]) >= 1710000060000
		]
		road_rows_after_annotation_boundary = [
			row
			for row in rows
			if row["status"] == "road" and int(row["timestamp"]) >= 1710000090000
		]

		self.assertTrue(stay_rows_after_fmm_switch)
		self.assertTrue(road_rows_after_annotation_boundary)
		self.assertTrue(
			all(float(row["longitude"]) < 10 for row in stay_rows_after_fmm_switch)
		)
		self.assertTrue(
			all(float(row["longitude"]) >= 140 for row in road_rows_after_annotation_boundary)
		)

	def test_export_segment_label_dataset_falls_back_to_legacy_timeline_annotations(self) -> None:
		uid_dir = self.result_root / "5202"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5202,cell_a,116.40,39.90,1710000000,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5202,cell_a,39.90,116.40,road_bus,0,0,1710000000,1710000060",
					"5202,cell_a,39.91,116.41,road_bus,0,1,1710000000,1710000060",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5202",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		legacy_path = self.paths.review_root / "timeline_annotations" / "5202.json"
		legacy_path.parent.mkdir(parents=True, exist_ok=True)
		legacy_path.write_text(
			json.dumps(
				{
					"uid": "5202",
					"segments": [
						{"id": "legacy-1", "categoryId": "road_bus", "categoryName": "公交", "startTime": 1710000000, "endTime": 1710000060}
					],
				},
				ensure_ascii=False,
			),
			encoding="utf-8",
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_bundle_legacy",
			clean=True,
			create_zip=False,
		)

		self.assertTrue(manifest["uses_legacy_fallback"])
		self.assertEqual(manifest["samples"][0]["annotation_source"], "legacy")
		signal_rows = (Path(manifest["dataset_root"]) / "5202_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertTrue(signal_rows[1].endswith(",road_bus"))

	def test_write_timeline_annotations_canonicalizes_exclusive_segments(self) -> None:
		record = write_timeline_annotations(
			self.paths,
			{
				"uid": "5301",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "s1", "categoryId": "stay", "categoryName": "驻留", "startTime": 10, "endTime": 20},
					{"id": "s2", "categoryId": "road_car", "categoryName": "驾车", "startTime": 15, "endTime": 30},
				],
			},
		)

		self.assertEqual(record["segmentPolicy"]["exclusiveMode"], True)
		self.assertEqual(record["segments"][0]["startTime"], 10)
		self.assertEqual(record["segments"][0]["endTime"], 20)
		self.assertEqual(record["segments"][1]["startTime"], 20)
		self.assertEqual(record["segments"][1]["endTime"], 30)

	def test_export_segment_label_dataset_splits_signal_rows_across_segment_boundaries(self) -> None:
		uid_dir = self.result_root / "5302"
		self._write_csv(
			uid_dir / "signal.csv",
			"\n".join(
				[
					"uid,cid,longitude,latitude,t_in,t_out,status",
					"5302,cell_a,116.30,39.90,1710000000,1710000120,stay",
				]
			),
		)
		self._write_csv(
			uid_dir / "gps.csv",
			"\n".join(
				[
					"uid,longitude,latitude,timestamp,status",
					"5302,116.30,39.90,1710000000,stay",
					"5302,116.31,39.91,1710000120,road_car",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"uid,cid,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5302,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5302,cell_a,39.91,116.31,road_car,1,0,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5302",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5302",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
					{"id": "road", "categoryId": "road_car", "categoryName": "驾车", "startTime": 1710000060, "endTime": 1710000120},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_bundle_split_signal",
			clean=True,
			create_zip=False,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5302_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "5302,cell_a,116.3,39.9,1710000000000,1710000060000,stay")
		self.assertEqual(signal_rows[2], "5302,cell_a,116.3,39.9,1710000060000,1710000120000,road_car")

	def test_export_segment_label_dataset_prefers_last_annotated_overlapping_segment(self) -> None:
		uid_dir = self.result_root / "5203"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5203,cell_a,116.30,39.90,1710000000,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5203,cell_a,39.90,116.30,stay,0,0,1710000000,1710000120",
					"5203,cell_a,39.91,116.31,stay,0,1,1710000000,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5203",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5203",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": False,
					"intervalSemantics": "closed_interval",
				},
				"segments": [
					{"id": "s1", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000080},
					{"id": "s2", "categoryId": "road_car", "categoryName": "驾车", "startTime": 1710000050, "endTime": 1710000120},
				],
			},
		)
		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_overlap",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)
		gps_rows = (Path(manifest["dataset_root"]) / "5203_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertTrue(
			any(
				"1710000060000" in row and row.endswith(",road_car")
				for row in gps_rows[1:]
			)
		)
		signal_rows = (Path(manifest["dataset_root"]) / "5203_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1].split(",")[-1], "stay")
		self.assertEqual(signal_rows[2].split(",")[-1], "road_car")
		self.assertIn("1710000050000,1710000120000", signal_rows[2])

	def test_export_segment_label_dataset_writes_seconds_when_requested(self) -> None:
		uid_dir = self.result_root / "5204"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5204,cell_a,116.30,39.90,1710000000,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5204,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5204,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5204",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5204",
				"reviewer": "Alice",
				"segments": [
					{"id": "s1", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)
		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_seconds",
			clean=True,
			create_zip=False,
			timestamp_unit="seconds",
		)
		self.assertEqual(manifest["timestamp_unit"], "seconds")
		gps_rows = (Path(manifest["dataset_root"]) / "5204_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertIn("1710000000", gps_rows[1])
		self.assertNotIn("1710000000000", "\n".join(gps_rows))
		signal_rows = (Path(manifest["dataset_root"]) / "5204_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertIn("1710000000,1710000060,stay", signal_rows[1])

	def test_export_segment_label_dataset_maps_internal_railway_label_to_train(self) -> None:
		uid_dir = self.result_root / "5206"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5206,cell_a,116.30,39.90,1710000000,1710000030",
					"5206,cell_b,116.32,39.91,1710000030,1710000060",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5206,cell_a,39.90,116.30,road,0,0,1710000000,1710000060",
					"5206,cell_a,39.91,116.31,road,0,1,1710000000,1710000060",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5206",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5206",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "closed_interval",
				},
				"segments": [
					{
						"id": "annotation-category-1:1710000000:1710000030",
						"categoryId": "annotation-category-1",
						"categoryName": "railway",
						"startTime": 1710000000,
						"endTime": 1710000030,
					},
					{
						"id": "annotation-category-2:1710000030:1710000060",
						"categoryId": "annotation-category-2",
						"categoryName": "stay",
						"startTime": 1710000030,
						"endTime": 1710000060,
					},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_railway_alias",
			clean=True,
			create_zip=False,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5206_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		gps_rows = (Path(manifest["dataset_root"]) / "5206_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "5206,cell_a,116.3,39.9,1710000000000,1710000030000,train")
		self.assertEqual(signal_rows[2], "5206,cell_b,116.32,39.91,1710000030000,1710000060000,stay")
		self.assertTrue(any(row.endswith(",train") for row in gps_rows[1:]))
		self.assertTrue(any(row.endswith(",stay") for row in gps_rows[1:]))

	def test_export_segment_label_dataset_uses_line_status_as_signal_fallback_for_unlabeled_gap(self) -> None:
		uid_dir = self.result_root / "5207"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5207,cell_a,116.30,39.90,1710000000,1710000060",
					"5207,cell_b,116.32,39.91,1710000060,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5207,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5207,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
					"5207,cell_b,39.92,116.32,road,1,0,1710000060,1710000120",
					"5207,cell_b,39.93,116.33,road,1,1,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5207",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5207",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "closed_interval",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_signal_fallback",
			clean=True,
			create_zip=False,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5207_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "5207,cell_a,116.3,39.9,1710000000000,1710000060000,stay")
		self.assertEqual(signal_rows[2], "5207,cell_b,116.32,39.91,1710000060000,1710000120000,road")
		self.assertFalse(any(row.endswith(",") for row in signal_rows[1:]))

	def test_export_segment_label_dataset_labeled_span_only_relabels_clipped_boundary_signal_rows(self) -> None:
		uid_dir = self.result_root / "5208"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5208,cell_a,116.30,39.90,1710000000,1710000060",
					"5208,cell_b,116.32,39.91,1710000060,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5208,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5208,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
					"5208,cell_b,39.92,116.32,road,1,0,1710000060,1710000120",
					"5208,cell_b,39.93,116.33,road,1,1,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5208",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5208",
				"reviewer": "Alice",
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "closed_interval",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_signal_span_boundary",
			clean=True,
			create_zip=False,
			labeled_span_only=True,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5208_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "5208,cell_a,116.3,39.9,1710000000000,1710000060000,stay")
		self.assertEqual(signal_rows[2], "5208,cell_b,116.32,39.91,1710000060000,1710000060000,stay")
		self.assertFalse(any(row.endswith(",road") for row in signal_rows[1:]))

	def test_export_segment_label_dataset_drops_signal_rows_with_unsupported_fallback_status(self) -> None:
		uid_dir = self.result_root / "5209"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5209,cell_a,116.30,39.90,1710000000,1710000060",
					"5209,cell_b,116.32,39.91,1710000060,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5209,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5209,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
					"5209,cell_b,39.92,116.32,unmatched,1,0,1710000060,1710000120",
					"5209,cell_b,39.93,116.33,unmatched,1,1,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5209",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5209",
				"reviewer": "Alice",
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_drop_unsupported_signal",
			clean=True,
			create_zip=False,
		)

		signal_rows = (Path(manifest["dataset_root"]) / "5209_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(len(signal_rows), 2)
		self.assertEqual(signal_rows[1], "5209,cell_a,116.3,39.9,1710000000000,1710000060000,stay")
		self.assertFalse(any(row.endswith(",") for row in signal_rows[1:]))

	def test_export_segment_label_dataset_drops_gps_points_with_unsupported_fallback_status(self) -> None:
		uid_dir = self.result_root / "5210"
		self._write_csv(
			uid_dir / "raw.csv",
			"UID,CID,longitude,latitude,t_in,t_out\n5210,cell_a,116.30,39.90,1710000000,1710000060\n",
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5210,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"5210,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
					"5210,cell_b,39.92,116.32,unmatched,1,0,1710000060,1710000120",
					"5210,cell_b,39.93,116.33,unmatched,1,1,1710000060,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5210",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5210",
				"reviewer": "Alice",
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)

		manifest = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_drop_unsupported_gps",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)

		gps_rows = (Path(manifest["dataset_root"]) / "5210_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertTrue(all(row.endswith(",stay") for row in gps_rows[1:]))
		self.assertFalse(any(",unmatched" in row for row in gps_rows[1:]))
		self.assertFalse(any("1710000120000" in row for row in gps_rows[1:]))

	def test_export_segment_label_dataset_labeled_span_only_trims_rows(self) -> None:
		uid_dir = self.result_root / "5205"
		self._write_csv(
			uid_dir / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"5205,cell_a,116.30,39.90,1710000000,1710000120",
				]
			),
		)
		self._write_csv(
			uid_dir / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"5205,cell_a,39.90,116.30,stay,0,0,1710000000,1710000120",
					"5205,cell_a,39.91,116.31,stay,0,1,1710000000,1710000120",
				]
			),
		)
		write_review(
			self.paths,
			{
				"uid": "5205",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
			},
		)
		write_timeline_annotations(
			self.paths,
			{
				"uid": "5205",
				"reviewer": "Alice",
				"segmentPolicy": {"exclusiveMode": True, "intervalSemantics": "closed_interval"},
				"segments": [
					{"id": "a", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000020, "endTime": 1710000040},
					{"id": "b", "categoryId": "road_car", "categoryName": "驾车", "startTime": 1710000060, "endTime": 1710000080},
				],
			},
		)
		full = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_full_span",
			clean=True,
			create_zip=False,
			interval_seconds=5,
		)
		trimmed = export_segment_label_dataset(
			self.paths,
			reviewer_id="alice",
			bundle_name="dataset_trim_span",
			clean=True,
			create_zip=False,
			interval_seconds=5,
			labeled_span_only=True,
		)
		self.assertTrue(trimmed["labeled_span_only"])
		full_gps = (Path(full["dataset_root"]) / "5205_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		trim_gps = (Path(trimmed["dataset_root"]) / "5205_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertGreater(len(full_gps), len(trim_gps))
		self.assertFalse(any("1710000000000" in row for row in trim_gps[1:]))
		self.assertTrue(any("1710000020000" in row for row in trim_gps[1:]))
		self.assertFalse(any("1710000100000" in row for row in trim_gps[1:]))

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

	def test_export_reviewer_bundle_supports_uid_and_tag_filters(self) -> None:
		self._write_uid_assets("7101", line=True, fmm=True)
		self._write_uid_assets("7102", line=True, fmm=True)

		write_review(
			self.paths,
			{
				"uid": "7101",
				"decision": "accept",
				"reviewer": "Alice",
				"reference_source": "line.csv",
				"trajectory_tags": ["subway", "focus"],
			},
		)
		write_review(
			self.paths,
			{
				"uid": "7102",
				"decision": "reject",
				"reviewer": "Alice",
				"reference_source": "line.csv",
				"trajectory_tags": ["road_taxi"],
			},
		)

		manifest = export_reviewer_bundle(
			self.paths,
			reviewer_id="alice",
			clean=True,
			bundle_name="filtered_bundle",
			uids=["7101", "9999"],
			trajectory_tags=["subway"],
			decisions=["accept", "reject"],
		)

		self.assertEqual(manifest["sample_count"], 1)
		self.assertEqual(manifest["uid_filter"], ["7101", "9999"])
		self.assertEqual(manifest["trajectory_tag_filter"], ["subway"])
		self.assertEqual(manifest["samples"][0]["uid"], "7101")


if __name__ == "__main__":
	unittest.main()
