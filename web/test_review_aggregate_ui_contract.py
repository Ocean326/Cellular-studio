from __future__ import annotations

import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
INDEX_HTML = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
STYLES_CSS = (WEB_ROOT / "styles" / "index.css").read_text(encoding="utf-8")


class ReviewAggregateUiContractTest(unittest.TestCase):
	def test_review_aggregate_panel_markup_exists(self) -> None:
		self.assertIn('id="review-aggregate-panel"', INDEX_HTML)
		self.assertIn('id="review-aggregate-list"', INDEX_HTML)
		self.assertNotIn('id="review-aggregate-panel" class="collapsed" aria-hidden="true"', INDEX_HTML)

	def test_review_aggregate_panel_is_not_hard_hidden(self) -> None:
		self.assertNotIn(
			"#review-aggregate-panel {\n\t\t\tdisplay: none !important;",
			STYLES_CSS,
		)


if __name__ == "__main__":
	unittest.main()
