from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML_PATH = WEB_ROOT / "index.html"
TRACK_INSPECTION_JS_PATH = WEB_ROOT / "app" / "features" / "track_inspection" / "track_inspection.js"
BOOT_JS_PATH = WEB_ROOT / "app" / "runtime" / "boot.js"
BOOTSTRAP_JS_PATH = WEB_ROOT / "app" / "studio_bootstrap.js"


class DateWindowQuickSegmentUiContractTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		cls.track_js = TRACK_INSPECTION_JS_PATH.read_text(encoding="utf-8")
		cls.boot_js = BOOT_JS_PATH.read_text(encoding="utf-8")
		cls.bootstrap_js = BOOTSTRAP_JS_PATH.read_text(encoding="utf-8")

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


if __name__ == "__main__":
	unittest.main()
