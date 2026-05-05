from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_PARENT = Path(__file__).resolve().parents[3]
if str(REPO_PARENT) not in os.sys.path:
	os.sys.path.insert(0, str(REPO_PARENT))

from trajectory_annotation_studio.scripts.studio_agent_segment_context import (
	BEIJING_OFFLINE_BBOX,
	SegmentContextError,
	discover_uid_csv_paths,
	downsample_coordinates,
	export_visual_context,
	load_materialized_context,
	parse_uid_csv,
	summarize_materialized_sample,
)


class StudioAgentSegmentContextTest(unittest.TestCase):
	def test_parse_csv_lat_lon_aliases_and_segments(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			p = Path(tmp) / "traj.csv"
			p.write_text(
				"uid,Lat,Lon,timestamp_ms,Status,Source\n"
				"u1,39.900,116.300,1000,stay,gps\n"
				"u1,39.901,116.301,2000,stay,gps\n"
				"u1,39.902,116.302,3000,move,gps\n"
				"u1,39.903,116.303,4000,move,od\n",
				encoding="utf-8",
			)
			layer = parse_uid_csv(p)
		self.assertEqual(layer["row_count"], 4)
		self.assertEqual(layer["parsed_points"], 4)
		self.assertEqual(layer["bounds"]["min_lat"], 39.9)
		self.assertEqual(layer["time_range"]["min"], 1000.0)
		self.assertEqual(layer["time_range"]["max"], 4000.0)
		segs = layer["status_segments"]
		self.assertEqual(len(segs), 2)
		self.assertEqual(segs[0]["status"], "stay")
		self.assertEqual(segs[0]["count"], 2)
		self.assertEqual(segs[1]["status"], "move")
		src = layer["source_segments"]
		self.assertEqual(src[-1]["source"], "od")
		self.assertEqual(src[-1]["count"], 1)

	def test_summarize_materialized_and_bbox_warning(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			uid_dir = root / "9001"
			uid_dir.mkdir()
			line = (
				"uid,latitude,longitude,timestamp_ms,status,source\n"
				"9001,20.0,100.0,1,a,b\n"
			)
			(uid_dir / "line.csv").write_text(line, encoding="utf-8")
			context = {
				"uid": "9001",
				"batch": "smoke",
				"tags": ["t1"],
				"files": [
					{"relative_path": "9001/line.csv", "exists": True},
				],
			}
			(root / "context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

			summary = summarize_materialized_sample(root)

		self.assertEqual(summary["uid"], "9001")
		self.assertEqual(summary["batch"], "smoke")
		self.assertIn("outside_offline_basemap_bbox", summary["warnings"])
		self.assertEqual(summary["aggregate"]["total_row_count"], 1)
		b = summary["aggregate"]["bounds"]
		self.assertEqual(b["min_lat"], 20.0)

	def test_downsample_coordinates(self) -> None:
		pts = [(float(i), 0.0) for i in range(100)]
		out = downsample_coordinates(pts, 10)
		self.assertEqual(len(out), 10)
		self.assertEqual(out[-1], [99.0, 0.0])

	def test_discover_fallback_glob(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			(root / "x.csv").write_text("lat,lon\n1,2\n", encoding="utf-8")
			context: dict = {"files": []}
			paths = discover_uid_csv_paths(root, context)
		self.assertEqual(len(paths), 1)

	def test_missing_context_raises(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			with self.assertRaises(SegmentContextError):
				load_materialized_context(root)

	def test_export_visual_context_files(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			uid_dir = root / "6001"
			uid_dir.mkdir()
			(uid_dir / "line.csv").write_text(
				"uid,latitude,longitude,timestamp_ms,status,source\n"
				"6001,39.9,116.3,1,stay,gps\n"
				"6001,39.905,116.305,2,stay,gps\n",
				encoding="utf-8",
			)
			context = {
				"uid": "6001",
				"batch": "b0",
				"tags": [],
				"files": [{"relative_path": "6001/line.csv", "exists": True}],
			}
			(root / "context.json").write_text(json.dumps(context), encoding="utf-8")
			out_dir = root / "out"
			base = "http://127.0.0.1:8016"
			result = export_visual_context(root, out_dir, base_url=base)

			self.assertTrue(Path(result["visual_context_path"]).is_file())
			self.assertTrue(Path(result["index_html_path"]).is_file())
			payload = json.loads(Path(result["visual_context_path"]).read_text(encoding="utf-8"))
			self.assertEqual(payload["tile_url_template"], f"{base}/offline_tiles/beijing/{{z}}/{{x}}/{{y}}.png")
			self.assertIn("/web/vendor/leaflet/leaflet.js", payload["leaflet_js_url"])
			self.assertEqual(payload["basemap"]["mode"], "offline_tiles")
			self.assertTrue(any(layer.get("geojson") for layer in payload["layers"]))
			html = Path(result["index_html_path"]).read_text(encoding="utf-8")
			self.assertIn("L.tileLayer", html)
			self.assertIn(payload["tile_url_template"], html)
			self.assertNotIn(".svg", html.lower())


if __name__ == "__main__":
	unittest.main()
