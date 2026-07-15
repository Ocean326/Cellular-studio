from __future__ import annotations

import csv
import io
import json
import tempfile
import threading
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import review_server as review_server_module
from .review_lib import resolve_review_paths
from .review_server import ReviewRequestHandler


class ReviewServerApiTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.project_root = Path(self.temp_dir.name)
		self.result_root = self.project_root / "data" / "result"
		self.incoming_root = self.project_root / "incoming"
		self.batches_root = self.project_root / "published"
		self.result_root.mkdir(parents=True, exist_ok=True)
		self._write_csv(self.result_root / "6001" / "raw.csv", "uid,latitude\n6001,39.9\n")
		self._write_csv(self.result_root / "6001" / "line.csv", "latitude,longitude\n39.9,116.3\n")
		self.paths = resolve_review_paths(project_root=self.project_root)
		handler = lambda *args, **kwargs: ReviewRequestHandler(
			*args,
			directory=str(self.paths.project_root),
			review_paths=self.paths,
			batches_root=self.batches_root,
			batches={},
			batch_order=[],
			default_batch="current",
			incoming_root=self.incoming_root,
			upload_max_bytes=1024,
			signal6_pipeline_mode="legacy",
			**kwargs,
		)
		self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
		self.port = self.httpd.server_address[1]
		self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
		self.thread.start()

	def tearDown(self) -> None:
		self.httpd.shutdown()
		self.httpd.server_close()
		self.thread.join(timeout=2)
		self.temp_dir.cleanup()

	def _write_csv(self, path: Path, content: str) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(content, encoding="utf-8")

	def _write_manifest(self, payload: dict) -> None:
		(self.result_root / "manifest.json").write_text(
			json.dumps(payload, ensure_ascii=False) + "\n",
			encoding="utf-8",
		)

	def _create_published_batch(self, batch_name: str, metadata: dict | None = None) -> Path:
		batch_root = self.batches_root / batch_name
		(batch_root / "review" / "reviewers").mkdir(parents=True, exist_ok=True)
		(batch_root / "review" / "aggregate").mkdir(parents=True, exist_ok=True)
		(batch_root / "review" / "system").mkdir(parents=True, exist_ok=True)
		(batch_root / "accepted_assets" / "reviewers").mkdir(parents=True, exist_ok=True)
		(batch_root / "review_exports" / "aggregate").mkdir(parents=True, exist_ok=True)
		batch_meta = {
			"name": batch_name,
			"label": batch_name,
			"source_result_root": str(self.result_root),
		}
		if metadata:
			batch_meta.update(metadata)
		(batch_root / "batch_meta.json").write_text(
			json.dumps(batch_meta) + "\n",
			encoding="utf-8",
		)
		return batch_root

	def _request(
		self,
		method: str,
		path: str,
		payload: dict | bytes | None = None,
		headers: dict | None = None,
		expect_status: int = 200,
	) -> dict:
		data = None
		request_headers = dict(headers or {})
		if isinstance(payload, dict):
			data = json.dumps(payload).encode("utf-8")
			request_headers["Content-Type"] = "application/json"
		elif isinstance(payload, bytes):
			data = payload
		request = Request(
			f"http://127.0.0.1:{self.port}{path}",
			data=data,
			headers=request_headers,
			method=method,
		)
		try:
			with urlopen(request, timeout=5) as response:
				self.assertEqual(response.status, expect_status)
				return json.loads(response.read().decode("utf-8"))
		except HTTPError as exc:
			body = json.loads(exc.read().decode("utf-8"))
			exc.close()
			if exc.code != expect_status:
				raise
			return body

	def _fetch_raw(self, method: str, path: str, headers: dict | None = None) -> tuple[int, str]:
		request = Request(
			f"http://127.0.0.1:{self.port}{path}",
			headers=dict(headers or {}),
			method=method,
		)
		try:
			with urlopen(request, timeout=5) as response:
				return response.status, response.read().decode("utf-8", errors="ignore")
		except HTTPError as exc:
			body = exc.read().decode("utf-8", errors="ignore")
			exc.close()
			return exc.code, body

	def test_offline_tile_endpoint_returns_png_payload(self) -> None:
		class FakeOfflineTileService:
			def __init__(self, *args, **kwargs) -> None:
				pass

			def render_png(self, z: int, x: int, y: int) -> bytes:
				return f"png:{z}/{x}/{y}".encode("utf-8")

		original = review_server_module.OfflineTileService
		review_server_module.OfflineTileService = FakeOfflineTileService
		try:
			status, body = self._fetch_raw("GET", "/offline_tiles/beijing/11/1684/776.png")
		finally:
			review_server_module.OfflineTileService = original

		self.assertEqual(status, 200)
		self.assertEqual(body, "png:11/1684/776")

	def test_session_review_aggregate_and_export_flow(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]
		bob = self._request("POST", "/api/reviewers/session", {"display_name": "Bob"})["reviewer"]

		self.assertEqual(alice["reviewer_id"], "alice")
		self.assertEqual(bob["reviewer_id"], "bob")

		self._request(
			"POST",
			"/api/reviews",
			{
				"uid": "6001",
				"decision": "accept",
				"reviewer_id": "alice",
				"reviewer_name": "Alice",
				"reference_source": "line.csv",
			},
		)
		self._request(
			"POST",
			"/api/reviews",
			{
				"uid": "6001",
				"decision": "reject",
				"reviewer_id": "bob",
				"reviewer_name": "Bob",
			},
		)
		self._request(
			"POST",
			"/api/timeline-annotations",
			{
				"uid": "6001",
				"reviewer_id": "alice",
				"reviewer_name": "Alice",
				"pins": [{"id": "p1", "time": 10, "layerKey": "raw", "label": "pin"}],
				"segments": [{"id": "s1", "categoryId": "focus", "categoryName": "重点段", "color": "#fff", "startTime": 10, "endTime": 20}],
			},
		)

		alice_reviews = self._request("GET", "/api/reviews?reviewer_id=alice")
		aggregate = self._request("GET", "/api/reviews/aggregate?uid=6001")["aggregate"]
		timeline_aggregate = self._request("GET", "/api/timeline-annotations/aggregate?uid=6001")["aggregate"]
		accepted = self._request("POST", "/api/export/accepted", {"reviewer_id": "alice", "clean": True})
		bundle = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{"reviewer_id": "alice", "clean": True, "bundle_name": "alice_bundle", "create_zip": True},
		)

		self.assertEqual(alice_reviews["reviews"]["6001"]["decision"], "accept")
		self.assertEqual(len(aggregate["latest_reviews"]), 2)
		self.assertEqual(aggregate["decision_counts"]["accept"], 1)
		self.assertEqual(aggregate["decision_counts"]["reject"], 1)
		self.assertEqual(len(timeline_aggregate["annotations"]), 1)
		self.assertEqual(accepted["accepted_count"], 1)
		self.assertEqual(bundle["sample_count"], 1)
		self.assertTrue(Path(bundle["bundle_root"]).exists())
		self.assertTrue(Path(bundle["zip_path"]).exists())
		self.assertIn("/api/export/reviewer-bundle/download?", bundle["download_url"])

		status, _ = self._fetch_raw("GET", bundle["download_url"])
		self.assertEqual(status, 200)

	def test_timeline_annotations_api_normalizes_millisecond_timestamps(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]

		self._request(
			"POST",
			"/api/timeline-annotations",
			{
				"uid": "6001",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"pins": [{"id": "p1", "time": 1710000030000, "layerKey": "raw", "label": "pin"}],
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

		annotations = self._request(
			"GET",
			f"/api/timeline-annotations?uid=6001&reviewer_id={alice['reviewer_id']}",
		)["annotations"]

		self.assertEqual(annotations["pins"][0]["time"], 1710000030)
		self.assertEqual(annotations["segments"][0]["startTime"], 1710000000)
		self.assertEqual(annotations["segments"][0]["endTime"], 1710000060)

	def test_export_reviewer_bundle_accepts_uid_and_tag_filters(self) -> None:
		self._create_published_batch("filter-batch")
		self._request("POST", "/api/reviewers/session?batch=filter-batch", {"display_name": "Alice"})
		self._write_csv(self.result_root / "7101" / "raw.csv", "uid,latitude\n7101,39.9\n")
		self._write_csv(self.result_root / "7101" / "line.csv", "latitude,longitude\n39.9,116.3\n")
		self._write_csv(self.result_root / "7102" / "raw.csv", "uid,latitude\n7102,39.9\n")
		self._write_csv(self.result_root / "7102" / "line.csv", "latitude,longitude\n39.9,116.3\n")

		self._request(
			"POST",
			"/api/reviews?batch=filter-batch",
			{
				"uid": "7101",
				"decision": "accept",
				"reviewer_id": "alice",
				"reviewer_name": "Alice",
				"reference_source": "line.csv",
				"trajectory_tags": ["subway"],
			},
		)
		self._request(
			"POST",
			"/api/reviews?batch=filter-batch",
			{
				"uid": "7102",
				"decision": "reject",
				"reviewer_id": "alice",
				"reviewer_name": "Alice",
				"reference_source": "line.csv",
				"trajectory_tags": ["road_taxi"],
			},
		)

		bundle = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{
				"batch": "filter-batch",
				"reviewer_id": "alice",
				"uids": ["7101"],
				"trajectory_tags": ["subway"],
				"decisions": ["accept", "reject"],
				"bundle_name": "filtered_bundle",
				"create_zip": True,
				"clean": True,
			},
		)
		self.assertEqual(bundle["sample_count"], 1)
		self.assertEqual(bundle["samples"][0]["uid"], "7101")

	def test_export_segment_label_dataset_api_returns_downloadable_zip(self) -> None:
		self._create_published_batch("dataset-batch")
		alice = self._request("POST", "/api/reviewers/session?batch=dataset-batch", {"display_name": "Alice"})["reviewer"]
		self._write_csv(
			self.result_root / "7201" / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"7201,cell_a,116.30,39.90,1710000000,1710000060",
				]
			),
		)
		self._write_csv(
			self.result_root / "7201" / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"7201,cell_a,39.90,116.30,stay,0,0,1710000000,1710000060",
					"7201,cell_a,39.91,116.31,stay,0,1,1710000000,1710000060",
				]
			),
		)
		self._request(
			"POST",
			"/api/reviews?batch=dataset-batch",
			{
				"uid": "7201",
				"decision": "accept",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"reference_source": "line.csv",
			},
		)
		self._request(
			"POST",
			"/api/timeline-annotations?batch=dataset-batch",
			{
				"uid": "7201",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"segments": [
					{"id": "s1", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000000, "endTime": 1710000060},
				],
			},
		)

		manifest = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{
				"batch": "dataset-batch",
				"reviewer_id": alice["reviewer_id"],
				"bundle_name": "dataset_bundle_api",
				"create_zip": True,
				"clean": True,
				"export_mode": "segment_label_dataset",
				"interval_seconds": 2,
			},
		)

		self.assertEqual(manifest["export_mode"], "segment_label_dataset")
		self.assertEqual(manifest["interval_seconds"], 5)
		self.assertEqual(manifest["annotation_sources"], ["reviewer"])
		self.assertEqual(manifest["uses_legacy_fallback"], False)
		self.assertEqual(manifest["interval_semantics"], "closed_interval")
		self.assertEqual(manifest["sample_count"], 1)
		self.assertEqual(manifest["download_name"], "dataset_bundle_api_dataset.zip")
		self.assertTrue(Path(manifest["zip_path"]).exists())
		status, _ = self._fetch_raw("GET", manifest["download_url"])
		self.assertEqual(status, 200)

	def test_export_segment_label_dataset_api_maps_internal_railway_label_to_train(self) -> None:
		self._create_published_batch("dataset-railway-batch")
		alice = self._request("POST", "/api/reviewers/session?batch=dataset-railway-batch", {"display_name": "Alice"})["reviewer"]
		self._write_csv(
			self.result_root / "7202" / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"7202,cell_a,116.30,39.90,1710000000,1710000030",
					"7202,cell_b,116.32,39.91,1710000030,1710000060",
				]
			),
		)
		self._write_csv(
			self.result_root / "7202" / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"7202,cell_a,39.90,116.30,road,0,0,1710000000,1710000060",
					"7202,cell_a,39.91,116.31,road,0,1,1710000000,1710000060",
				]
			),
		)
		self._request(
			"POST",
			"/api/reviews?batch=dataset-railway-batch",
			{
				"uid": "7202",
				"decision": "accept",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"reference_source": "line.csv",
			},
		)
		self._request(
			"POST",
			"/api/timeline-annotations?batch=dataset-railway-batch",
			{
				"uid": "7202",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
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

		manifest = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{
				"batch": "dataset-railway-batch",
				"reviewer_id": alice["reviewer_id"],
				"bundle_name": "dataset_bundle_railway_api",
				"create_zip": False,
				"clean": True,
				"export_mode": "segment_label_dataset",
			},
		)

		dataset_root = Path(manifest["dataset_root"])
		signal_rows = (dataset_root / "7202_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		gps_rows = (dataset_root / "7202_gps.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "7202,cell_a,116.3,39.9,1710000000000,1710000030000,train")
		self.assertEqual(signal_rows[2], "7202,cell_b,116.32,39.91,1710000030000,1710000060000,stay")
		self.assertTrue(any(row.endswith(",train") for row in gps_rows[1:]))

	def test_export_segment_label_dataset_api_keeps_snap_geometry_until_stay_boundary(self) -> None:
		self._create_published_batch("dataset-stay-boundary-batch")
		alice = self._request(
			"POST",
			"/api/reviewers/session?batch=dataset-stay-boundary-batch",
			{"display_name": "Alice"},
		)["reviewer"]
		self._write_csv(
			self.result_root / "7203" / "raw.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"7203,cell_a,1.00,1.00,1710000020,1710000060",
					"7203,cell_b,1.10,1.10,1710000060,1710000090",
					"7203,cell_c,2.00,2.00,1710000090,1710000120",
				]
			),
		)
		self._write_csv(
			self.result_root / "7203" / "snap.csv",
			"\n".join(
				[
					"UID,CID,longitude,latitude,t_in,t_out",
					"7203,cell_a,1.00,1.00,1710000020,1710000060",
					"7203,cell_b,1.10,1.10,1710000060,1710000090",
					"7203,cell_c,2.00,2.00,1710000090,1710000120",
				]
			),
		)
		self._write_csv(
			self.result_root / "7203" / "fmm.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,t_in,is_stationary,match_type,segment_idx,od_segment_idx,point_order,segment_start_time,segment_end_time",
					"7203,-1,30.00,130.00,1710000020,false,railway,0,0,0,1710000020,1710000060",
					"7203,-1,30.00,130.06,1710000060,false,railway,0,0,1,1710000020,1710000060",
					"7203,-1,40.00,140.00,1710000060,false,road,1,1,0,1710000060,1710000120",
					"7203,-1,40.00,140.12,1710000120,false,road,1,1,1,1710000060,1710000120",
				]
			),
		)
		self._write_csv(
			self.result_root / "7203" / "line.csv",
			"\n".join(
				[
					"UID,CID,latitude,longitude,match_type,segment_idx,point_order,segment_start_time,segment_end_time",
					"7203,cell_a,10.00,10.00,road,0,0,1710000020,1710000120",
					"7203,cell_b,10.10,10.10,road,0,1,1710000020,1710000120",
				]
			),
		)
		self._request(
			"POST",
			"/api/reviews?batch=dataset-stay-boundary-batch",
			{
				"uid": "7203",
				"decision": "accept",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"reference_source": "fmm.csv",
			},
		)
		self._request(
			"POST",
			"/api/timeline-annotations?batch=dataset-stay-boundary-batch",
			{
				"uid": "7203",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
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

		manifest = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{
				"batch": "dataset-stay-boundary-batch",
				"reviewer_id": alice["reviewer_id"],
				"bundle_name": "dataset_bundle_stay_boundary_api",
				"create_zip": False,
				"clean": True,
				"export_mode": "segment_label_dataset",
				"interval_seconds": 5,
			},
		)

		with open(Path(manifest["dataset_root"]) / "7203_gps.csv", encoding="utf-8") as handle:
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

	def test_export_segment_label_dataset_api_applies_signal_track_edit_positions(self) -> None:
		self._create_published_batch("dataset-signal-track-edit-batch")
		self._write_manifest(
			{
				"review_reference_files": ["signal.csv"],
				"layers": [{"filename": "signal.csv"}],
			}
		)
		alice = self._request(
			"POST",
			"/api/reviewers/session?batch=dataset-signal-track-edit-batch",
			{"display_name": "Alice"},
		)["reviewer"]
		self._write_csv(
			self.result_root / "7204" / "signal.csv",
			"\n".join(
				[
					"uid,cid,longitude,latitude,t_in,t_out,status",
					"7204,cell_a,116.30,39.90,1710000000,1710000060,road",
					"7204,cell_b,116.32,39.91,1710000060,1710000120,stay",
				]
			),
		)
		self._request(
			"POST",
			"/api/reviews?batch=dataset-signal-track-edit-batch",
			{
				"uid": "7204",
				"decision": "accept",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"reference_source": "signal.csv",
			},
		)
		self._request(
			"POST",
			"/api/timeline-annotations?batch=dataset-signal-track-edit-batch",
			{
				"uid": "7204",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"segments": [
					{"id": "road", "categoryId": "road", "categoryName": "乘车", "startTime": 1710000000, "endTime": 1710000060},
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 1710000060, "endTime": 1710000120},
				],
			},
		)
		self._request(
			"POST",
			"/api/track-edits?batch=dataset-signal-track-edit-batch",
			{
				"uid": "7204",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"patches": [
					{
						"pointId": "signal:7204:1710000030000:0",
						"layerKey": "signal",
						"rowIndex": 0,
						"timestamp": 1710000030,
						"position": {"latitude": 40.12, "longitude": 120.34},
						"metadata": {},
					},
				],
			},
		)

		manifest = self._request(
			"POST",
			"/api/export/reviewer-bundle",
			{
				"batch": "dataset-signal-track-edit-batch",
				"reviewer_id": alice["reviewer_id"],
				"bundle_name": "dataset_bundle_signal_track_edit_api",
				"create_zip": False,
				"clean": True,
				"export_mode": "segment_label_dataset",
			},
		)

		signal_rows = (Path(manifest["dataset_root"]) / "7204_signal.csv").read_text(encoding="utf-8").strip().splitlines()
		self.assertEqual(signal_rows[1], "7204,cell_a,120.34,40.12,1710000000000,1710000060000,road")
		self.assertEqual(signal_rows[2], "7204,cell_b,116.32,39.91,1710000060000,1710000120000,stay")

	def test_timeline_annotations_api_canonicalizes_exclusive_segments(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]

		response = self._request(
			"POST",
			"/api/timeline-annotations",
			{
				"uid": "6001",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"segmentPolicy": {
					"exclusiveMode": True,
					"intervalSemantics": "left_open_right_closed",
				},
				"segments": [
					{"id": "stay", "categoryId": "stay", "categoryName": "驻留", "startTime": 10, "endTime": 20},
					{"id": "road", "categoryId": "road_car", "categoryName": "驾车", "startTime": 15, "endTime": 30},
				],
			},
		)

		annotations = response["annotations"]
		self.assertEqual(annotations["segmentPolicy"]["exclusiveMode"], True)
		self.assertEqual(annotations["segmentPolicy"]["intervalSemantics"], "left_open_right_closed")
		self.assertEqual(len(annotations["segments"]), 2)
		self.assertEqual(annotations["segments"][0]["startTime"], 10)
		self.assertEqual(annotations["segments"][0]["endTime"], 20)
		self.assertEqual(annotations["segments"][1]["startTime"], 20)
		self.assertEqual(annotations["segments"][1]["endTime"], 30)

	def test_timeline_annotations_preserve_window_quick_segment_metadata(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]

		self._request(
			"POST",
			"/api/timeline-annotations",
			{
				"uid": "6001",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
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

		annotations = self._request("GET", f"/api/timeline-annotations?uid=6001&reviewer_id={alice['reviewer_id']}")["annotations"]
		aggregate = self._request("GET", "/api/timeline-annotations/aggregate?uid=6001")["aggregate"]
		segment = annotations["segments"][0]

		self.assertEqual(segment["entryMode"], "window_quick")
		self.assertEqual(segment["segmentScope"], "date_window")
		self.assertEqual(segment["windowStartDay"], "2026-04-10")
		self.assertEqual(segment["windowEndDay"], "2026-04-12")
		self.assertEqual(segment["fixedSpanDays"], 2)
		self.assertEqual(segment["sourceLayerKey"], "line")
		self.assertEqual(aggregate["annotations"][0]["window_quick_segment_count"], 1)

	def test_timeline_annotations_get_replay_is_read_only_when_reviewer_profile_is_missing(self) -> None:
		registry_path = self.paths.review_root / "system" / "reviewer_registry.json"
		profile_path = self.paths.review_root / "reviewers" / "ghost" / "profile.json"

		annotations = self._request("GET", "/api/timeline-annotations?uid=6001&reviewer_id=ghost")["annotations"]

		self.assertEqual(annotations["uid"], "6001")
		self.assertEqual(annotations["reviewer_id"], "ghost")
		self.assertEqual(annotations["segments"], [])
		self.assertEqual(annotations["pins"], [])
		self.assertFalse(registry_path.exists())
		self.assertFalse(profile_path.exists())

	def test_track_edits_api_round_trip(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]

		response = self._request(
			"POST",
			"/api/track-edits",
			{
				"uid": "6001",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"pointPatches": [
					{
						"pointId": "raw:1",
						"layerKey": "raw",
						"rowIndex": "1",
						"timestamp": "1710000001.5",
						"position": {"latitude": "39.91", "longitude": "116.31"},
						"metadata": {"source": "drag"},
					},
				],
			},
		)

		track_edits = response["track_edits"]
		self.assertEqual(track_edits["schema_version"], 1)
		self.assertEqual(track_edits["reviewer_id"], "alice")
		self.assertEqual(track_edits["patches"][0]["rowIndex"], 1)
		self.assertEqual(track_edits["patches"][0]["timestamp"], 1710000001.5)
		self.assertEqual(track_edits["patches"][0]["metadata"]["source"], "drag")
		self.assertEqual(track_edits["pointPatches"][0]["pointId"], "raw:1")

		loaded = self._request("GET", "/api/track-edits?uid=6001&reviewer_id=alice")["track_edits"]
		self.assertEqual(loaded, track_edits)

	def test_track_edits_api_is_scoped_per_reviewer(self) -> None:
		alice = self._request("POST", "/api/reviewers/session", {"display_name": "Alice"})["reviewer"]
		bob = self._request("POST", "/api/reviewers/session", {"display_name": "Bob"})["reviewer"]

		self._request(
			"POST",
			"/api/track-edits",
			{
				"uid": "6001",
				"reviewer_id": alice["reviewer_id"],
				"reviewer_name": alice["reviewer_name"],
				"patches": [
					{
						"pointId": "raw:alice",
						"layerKey": "raw",
						"rowIndex": 3,
						"timestamp": 1710000003,
						"position": {"latitude": 39.93, "longitude": 116.33},
						"metadata": {"owner": "alice"},
					},
				],
			},
		)
		self._request(
			"POST",
			"/api/track-edits",
			{
				"uid": "6001",
				"reviewer_id": bob["reviewer_id"],
				"reviewer_name": bob["reviewer_name"],
				"patches": [
					{
						"pointId": "raw:bob",
						"layerKey": "raw",
						"rowIndex": 4,
						"timestamp": 1710000004,
						"position": {"latitude": 39.94, "longitude": 116.34},
						"metadata": {"owner": "bob"},
					},
				],
			},
		)

		alice_edits = self._request("GET", "/api/track-edits?uid=6001&reviewer_id=alice")["track_edits"]
		bob_edits = self._request("GET", "/api/track-edits?uid=6001&reviewer_id=bob")["track_edits"]
		missing_reviewer = self._request("GET", "/api/track-edits?uid=6001", expect_status=400)

		self.assertEqual(alice_edits["patches"][0]["metadata"]["owner"], "alice")
		self.assertEqual(bob_edits["patches"][0]["metadata"]["owner"], "bob")
		self.assertEqual(alice_edits["patches"][0]["pointId"], "raw:alice")
		self.assertEqual(bob_edits["patches"][0]["pointId"], "raw:bob")
		self.assertEqual(missing_reviewer["error"], "reviewer_id is required")

	def test_admin_incoming_upload_and_list(self) -> None:
		initial = self._request("GET", "/api/admin/incoming")
		self.assertTrue(initial["enabled"])
		self.assertEqual(initial["items"], [])

		payload = b"PK\x03\x04fake zip payload"
		uploaded = self._request(
			"POST",
			"/api/admin/incoming/upload?name=round1_bundle.zip",
			payload=payload,
			headers={
				"Content-Type": "application/zip",
				"X-Upload-Filename": "round1_bundle.zip",
			},
			expect_status=201,
		)
		item = uploaded["item"]
		self.assertEqual(uploaded["status"], "uploaded")
		self.assertEqual(item["original_name"], "round1_bundle.zip")
		self.assertEqual(item["size_bytes"], len(payload))
		self.assertTrue(Path(item["payload_path"]).exists())
		self.assertTrue(Path(item["upload_root"]).exists())

		listed = self._request("GET", "/api/admin/incoming")
		self.assertEqual(len(listed["items"]), 1)
		self.assertEqual(listed["items"][0]["upload_id"], item["upload_id"])
		self.assertEqual(listed["items"][0]["status"], "uploaded")

	def test_admin_incoming_upload_validations(self) -> None:
		bad_suffix = self._request(
			"POST",
			"/api/admin/incoming/upload?name=not_a_zip.txt",
			payload=b"hello",
			headers={"Content-Type": "application/octet-stream"},
			expect_status=400,
		)
		self.assertEqual(bad_suffix["code"], "invalid_upload_name")

		too_large = self._request(
			"POST",
			"/api/admin/incoming/upload?name=too_big.zip",
			payload=b"x" * 2048,
			headers={"Content-Type": "application/zip"},
			expect_status=413,
		)
		self.assertEqual(too_large["code"], "upload_too_large")

	def test_review_endpoints_pick_up_batches_published_after_server_start(self) -> None:
		self._create_published_batch("incoming_demo_b01")

		health = self._request("GET", "/api/health?batch=incoming_demo_b01")
		self.assertEqual(health["batch"], "incoming_demo_b01")
		self.assertEqual(Path(health["result_root"]).resolve(), self.result_root.resolve())

		reviewer = self._request(
			"POST",
			"/api/reviewers/session",
			{"batch": "incoming_demo_b01", "display_name": "Alice Demo"},
		)["reviewer"]
		review = self._request(
			"POST",
			"/api/reviews",
			{
				"batch": "incoming_demo_b01",
				"uid": "6001",
				"decision": "accept",
				"reviewer_id": reviewer["reviewer_id"],
				"reviewer_name": reviewer["reviewer_name"],
				"reference_source": "line.csv",
			},
		)["review"]

		self.assertEqual(review["decision"], "accept")
		self.assertEqual(review["reviewer_id"], "alice-demo")

	def test_batch_list_exposes_ui_config_from_batch_meta(self) -> None:
		self._create_published_batch(
			"ui_demo_b01",
			metadata={
				"ui_config": {
					"annotation_enabled": False,
					"layer_specs": {
						"raw": {"defaultColor": "#123456"},
					},
				},
			},
		)

		payload = self._request("GET", "/api/batches")
		batch = next(item for item in payload["batches"] if item["name"] == "ui_demo_b01")

		self.assertEqual(batch["ui_config"]["annotation_enabled"], False)
		self.assertEqual(batch["ui_config"]["layer_specs"]["raw"]["defaultColor"], "#123456")

	def test_api_me_returns_actor_identity(self) -> None:
		payload = self._request(
			"GET",
			"/api/me",
			headers={
				"X-Forwarded-User": "alice.demo@example.com",
				"X-Display-Name": "Alice Demo",
				"X-Actor-Role": "annotator",
			},
		)

		self.assertEqual(payload["actor"]["actor_id"], "alice-demo")
		self.assertEqual(payload["actor"]["display_name"], "Alice Demo")
		self.assertEqual(payload["actor"]["role"], "annotator")

	def test_user_upload_private_batch_is_owner_scoped_and_batch_data_is_protected(self) -> None:
		headers = {
			"X-Forwarded-User": "alice@example.com",
			"X-Display-Name": "Alice",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "trajectory4",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Alice Trajectory4",
				"original_name": "alice_traj.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		csv_payload = (
			"uid,latitude,longitude,timestamp_ms,status\n"
			"u1001,39.901,116.391,1713340800000,stay\n"
			"u1001,39.902,116.392,1713340860000,walking\n"
		).encode("utf-8")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=csv_payload,
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "alice_traj.csv",
			},
			expect_status=201,
		)
		published = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/process",
			headers=headers,
		)["upload"]

		owner_batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		other_batches = self._request(
			"GET",
			"/api/batches",
			headers={"X-Forwarded-User": "bob@example.com", "X-Display-Name": "Bob"},
		)["batches"]
		allowed_status, allowed_manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)
		denied_status, _ = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers={"X-Forwarded-User": "bob@example.com", "X-Display-Name": "Bob"},
		)

		self.assertEqual(published["status"], "published")
		self.assertTrue(any(batch["name"] == published["batch_name"] for batch in owner_batches))
		self.assertFalse(any(batch["name"] == published["batch_name"] for batch in other_batches))
		self.assertEqual(allowed_status, 200)
		self.assertIn('"gps.csv"', allowed_manifest)
		self.assertEqual(denied_status, 404)

	def test_user_upload_blob_immediately_publishes_trajectory4_preview_batch(self) -> None:
		headers = {
			"X-Forwarded-User": "preview@example.com",
			"X-Display-Name": "Preview User",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "trajectory4",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Preview Trajectory4",
				"original_name": "preview_traj.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		uploaded = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,latitude,longitude,timestamp_ms,status\n"
				"p1001,39.901,116.391,1713340800000,stay\n"
				"p1001,39.902,116.392,1713340860000,walking\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "preview_traj.csv",
			},
			expect_status=201,
		)["upload"]
		batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		manifest_status, manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{uploaded['batch_name']}/manifest.json",
			headers=headers,
		)

		self.assertEqual(uploaded["status"], "preview_ready")
		self.assertTrue(uploaded["batch_name"])
		self.assertTrue(any(batch["name"] == uploaded["batch_name"] for batch in batches))
		self.assertEqual(manifest_status, 200)
		self.assertIn('"gps.csv"', manifest)

	def test_user_upload_blob_immediately_publishes_signal6_raw_preview_batch(self) -> None:
		headers = {
			"X-Forwarded-User": "signal-preview@example.com",
			"X-Display-Name": "Signal Preview",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Preview Signal6",
				"original_name": "preview_signal.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		uploaded = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,cid,lat,lon,t_in,t_out,status\n"
				"s3001,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
				"s3001,1102,39.9142,116.4174,1713340980000,1713341160000,subway\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "preview_signal.csv",
			},
			expect_status=201,
		)["upload"]
		batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		manifest_status, manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{uploaded['batch_name']}/manifest.json",
			headers=headers,
		)

		self.assertEqual(uploaded["status"], "preview_ready")
		self.assertTrue(uploaded["batch_name"])
		self.assertTrue(any(batch["name"] == uploaded["batch_name"] for batch in batches))
		self.assertEqual(manifest_status, 200)
		self.assertIn('"signal.csv"', manifest)

	def test_user_upload_signal6_preview_drops_outside_beijing_rows(self) -> None:
		headers = {
			"X-Forwarded-User": "signal-preview-bbox@example.com",
			"X-Display-Name": "Signal Preview BBox",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Preview Signal6 BBox",
				"original_name": "preview_signal_bbox.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		uploaded = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,cid,lat,lon,t_in,t_out,status\n"
				"s3001,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
				"s3001,bad0,0,0,1713340980000,1713341160000,road\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "preview_signal_bbox.csv",
			},
			expect_status=201,
		)["upload"]
		rows = list(
			csv.DictReader(
				(Path(uploaded["result_root"]) / "s3001" / "signal.csv")
				.read_text(encoding="utf-8")
				.splitlines()
			)
		)

		self.assertEqual(uploaded["status"], "preview_ready")
		self.assertIn("忽略 1 行北京范围外信令点", uploaded["note"])
		self.assertEqual([row["cid"] for row in rows], ["1101"])

	def test_user_upload_auto_type_detects_trajectory4_preview(self) -> None:
		headers = {
			"X-Forwarded-User": "auto-traj@example.com",
			"X-Display-Name": "Auto Traj",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "auto",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Auto Upload",
				"original_name": "auto_traj.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		uploaded = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,latitude,longitude,timestamp_ms,status\n"
				"a1001,39.901,116.391,1713340800000,stay\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "auto_traj.csv",
			},
			expect_status=201,
		)["upload"]
		self.assertEqual(uploaded["status"], "preview_ready")
		self.assertEqual(uploaded["upload_type"], "trajectory4")

	def test_user_upload_auto_type_detects_signal6_on_process(self) -> None:
		headers = {
			"X-Forwarded-User": "auto-signal@example.com",
			"X-Display-Name": "Auto Signal",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "auto",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Auto Signal Upload",
				"original_name": "auto_signal.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,cid,lat,lon,t_in,t_out,status\n"
				"s3001,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "auto_signal.csv",
			},
			expect_status=201,
		)
		def fake_build_signal6_result(source_path, result_root, **kwargs):
			result_root = Path(result_root)
			uid_dir = result_root / "s3001"
			uid_dir.mkdir(parents=True, exist_ok=True)
			(uid_dir / "line.csv").write_text("uid,latitude,longitude\ns3001,39.9,116.3\n", encoding="utf-8")
			(uid_dir / "fmm.csv").write_text("UID,latitude,longitude\ns3001,39.9,116.3\n", encoding="utf-8")
			(result_root / "states_index.json").write_text(json.dumps({"s3001": []}) + "\n", encoding="utf-8")
			(result_root / "manifest.json").write_text(
				json.dumps(
					{
						"title": "Auto Signal Upload",
						"ui_mode": "chain2",
						"uids": ["s3001"],
						"layers": ["line", "fmm"],
						"layer_specs": {
							"line": {"filename": "line.csv"},
							"fmm": {"filename": "fmm.csv"},
						},
						"review_reference_files": ["line.csv", "fmm.csv"],
					}
				)
				+ "\n",
				encoding="utf-8",
			)
			return {
				"adapter": "signal6",
				"pipeline_mode": "v311",
				"ui_mode": "chain2",
				"review_reference_files": ["line.csv", "fmm.csv"],
				"filter_state_options": [],
				"fmm_algorithm": {"profile": "speed_sparsity_90"},
			}

		with mock.patch.object(
			review_server_module,
			"build_signal6_result",
			side_effect=fake_build_signal6_result,
		) as mocked:
			published = self._request(
				"POST",
				f"/api/uploads/{created['upload_id']}/process",
				headers=headers,
			)["upload"]
		self.assertEqual(published["upload_type"], "signal6")
		self.assertEqual(published["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertEqual(published["signal6_pipeline_mode"], "v311")
		self.assertEqual(mocked.call_args.kwargs["pipeline_mode"], "v311")
		self.assertTrue(mocked.call_args.kwargs["pipeline_options"]["speed_sparsity_hybrid"])

	def test_user_upload_signal6_process_passes_algorithm_profile_options(self) -> None:
		headers = {
			"X-Forwarded-User": "algo@example.com",
			"X-Display-Name": "Algo User",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "private",
				"annotation_mode": "annotatable",
				"display_name": "Algo Signal6",
				"original_name": "algo_signal.csv",
				"signal6_algorithm_profile": "speed_sparsity_90",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		self.assertEqual(created["signal6_algorithm_profile"], "speed_sparsity_90")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=(
				"uid,cid,lat,lon,t_in,t_out,status\n"
				"s3001,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
			).encode("utf-8"),
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "algo_signal.csv",
			},
			expect_status=201,
		)
		def fake_build_signal6_result(source_path, result_root, **kwargs):
			result_root = Path(result_root)
			uid_dir = result_root / "s3001"
			uid_dir.mkdir(parents=True, exist_ok=True)
			(uid_dir / "line.csv").write_text("uid,latitude,longitude\ns3001,39.9,116.3\n", encoding="utf-8")
			(uid_dir / "fmm.csv").write_text("UID,latitude,longitude\ns3001,39.9,116.3\n", encoding="utf-8")
			(result_root / "states_index.json").write_text(json.dumps({"s3001": []}) + "\n", encoding="utf-8")
			(result_root / "manifest.json").write_text(
				json.dumps(
					{
						"title": "Algo Signal6",
						"ui_mode": "chain2",
						"uids": ["s3001"],
						"layers": ["line", "fmm"],
						"layer_specs": {
							"line": {"filename": "line.csv"},
							"fmm": {"filename": "fmm.csv"},
						},
						"review_reference_files": ["line.csv", "fmm.csv"],
					}
				)
				+ "\n",
				encoding="utf-8",
			)
			return {
				"adapter": "signal6",
				"pipeline_mode": "v311",
				"ui_mode": "chain2",
				"review_reference_files": ["line.csv", "fmm.csv"],
				"filter_state_options": [],
				"fmm_algorithm": {"profile": "speed_sparsity_90"},
			}

		with mock.patch.object(
			review_server_module,
			"build_signal6_result",
			side_effect=fake_build_signal6_result,
		) as mocked:
			published = self._request(
				"POST",
				f"/api/uploads/{created['upload_id']}/process",
				headers=headers,
			)["upload"]

		kwargs = mocked.call_args.kwargs
		self.assertEqual(kwargs["pipeline_mode"], "v311")
		self.assertEqual(kwargs["pipeline_options"]["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertTrue(kwargs["pipeline_options"]["speed_sparsity_hybrid"])
		self.assertEqual(published["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertEqual(published["signal6_pipeline_mode"], "v311")
		self.assertEqual(published["fmm_algorithm"]["profile"], "speed_sparsity_90")

	def test_user_upload_signal_triplet_zip_processes_with_productized_profile(self) -> None:
		headers = {
			"X-Forwarded-User": "triplet@example.com",
			"X-Display-Name": "Triplet User",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal_triplet",
				"visibility_scope": "private",
				"annotation_mode": "annotatable",
				"display_name": "Triplet Upload",
				"original_name": "triplet.zip",
				"signal6_algorithm_profile": "speed_sparsity_90",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		zip_buffer = io.BytesIO()
		with zipfile.ZipFile(zip_buffer, "w") as archive:
			archive.writestr("route_01/signal.csv", "uid,cid,latitude,longitude,t_in,t_out\ns3001,1101,39.9042,116.4074,1713340800000,1713340860000\n")
			archive.writestr("route_01/gate.csv", "uid,latitude,longitude,timestamp_ms\ns3001,39.9042,116.4074,1713340800000\n")
			archive.writestr("route_01/lbs.csv", "uid,segment_id,point_index,latitude,longitude,timestamp_ms\ns3001,LBS-01,0,39.9042,116.4074,1713340800000\n")
		uploaded = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=zip_buffer.getvalue(),
			headers={
				**headers,
				"Content-Type": "application/zip",
				"X-Upload-Filename": "triplet.zip",
			},
			expect_status=201,
		)["upload"]
		self.assertEqual(uploaded["status"], "uploaded")
		self.assertIn("多源轨迹包已上传", uploaded["note"])

		def fake_build_signal_triplet_result(source_path, result_root, **kwargs):
			result_root = Path(result_root)
			uid_dir = result_root / "s3001"
			uid_dir.mkdir(parents=True, exist_ok=True)
			for name in ("signal.csv", "gate.csv", "lbs.csv", "snap.csv", "od.csv", "reconstruction.csv"):
				(uid_dir / name).write_text("uid,latitude,longitude\ns3001,39.9,116.3\n", encoding="utf-8")
			(result_root / "states_index.json").write_text(json.dumps({"s3001": []}) + "\n", encoding="utf-8")
			(result_root / "manifest.json").write_text(
				json.dumps(
					{
						"title": "Triplet Upload",
						"ui_mode": "trajectory_layers",
						"uids": ["s3001"],
						"layers": ["signal", "gate", "lbs", "snap", "od", "reconstruction"],
						"layer_specs": {key: {"filename": f"{key}.csv"} for key in ["signal", "gate", "lbs", "snap", "od", "reconstruction"]},
						"review_reference_files": ["signal.csv", "gate.csv", "lbs.csv", "snap.csv", "od.csv", "reconstruction.csv"],
					}
				)
				+ "\n",
				encoding="utf-8",
			)
			return {
				"adapter": "signal_triplet",
				"pipeline_mode": "v311",
				"ui_mode": "trajectory_layers",
				"review_reference_files": ["signal.csv", "gate.csv", "lbs.csv", "snap.csv", "od.csv", "reconstruction.csv"],
				"filter_state_options": [],
				"fmm_algorithm": {"profile": "speed_sparsity_90"},
			}

		with mock.patch.object(
			review_server_module,
			"build_signal_triplet_result",
			side_effect=fake_build_signal_triplet_result,
		) as mocked:
			published = self._request(
				"POST",
				f"/api/uploads/{created['upload_id']}/process",
				headers=headers,
			)["upload"]

		kwargs = mocked.call_args.kwargs
		self.assertEqual(kwargs["pipeline_options"]["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertTrue(kwargs["pipeline_options"]["speed_sparsity_hybrid"])
		self.assertEqual(published["upload_type"], "signal_triplet")
		self.assertEqual(published["signal6_algorithm_profile"], "speed_sparsity_90")
		self.assertEqual(published["signal6_pipeline_mode"], "v311")
		self.assertEqual(published["fmm_algorithm"]["profile"], "speed_sparsity_90")

	def test_user_upload_public_view_only_batch_can_be_listed_and_soft_deleted(self) -> None:
		headers = {
			"X-Forwarded-User": "carol@example.com",
			"X-Display-Name": "Carol",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "public",
				"annotation_mode": "view_only",
				"display_name": "Carol Signal6",
				"original_name": "carol_signal.csv",
				"signal6_algorithm_profile": "baseline_v311",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		csv_payload = (
			"uid,cid,lat,lon,t_in,t_out,status\n"
			"s2001,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
		).encode("utf-8")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=csv_payload,
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "carol_signal.csv",
			},
			expect_status=201,
		)
		published = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/process",
			headers=headers,
		)["upload"]

		public_batches = self._request(
			"GET",
			"/api/batches",
			headers={"X-Forwarded-User": "dave@example.com", "X-Display-Name": "Dave"},
		)["batches"]
		public_batch = next(batch for batch in public_batches if batch["name"] == published["batch_name"])
		self.assertEqual(public_batch["visibility_scope"], "public")
		self.assertEqual(public_batch["annotation_mode"], "view_only")
		self.assertEqual(public_batch["ui_config"]["annotation_enabled"], False)
		self.assertEqual(public_batch["ui_config"]["hide_review_panel"], True)

		deleted = self._request(
			"DELETE",
			f"/api/uploads/{created['upload_id']}",
			headers=headers,
		)
		remaining_batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		status_code, _ = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)
		uploads = self._request("GET", "/api/uploads", headers=headers)["items"]
		upload_record = next(item for item in uploads if item["upload_id"] == created["upload_id"])

		self.assertEqual(deleted["status"], "deleted")
		self.assertFalse(any(batch["name"] == published["batch_name"] for batch in remaining_batches))
		self.assertEqual(status_code, 404)
		self.assertEqual(upload_record["status"], "deleted")

	def test_user_upload_full_flow_supports_publish_open_and_delete(self) -> None:
		headers = {
			"X-Forwarded-User": "flow@example.com",
			"X-Display-Name": "Flow Tester",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "trajectory4",
				"visibility_scope": "owner_only",
				"annotation_mode": "annotatable",
				"display_name": "Flow Trajectory4",
				"original_name": "flow_traj.csv",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		csv_payload = (
			"uid,latitude,longitude,timestamp_ms,status\n"
			"flow1001,39.901,116.391,1713340800000,stay\n"
			"flow1001,39.902,116.392,1713340860000,walking\n"
		).encode("utf-8")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=csv_payload,
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "flow_traj.csv",
			},
			expect_status=201,
		)
		published = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/process",
			headers=headers,
		)["upload"]

		batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		selected_batch = next(batch for batch in batches if batch["name"] == published["batch_name"])
		health = self._request("GET", f"/api/health?batch={published['batch_name']}", headers=headers)
		manifest_status, manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)

		self.assertEqual(published["status"], "published")
		self.assertEqual(selected_batch["name"], published["batch_name"])
		self.assertEqual(health["batch"], published["batch_name"])
		self.assertEqual(manifest_status, 200)
		self.assertIn('"gps.csv"', manifest)

		deleted = self._request(
			"DELETE",
			f"/api/uploads/{created['upload_id']}",
			headers=headers,
		)
		remaining_batches = self._request("GET", "/api/batches", headers=headers)["batches"]
		manifest_status_after_delete, _ = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)
		uploads = self._request("GET", "/api/uploads", headers=headers)["items"]
		upload_record = next(item for item in uploads if item["upload_id"] == created["upload_id"])

		self.assertEqual(deleted["status"], "deleted")
		self.assertFalse(any(batch["name"] == published["batch_name"] for batch in remaining_batches))
		self.assertEqual(manifest_status_after_delete, 404)
		self.assertEqual(upload_record["status"], "deleted")

	def test_user_upload_process_accepts_case_insensitive_headers(self) -> None:
		headers = {
			"X-Forwarded-User": "erin@example.com",
			"X-Display-Name": "Erin",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "private",
				"annotation_mode": "annotatable",
				"display_name": "Erin Signal6 Casefold",
				"original_name": "erin_signal_casefold.csv",
				"signal6_algorithm_profile": "baseline_v311",
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		csv_payload = (
			"UID,CID,Lat,Lon,TIn,TOut,Status\n"
			"s2601,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
			"s2601,1102,39.9142,116.4174,1713340980000,1713341160000,subway\n"
		).encode("utf-8")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=csv_payload,
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "erin_signal_casefold.csv",
			},
			expect_status=201,
		)
		published = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/process",
			headers=headers,
		)["upload"]

		status_code, manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)

		self.assertEqual(published["status"], "published")
		self.assertEqual(status_code, 200)
		self.assertIn('"signal.csv"', manifest)

	def test_user_upload_process_applies_custom_field_mapping(self) -> None:
		headers = {
			"X-Forwarded-User": "frank@example.com",
			"X-Display-Name": "Frank",
		}
		created = self._request(
			"POST",
			"/api/uploads",
			{
				"upload_type": "signal6",
				"visibility_scope": "private",
				"annotation_mode": "annotatable",
				"display_name": "Frank Signal6 Custom Mapping",
				"original_name": "frank_signal_custom.csv",
				"signal6_algorithm_profile": "baseline_v311",
				"field_mapping": {
					"uid": "subscriberId",
					"cid": "cellCode",
					"latitude": "gpsLat",
					"longitude": "gpsLon",
					"t_in": "procedureStartTime",
					"t_out": "proceduereEndTime",
					"status": "sceneType",
				},
			},
			headers=headers,
			expect_status=201,
		)["upload"]
		csv_payload = (
			"subscriberId,cellCode,gpsLat,gpsLon,procedureStartTime,proceduereEndTime,sceneType\n"
			"s2701,1101,39.9042,116.4074,1713340800000,1713340980000,road\n"
		).encode("utf-8")
		self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/blob",
			payload=csv_payload,
			headers={
				**headers,
				"Content-Type": "text/csv",
				"X-Upload-Filename": "frank_signal_custom.csv",
			},
			expect_status=201,
		)
		published = self._request(
			"POST",
			f"/api/uploads/{created['upload_id']}/process",
			headers=headers,
		)["upload"]
		uploads = self._request("GET", "/api/uploads", headers=headers)["items"]
		upload_record = next(item for item in uploads if item["upload_id"] == created["upload_id"])
		status_code, manifest = self._fetch_raw(
			"GET",
			f"/batch-data/{published['batch_name']}/manifest.json",
			headers=headers,
		)

		self.assertEqual(published["status"], "published")
		self.assertEqual(status_code, 200)
		self.assertIn('"signal.csv"', manifest)
		self.assertEqual(upload_record["field_mapping"]["uid"], ["subscriber_id"])
		self.assertIn("t_out", upload_record["field_mapping"])


if __name__ == "__main__":
	unittest.main()
