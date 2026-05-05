from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML_PATH = WEB_ROOT / "index.html"
INDEX_CSS_PATH = WEB_ROOT / "styles" / "index.css"
BOOT_JS_PATH = WEB_ROOT / "app" / "runtime" / "boot.js"


class ThemeModeUiContractTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
		cls.css = INDEX_CSS_PATH.read_text(encoding="utf-8")
		cls.boot_js = BOOT_JS_PATH.read_text(encoding="utf-8")

	def test_theme_toggle_markup_is_present_in_floating_stack(self) -> None:
		self.assertIn('id="floating-tools-stack"', self.html)
		self.assertIn('id="theme-mode-toggle"', self.html)
		self.assertIn('id="theme-mode-label"', self.html)
		self.assertIn('data-label="夜景"', self.html)
		self.assertIn('aria-pressed="false"', self.html)

	def test_css_contains_midnight_glass_theme_overrides(self) -> None:
		self.assertIn("--font-ui:", self.css)
		self.assertIn("--font-display:", self.css)
		self.assertIn("#theme-mode-toggle.active", self.css)
		self.assertIn('body[data-theme="night"] {', self.css)
		self.assertIn('body[data-theme="night"] #map .leaflet-tile-pane', self.css)
		self.assertIn('body[data-theme="night"] #review-panel', self.css)

	def test_bootstrap_persists_and_applies_theme_mode(self) -> None:
		self.assertIn('const THEME_MODE_STORAGE_KEY = "studioThemeMode"', self.boot_js)
		self.assertIn('const themeModeToggle = document.getElementById("theme-mode-toggle")', self.boot_js)
		self.assertIn('document.body.dataset.theme = themeMode', self.boot_js)
		self.assertIn('localStorage.setItem(THEME_MODE_STORAGE_KEY, themeMode)', self.boot_js)
		self.assertIn('themeModeToggle.addEventListener("click"', self.boot_js)


if __name__ == "__main__":
	unittest.main()
