from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML_PATH = WEB_ROOT / "index.html"
INDEX_CSS_PATH = WEB_ROOT / "styles" / "index.css"
BOOT_JS_PATH = WEB_ROOT / "app" / "runtime" / "boot.js"
RUNTIME_CONFIG_PATH = WEB_ROOT / "app" / "runtime" / "runtime_config.js"


class BasemapModeUiContractTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		cls.css = INDEX_CSS_PATH.read_text(encoding="utf-8")
		cls.boot_js = BOOT_JS_PATH.read_text(encoding="utf-8")
		cls.runtime_config = RUNTIME_CONFIG_PATH.read_text(encoding="utf-8")

	def test_basemap_panel_markup_exists_inside_map_tools_panel(self) -> None:
		self.assertIn('id="map-tools-panel"', self.html)
		self.assertIn('id="basemap-panel"', self.html)
		self.assertIn('id="basemap-mode-controls"', self.html)
		self.assertIn('id="basemap-mode-status"', self.html)

	def test_basemap_panel_styles_are_declared(self) -> None:
		self.assertIn("#basemap-mode-controls", self.css)
		self.assertIn(".basemap-mode-option", self.css)
		self.assertIn(".basemap-mode-option.active", self.css)
		self.assertIn('body[data-theme="night"] .basemap-mode-option', self.css)

	def test_bootstrap_renders_and_switches_basemap_mode(self) -> None:
		self.assertIn('const basemapModeControls = document.getElementById("basemap-mode-controls")', self.boot_js)
		self.assertIn("function renderBasemapModeControls()", self.boot_js)
		self.assertIn('applyBasemapMode(nextMode, { persist: true, keepView: true });', self.boot_js)

	def test_runtime_config_defines_three_tile_modes(self) -> None:
		self.assertIn('const TILE_MODE_STORAGE_KEY = "trajectoryStudioTileModeV1"', self.runtime_config)
		self.assertIn("online:", self.runtime_config)
		self.assertIn("offline:", self.runtime_config)
		self.assertIn("intranet:", self.runtime_config)


if __name__ == "__main__":
	unittest.main()
