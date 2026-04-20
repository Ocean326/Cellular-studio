from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AdapterTemplateTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name)
		self.repo_root = Path(__file__).resolve().parents[2]
		self.script_path = self.repo_root / "adapters" / "template" / "build_batch.py"
		self.example_input = self.repo_root / "adapters" / "template" / "examples" / "source_records.example.json"

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def test_template_builds_minimal_batch(self) -> None:
		output_root = self.root / "template_batch"
		result = subprocess.run(
			[
				sys.executable,
				str(self.script_path),
				"--input-json",
				str(self.example_input),
				"--output-batch-root",
				str(output_root),
				"--batch-name",
				"template_demo",
			],
			check=True,
			capture_output=True,
			text=True,
		)

		payload = json.loads(result.stdout)
		manifest = json.loads((output_root / "result" / "manifest.json").read_text(encoding="utf-8"))
		states_index = json.loads((output_root / "result" / "states_index.json").read_text(encoding="utf-8"))
		batch_meta = json.loads((output_root / "batch_meta.json").read_text(encoding="utf-8"))

		self.assertEqual(payload["uid_count"], 2)
		self.assertEqual(manifest["review_reference_files"], ["raw.csv"])
		self.assertEqual(manifest["layer_specs"]["raw"]["review_reference"], True)
		self.assertEqual(states_index["1001"], ["road", "stay"])
		self.assertEqual(states_index["1002"], ["road", "subway"])
		self.assertEqual(batch_meta["name"], "template_demo")
		self.assertTrue((output_root / "review" / "reviewers").exists())
		self.assertTrue((output_root / "accepted_assets" / "reviewers").exists())
		self.assertTrue((output_root / "result" / "1001" / "raw.csv").exists())
		self.assertTrue((output_root / "result" / "1002" / "raw.csv").exists())


if __name__ == "__main__":
	unittest.main()
