from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML_PATH = WEB_ROOT / "index.html"
TRACK_INSPECTION_JS_PATH = WEB_ROOT / "app" / "features" / "track_inspection" / "track_inspection.js"
BOOT_JS_PATH = WEB_ROOT / "app" / "runtime" / "boot.js"
BOOTSTRAP_JS_PATH = WEB_ROOT / "app" / "studio_bootstrap.js"
STATE_JS_PATH = WEB_ROOT / "app" / "runtime" / "state.js"
WORKSPACE_JS_PATH = WEB_ROOT / "app" / "features" / "workspace" / "workspace.js"


class DateWindowQuickSegmentUiContractTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		cls.track_js = TRACK_INSPECTION_JS_PATH.read_text(encoding="utf-8")
		cls.boot_js = BOOT_JS_PATH.read_text(encoding="utf-8")
		cls.bootstrap_js = BOOTSTRAP_JS_PATH.read_text(encoding="utf-8")
		cls.state_js = STATE_JS_PATH.read_text(encoding="utf-8")
		cls.workspace_js = WORKSPACE_JS_PATH.read_text(encoding="utf-8")

	def test_date_window_markup_exposes_span_and_quick_segment_controls(self) -> None:
		self.assertIn('id="date-window-fixed-span"', self.html)
		self.assertIn('id="date-window-quick-category"', self.html)
		self.assertIn('id="date-window-quick-toggle"', self.html)
		self.assertIn('id="date-window-quick-status"', self.html)
		self.assertIn("跨度", self.html)
		self.assertIn("整段标记", self.html)

	def test_track_inspection_contains_window_quick_segment_logic(self) -> None:
		self.assertIn("function setCurrentTimeWindowFixedSpanDays", self.track_js)
		self.assertIn("function toggleCurrentWindowQuickSegment", self.track_js)
		self.assertIn("function autoSelectAcceptDecisionAfterAnnotation", self.track_js)
		self.assertIn('setDecisionButtons("accept")', self.track_js)
		self.assertIn('entryMode: "window_quick"', self.track_js)
		self.assertIn('segmentScope: "date_window"', self.track_js)
		self.assertIn("windowStartDay", self.track_js)
		self.assertIn("windowEndDay", self.track_js)
		self.assertIn("fixedSpanDays", self.track_js)

	def test_bootstrap_help_mentions_span_and_quick_segment(self) -> None:
		self.assertIn("日期窗口快标", self.bootstrap_js)
		self.assertIn("跨度 x 天", self.bootstrap_js)
		self.assertIn("整段标记", self.bootstrap_js)

	def test_boot_wires_new_controls(self) -> None:
		self.assertIn('document.getElementById("date-window-fixed-span")', self.boot_js)
		self.assertIn('document.getElementById("date-window-quick-category")', self.boot_js)
		self.assertIn('document.getElementById("date-window-quick-toggle")', self.boot_js)
		self.assertIn("setCurrentTimeWindowFixedSpanDays", self.boot_js)
		self.assertIn("toggleCurrentWindowQuickSegment", self.boot_js)

	def test_annotation_settings_exposes_review_shortcuts(self) -> None:
		self.assertIn('id="annotation-shortcut-list"', self.html)
		self.assertIn("标记快捷键", self.html)
		self.assertIn("function renderAnnotationShortcutList", self.track_js)
		self.assertIn("function handleReviewShortcutKeyboardEvent", self.track_js)
		self.assertIn("function buildReviewChordBindingFromKeyboardEvent", self.track_js)
		self.assertIn("function isKeyboardTargetBlockingReviewShortcuts", self.track_js)
		self.assertIn("reviewShortcuts", self.track_js)
		self.assertIn("handleReviewShortcutKeyboardEvent", self.boot_js)
		self.assertIn("isKeyboardTargetBlockingReviewShortcuts", self.boot_js)

	def test_workspace_respects_batch_hide_review_panel(self) -> None:
		workspace_js = (WEB_ROOT / "app" / "features" / "workspace" / "workspace.js").read_text(encoding="utf-8")
		review_flow_js = (WEB_ROOT / "app" / "features" / "review_flow" / "review_flow.js").read_text(encoding="utf-8")
		self.assertIn("batchUiConfig?.hide_review_panel", workspace_js)
		self.assertNotIn("currentUiConfig.hideReviewPanel = false;", workspace_js)
		self.assertIn('classList.toggle("review-panel-hidden"', review_flow_js)

	def test_review_panel_defaults_collapsed(self) -> None:
		self.assertIn('id="review-panel" class="collapsed"', self.html)
		self.assertIn('id="review-panel-toggle" class="review-panel-toggle" type="button">展开</button>', self.html)
		self.assertIn("let reviewPanelCollapsed = true;", self.state_js)

	def test_signal_popup_prefers_display_end_time(self) -> None:
		self.assertIn("row.display_t_out", self.track_js)
		self.assertLess(self.track_js.index("row.display_t_out"), self.track_js.index("row.t_out"))

	def test_map_bounds_skip_unrenderable_bucket_and_od_coordinates(self) -> None:
		self.assertIn("if (!isRenderableCoordinate(lat, lon)) return;", self.track_js)
		self.assertIn("if (!isRenderableCoordinate(slat, slon)) continue;", self.track_js)
		self.assertIn("if (isRenderableCoordinate(elat, elon))", self.track_js)

	def test_gps_comparison_panel_follows_gps_layer_visibility(self) -> None:
		self.assertIn("function getGpsTruthLayerKeysForComparison", self.workspace_js)
		self.assertIn("function isGpsTruthLayerVisibleForComparison", self.workspace_js)
		self.assertIn('directGpsInput.checked', self.workspace_js)
		self.assertIn('controlsRoot.querySelectorAll(".layer-row[data-layer]")', self.workspace_js)
		self.assertIn('input[data-opt="visible"]', self.workspace_js)
		self.assertIn("if (!isGpsTruthLayerVisibleForComparison())", self.workspace_js)
		self.assertIn('detailEl.textContent = "GPS 真值轨迹图层已关闭";', self.workspace_js)
		self.assertIn('layer === "gps" || (layerConfig[layer] || {}).kind === "gps"', self.track_js)
		self.assertIn("renderGpsComparisonPanel(currentUid);", self.track_js)

	def test_time_scrubber_uses_compact_flat_layout(self) -> None:
		self.assertNotIn('id="time-scrubber-segment-row"', self.html)
		self.assertNotIn('id="time-scrubber-segment-canvas"', self.html)
		self.assertNotIn('id="time-scrubber-segment-detail"', self.html)
		self.assertIn('id="time-scrubber-canvas"', self.html)
		self.assertIn('id="time-scrubber-overview-canvas"', self.html)
		self.assertIn("function drawTimeScrubberCanvas", self.track_js)
		self.assertIn("function drawTimeScrubberOverviewCanvas", self.track_js)

	def test_exclusive_segment_boundary_helpers_exist(self) -> None:
		self.assertIn("function normalizeExclusiveTimelineSegments", self.track_js)
		self.assertIn("existingSegment.endTime", self.track_js)
		self.assertIn("function timelineSegmentContainsTime", self.track_js)
		self.assertIn("targetTime > segment.startTime", self.track_js)
		self.assertIn("laneEnds[laneIndex] = segment.endTime;", self.track_js)


if __name__ == "__main__":
	unittest.main()
