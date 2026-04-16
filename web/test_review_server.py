from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
	sys.path.insert(0, str(THIS_DIR))

from review_lib import resolve_review_paths
from review_server import ReviewRequestHandler


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


if __name__ == "__main__":
	unittest.main()
