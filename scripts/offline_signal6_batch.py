from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
	from trajectory_annotation_studio.scripts.server_batch_lib import (
		publish_batch,
		read_json,
		validate_batch_root,
		write_json,
	)
	from trajectory_annotation_studio.scripts.user_upload_adapter_lib import (
		UserUploadAdapterError,
		build_signal6_result,
		normalize_signal6_algorithm_profile,
		normalize_signal6_pipeline_mode,
		signal6_pipeline_mode_for_profile,
		signal6_pipeline_options_for_profile,
	)
except ImportError:
	from server_batch_lib import publish_batch, read_json, validate_batch_root, write_json  # type: ignore
	from user_upload_adapter_lib import (  # type: ignore
		UserUploadAdapterError,
		build_signal6_result,
		normalize_signal6_algorithm_profile,
		normalize_signal6_pipeline_mode,
		signal6_pipeline_mode_for_profile,
		signal6_pipeline_options_for_profile,
	)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"离线/内网：从 signal6 六元组 CSV 运行 snap+OD+FMM，并生成可导入标注平台的 published batch 目录。"
		)
	)
	parser.add_argument("--input", required=True, type=Path, help="输入 CSV（uid,cid,lat,lon,t_in,t_out 及可选 status）")
	parser.add_argument(
		"--published-root",
		required=True,
		type=Path,
		help="发布根目录；最终批次路径为 <published-root>/<batch-name>/",
	)
	parser.add_argument("--batch-name", required=True, help="批次目录名（同 publish_batch）")
	parser.add_argument("--title", default="", help="manifest 与 batch 展示标题，默认同 batch-name")
	parser.add_argument(
		"--pipeline-mode",
		default="v311",
		help="signal6 处理模式；离线链路应使用 v311（snap+od+fmm）",
	)
	parser.add_argument(
		"--algorithm-profile",
		default="speed_sparsity_90",
		choices=("baseline_v311", "mainroad_weighted", "major_roads", "speed_sparsity_90"),
		help="signal6 算法方案；默认使用 90%% 展示算法",
	)
	parser.add_argument(
		"--field-mapping",
		type=Path,
		default=None,
		help="可选 JSON 文件，字段映射对象（与上传接口 field_mapping 相同）",
	)
	parser.add_argument("--label", default="", help="batch_meta.label，默认用 title")
	parser.add_argument("--version", default="offline-batch-v1", help="batch_meta.version")
	parser.add_argument("--keywords", default="offline-batch,signal6", help="逗号分隔关键词")
	parser.add_argument("--force", action="store_true", help="若目标批次已存在则覆盖（publish_batch force）")
	parser.add_argument(
		"--keep-workspace",
		action="store_true",
		help="保留临时工作目录（含 cache/OD/fmm 中间产物）并打印路径，便于排错",
	)
	return parser.parse_args()


def _load_field_mapping(path: Path | None) -> Any:
	if path is None:
		return None
	with open(path.expanduser().resolve(), encoding="utf-8") as handle:
		return json.load(handle)


def main() -> None:
	args = parse_args()
	input_csv = args.input.expanduser().resolve()
	published_root = args.published_root.expanduser().resolve()
	batch_name = str(args.batch_name).strip()
	if not batch_name:
		raise SystemExit("batch-name must be non-empty")
	title = (args.title or batch_name).strip()
	label = (args.label or title).strip()
	keywords = [item.strip() for item in str(args.keywords).split(",") if item.strip()]
	algorithm_profile = normalize_signal6_algorithm_profile(args.algorithm_profile)
	pipeline_mode = signal6_pipeline_mode_for_profile(
		normalize_signal6_pipeline_mode(args.pipeline_mode),
		algorithm_profile,
	)
	pipeline_options = signal6_pipeline_options_for_profile(algorithm_profile)
	field_mapping = _load_field_mapping(args.field_mapping)

	if not input_csv.is_file():
		raise SystemExit(f"input not found: {input_csv}")

	published_root.mkdir(parents=True, exist_ok=True)
	target_batch = published_root / batch_name
	if target_batch.exists() and not args.force:
		raise SystemExit(f"batch already exists (use --force): {target_batch}")

	work_root: Path | None = None
	try:
		work_root = Path(tempfile.mkdtemp(prefix=f"signal6_offline_{batch_name}_"))
		result_in_work = work_root / "result"
		adapter_report = build_signal6_result(
			input_csv,
			result_in_work,
			title=title,
			field_mapping=field_mapping,
			pipeline_mode=pipeline_mode,
			pipeline_options=pipeline_options,
		)
		publish_report = publish_batch(
			published_root=published_root,
			batch_name=batch_name,
			source_result_root=result_in_work,
			label=label,
			version=str(args.version),
			keywords=keywords,
			status="published",
			force=bool(args.force),
			validate=True,
			extra_metadata={
				"offline_signal6_batch": True,
				"source_csv": str(input_csv),
				"adapter": adapter_report.get("adapter"),
				"pipeline_mode": adapter_report.get("pipeline_mode"),
				"signal6_algorithm_profile": adapter_report.get("signal6_algorithm_profile") or algorithm_profile,
				"fmm_algorithm": adapter_report.get("fmm_algorithm"),
				"ui_mode": adapter_report.get("ui_mode"),
				"uid_count": adapter_report.get("uid_count"),
				"row_count": adapter_report.get("row_count"),
			},
		)
		target_root = Path(publish_report["target_root"])
		local_result = target_root / "result"
		if local_result.exists():
			shutil.rmtree(local_result)
		shutil.copytree(result_in_work, local_result, symlinks=False)

		meta_path = target_root / "batch_meta.json"
		metadata = read_json(meta_path)
		metadata["source_result_root"] = str(local_result.resolve())
		write_json(meta_path, metadata)

		post_validation = validate_batch_root(target_root)
		write_json(target_root / "validation_report.json", post_validation)
		if not post_validation["ok"]:
			raise ValueError(f"post-copy batch validation failed: {post_validation['errors']}")

		out_report = {
			"ok": True,
			"target_root": str(target_root),
			"result_root": str(local_result),
			"adapter_report": adapter_report,
			"publish_report": publish_report,
			"validation": post_validation,
		}
		if args.keep_workspace and work_root is not None:
			out_report["workspace_root"] = str(work_root)
		print(json.dumps(out_report, ensure_ascii=False, indent=2))
	finally:
		if work_root is not None and not args.keep_workspace:
			shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
	try:
		main()
	except UserUploadAdapterError as exc:
		print(str(exc), file=sys.stderr)
		raise SystemExit(2) from exc
	except KeyboardInterrupt:
		raise SystemExit(130)
