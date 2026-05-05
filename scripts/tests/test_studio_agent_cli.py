from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_PARENT = Path(__file__).resolve().parents[3]
if str(REPO_PARENT) not in os.sys.path:
	os.sys.path.insert(0, str(REPO_PARENT))

from trajectory_annotation_studio.web.review_lib import resolve_review_paths
from trajectory_annotation_studio.web.review_server import ReviewRequestHandler
from trajectory_annotation_studio.scripts.studio_agent_cli import main as studio_agent_main
from trajectory_annotation_studio.scripts.studio_agent_client import StudioAgentClient


class StudioAgentCliTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.project_root = Path(self.temp_dir.name)
		self.result_root = self.project_root / "data" / "result"
		self.review_root = self.project_root / "data" / "review"
		self.export_root = self.project_root / "data" / "review" / "accepted_assets"
		self.result_root.mkdir(parents=True, exist_ok=True)
		self.review_paths = resolve_review_paths(
			project_root=self.project_root,
			result_root=self.result_root,
			review_root=self.review_root,
			export_root=self.export_root,
		)
		self._write_result_fixture()
		handler = lambda *args, **kwargs: ReviewRequestHandler(
			*args,
			directory=str(self.project_root),
			review_paths=self.review_paths,
			batches_root=None,
			batches={},
			batch_order=[],
			default_batch="current",
			incoming_root=None,
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

	def _write_result_fixture(self) -> None:
		manifest = {
			"ui_mode": "chain2",
			"uids": ["6001"],
			"layers": ["signal", "line", "fmm"],
			"layer_specs": {
				"signal": {"filename": "signal.csv"},
				"line": {"filename": "line.csv"},
				"fmm": {"filename": "fmm.csv", "review_reference": True},
			},
			"review_reference_files": ["fmm.csv"],
			"states": {"6001": ["stay", "home_candidate"]},
		}
		(self.result_root / "manifest.json").write_text(
			json.dumps(manifest, ensure_ascii=False) + "\n",
			encoding="utf-8",
		)
		uid_root = self.result_root / "6001"
		uid_root.mkdir(parents=True, exist_ok=True)
		(uid_root / "signal.csv").write_text(
			"uid,event_index,cid,latitude,longitude,t_in,t_out\n6001,0,1,39.9,116.3,1,2\n",
			encoding="utf-8",
		)
		(uid_root / "line.csv").write_text(
			"uid,latitude,longitude,match_type,segment_idx,od_segment_idx,is_stationary,point_order,segment_start_time,segment_end_time\n"
			"6001,39.9,116.3,stay,0,0,True,0,1,2\n",
			encoding="utf-8",
		)
		(uid_root / "fmm.csv").write_text(
			"UID,CID,latitude,longitude,t_in,is_stationary,match_type,segment_idx,od_segment_idx,point_order,segment_start_time,segment_end_time\n"
			"6001,-1,39.9,116.3,1,False,road,0,0,0,1,2\n",
			encoding="utf-8",
		)
		(uid_root / "od.csv").write_text(
			"start_latitude,start_longitude,end_latitude,end_longitude,start_time,end_time,time_diff,speed,is_stationary\n"
			"39.9000,116.3000,39.9010,116.3010,1,301,300,0.7,False\n",
			encoding="utf-8",
		)
		(uid_root / "case_manifest.json").write_text(
			json.dumps({"uid": "6001", "case_bucket": "smoke"}),
			encoding="utf-8",
		)

	def _run_cli(self, *argv: str) -> dict:
		code, payload, stderr = self._run_cli_result(*argv)
		self.assertEqual(code, 0, stderr)
		return payload

	def _run_cli_result(self, *argv: str) -> tuple[int, dict, str]:
		stdout = io.StringIO()
		stderr = io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = studio_agent_main(
				[
					"--base-url",
					f"http://127.0.0.1:{self.port}",
					"--json",
					*argv,
				]
			)
		payload = json.loads(stdout.getvalue()) if stdout.getvalue().strip() else {}
		return code, payload, stderr.getvalue()

	def test_sample_inspect_and_materialize(self) -> None:
		list_payload = self._run_cli(
			"sample",
			"list",
			"--review-status",
			"unreviewed",
		)
		self.assertEqual(list_payload["total"], 1)
		self.assertEqual(list_payload["items"][0]["uid"], "6001")
		self.assertFalse(list_payload["items"][0]["reviewed"])

		inspect_payload = self._run_cli(
			"sample",
			"inspect",
			"--uid",
			"6001",
			"--preview-rows",
			"2",
		)
		self.assertEqual(inspect_payload["uid"], "6001")
		self.assertEqual(inspect_payload["tags"], ["stay", "home_candidate"])
		self.assertTrue(any(item["relative_path"] == "6001/fmm.csv" for item in inspect_payload["files"]))

		output_dir = self.project_root / "materialized"
		materialize_payload = self._run_cli(
			"sample",
			"materialize",
			"--uid",
			"6001",
			"--output-dir",
			str(output_dir),
		)
		self.assertEqual(materialize_payload["uid"], "6001")
		self.assertTrue((output_dir / "context.json").exists())
		self.assertTrue((output_dir / "6001" / "signal.csv").exists())

		summary_payload = self._run_cli(
			"sample",
			"segment-summary",
			"--sample-root",
			str(output_dir),
		)
		self.assertEqual(summary_payload["uid"], "6001")
		self.assertEqual(summary_payload["batch"], "current")
		self.assertEqual(summary_payload["aggregate"]["csv_files"], 4)
		self.assertTrue(any(layer["relative_path"] == "6001/fmm.csv" for layer in summary_payload["layers"]))

		visual_dir = self.project_root / "visual-context"
		visual_payload = self._run_cli(
			"sample",
			"visual-context",
			"export",
			"--sample-root",
			str(output_dir),
			"--output-dir",
			str(visual_dir),
		)
		self.assertTrue(Path(visual_payload["visual_context_path"]).is_file())
		self.assertTrue(Path(visual_payload["index_html_path"]).is_file())
		self.assertEqual(visual_payload["payload"]["basemap"]["mode"], "offline_tiles")
		self.assertIn("/offline_tiles/beijing/", visual_payload["payload"]["tile_url_template"])

	def test_review_submit_and_roundtrip(self) -> None:
		reviewer_payload = self._run_cli(
			"reviewer",
			"start",
			"--name",
			"Codex Probe",
			"--reviewer-id",
			"codex_probe",
		)
		reviewer_id = reviewer_payload["reviewer"]["reviewer_id"]
		self.assertEqual(reviewer_id, "codex-probe")

		review_payload = self._run_cli(
			"review",
			"submit",
			"--uid",
			"6001",
			"--decision",
			"skip",
			"--reviewer-id",
			reviewer_id,
			"--reviewer-name",
			"Codex Probe",
			"--notes",
			"smoke",
			"--reference-source",
			"fmm.csv",
			"--tag",
			"agent_probe",
		)
		self.assertEqual(review_payload["review"]["decision"], "skip")

		reviewed_payload = self._run_cli(
			"sample",
			"list",
			"--review-status",
			"reviewed",
		)
		self.assertEqual(reviewed_payload["total"], 1)
		self.assertTrue(reviewed_payload["items"][0]["reviewed"])
		self.assertEqual(reviewed_payload["items"][0]["reviewer_count"], 1)

		unreviewed_for_reviewer = self._run_cli(
			"sample",
			"list",
			"--review-status",
			"unreviewed",
			"--reviewer-id",
			reviewer_id,
		)
		self.assertEqual(unreviewed_for_reviewer["total"], 0)

		roundtrip_payload = self._run_cli(
			"dev",
			"roundtrip",
			"--uid",
			"6001",
			"--reviewer-name",
			"Codex Probe",
			"--reviewer-id",
			reviewer_id,
			"--decision",
			"accept",
			"--with-segment",
			"--segment-start-ms",
			"1",
			"--segment-end-ms",
			"2",
		)
		self.assertEqual(roundtrip_payload["session"]["reviewer_id"], reviewer_id)
		self.assertEqual(roundtrip_payload["review"]["review"]["decision"], "accept")
		self.assertEqual(
			roundtrip_payload["aggregate"]["aggregate"]["decision_counts"]["accept"],
			1,
		)
		self.assertEqual(
			len(roundtrip_payload["timeline_aggregate"]["aggregate"]["annotations"]),
			1,
		)

	def test_track_edits_put_get_export_roundtrip(self) -> None:
		reviewer_payload = self._run_cli(
			"reviewer",
			"start",
			"--name",
			"Track Edit Probe",
			"--reviewer-id",
			"track_edit_probe",
		)
		reviewer_id = reviewer_payload["reviewer"]["reviewer_id"]
		reviewer_name = reviewer_payload["reviewer"]["reviewer_name"]
		self.assertEqual(reviewer_id, "track-edit-probe")

		put_payload = self._run_cli(
			"track-edits",
			"put",
			"--uid",
			"6001",
			"--reviewer-id",
			reviewer_id,
			"--reviewer-name",
			reviewer_name,
			"--payload-json",
			json.dumps(
				{
					"pointPatches": [
						{
							"pointId": "line:0",
							"layerKey": "line",
							"rowIndex": 0,
							"timestamp": 1,
							"position": {"latitude": 39.901, "longitude": 116.301},
							"metadata": {"source": "cli_roundtrip"},
						},
					],
				},
				ensure_ascii=False,
			),
		)
		self.assertEqual(put_payload["track_edits"]["patches"][0]["metadata"]["source"], "cli_roundtrip")

		got = self._run_cli(
			"track-edits",
			"get",
			"--uid",
			"6001",
			"--reviewer-id",
			reviewer_id,
		)
		self.assertEqual(got["track_edits"]["patches"], put_payload["track_edits"]["patches"])

		exported = self._run_cli(
			"track-edits",
			"export",
			"--uid",
			"6001",
			"--reviewer-id",
			reviewer_id,
		)
		self.assertEqual(exported["uid"], "6001")
		self.assertEqual(exported["reviewer_id"], reviewer_id)
		self.assertEqual(exported["track_edits"]["patches"], put_payload["track_edits"]["patches"])
		self.assertIn("pins", exported["timeline_annotations"])
		self.assertIn("segments", exported["timeline_annotations"])

	def test_mode_label_candidates_and_apply_dry_run(self) -> None:
		out = self._run_cli(
			"mode-label",
			"candidates",
			"--result-root",
			str(self.result_root),
			"--label",
			"road,low_speed",
			"--per-label",
			"1",
		)
		self.assertEqual(out["schema"], "studio_agent_mode_candidates/v1")
		self.assertEqual(len(out["classes"]["road"]), 1)
		self.assertEqual(len(out["classes"]["low_speed"]), 1)
		self.assertEqual(out["classes"]["road"][0]["uid"], "6001")
		self.assertEqual(out["classes"]["low_speed"][0]["uid"], "6001")
		self.assertEqual(len(out["annotation_plan"]), 2)

		dry = self._run_cli(
			"mode-label",
			"apply",
			"--plan-json",
			json.dumps(out, ensure_ascii=False),
			"--reviewer-id",
			"mode_probe",
			"--reviewer-name",
			"Mode Probe",
			"--dry-run",
		)
		self.assertEqual(dry["status"], "dry_run")
		self.assertEqual(dry["uid_count"], 1)
		self.assertEqual(dry["segment_count"], 2)

	def test_timeline_validate_command(self) -> None:
		valid_payload = {
			"segments": [
				{
					"startTime": 1,
					"endTime": 2,
					"semanticTags": ["mode:walk", "purpose:commute"],
					"reconstructionQuality": "accurate",
					"visualEvidenceRefs": ["visual_context:6001"],
					"confidence": 0.8,
				},
			],
		}
		ok_payload = self._run_cli(
			"timeline",
			"validate",
			"--payload-json",
			json.dumps(valid_payload, ensure_ascii=False),
		)
		self.assertTrue(ok_payload["ok"], ok_payload["errors"])
		self.assertEqual(ok_payload["status"], "ok")
		self.assertEqual(ok_payload["segment_count"], 1)

		invalid_payload = {
			"segments": [
				{
					"startTime": 1,
					"endTime": 2,
					"semanticTags": ["mode:walk"],
					"reconstructionQuality": "inaccurate",
				},
			],
		}
		code, bad_payload, stderr = self._run_cli_result(
			"timeline",
			"validate",
			"--payload-json",
			json.dumps(invalid_payload, ensure_ascii=False),
			"--fail-on-error",
		)
		self.assertEqual(stderr, "")
		self.assertEqual(code, 1)
		self.assertFalse(bad_payload["ok"])
		self.assertEqual(bad_payload["status"], "invalid")
		self.assertTrue(any("inaccurate" in item for item in bad_payload["errors"]))

	def test_bundle_export_help_includes_segment_dataset_flags(self) -> None:
		buf = io.StringIO()
		with contextlib.redirect_stdout(buf):
			with self.assertRaises(SystemExit) as ctx:
				studio_agent_main(["bundle", "export", "--help"])
		self.assertEqual(ctx.exception.code, 0)
		for needle in ("--interval-seconds", "--timestamp-unit", "--labeled-span-only"):
			self.assertIn(needle, buf.getvalue())

	def test_bundle_export_client_payload_omits_dataset_options_unless_set(self) -> None:
		with patch.object(StudioAgentClient, "_request_json", return_value={}) as mock_req:
			StudioAgentClient(base_url="http://127.0.0.1:9").export_reviewer_bundle("alice")
		payload = mock_req.call_args.kwargs["payload"]
		self.assertNotIn("interval_seconds", payload)
		self.assertNotIn("timestamp_unit", payload)
		self.assertNotIn("labeled_span_only", payload)

		with patch.object(StudioAgentClient, "_request_json", return_value={}) as mock_req:
			StudioAgentClient(base_url="http://127.0.0.1:9").export_reviewer_bundle(
				"alice",
				interval_seconds=10,
				timestamp_unit="seconds",
				labeled_span_only=True,
			)
		payload = mock_req.call_args.kwargs["payload"]
		self.assertEqual(payload["interval_seconds"], 10)
		self.assertEqual(payload["timestamp_unit"], "seconds")
		self.assertTrue(payload["labeled_span_only"])

	def test_bundle_export_segment_label_dataset_cli_passes_options(self) -> None:
		reviewer_payload = self._run_cli(
			"reviewer",
			"start",
			"--name",
			"Dataset Probe",
			"--reviewer-id",
			"dataset_cli",
		)
		reviewer_id = reviewer_payload["reviewer"]["reviewer_id"]
		reviewer_name = reviewer_payload["reviewer"]["reviewer_name"]
		self._run_cli(
			"review",
			"submit",
			"--uid",
			"6001",
			"--decision",
			"accept",
			"--reviewer-id",
			reviewer_id,
			"--reviewer-name",
			reviewer_name,
			"--notes",
			"dataset_export",
			"--reference-source",
			"line.csv",
		)
		segment_payload = {
			"segments": [
				{
					"id": "s1",
					"categoryId": "stay",
					"categoryName": "驻留",
					"startTime": 0,
					"endTime": 10_000,
				},
			],
		}
		self._run_cli(
			"timeline",
			"put",
			"--uid",
			"6001",
			"--reviewer-id",
			reviewer_id,
			"--reviewer-name",
			reviewer_name,
			"--payload-json",
			json.dumps(segment_payload, ensure_ascii=False),
		)
		out = self._run_cli(
			"bundle",
			"export",
			"--reviewer-id",
			reviewer_id,
			"--export-mode",
			"segment_label_dataset",
			"--bundle-name",
			"cli_seg_dataset",
			"--clean",
			"--create-zip",
			"--interval-seconds",
			"10",
			"--timestamp-unit",
			"seconds",
			"--labeled-span-only",
		)
		self.assertEqual(out["export_mode"], "segment_label_dataset")
		self.assertEqual(out["interval_seconds"], 10)
		self.assertEqual(out["timestamp_unit"], "seconds")
		self.assertTrue(out["labeled_span_only"])
		self.assertEqual(out["sample_count"], 1)
