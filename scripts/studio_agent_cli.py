#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
	from .studio_agent_client import (
		DEFAULT_BASE_URL,
		DEFAULT_TIMEOUT_SECONDS,
		StudioAgentClient,
		StudioAgentClientError,
	)
	from .studio_agent_segment_context import (
		export_visual_context,
		summarize_materialized_sample,
	)
	from .studio_agent_mode_labeling import (
		apply_annotation_plan,
		discover_mode_candidates,
		parse_mode_labels,
	)
	from .studio_agent_timeline_validation import validate_timeline_payload
except ImportError:
	REPO_ROOT = Path(__file__).resolve().parents[1]
	if str(REPO_ROOT.parent) not in sys.path:
		sys.path.insert(0, str(REPO_ROOT.parent))
	from trajectory_annotation_studio.scripts.studio_agent_client import (  # type: ignore
		DEFAULT_BASE_URL,
		DEFAULT_TIMEOUT_SECONDS,
		StudioAgentClient,
		StudioAgentClientError,
	)
	from trajectory_annotation_studio.scripts.studio_agent_segment_context import (  # type: ignore
		export_visual_context,
		summarize_materialized_sample,
	)
	from trajectory_annotation_studio.scripts.studio_agent_mode_labeling import (  # type: ignore
		apply_annotation_plan,
		discover_mode_candidates,
		parse_mode_labels,
	)
	from trajectory_annotation_studio.scripts.studio_agent_timeline_validation import (  # type: ignore
		validate_timeline_payload,
	)


def _parse_string_list(values: list[str] | None) -> list[str]:
	items: list[str] = []
	for value in values or []:
		for piece in str(value).replace("|", ",").split(","):
			text = piece.strip()
			if text:
				items.append(text)
	return items


def _load_json_payload(payload_file: str | None, payload_json: str | None) -> dict[str, Any]:
	if payload_file:
		return json.loads(Path(payload_file).read_text(encoding="utf-8"))
	if payload_json:
		return json.loads(payload_json)
	return {}


def _emit(payload: dict[str, Any], as_json: bool) -> None:
	if as_json:
		print(json.dumps(payload, ensure_ascii=False))
		return
	print(json.dumps(payload, ensure_ascii=False, indent=2))


def _make_client(args: argparse.Namespace) -> StudioAgentClient:
	return StudioAgentClient(
		base_url=args.base_url,
		batch=str(getattr(args, "batch", "") or "").strip() or None,
		timeout_seconds=float(args.timeout),
	)


def cmd_health(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).health(batch=args.batch)


def cmd_batch_list(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).list_batches()


def cmd_batch_show(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	payload = client.list_batches()
	target_batch = str(args.batch or payload.get("current_batch") or "").strip()
	if not target_batch:
		raise StudioAgentClientError("No batch available")
	for batch in payload.get("batches", []) or []:
		if str(batch.get("name") or "") == target_batch:
			return {
				"current_batch": payload.get("current_batch"),
				"batch": batch,
			}
	raise StudioAgentClientError(f"Batch not found: {target_batch}")


def cmd_sample_list(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	return client.list_samples(
		batch=args.batch,
		tags=_parse_string_list(args.tag),
		limit=args.limit,
		offset=args.offset,
		review_status=args.review_status,
		reviewer_id=args.reviewer_id,
	)


def cmd_sample_inspect(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	return client.inspect_sample(
		uid=args.uid,
		batch=args.batch,
		preview_rows=args.preview_rows,
		include_files=_parse_string_list(args.file),
		include_aggregate=not args.no_aggregate,
	)


def cmd_sample_materialize(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	return client.materialize_sample(
		uid=args.uid,
		output_dir=args.output_dir,
		batch=args.batch,
		preview_rows=args.preview_rows,
		include_files=_parse_string_list(args.file),
	)


def cmd_sample_segment_summary(args: argparse.Namespace) -> dict[str, Any]:
	return summarize_materialized_sample(args.sample_root)


def cmd_sample_visual_context_export(args: argparse.Namespace) -> dict[str, Any]:
	return export_visual_context(
		args.sample_root,
		args.output_dir,
		base_url=args.visual_base_url,
		max_points_per_layer=args.max_points_per_layer,
	)


def cmd_reviewer_start(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	return client.open_reviewer_session(
		display_name=args.name,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)


def cmd_reviewer_list(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).list_reviewers(batch=args.batch)


def cmd_review_get(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).get_review(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)


def cmd_review_submit(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).submit_review(
		uid=args.uid,
		decision=args.decision,
		reviewer_id=args.reviewer_id,
		reviewer_name=args.reviewer_name,
		notes=args.notes,
		reference_source=args.reference_source,
		trajectory_tags=_parse_string_list(args.tag),
		batch=args.batch,
	)


def cmd_timeline_get(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).get_timeline(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)


def cmd_timeline_put(args: argparse.Namespace) -> dict[str, Any]:
	payload = _load_json_payload(args.payload_file, args.payload_json)
	return _make_client(args).put_timeline(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		reviewer_name=args.reviewer_name,
		payload=payload,
		batch=args.batch,
	)


def cmd_timeline_validate(args: argparse.Namespace) -> dict[str, Any]:
	payload = _load_json_payload(args.payload_file, args.payload_json)
	sample_summary = None
	if args.sample_summary_file:
		sample_summary = json.loads(Path(args.sample_summary_file).read_text(encoding="utf-8"))
	result = validate_timeline_payload(payload, sample_summary=sample_summary)
	result["status"] = "ok" if result.get("ok") else "invalid"
	if args.fail_on_error and not result.get("ok"):
		result["__exit_code"] = 1
	return result


def cmd_track_edits_get(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).get_track_edits(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)


def cmd_track_edits_put(args: argparse.Namespace) -> dict[str, Any]:
	payload = _load_json_payload(args.payload_file, args.payload_json)
	return _make_client(args).put_track_edits(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		reviewer_name=args.reviewer_name,
		payload=payload,
		batch=args.batch,
	)


def cmd_track_edits_export(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).export_track_edits(
		uid=args.uid,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)


def cmd_mode_label_candidates(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	result_root = Path(args.result_root).expanduser().resolve() if args.result_root else client.batch_result_root(batch=args.batch)
	payload = discover_mode_candidates(
		result_root,
		labels=parse_mode_labels(args.label),
		per_label=args.per_label,
		max_uids=args.max_uids,
	)
	batch_name = str(args.batch or payload.get("batch") or "").strip()
	if not batch_name:
		batch_name = client._effective_batch(batch=args.batch)
	payload["batch"] = batch_name
	if args.output_file:
		output_path = Path(args.output_file).expanduser().resolve()
		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
		payload["output_file"] = str(output_path)
	return payload


def cmd_mode_label_apply(args: argparse.Namespace) -> dict[str, Any]:
	payload = _load_json_payload(args.plan_file, args.plan_json)
	return apply_annotation_plan(
		_make_client(args),
		payload,
		batch=args.batch or payload.get("batch"),
		reviewer_id=args.reviewer_id,
		reviewer_name=args.reviewer_name,
		decision=args.decision,
		notes=args.notes,
		dry_run=args.dry_run,
	)


def cmd_aggregate_uid(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).review_aggregate(uid=args.uid, batch=args.batch)


def cmd_aggregate_export(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).export_review_aggregate(clean=args.clean, batch=args.batch)


def cmd_bundle_export(args: argparse.Namespace) -> dict[str, Any]:
	return _make_client(args).export_reviewer_bundle(
		reviewer_id=args.reviewer_id,
		batch=args.batch,
		clean=args.clean,
		create_zip=args.create_zip,
		decision_filters=_parse_string_list(args.decision),
		uids=_parse_string_list(args.uid),
		trajectory_tags=_parse_string_list(args.tag),
		export_mode=args.export_mode,
		bundle_name=args.bundle_name,
		interval_seconds=args.interval_seconds,
		timestamp_unit=args.timestamp_unit,
		labeled_span_only=bool(args.labeled_span_only),
	)


def cmd_dev_roundtrip(args: argparse.Namespace) -> dict[str, Any]:
	client = _make_client(args)
	session = client.open_reviewer_session(
		display_name=args.reviewer_name,
		reviewer_id=args.reviewer_id,
		batch=args.batch,
	)
	reviewer = session["reviewer"]
	payload: dict[str, Any] = {
		"session": reviewer,
		"sample": client.inspect_sample(
			uid=args.uid,
			batch=args.batch,
			preview_rows=args.preview_rows,
			include_files=_parse_string_list(args.file),
			include_aggregate=True,
		),
	}
	if args.dry_run:
		payload["mode"] = "dry_run"
		return payload
	review = client.submit_review(
		uid=args.uid,
		decision=args.decision,
		reviewer_id=reviewer["reviewer_id"],
		reviewer_name=reviewer["reviewer_name"],
		notes=args.notes,
		reference_source=args.reference_source,
		trajectory_tags=_parse_string_list(args.tag),
		batch=args.batch,
	)
	payload["review"] = review
	if args.with_segment:
		timeline = client.put_timeline(
			uid=args.uid,
			reviewer_id=reviewer["reviewer_id"],
			reviewer_name=reviewer["reviewer_name"],
			payload={
				"pins": [],
				"segments": [
					{
						"id": f"dev:{args.uid}:segment",
						"categoryId": args.segment_category_id,
						"categoryName": args.segment_category_name,
						"color": args.segment_color,
						"startTime": int(args.segment_start_ms),
						"endTime": int(args.segment_end_ms),
					}
				],
			},
			batch=args.batch,
		)
		payload["timeline"] = timeline
	payload["aggregate"] = client.review_aggregate(uid=args.uid, batch=args.batch)
	payload["timeline_aggregate"] = client.timeline_aggregate(uid=args.uid, batch=args.batch)
	if args.export:
		payload["export"] = client.export_review_aggregate(clean=False, batch=args.batch)
	return payload


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Agent-native CLI for trajectory_annotation_studio review flows."
	)
	parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="review server base url")
	parser.add_argument("--batch", default=None, help="target batch name; defaults to current batch")
	parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout in seconds")
	parser.add_argument("--json", action="store_true", help="emit compact machine-readable JSON")
	subparsers = parser.add_subparsers(dest="command", required=True)

	health = subparsers.add_parser("health", help="check server and batch routing")
	health.set_defaults(func=cmd_health)

	batch = subparsers.add_parser("batch", help="batch operations")
	batch_sub = batch.add_subparsers(dest="batch_command", required=True)
	batch_list = batch_sub.add_parser("list", help="list visible batches")
	batch_list.set_defaults(func=cmd_batch_list)
	batch_show = batch_sub.add_parser("show", help="show current or named batch")
	batch_show.set_defaults(func=cmd_batch_show)

	sample = subparsers.add_parser("sample", help="sample inspection and export")
	sample_sub = sample.add_subparsers(dest="sample_command", required=True)
	sample_list = sample_sub.add_parser("list", help="list sample uids")
	sample_list.add_argument("--tag", action="append", default=[], help="filter by one or more tags")
	sample_list.add_argument("--limit", type=int, default=20, help="max returned items")
	sample_list.add_argument("--offset", type=int, default=0, help="pagination offset")
	sample_list.add_argument(
		"--review-status",
		default="any",
		choices=["any", "reviewed", "unreviewed"],
		help="filter by review state; if reviewer-id is given, applies to that reviewer",
	)
	sample_list.add_argument(
		"--reviewer-id",
		default=None,
		help="optional reviewer id used together with --review-status",
	)
	sample_list.set_defaults(func=cmd_sample_list)
	sample_inspect = sample_sub.add_parser("inspect", help="fetch one uid context")
	sample_inspect.add_argument("--uid", required=True, help="uid to inspect")
	sample_inspect.add_argument("--preview-rows", type=int, default=8, help="rows to preview per CSV")
	sample_inspect.add_argument("--file", action="append", default=[], help="override included files")
	sample_inspect.add_argument("--no-aggregate", action="store_true", help="skip review/timeline aggregates")
	sample_inspect.set_defaults(func=cmd_sample_inspect)
	sample_materialize = sample_sub.add_parser("materialize", help="write one uid context to a local folder")
	sample_materialize.add_argument("--uid", required=True, help="uid to materialize")
	sample_materialize.add_argument("--output-dir", required=True, help="target output directory")
	sample_materialize.add_argument("--preview-rows", type=int, default=8, help="rows to preview per CSV")
	sample_materialize.add_argument("--file", action="append", default=[], help="override included files")
	sample_materialize.set_defaults(func=cmd_sample_materialize)
	sample_segment_summary = sample_sub.add_parser(
		"segment-summary",
		help="summarize a materialized sample for agent segment planning",
	)
	sample_segment_summary.add_argument("--sample-root", required=True, help="materialized sample root with context.json")
	sample_segment_summary.set_defaults(func=cmd_sample_segment_summary)
	sample_visual_context = sample_sub.add_parser("visual-context", help="visual context export operations")
	sample_visual_context_sub = sample_visual_context.add_subparsers(dest="sample_visual_context_command", required=True)
	sample_visual_context_export = sample_visual_context_sub.add_parser(
		"export",
		help="export visual_context.json and a Leaflet map page for a materialized sample",
	)
	sample_visual_context_export.add_argument("--sample-root", required=True, help="materialized sample root with context.json")
	sample_visual_context_export.add_argument(
		"--output-dir",
		default=None,
		help="target output directory; defaults to <sample-root>/visual_export",
	)
	sample_visual_context_export.add_argument(
		"--visual-base-url",
		default=DEFAULT_BASE_URL,
		help="base URL for Leaflet assets and offline Beijing tile URLs",
	)
	sample_visual_context_export.add_argument(
		"--max-points-per-layer",
		type=int,
		default=384,
		help="maximum line coordinates embedded per CSV layer",
	)
	sample_visual_context_export.set_defaults(func=cmd_sample_visual_context_export)

	reviewer = subparsers.add_parser("reviewer", help="reviewer identity operations")
	reviewer_sub = reviewer.add_subparsers(dest="reviewer_command", required=True)
	reviewer_start = reviewer_sub.add_parser("start", help="open or reuse a reviewer session")
	reviewer_start.add_argument("--name", required=True, help="reviewer display name")
	reviewer_start.add_argument("--reviewer-id", default=None, help="explicit reviewer id")
	reviewer_start.set_defaults(func=cmd_reviewer_start)
	reviewer_list = reviewer_sub.add_parser("list", help="list known reviewers")
	reviewer_list.set_defaults(func=cmd_reviewer_list)

	review = subparsers.add_parser("review", help="review read/write")
	review_sub = review.add_subparsers(dest="review_command", required=True)
	review_get = review_sub.add_parser("get", help="get latest review for a uid")
	review_get.add_argument("--uid", required=True, help="uid")
	review_get.add_argument("--reviewer-id", default=None, help="optional reviewer id")
	review_get.set_defaults(func=cmd_review_get)
	review_submit = review_sub.add_parser("submit", help="submit a review decision")
	review_submit.add_argument("--uid", required=True, help="uid")
	review_submit.add_argument("--decision", required=True, choices=["accept", "reject", "skip"], help="review decision")
	review_submit.add_argument("--reviewer-id", required=True, help="reviewer id")
	review_submit.add_argument("--reviewer-name", required=True, help="reviewer display name")
	review_submit.add_argument("--notes", default="", help="review notes")
	review_submit.add_argument("--reference-source", default="", help="reference file name such as fmm.csv")
	review_submit.add_argument("--tag", action="append", default=[], help="trajectory tags")
	review_submit.set_defaults(func=cmd_review_submit)

	timeline = subparsers.add_parser("timeline", help="timeline annotation read/write")
	timeline_sub = timeline.add_subparsers(dest="timeline_command", required=True)
	timeline_get = timeline_sub.add_parser("get", help="get timeline annotations for a uid")
	timeline_get.add_argument("--uid", required=True, help="uid")
	timeline_get.add_argument("--reviewer-id", default=None, help="optional reviewer id")
	timeline_get.set_defaults(func=cmd_timeline_get)
	timeline_put = timeline_sub.add_parser("put", help="write timeline annotations from JSON")
	timeline_put.add_argument("--uid", required=True, help="uid")
	timeline_put.add_argument("--reviewer-id", required=True, help="reviewer id")
	timeline_put.add_argument("--reviewer-name", required=True, help="reviewer display name")
	timeline_put.add_argument("--payload-file", default=None, help="path to JSON payload file")
	timeline_put.add_argument("--payload-json", default=None, help="inline JSON payload")
	timeline_put.set_defaults(func=cmd_timeline_put)
	timeline_validate = timeline_sub.add_parser(
		"validate",
		help="validate vNext segment timeline payloads before writing",
	)
	timeline_validate_payload = timeline_validate.add_mutually_exclusive_group(required=True)
	timeline_validate_payload.add_argument("--payload-file", default=None, help="path to JSON payload file")
	timeline_validate_payload.add_argument("--payload-json", default=None, help="inline JSON payload")
	timeline_validate.add_argument(
		"--sample-summary-file",
		default=None,
		help="optional segment-summary JSON used for consistency warnings",
	)
	timeline_validate.add_argument(
		"--fail-on-error",
		action="store_true",
		help="return exit code 1 when validation errors are present",
	)
	timeline_validate.set_defaults(func=cmd_timeline_validate)

	track_edits = subparsers.add_parser("track-edits", help="track point edit read/write and lightweight export bundle")
	track_edits_sub = track_edits.add_subparsers(dest="track_edits_command", required=True)
	track_edits_get = track_edits_sub.add_parser("get", help="load persisted track edits for a uid/reviewer")
	track_edits_get.add_argument("--uid", required=True, help="uid")
	track_edits_get.add_argument("--reviewer-id", required=True, help="reviewer id")
	track_edits_get.set_defaults(func=cmd_track_edits_get)
	track_edits_put = track_edits_sub.add_parser("put", help="write track edits from JSON payload")
	track_edits_put.add_argument("--uid", required=True, help="uid")
	track_edits_put.add_argument("--reviewer-id", required=True, help="reviewer id")
	track_edits_put.add_argument("--reviewer-name", required=True, help="reviewer display name")
	track_edits_put.add_argument("--payload-file", default=None, help="path to JSON payload file")
	track_edits_put.add_argument("--payload-json", default=None, help="inline JSON payload")
	track_edits_put.set_defaults(func=cmd_track_edits_put)
	track_edits_export = track_edits_sub.add_parser(
		"export",
		help="compose track edits plus reviewer timeline annotations for downstream tooling",
	)
	track_edits_export.add_argument("--uid", required=True, help="uid")
	track_edits_export.add_argument("--reviewer-id", required=True, help="reviewer id")
	track_edits_export.set_defaults(func=cmd_track_edits_export)

	mode_label = subparsers.add_parser("mode-label", help="multi-mode candidate discovery and annotation application")
	mode_label_sub = mode_label.add_subparsers(dest="mode_label_command", required=True)
	mode_label_candidates = mode_label_sub.add_parser(
		"candidates",
		help="find candidate trajectories for subway/low_speed/road/stay/flight/railway labeling",
	)
	mode_label_candidates.add_argument(
		"--label",
		action="append",
		default=[],
		help="target label(s), comma-separated or repeated; defaults to all six requested labels",
	)
	mode_label_candidates.add_argument("--per-label", type=int, default=6, help="number of UID candidates per label")
	mode_label_candidates.add_argument("--max-uids", type=int, default=None, help="optional scan cap for smoke tests")
	mode_label_candidates.add_argument("--result-root", default=None, help="local result root override")
	mode_label_candidates.add_argument("--output-file", default=None, help="optional path to write the candidate plan JSON")
	mode_label_candidates.set_defaults(func=cmd_mode_label_candidates)
	mode_label_apply = mode_label_sub.add_parser("apply", help="apply a candidate annotation plan as review + timeline")
	mode_label_apply_payload = mode_label_apply.add_mutually_exclusive_group(required=True)
	mode_label_apply_payload.add_argument("--plan-file", default=None, help="candidate plan JSON from mode-label candidates")
	mode_label_apply_payload.add_argument("--plan-json", default=None, help="inline candidate plan JSON")
	mode_label_apply.add_argument("--reviewer-id", required=True, help="reviewer id for written annotations")
	mode_label_apply.add_argument("--reviewer-name", required=True, help="reviewer display name")
	mode_label_apply.add_argument("--decision", default="accept", choices=["accept", "reject", "skip"], help="review decision")
	mode_label_apply.add_argument("--notes", default="studio-agent multimode labeling", help="review note prefix")
	mode_label_apply.add_argument("--dry-run", action="store_true", help="validate grouping without writing")
	mode_label_apply.set_defaults(func=cmd_mode_label_apply)

	aggregate = subparsers.add_parser("aggregate", help="aggregate surfaces")
	aggregate_sub = aggregate.add_subparsers(dest="aggregate_command", required=True)
	aggregate_uid = aggregate_sub.add_parser("uid", help="show one uid review aggregate")
	aggregate_uid.add_argument("--uid", required=True, help="uid")
	aggregate_uid.set_defaults(func=cmd_aggregate_uid)
	aggregate_export = aggregate_sub.add_parser("export", help="export review aggregate")
	aggregate_export.add_argument("--clean", action="store_true", help="clean output root before export")
	aggregate_export.set_defaults(func=cmd_aggregate_export)

	bundle = subparsers.add_parser("bundle", help="reviewer bundle export")
	bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
	bundle_export = bundle_sub.add_parser("export", help="export reviewer bundle or segment dataset")
	bundle_export.add_argument("--reviewer-id", required=True, help="reviewer id")
	bundle_export.add_argument("--clean", action="store_true", help="clean output root before export")
	bundle_export.add_argument("--create-zip", action="store_true", help="create zip bundle")
	bundle_export.add_argument("--bundle-name", default=None, help="override bundle name")
	bundle_export.add_argument("--export-mode", default="", help="optional export mode, e.g. segment_label_dataset")
	bundle_export.add_argument("--decision", action="append", default=[], help="decision filter")
	bundle_export.add_argument("--uid", action="append", default=[], help="uid filter")
	bundle_export.add_argument("--tag", action="append", default=[], help="trajectory tag filter")
	bundle_export.add_argument(
		"--interval-seconds",
		type=int,
		default=None,
		help="segment_label_dataset export: GPS resampling interval in seconds (omit for server default)",
	)
	bundle_export.add_argument(
		"--timestamp-unit",
		default=None,
		help="segment_label_dataset export: timestamp unit for CSV epochs, e.g. ms or seconds",
	)
	bundle_export.add_argument(
		"--labeled-span-only",
		action="store_true",
		help="segment_label_dataset export: trim rows to labeled segment span only",
	)
	bundle_export.set_defaults(func=cmd_bundle_export)

	dev = subparsers.add_parser("dev", help="developer smoke surfaces")
	dev_sub = dev.add_subparsers(dest="dev_command", required=True)
	roundtrip = dev_sub.add_parser("roundtrip", help="exercise sample->review->aggregate on a disposable batch")
	roundtrip.add_argument("--uid", required=True, help="uid")
	roundtrip.add_argument("--reviewer-name", required=True, help="reviewer display name")
	roundtrip.add_argument("--reviewer-id", default=None, help="optional reviewer id")
	roundtrip.add_argument("--decision", default="skip", choices=["accept", "reject", "skip"], help="decision to write")
	roundtrip.add_argument("--notes", default="studio-agent dev roundtrip", help="review note")
	roundtrip.add_argument("--reference-source", default="fmm.csv", help="reference file name")
	roundtrip.add_argument("--tag", action="append", default=["agent_probe"], help="review tags")
	roundtrip.add_argument("--file", action="append", default=[], help="override inspected files")
	roundtrip.add_argument("--preview-rows", type=int, default=8, help="rows to preview per CSV")
	roundtrip.add_argument("--dry-run", action="store_true", help="inspect only; do not write review")
	roundtrip.add_argument("--export", action="store_true", help="also export aggregate after write")
	roundtrip.add_argument("--with-segment", action="store_true", help="also write a tiny synthetic segment annotation")
	roundtrip.add_argument("--segment-category-id", default="evidence_gap", help="segment category id")
	roundtrip.add_argument("--segment-category-name", default="证据不足", help="segment category label")
	roundtrip.add_argument("--segment-color", default="#B2BEC3", help="segment color")
	roundtrip.add_argument("--segment-start-ms", type=int, default=0, help="segment start time in ms")
	roundtrip.add_argument("--segment-end-ms", type=int, default=1, help="segment end time in ms")
	roundtrip.set_defaults(func=cmd_dev_roundtrip)

	return parser


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	try:
		payload = args.func(args)
	except (StudioAgentClientError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
		error_payload = {"status": "error", "error": str(exc)}
		if getattr(args, "json", False):
			print(json.dumps(error_payload, ensure_ascii=False))
		else:
			print(str(exc), file=sys.stderr)
		return 1
	exit_code = int(payload.pop("__exit_code", 0) or 0)
	_emit(payload, as_json=bool(args.json))
	return exit_code


if __name__ == "__main__":
	raise SystemExit(main())
