from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from review_lib import read_latest_reviews, resolve_review_paths


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Export a subset of reviewed samples at any time for organizer follow-up."
	)
	parser.add_argument("--project-root", default=None, help="cellular_quality project root")
	parser.add_argument("--result-root", default=None, help="Override result root")
	parser.add_argument("--review-root", default=None, help="Override review ledger root")
	parser.add_argument("--export-root", default=None, help="Override export root base")
	parser.add_argument(
		"--decision",
		default="accept",
		choices=["accept", "reject", "skip", "reviewed", "all"],
		help="Which latest-review decision set to export.",
	)
	parser.add_argument("--limit", type=int, default=None, help="Optional max sample count")
	parser.add_argument(
		"--order",
		default="latest",
		choices=["latest", "uid"],
		help="Export order: latest review first, or UID lexical order.",
	)
	parser.add_argument(
		"--output-dir",
		required=True,
		help="Output directory for this reviewed subset snapshot.",
	)
	parser.add_argument(
		"--copy-files",
		action="store_true",
		help="Copy per-UID result files into the snapshot. Default writes only selection manifest.",
	)
	return parser.parse_args()


def _matches_decision(review: dict, decision: str) -> bool:
	value = str(review.get("decision") or "").strip().lower()
	if decision == "all":
		return True
	if decision == "reviewed":
		return value in {"accept", "reject", "skip"}
	return value == decision


def _sort_reviews(items: list[dict], order: str) -> list[dict]:
	if order == "uid":
		return sorted(items, key=lambda item: str(item.get("uid") or item.get("sample_id") or ""))
	return sorted(
		items,
		key=lambda item: (
			str(item.get("timestamp") or ""),
			str(item.get("uid") or item.get("sample_id") or ""),
		),
		reverse=True,
	)


def _copy_sample_tree(result_root: Path, output_samples_root: Path, review: dict) -> dict[str, object]:
	sample_id = str(review.get("sample_id") or review.get("uid") or "").strip()
	if not sample_id:
		raise ValueError(f"Review entry missing sample_id/uid: {review}")
	src_dir = result_root / sample_id
	dst_dir = output_samples_root / sample_id
	record = {
		"sample_id": sample_id,
		"uid": str(review.get("uid") or sample_id),
		"decision": str(review.get("decision") or ""),
		"timestamp": str(review.get("timestamp") or ""),
		"reviewer": str(review.get("reviewer") or ""),
		"notes": str(review.get("notes") or ""),
		"reference_source": str(review.get("reference_source") or ""),
		"source_dir": str(src_dir),
		"copied": False,
	}
	if src_dir.exists():
		shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
		review_path = dst_dir / "review.json"
		review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
		record["copied"] = True
	return record


def main() -> None:
	args = parse_args()
	paths = resolve_review_paths(
		project_root=args.project_root,
		result_root=args.result_root,
		review_root=args.review_root,
		export_root=args.export_root,
	)
	index_payload = read_latest_reviews(paths)
	reviews = list(index_payload.get("reviews", {}).values())
	selected = [item for item in reviews if _matches_decision(item, args.decision)]
	selected = _sort_reviews(selected, args.order)
	if args.limit is not None:
		selected = selected[: max(0, int(args.limit))]

	output_dir = Path(args.output_dir).expanduser().resolve()
	if output_dir.exists():
		shutil.rmtree(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	records: list[dict[str, object]] = []
	if args.copy_files:
		samples_root = output_dir / "samples"
		samples_root.mkdir(parents=True, exist_ok=True)
		for review in selected:
			records.append(_copy_sample_tree(paths.result_root, samples_root, review))
	else:
		for review in selected:
			records.append(
				{
					"sample_id": str(review.get("sample_id") or review.get("uid") or ""),
					"uid": str(review.get("uid") or review.get("sample_id") or ""),
					"decision": str(review.get("decision") or ""),
					"timestamp": str(review.get("timestamp") or ""),
					"reviewer": str(review.get("reviewer") or ""),
					"notes": str(review.get("notes") or ""),
					"reference_source": str(review.get("reference_source") or ""),
				}
			)

	manifest = {
		"generated_from": str(paths.latest_path),
		"result_root": str(paths.result_root),
		"review_root": str(paths.review_root),
		"decision_filter": args.decision,
		"limit": args.limit,
		"order": args.order,
		"copy_files": bool(args.copy_files),
		"count": len(records),
		"samples": records,
	}
	(output_dir / "reviewed_subset_manifest.json").write_text(
		json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
		encoding="utf-8",
	)
	print(json.dumps({"output_dir": str(output_dir), "count": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
