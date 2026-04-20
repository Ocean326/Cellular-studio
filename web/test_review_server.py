from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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
				return response.status, response.read().decode("utf-8")
		except HTTPError as exc:
			body = exc.read().decode("utf-8")
			exc.close()
			return exc.code, body

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
