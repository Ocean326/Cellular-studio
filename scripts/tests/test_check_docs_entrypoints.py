from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .. import check_docs_entrypoints


class DocsEntrypointCheckTest(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.root = Path(self.temp_dir.name).resolve()
		self.repo_root = Path(__file__).resolve().parents[2]
		self.script_path = self.repo_root / "scripts" / "check_docs_entrypoints.py"

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def _write(self, relative_path: str, content: str) -> None:
		path = self.root / relative_path
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(content, encoding="utf-8")

	def _bootstrap_repo(self) -> None:
		self._write("README.md", "# README\n\n- [Docs](docs/README.md)\n")
		self._write("CONTRIBUTING.md", "# CONTRIBUTING\n\n- [Current](CURRENT.md)\n")
		self._write("CURRENT.md", "# CURRENT\n\n- [Index](docs/INDEX.md)\n")
		self._write("AGENTS.md", "# AGENTS\n\n- [Maintenance](docs/DOCS_MAINTENANCE.md)\n")
		self._write("docs/README.md", "# Docs README\n\n- [Index](INDEX.md)\n")
		self._write("docs/DOCS_MAINTENANCE.md", "# Maintenance\n\n- [Index](INDEX.md)\n")
		self._write("docs/01-overview.md", "# Overview\n")
		self._write("tests/example-test-cases.md", "# Tests\n")
		self._write("web/README.md", "# Web\n")
		self._write("deploy/docker/README.offline.md", "# Offline\n")
		self._write("adapters/README.md", "# Adapters\n")
		self._write("adapters/template/README.md", "# Template Adapter\n")
		self._write(
			"docs/INDEX.md",
			"""# Index

- [README](../README.md)
- [CONTRIBUTING](../CONTRIBUTING.md)
- [CURRENT](../CURRENT.md)
- [AGENTS](../AGENTS.md)
- [Docs Root](README.md)
- [Docs Maintenance](DOCS_MAINTENANCE.md)
- [Overview](01-overview.md)
- [Web README](../web/README.md)
- [Offline README](../deploy/docker/README.offline.md)
- [Adapters README](../adapters/README.md)
- [Template Adapter](../adapters/template/README.md)
- [Test Cases](../tests/example-test-cases.md)
""",
		)

	def _run_script(self) -> subprocess.CompletedProcess[str]:
		return subprocess.run(
			[
				sys.executable,
				str(self.script_path),
				"--root",
				str(self.root),
			],
			capture_output=True,
			text=True,
		)

	def test_resolve_local_link_rejects_external_and_escape_targets(self) -> None:
		base_path = self.root / "docs" / "INDEX.md"
		repo_root = self.root.resolve()
		base_path.parent.mkdir(parents=True, exist_ok=True)
		base_path.write_text("# Index\n", encoding="utf-8")

		self.assertIsNone(check_docs_entrypoints.resolve_local_link(base_path, "https://example.com", repo_root))
		self.assertIsNone(check_docs_entrypoints.resolve_local_link(base_path, "mailto:test@example.com", repo_root))
		self.assertIsNone(check_docs_entrypoints.resolve_local_link(base_path, "#section", repo_root))
		self.assertIsNone(check_docs_entrypoints.resolve_local_link(base_path, "../../outside.md", repo_root))

	def test_build_expected_index_targets_collects_docs_tests_and_adapters(self) -> None:
		self._bootstrap_repo()

		targets = {path.resolve() for path in check_docs_entrypoints.build_expected_index_targets(self.root)}

		self.assertIn((self.root / "README.md").resolve(), targets)
		self.assertIn((self.root / "CONTRIBUTING.md").resolve(), targets)
		self.assertIn((self.root / "CURRENT.md").resolve(), targets)
		self.assertIn((self.root / "AGENTS.md").resolve(), targets)
		self.assertIn((self.root / "docs" / "README.md").resolve(), targets)
		self.assertIn((self.root / "docs" / "DOCS_MAINTENANCE.md").resolve(), targets)
		self.assertIn((self.root / "docs" / "01-overview.md").resolve(), targets)
		self.assertIn((self.root / "tests" / "example-test-cases.md").resolve(), targets)
		self.assertIn((self.root / "web" / "README.md").resolve(), targets)
		self.assertIn((self.root / "deploy" / "docker" / "README.offline.md").resolve(), targets)
		self.assertIn((self.root / "adapters" / "README.md").resolve(), targets)
		self.assertIn((self.root / "adapters" / "template" / "README.md").resolve(), targets)
		self.assertNotIn((self.root / "docs" / "INDEX.md").resolve(), targets)

	def test_script_passes_for_complete_repo(self) -> None:
		self._bootstrap_repo()

		result = self._run_script()

		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertIn("docs entrypoints OK", result.stdout)

	def test_script_fails_when_index_is_missing_entry(self) -> None:
		self._bootstrap_repo()
		self._write(
			"docs/INDEX.md",
			"""# Index

- [README](../README.md)
- [CONTRIBUTING](../CONTRIBUTING.md)
- [CURRENT](../CURRENT.md)
- [AGENTS](../AGENTS.md)
- [Docs Root](README.md)
- [Docs Maintenance](DOCS_MAINTENANCE.md)
- [Web README](../web/README.md)
- [Offline README](../deploy/docker/README.offline.md)
- [Adapters README](../adapters/README.md)
- [Template Adapter](../adapters/template/README.md)
- [Test Cases](../tests/example-test-cases.md)
""",
		)

		result = self._run_script()

		self.assertNotEqual(result.returncode, 0)
		self.assertIn("docs/INDEX.md missing index entry for docs/01-overview.md", result.stdout)


if __name__ == "__main__":
	unittest.main()
