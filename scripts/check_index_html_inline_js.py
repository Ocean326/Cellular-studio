#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path


class InlineScriptCollector(HTMLParser):
	def __init__(self) -> None:
		super().__init__()
		self.inline_scripts: list[str] = []
		self.local_script_srcs: list[str] = []
		self._capturing = False
		self._chunks: list[str] = []

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		if tag.lower() != "script":
			return
		attr_map = {key: value for key, value in attrs}
		src = str(attr_map.get("src") or "").strip()
		if src:
			if not src.startswith(("http://", "https://", "//")):
				self.local_script_srcs.append(src)
			return
		self._capturing = True
		self._chunks = []

	def handle_data(self, data: str) -> None:
		if self._capturing:
			self._chunks.append(data)

	def handle_endtag(self, tag: str) -> None:
		if tag.lower() != "script" or not self._capturing:
			return
		script = "".join(self._chunks).strip()
		if script:
			self.inline_scripts.append(script)
		self._capturing = False
		self._chunks = []


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Syntax-check inline and local JavaScript referenced by web/index.html.")
	parser.add_argument(
		"--html",
		default=str(Path(__file__).resolve().parents[1] / "web" / "index.html"),
		help="HTML file to inspect.",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	html_path = Path(args.html).expanduser().resolve()
	node_bin = shutil.which("node")
	if node_bin is None:
		raise SystemExit("node is required to syntax-check inline JavaScript")
	if not html_path.exists():
		raise FileNotFoundError(f"HTML file not found: {html_path}")

	collector = InlineScriptCollector()
	collector.feed(html_path.read_text(encoding="utf-8"))
	if not collector.inline_scripts and not collector.local_script_srcs:
		raise SystemExit(f"no inline or local <script> blocks found in {html_path}")

	for index, script in enumerate(collector.inline_scripts, start=1):
		with tempfile.NamedTemporaryFile(
			"w",
			prefix=f"inline_script_{index:02d}_",
			suffix=".js",
			encoding="utf-8",
			delete=False,
		) as handle:
			handle.write(script)
			tmp_path = Path(handle.name)
		try:
			subprocess.run(
				[node_bin, "--check", str(tmp_path)],
				check=True,
			)
		finally:
			tmp_path.unlink(missing_ok=True)

	checked_local_paths: list[Path] = []
	for src in collector.local_script_srcs:
		normalized_src = src.split("?", 1)[0].split("#", 1)[0]
		if not normalized_src:
			continue
		if normalized_src.startswith("/"):
			candidate = (html_path.parents[1] / normalized_src.lstrip("/")).resolve()
		else:
			candidate = (html_path.parent / normalized_src).resolve()
		if candidate in checked_local_paths:
			continue
		if not candidate.exists():
			raise FileNotFoundError(f"local script referenced by HTML was not found: {candidate}")
		subprocess.run([node_bin, "--check", str(candidate)], check=True)
		checked_local_paths.append(candidate)

	print(
		"JavaScript syntax OK: "
		f"{html_path} (inline={len(collector.inline_scripts)}, local={len(checked_local_paths)})"
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
