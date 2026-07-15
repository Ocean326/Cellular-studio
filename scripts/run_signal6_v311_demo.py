from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.user_upload_adapter_lib import build_signal6_result


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Run the local signal6 v311 pipeline for the signal/GPS demo.")
	parser.add_argument("--input", required=True, type=Path)
	parser.add_argument("--output-root", required=True, type=Path)
	parser.add_argument("--title", default="测试号信令v311还原结果")
	parser.add_argument("--fmm-version", choices=("original", "mainroad"), default="original")
	parser.add_argument("--force", action="store_true")
	return parser.parse_args()


def default_pipeline_options(*, fmm_version: str = "original") -> dict[str, object]:
	return {
		"jobs": 1,
		"od_parallel": False,
		"od_workers": 1,
		"chunksize": 20,
		"fmm_version": fmm_version,
		"fmm_variant_params": {
			"road": {
				"r": 0.018 if fmm_version == "mainroad" else 0.015,
				"k": 512,
				"error": 0.008,
				"reverse_tolerance": 0.05 if fmm_version == "mainroad" else 0.0,
				"ubodt_delta_multiplier": 1.35 if fmm_version == "mainroad" else 1.0,
			},
			"subway": {"r": -1.0},
			"railway": {"r": -1.0},
		},
	}


def main() -> int:
	args = parse_args()
	output_root = args.output_root.expanduser().resolve()
	if output_root.exists():
		if not args.force:
			raise FileExistsError(f"output exists: {output_root}")
		shutil.rmtree(output_root)
	report = build_signal6_result(
		args.input.expanduser().resolve(),
		output_root,
		title=args.title,
		pipeline_mode="v311",
		pipeline_options=default_pipeline_options(fmm_version=args.fmm_version),
	)
	print(json.dumps(report, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
