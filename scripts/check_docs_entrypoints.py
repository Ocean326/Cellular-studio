#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote


ENTRYPOINT_DOCS = [
	Path("README.md"),
	Path("CONTRIBUTING.md"),
	Path("CURRENT.md"),
	Path("AGENTS.md"),
	Path("docs/README.md"),
	Path("docs/INDEX.md"),
	Path("docs/DOCS_MAINTENANCE.md"),
]

INDEX_FIXED_TARGETS = [
	Path("README.md"),
	Path("CONTRIBUTING.md"),
	Path("CURRENT.md"),
	Path("AGENTS.md"),
	Path("docs/README.md"),
	Path("docs/DOCS_MAINTENANCE.md"),
	Path("web/README.md"),
	Path("deploy/docker/README.offline.md"),
	Path("adapters/README.md"),
]

DOCS_INDEX_EXCLUDES = {
	Path("docs/README.md"),
	Path("docs/INDEX.md"),
	Path("docs/DOCS_MAINTENANCE.md"),
}

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)#][^)#]*)(?:#[^)]+)?\)")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Validate docs entrypoint links and INDEX coverage for repo docs surfaces."
	)
	parser.add_argument(
		"--root",
		default=str(Path(__file__).resolve().parents[1]),
		help="Repository root to validate.",
	)
	return parser.parse_args()


def resolve_local_link(base_path: Path, raw_target: str, repo_root: Path) -> Path | None:
	if "://" in raw_target or raw_target.startswith(("mailto:", "#")):
		return None
	target = unquote(raw_target)
	candidate = (base_path.parent / target).resolve()
	try:
		candidate.relative_to(repo_root)
	except ValueError:
		return None
	return candidate


def collect_local_links(path: Path, repo_root: Path) -> tuple[list[tuple[int, str]], set[Path]]:
	missing: list[tuple[int, str]] = []
	resolved: set[Path] = set()
	for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
		for raw_target in LINK_PATTERN.findall(line):
			candidate = resolve_local_link(path, raw_target, repo_root)
			if candidate is None:
				continue
			if not candidate.exists():
				missing.append((line_no, raw_target))
				continue
			resolved.add(candidate)
	return missing, resolved


def build_expected_index_targets(repo_root: Path) -> set[Path]:
	expected: set[Path] = set()
	for relative_path in INDEX_FIXED_TARGETS:
		candidate = repo_root / relative_path
		if candidate.exists():
			expected.add(candidate.resolve())

	for path in sorted((repo_root / "docs").glob("*.md")):
		relative_path = path.relative_to(repo_root)
		if relative_path in DOCS_INDEX_EXCLUDES:
			continue
		expected.add(path.resolve())

	for path in sorted((repo_root / "tests").glob("*.md")):
		expected.add(path.resolve())

	for path in sorted((repo_root / "adapters").glob("*/README.md")):
		expected.add(path.resolve())

	return expected


def main() -> int:
	args = parse_args()
	repo_root = Path(args.root).expanduser().resolve()
	missing_files = [path for path in ENTRYPOINT_DOCS if not (repo_root / path).exists()]
	if missing_files:
		for path in missing_files:
			print(f"missing entrypoint file: {path}")
		return 1

	issues: list[str] = []
	total_links = 0
	index_links: set[Path] = set()

	for relative_path in ENTRYPOINT_DOCS:
		path = (repo_root / relative_path).resolve()
		missing_links, resolved_links = collect_local_links(path, repo_root)
		total_links += len(resolved_links)
		for line_no, raw_target in missing_links:
			issues.append(f"{relative_path}:{line_no} missing {raw_target}")
		if relative_path == Path("docs/INDEX.md"):
			index_links = resolved_links

	expected_index_targets = build_expected_index_targets(repo_root)
	index_paths = {path.resolve() for path in index_links}
	missing_from_index = sorted(
		path.relative_to(repo_root).as_posix()
		for path in expected_index_targets
		if path.resolve() not in index_paths
	)
	for relative_path in missing_from_index:
		issues.append(f"docs/INDEX.md missing index entry for {relative_path}")

	if issues:
		for issue in issues:
			print(issue)
		return 1

	print(
		"docs entrypoints OK: "
		f"entry_docs={len(ENTRYPOINT_DOCS)} "
		f"resolved_links={total_links} "
		f"indexed_targets={len(expected_index_targets)}"
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
