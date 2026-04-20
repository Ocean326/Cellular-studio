from __future__ import annotations

import unittest
from pathlib import Path


INDEX_HTML_PATH = Path(__file__).resolve().parent / "index.html"
INDEX_CSS_PATH = Path(__file__).resolve().parent / "styles" / "index.css"
STUDIO_MANAGEMENT_JS_PATH = Path(__file__).resolve().parent / "app" / "features" / "studio_admin" / "studio_management.js"
STUDIO_MANAGEMENT_CORE_PATH = Path(__file__).resolve().parent / "app" / "features" / "studio_admin" / "studio_management_core.js"


class StudioManagementUiContractTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		cls.css = INDEX_CSS_PATH.read_text(encoding="utf-8")
		cls.studio_management_js = STUDIO_MANAGEMENT_JS_PATH.read_text(encoding="utf-8")
		cls.core_js = STUDIO_MANAGEMENT_CORE_PATH.read_text(encoding="utf-8")

	def test_right_edge_entry_button_and_help_popover_exist(self) -> None:
		self.assertIn('id="studio-management-entry"', self.html)
		self.assertIn("#studio-management-entry {", self.css)
		self.assertRegex(self.css, r"#studio-management-entry\s*\{[^}]*position:\s*fixed;")
		self.assertRegex(self.css, r"#studio-management-entry\s*\{[^}]*right:\s*14px;")
		self.assertRegex(self.css, r"#studio-management-entry\s*\{[^}]*top:\s*50%;")
		self.assertIn('id="studio-management-custom-fields-toggle"', self.html)
		self.assertIn('id="studio-management-custom-fields"', self.html)
		self.assertIn('id="studio-management-help-anchor"', self.html)
		self.assertIn('id="studio-management-help-trigger"', self.html)
		self.assertIn('id="studio-management-help-popover"', self.html)
		self.assertIn('aria-controls="studio-management-help-popover"', self.html)
		self.assertIn('aria-expanded="false"', self.html)
		self.assertIn(">说明<", self.html)
		self.assertIn("studio-management-help-popover collapsed", self.html)
		self.assertIn('./app/features/studio_admin/studio_management_core.js', self.html)

	def test_progress_panel_dom_and_logic_exist(self) -> None:
		self.assertIn('id="studio-management-progress"', self.html)
		self.assertIn('id="studio-management-progress-bar"', self.html)
		self.assertIn("function renderStudioManagementProgress()", self.studio_management_js)
		self.assertIn("function startStudioManagementProcessProgress", self.studio_management_js)
		self.assertIn("function renderStudioManagementCustomFields()", self.studio_management_js)
		self.assertIn("function setStudioManagementHelpVisibility", self.studio_management_js)
		self.assertIn("function uploadStudioManagementBlob", self.studio_management_js)
		self.assertIn("function isStudioManagementVisibleUpload", self.studio_management_js)
		self.assertIn('xhr.upload.addEventListener("progress"', self.core_js)
		self.assertIn("modules.studioAdminCore = Object.freeze", self.core_js)

	def test_help_copy_mentions_casefold_and_signal_rules(self) -> None:
		self.assertIn("字段名大小写不敏感", self.core_js)
		self.assertIn("北京范围", self.core_js)
		self.assertIn("lat 39.4~41.1，lon 115.7~117.4", self.core_js)
		self.assertIn("多个 uid", self.core_js)
		self.assertIn("proceduereEndTime", self.core_js)
		self.assertIn(".studio-management-custom-fields-grid", self.css)
		self.assertIn(".studio-management-help-alias", self.css)


if __name__ == "__main__":
	unittest.main()
