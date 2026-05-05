from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML_PATH = WEB_ROOT / "index.html"
STATE_JS_PATH = WEB_ROOT / "app" / "runtime" / "state.js"
BOOTSTRAP_JS_PATH = WEB_ROOT / "app" / "studio_bootstrap.js"
FOUNDATION_JS_PATH = WEB_ROOT / "app" / "runtime" / "foundation.js"
BOOT_JS_PATH = WEB_ROOT / "app" / "runtime" / "boot.js"
TRACK_INSPECTION_JS_PATH = WEB_ROOT / "app" / "features" / "track_inspection" / "track_inspection.js"


class TrackEditUiContractTest(unittest.TestCase):
	def test_index_html_exposes_track_edit_controls(self) -> None:
		html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		for required_id in [
			'review-mode-switch',
			'review-mode-annotation-btn',
			'track-edit-panel',
			'track-edit-toggle',
			'track-edit-undo-btn',
			'track-edit-redo-btn',
			'track-edit-save-btn',
			'track-edit-save-options-btn',
			'track-edit-save-menu',
			'track-edit-save-overwrite',
			'track-edit-save-download',
			'track-edit-clear-selection',
			'track-edit-show-coordinates',
			'track-edit-coordinate-summary',
			'track-edit-status',
			'track-edit-selection',
			'track-edit-context-menu',
			'track-edit-context-value',
			'track-edit-context-apply',
			'track-edit-context-close',
		]:
			self.assertIn(f'id="{required_id}"', html)

	def test_runtime_state_and_bootstrap_expose_track_edit_storage_and_state(self) -> None:
		bootstrap_js = BOOTSTRAP_JS_PATH.read_text(encoding="utf-8")
		foundation_js = FOUNDATION_JS_PATH.read_text(encoding="utf-8")
		state_js = STATE_JS_PATH.read_text(encoding="utf-8")

		self.assertIn('const TRACK_EDITS_STORAGE_KEY = "trajectoryTrackEditsV1";', bootstrap_js)
		self.assertIn("TRACK_EDITS_STORAGE_KEY", foundation_js)
		self.assertIn("trackEditsByTrack = loadTimelineAnnotationStore(TRACK_EDITS_STORAGE_KEY)", state_js)
		self.assertIn("let trackEditState = {", state_js)
		self.assertIn("renderedMarkersByPointId", state_js)
		self.assertIn('const normalizedBase = String(REVIEW_API_BASE || "/api").trim() || "/api";', foundation_js)
		self.assertIn('const trimmedBase = normalizedBase.replace(/\\/+$/, "");', foundation_js)
		self.assertIn("return url.origin === window.location.origin", foundation_js)

	def test_track_inspection_exports_track_edit_runtime_helpers(self) -> None:
		js = TRACK_INSPECTION_JS_PATH.read_text(encoding="utf-8")
		for symbol in [
			"function loadTrackEditsForUid(",
			"function applyCurrentTrackEditsToCurrentData(",
			"function upsertCurrentTrackEditPatches(",
			"function renderEditableTrackLayer(",
			"function toggleTrackEditMode(",
			"function undoTrackEditChange(",
			"function redoTrackEditChange(",
			"function saveCurrentTrackEdits(",
			"function downloadCurrentTrackEditsAsJson(",
			"function setTrackEditSpaceModifierActive(",
			"function syncTrackEditMapInteractionLock(",
			"function applyTrackEditMetadataPatch(",
			"function selectTrackEditPoint(",
		]:
			self.assertIn(symbol, js)

	def test_boot_script_wires_track_edit_controls(self) -> None:
		js = BOOT_JS_PATH.read_text(encoding="utf-8")
		for snippet in [
			'const trackEditToggle = document.getElementById("track-edit-toggle");',
			'const reviewModeAnnotationButton = document.getElementById("review-mode-annotation-btn");',
			'const trackEditUndoButton = document.getElementById("track-edit-undo-btn");',
			'const trackEditSaveOptionsButton = document.getElementById("track-edit-save-options-btn");',
			'const trackEditContextMenu = document.getElementById("track-edit-context-menu");',
			'const trackEditSaveMenu = document.getElementById("track-edit-save-menu");',
			'trackEditToggle?.addEventListener("click", () => {',
			'reviewModeAnnotationButton?.addEventListener("click", () => {',
			'trackEditUndoButton?.addEventListener("click", () => {',
			'trackEditSaveOptionsButton?.addEventListener("click", (event) => {',
			'trackEditContextApply?.addEventListener("click", () => {',
			'closeTrackEditContextMenu();',
			'downloadCurrentTrackEditsAsJson();',
			'setTrackEditSpaceModifierActive(true);',
		]:
			self.assertIn(snippet, js)


if __name__ == "__main__":
	unittest.main()
