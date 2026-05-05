from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO_PARENT = Path(__file__).resolve().parents[3]
if str(REPO_PARENT) not in os.sys.path:
	os.sys.path.insert(0, str(REPO_PARENT))

from trajectory_annotation_studio.scripts.studio_agent_timeline_validation import (
	validate_timeline_payload,
)


def _minimal_segment(**extra: object) -> dict:
	base = {
		"startTime": 0.0,
		"endTime": 10.0,
		"categoryId": "leg",
		"reconstructionQuality": "accurate",
	}
	base.update(extra)
	return base


class ValidateTimelinePayloadTest(unittest.TestCase):
	def test_ok_minimal(self) -> None:
		payload = {"segments": [_minimal_segment()]}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"])
		self.assertEqual(r["errors"], [])
		self.assertEqual(r["segment_count"], 1)
		self.assertEqual(r["track_edit_ref_count"], 0)

	def test_ok_semantic_tags_instead_of_category(self) -> None:
		payload = {
			"segments": [
				{
					"startTime": 1,
					"endTime": 2,
					"semanticTags": ["mode:walk", "chain:home-work"],
					"reconstructionQuality": "uncertain",
				},
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])

	def test_ok_inaccurate_with_evidence(self) -> None:
		payload = {
			"segments": [
				_minimal_segment(
					reconstructionQuality="inaccurate",
					evidence={"summary": "gap"},
				),
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])

	def test_ok_inaccurate_with_track_edit_refs(self) -> None:
		payload = {
			"segments": [
				_minimal_segment(
					reconstructionQuality="INACCURATE",
					trackEditRefs=["edit-1"],
				),
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])
		self.assertEqual(r["track_edit_ref_count"], 1)

	def test_track_edit_ref_count_unique_across_segments(self) -> None:
		payload = {
			"segments": [
				_minimal_segment(trackEditRefs=["a", "b"]),
				_minimal_segment(
					startTime=20,
					endTime=30,
					trackEditRefs=["b", "c"],
				),
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])
		self.assertEqual(r["track_edit_ref_count"], 3)

	def test_payload_not_object(self) -> None:
		r = validate_timeline_payload([])
		self.assertFalse(r["ok"])
		self.assertIn("JSON object", r["errors"][0])

	def test_segments_not_list(self) -> None:
		r = validate_timeline_payload({"segments": {}})
		self.assertFalse(r["ok"])
		self.assertTrue(any("must be a list" in e for e in r["errors"]))

	def test_segments_null(self) -> None:
		r = validate_timeline_payload({"segments": None})
		self.assertFalse(r["ok"])
		self.assertTrue(any("null" in e for e in r["errors"]))

	def test_segment_not_object(self) -> None:
		r = validate_timeline_payload({"segments": [1]})
		self.assertFalse(r["ok"])
		self.assertTrue(any("must be an object" in e for e in r["errors"]))

	def test_time_order(self) -> None:
		r = validate_timeline_payload(
			{"segments": [_minimal_segment(startTime=5, endTime=3)]},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("start < end" in e for e in r["errors"]))

	def test_missing_bounds(self) -> None:
		r = validate_timeline_payload(
			{"segments": [{"categoryId": "x"}]},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("startTime/endTime" in e for e in r["errors"]))

	def test_start_end_alias(self) -> None:
		payload = {
			"segments": [
				{
					"start": 0,
					"end": 1,
					"categoryName": "trip",
					"accuracyLabel": "review_needed",
				},
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])

	def test_start_start_time_disagree_warns(self) -> None:
		payload = {
			"segments": [
				{
					"startTime": 0,
					"start": 1,
					"endTime": 2,
					"categoryId": "a",
				},
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])
		self.assertTrue(any("disagree" in w for w in r["warnings"]))

	def test_missing_category_and_tags(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					{"startTime": 0, "endTime": 1},
				],
			},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("semanticTags" in e for e in r["errors"]))

	def test_semantic_tags_wrong_type(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					{
						"startTime": 0,
						"endTime": 1,
						"semanticTags": "not-a-list",
					},
				],
			},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("semanticTags" in e for e in r["errors"]))

	def test_quality_alias_needs_review(self) -> None:
		payload = {
			"segments": [
				_minimal_segment(reconstructionQuality="needs-review", categoryId="x"),
			],
		}
		r = validate_timeline_payload(payload)
		self.assertTrue(r["ok"], r["errors"])

	def test_invalid_quality(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					_minimal_segment(reconstructionQuality="bogus"),
				],
			},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("accurate" in e for e in r["errors"]))

	def test_confidence_bounds(self) -> None:
		ok = validate_timeline_payload(
			{"segments": [_minimal_segment(confidence=0.5)]},
		)
		self.assertTrue(ok["ok"], ok["errors"])
		bad = validate_timeline_payload(
			{"segments": [_minimal_segment(confidence=1.5)]},
		)
		self.assertFalse(bad["ok"])

	def test_confidence_string_ok(self) -> None:
		r = validate_timeline_payload(
			{"segments": [_minimal_segment(confidence="0.25")]},
		)
		self.assertTrue(r["ok"], r["errors"])

	def test_inaccurate_without_evidence_or_refs(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					_minimal_segment(
						categoryId="c",
						reconstructionQuality="inaccurate",
					),
				],
			},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("inaccurate" in e for e in r["errors"]))

	def test_inaccurate_empty_evidence_fails(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					_minimal_segment(
						reconstructionQuality="inaccurate",
						evidence={},
					),
				],
			},
		)
		self.assertFalse(r["ok"])

	def test_duplicate_track_edit_refs(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					_minimal_segment(trackEditRefs=["x", "x"]),
				],
			},
		)
		self.assertFalse(r["ok"])
		self.assertTrue(any("unique" in e for e in r["errors"]))

	def test_accurate_inaccurate_disagree_warning(self) -> None:
		r = validate_timeline_payload(
			{
				"segments": [
					{
						"startTime": 0,
						"endTime": 1,
						"categoryId": "c",
						"reconstructionQuality": "accurate",
						"accuracyLabel": "inaccurate",
						"evidence": {"k": "v"},
						"trackEditRefs": ["e1"],
					},
				],
			},
		)
		self.assertTrue(r["ok"], r["errors"])
		self.assertTrue(any("disagree" in w for w in r["warnings"]))

	def test_sample_summary_segment_count_warning(self) -> None:
		payload = {"segments": [_minimal_segment()]}
		r = validate_timeline_payload(payload, sample_summary={"segment_count": 2})
		self.assertTrue(r["ok"], r["errors"])
		self.assertTrue(any("sample_summary" in w for w in r["warnings"]))


if __name__ == "__main__":
	unittest.main()
