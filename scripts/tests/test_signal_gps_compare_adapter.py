from __future__ import annotations

import csv
import json
import argparse
import tempfile
import unittest
from pathlib import Path

from adapters.signal_gps_compare import build_batch
from adapters.signal_gps_compare import build_v311_comparison_batch
from scripts import run_signal6_v311_demo


class SignalGpsCompareAdapterTest(unittest.TestCase):
	def test_v311_mixed_csv_kml_truth_assigns_kml_to_latest_signal_segments(self) -> None:
		def recon(name: str, lon: float, lat: float) -> build_batch.Reconstruction:
			return build_batch.Reconstruction(
				path=Path(name),
				points=[build_batch.Point(lat=lat, lon=lon), build_batch.Point(lat=lat + 0.001, lon=lon + 0.001)],
				source_xy=[(lon, lat), (lon + 0.001, lat + 0.001)],
			)

		def signal(name: str, lon: float, lat: float) -> build_batch.GpsTrack:
			return build_batch.GpsTrack(
				path=Path(name),
				points=[build_batch.Point(lat=lat, lon=lon), build_batch.Point(lat=lat + 0.001, lon=lon + 0.001)],
				source_times=[],
				source_time_ms=[],
				start_ms=None,
				end_ms=None,
				declared_start_ms=None,
				declared_end_ms=None,
			)

		truths = [
			recon("old_a.csv", 116.30, 39.90),
			recon("old_b.csv", 116.40, 39.90),
			# Deliberately geometrically closer to old_a; the mixed-source rule should still reserve
			# KML truth for the newest signal segment when CSV and KML truths are present together.
			recon("2026-06-02 0751北京城区东城区到海淀区.kml", 116.30, 39.90),
		]
		signals = [
			signal("202605291922-1957（测试1）青年湖-西站.csv", 116.30, 39.90),
			signal("202605292018-2036（测试2）西站-苏州桥.csv", 116.40, 39.90),
			signal("202606020751-0828（西站）.csv", 116.50, 39.90),
		]

		assignments = build_v311_comparison_batch.assign_truth_tracks_to_signal_tracks(truths, signals)

		self.assertEqual(
			assignments["202606020751-0828（西站）.csv"].path.name,
			"2026-06-02 0751北京城区东城区到海淀区.kml",
		)
		self.assertTrue(assignments["202605291922-1957（测试1）青年湖-西站.csv"].path.name.endswith(".csv"))
		self.assertTrue(assignments["202605292018-2036（测试2）西站-苏州桥.csv"].path.name.endswith(".csv"))

	def test_signal6_v311_demo_disables_subway_fmm_matching(self) -> None:
		options = run_signal6_v311_demo.default_pipeline_options()
		self.assertEqual(options.get("fmm_version"), "original")
		variant_params = options.get("fmm_variant_params")
		self.assertIsInstance(variant_params, dict)
		subway_params = variant_params.get("subway")
		self.assertIsInstance(subway_params, dict)
		self.assertLessEqual(float(subway_params["r"]), 0.0)

	def test_signal6_v311_demo_mainroad_fmm_switch(self) -> None:
		options = run_signal6_v311_demo.default_pipeline_options(fmm_version="mainroad")
		self.assertEqual(options.get("fmm_version"), "mainroad")
		variant_params = options.get("fmm_variant_params")
		self.assertIsInstance(variant_params, dict)
		road_params = variant_params.get("road")
		self.assertIsInstance(road_params, dict)
		self.assertAlmostEqual(float(road_params["reverse_tolerance"]), 0.05)
		self.assertGreater(float(road_params["ubodt_delta_multiplier"]), 1.0)
		self.assertLessEqual(float(variant_params["subway"]["r"]), 0.0)
		self.assertLessEqual(float(variant_params["railway"]["r"]), 0.0)

	def test_v311_comparison_batch_collects_mainroad_fmm_metadata(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			result_root = root / "result"
			result_root.mkdir()
			(result_root / "manifest.json").write_text(
				json.dumps(
					{
						"fmm_version": "mainroad",
						"fmm_network_cost_field": "fmm_cost",
						"fmm_edges": "/tmp/mainroad_edges.shp",
					}
				),
				encoding="utf-8",
			)
			(root / "variant_config.json").write_text(
				json.dumps(
					{
						"name": "mainroad_weighted",
						"description": "weighted",
						"options": {
							"fmm_version": "mainroad",
							"fmm_variant_params": {
								"road": {
									"r": 0.018,
									"k": 512,
									"error": 0.008,
									"reverse_tolerance": 0.05,
									"ubodt_delta_multiplier": 1.35,
								}
							},
						},
						"speed_cost_rule": {
							"mainroad_limit_kmh": 80,
							"smallroad_limit_kmh": 20,
						},
						"speed_sparsity_road_class_prior": {
							"formula": "major_bias = speed_score * sparsity_score",
							"selected_major_routes": ["route_04", "route_06", "route_07", "route_08"],
						},
						"route02_startfix": {
							"dropped_snap_indices": [3, 4, 5, 6],
						},
					}
				),
				encoding="utf-8",
			)

			metadata = build_v311_comparison_batch.collect_v311_algorithm_metadata(result_root)

			self.assertEqual(metadata["fmm_version"], "mainroad")
			self.assertEqual(metadata["fmm_network_cost_field"], "fmm_cost")
			self.assertEqual(metadata["variant_name"], "mainroad_weighted")
			self.assertEqual(metadata["mechanism"]["network_cost_field"], "fmm_cost")
			self.assertEqual(metadata["speed_cost_rule"]["smallroad_limit_kmh"], 20)
			self.assertEqual(metadata["speed_sparsity_road_class_prior"]["selected_major_routes"], ["route_04", "route_06", "route_07", "route_08"])
			self.assertEqual(metadata["route02_startfix"]["dropped_snap_indices"], [3, 4, 5, 6])
			self.assertIn("highway_penalties", metadata["mechanism"])
			self.assertIn("original geometric", metadata["mechanism"]["summary"])

	def test_v311_lbs_sampling_is_sparse_stable_and_uid_varied(self) -> None:
		def make_points(count: int) -> list[build_batch.Point]:
			return [build_batch.Point(lat=39.9, lon=116.3 + index * 0.001) for index in range(count)]

		def road_rows(count: int) -> list[dict[str, str]]:
			return [{"matched": "1", "truth_segment_index": str(index)} for index in range(count - 1)]

		def segment_summary(uid: str, points: list[build_batch.Point]) -> tuple[list[dict[str, object]], list[float], float]:
			rows = build_v311_comparison_batch.build_lbs_rows(
				uid,
				points,
				road_rows(len(points)),
				None,
				None,
				"gps.csv",
			)
			segments: dict[str, dict[str, object]] = {}
			for row in rows:
				segment = segments.setdefault(
					row["segment_id"],
					{"length": float(row["segment_length_m"]), "indices": []},
				)
				segment["indices"].append(int(row["source_gps_index"]))  # type: ignore[index]
			lengths = [float(item["length"]) for item in segments.values()]
			covered = sum(lengths)
			total = sum(
				build_v311_comparison_batch.distance_m(points[index], points[index + 1])
				for index in range(len(points) - 1)
			)
			return list(segments.values()), lengths, covered / total if total else 0.0

		short_points = make_points(120)
		short_segments, short_lengths, short_fraction = segment_summary("route_01_short", short_points)
		self.assertEqual(len(short_segments), 1)
		self.assertLessEqual(short_fraction, 0.10)
		self.assertTrue(all(120.0 <= length <= 560.0 for length in short_lengths))

		long_points = make_points(260)
		long_segments, long_lengths, long_fraction = segment_summary("route_03_long", long_points)
		self.assertEqual(len(long_segments), 2)
		self.assertLessEqual(long_fraction, 0.10)
		self.assertTrue(all(120.0 <= length <= 560.0 for length in long_lengths))

		repeated_segments, repeated_lengths, repeated_fraction = segment_summary("route_03_long", long_points)
		self.assertEqual(long_lengths, repeated_lengths)
		self.assertEqual(long_fraction, repeated_fraction)
		self.assertEqual([item["indices"] for item in long_segments], [item["indices"] for item in repeated_segments])

		other_segments, other_lengths, _other_fraction = segment_summary("route_04_long", long_points)
		self.assertNotEqual(
			([item["indices"] for item in long_segments], long_lengths),
			([item["indices"] for item in other_segments], other_lengths),
		)

	def test_build_batch_matches_gps_and_writes_comparison_manifest(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			signal_dir = root / "signal"
			gps_dir = root / "gps"
			batch_root = root / "batch"
			signal_dir.mkdir()
			gps_dir.mkdir()

			# Baidu Mercator coordinates near Beijing West Railway Station.
			(signal_dir / "recon.csv").write_text(
				"12950309.702371,4824059.555928,0,0,0\n"
				"12950291.820406,4824058.382705,0,0,0\n",
				encoding="utf-8",
			)
			with (gps_dir / "gps.csv").open("w", encoding="utf-8", newline="") as handle:
				writer = csv.writer(handle)
				writer.writerow(["20260529201102\t", "116.32675\t", "39.89637\t"])
				writer.writerow(["20260529201103\t", "116.32660\t", "39.89636\t"])

			original_parse_args = build_batch.parse_args
			try:
				build_batch.parse_args = lambda: argparse.Namespace(
					signal_dir=signal_dir,
					gps_dir=gps_dir,
					output_batch_root=batch_root,
					batch_name="demo",
					label="Demo",
					threshold_meters=300.0,
					synthetic_step_ms=1000,
					force=False,
					raw_signal_csv=Path(""),
				)
				build_batch.main()
			finally:
				build_batch.parse_args = original_parse_args

			manifest = json.loads((batch_root / "result" / "manifest.json").read_text(encoding="utf-8"))
			self.assertEqual(manifest["layers"], ["signal", "reconstruction", "gps"])
			self.assertIn("gps_comparison", manifest)
			self.assertIsInstance(manifest["gps_comparison"]["overall_accuracy_percent"], float)
			self.assertIn("WGS84 -> GCJ-02", manifest["gps_comparison"]["coordinate_system"])
			uid = manifest["uids"][0]
			self.assertTrue((batch_root / "result" / uid / "signal.csv").exists())
			self.assertTrue((batch_root / "result" / uid / "reconstruction.csv").exists())
			self.assertTrue((batch_root / "result" / uid / "gps_compare_segments.csv").exists())


if __name__ == "__main__":
	unittest.main()
