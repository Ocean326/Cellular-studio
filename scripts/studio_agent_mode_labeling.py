#!/usr/bin/env python3
"""Candidate discovery and application helpers for multi-mode agent labeling."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .studio_agent_client import StudioAgentClient


MODE_LABELS: dict[str, dict[str, Any]] = {
	"subway": {
		"aliases": {"subway", "地铁"},
		"categoryId": "subway",
		"categoryName": "地铁",
		"color": "#9c27b0",
		"status": "subway",
		"matchTypes": {"subway"},
	},
	"road": {
		"aliases": {"road", "乘车", "道路"},
		"categoryId": "road",
		"categoryName": "乘车",
		"color": "#4caf50",
		"status": "road",
		"matchTypes": {"road"},
	},
	"stay": {
		"aliases": {"stay", "驻留", "停留"},
		"categoryId": "stay",
		"categoryName": "驻留",
		"color": "#000000",
		"status": "stay",
		"matchTypes": {"stay"},
	},
	"low_speed": {
		"aliases": {"low_speed", "low-speed", "slow", "缓行", "低速"},
		"categoryId": "low_speed",
		"categoryName": "低速",
		"color": "#ff9800",
		"status": "low_speed",
		"matchTypes": set(),
	},
	"flight": {
		"aliases": {"flight", "plane", "air", "飞机", "航班"},
		"categoryId": "flight",
		"categoryName": "飞机",
		"color": "#f44336",
		"status": "flight",
		"matchTypes": set(),
	},
	"railway": {
		"aliases": {"railway", "rail", "train", "铁路", "火车", "列车"},
		"categoryId": "railway",
		"categoryName": "铁路",
		"color": "#795548",
		"status": "train",
		"matchTypes": {"railway"},
	},
}

_ALIAS_TO_LABEL = {
	alias.lower().replace("-", "_").replace(" ", "_"): label
	for label, spec in MODE_LABELS.items()
	for alias in spec["aliases"]
}

AIRPORTS = {
	"PEK": (40.0801, 116.5846),
	"PKX": (39.5099, 116.4105),
}


def normalize_mode_label(raw: Any) -> str:
	text = str(raw or "").strip()
	if not text:
		raise ValueError("empty mode label")
	key = text.lower().replace("-", "_").replace(" ", "_")
	label = _ALIAS_TO_LABEL.get(key)
	if label:
		return label
	if key in MODE_LABELS:
		return key
	raise ValueError(f"unsupported mode label: {raw!r}")


def parse_mode_labels(raw: str | Iterable[str] | None) -> list[str]:
	if raw is None:
		return ["subway", "low_speed", "road", "stay", "flight", "railway"]
	parts: list[str] = []
	if isinstance(raw, str):
		items = raw.replace("|", ",").split(",")
	else:
		items = []
		for value in raw:
			items.extend(str(value).replace("|", ",").split(","))
	for item in items:
		text = item.strip()
		if not text:
			continue
		label = normalize_mode_label(text)
		if label not in parts:
			parts.append(label)
	return parts or ["subway", "low_speed", "road", "stay", "flight", "railway"]


def _read_manifest(result_root: Path) -> dict[str, Any]:
	path = Path(result_root) / "manifest.json"
	return json.loads(path.read_text(encoding="utf-8"))


def _parse_float(value: Any) -> float | None:
	if value is None or isinstance(value, bool):
		return None
	try:
		out = float(str(value).strip())
	except (TypeError, ValueError):
		return None
	if not math.isfinite(out):
		return None
	return out


def _parse_bool(value: Any) -> bool:
	text = str(value or "").strip().lower()
	return text in {"1", "true", "yes", "y"}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
	radius = 6_371_000.0
	phi1 = math.radians(lat1)
	phi2 = math.radians(lat2)
	dphi = math.radians(lat2 - lat1)
	dlambda = math.radians(lon2 - lon1)
	a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
	return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _row_time_bounds(row: dict[str, Any]) -> tuple[float | None, float | None]:
	start = (
		_parse_float(row.get("segment_start_time"))
		or _parse_float(row.get("start_time"))
		or _parse_float(row.get("t_in"))
	)
	end = (
		_parse_float(row.get("segment_end_time"))
		or _parse_float(row.get("end_time"))
		or _parse_float(row.get("t_out"))
		or _parse_float(row.get("t_in"))
	)
	return start, end


def _direct_match_candidates_for_uid(result_root: Path, uid: str, label: str) -> list[dict[str, Any]]:
	match_types = MODE_LABELS[label].get("matchTypes") or set()
	if not match_types:
		return []
	out: list[dict[str, Any]] = []
	for filename in ("fmm.csv", "line.csv"):
		path = Path(result_root) / uid / filename
		if not path.is_file():
			continue
		groups: dict[tuple[str, str], dict[str, Any]] = {}
		with path.open(encoding="utf-8", errors="replace") as handle:
			for row in csv.DictReader(handle):
				match_type = str(row.get("match_type") or row.get("type") or "").strip().lower()
				if match_type not in match_types:
					continue
				segment_idx = str(row.get("segment_idx") or row.get("segment_id") or "0").strip()
				start, end = _row_time_bounds(row)
				if start is None or end is None:
					continue
				key = (match_type, segment_idx)
				group = groups.setdefault(
					key,
					{
						"uid": uid,
						"label": label,
						"matchType": match_type,
						"sourceFile": filename,
						"segmentIdx": segment_idx,
						"startTime": start,
						"endTime": end,
						"pointCount": 0,
					},
				)
				group["startTime"] = min(float(group["startTime"]), start)
				group["endTime"] = max(float(group["endTime"]), end)
				group["pointCount"] = int(group.get("pointCount") or 0) + 1
		for group in groups.values():
			duration = max(0.0, float(group["endTime"]) - float(group["startTime"]))
			if duration <= 0:
				continue
			group["durationSeconds"] = duration
			group["score"] = duration + min(int(group.get("pointCount") or 0), 10_000) * 2.0
			group["confidence"] = 0.88 if filename == "fmm.csv" else 0.82
			group["needsHumanReview"] = False
			group["evidenceMetric"] = f"match_type={group['matchType']} point_count={group['pointCount']} duration={duration:.0f}s"
			out.append(group)
		if out:
			break
	return out


def _low_speed_candidates_for_uid(result_root: Path, uid: str) -> list[dict[str, Any]]:
	path = Path(result_root) / uid / "od.csv"
	if not path.is_file():
		return []
	out: list[dict[str, Any]] = []
	with path.open(encoding="utf-8", errors="replace") as handle:
		for idx, row in enumerate(csv.DictReader(handle)):
			speed = _parse_float(row.get("speed"))
			duration = _parse_float(row.get("time_diff"))
			start = _parse_float(row.get("start_time"))
			end = _parse_float(row.get("end_time"))
			if speed is None or duration is None or start is None or end is None:
				continue
			if _parse_bool(row.get("is_stationary")):
				continue
			if not (0.2 <= speed <= 1.5 and 120.0 <= duration <= 7200.0):
				continue
			score = duration + (1.5 - abs(0.8 - speed)) * 300.0
			out.append(
				{
					"uid": uid,
					"label": "low_speed",
					"sourceFile": "od.csv",
					"segmentIdx": str(idx),
					"startTime": min(start, end),
					"endTime": max(start, end),
					"durationSeconds": max(0.0, abs(end - start)),
					"speed": speed,
					"score": score,
					"confidence": 0.68,
					"needsHumanReview": True,
					"evidenceMetric": f"od speed={speed:.3f}m/s duration={duration:.0f}s moving=true",
				}
			)
	return out


def _flight_candidates_for_uid(result_root: Path, uid: str) -> list[dict[str, Any]]:
	path = Path(result_root) / uid / "od.csv"
	if not path.is_file():
		return []
	out: list[dict[str, Any]] = []
	with path.open(encoding="utf-8", errors="replace") as handle:
		for idx, row in enumerate(csv.DictReader(handle)):
			speed = _parse_float(row.get("speed"))
			duration = _parse_float(row.get("time_diff"))
			start = _parse_float(row.get("start_time"))
			end = _parse_float(row.get("end_time"))
			slat = _parse_float(row.get("start_latitude"))
			slon = _parse_float(row.get("start_longitude"))
			elat = _parse_float(row.get("end_latitude"))
			elon = _parse_float(row.get("end_longitude"))
			if None in (speed, duration, start, end, slat, slon, elat, elon):
				continue
			if _parse_bool(row.get("is_stationary")) or duration < 60.0:
				continue
			distance_m = _haversine_m(float(slat), float(slon), float(elat), float(elon))
			airport_distance_m = min(
				min(
					_haversine_m(float(slat), float(slon), a_lat, a_lon),
					_haversine_m(float(elat), float(elon), a_lat, a_lon),
				)
				for a_lat, a_lon in AIRPORTS.values()
			)
			if speed < 20.0:
				continue
			if not (speed >= 35.0 or distance_m >= 20_000.0 or airport_distance_m <= 15_000.0):
				continue
			airport_bonus = max(0.0, (30_000.0 - airport_distance_m) / 1000.0)
			score = speed * 2.0 + distance_m / 1000.0 + airport_bonus
			confidence = 0.58 if speed >= 50.0 and (distance_m >= 20_000.0 or airport_distance_m <= 20_000.0) else 0.42
			out.append(
				{
					"uid": uid,
					"label": "flight",
					"sourceFile": "od.csv",
					"segmentIdx": str(idx),
					"startTime": min(float(start), float(end)),
					"endTime": max(float(start), float(end)),
					"durationSeconds": max(0.0, abs(float(end) - float(start))),
					"speed": float(speed),
					"distanceMeters": distance_m,
					"airportDistanceMeters": airport_distance_m,
					"score": score,
					"confidence": confidence,
					"needsHumanReview": True,
					"evidenceMetric": (
						f"flight_candidate speed={float(speed):.1f}m/s distance={distance_m:.0f}m "
						f"airport_distance={airport_distance_m:.0f}m"
					),
				}
			)
	return out


def _candidates_for_uid(result_root: Path, uid: str, label: str) -> list[dict[str, Any]]:
	if label == "low_speed":
		return _low_speed_candidates_for_uid(result_root, uid)
	if label == "flight":
		return _flight_candidates_for_uid(result_root, uid)
	return _direct_match_candidates_for_uid(result_root, uid, label)


def _best_per_uid(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
	best: dict[str, dict[str, Any]] = {}
	for item in candidates:
		uid = str(item.get("uid") or "")
		if not uid:
			continue
		prev = best.get(uid)
		if prev is None or float(item.get("score") or 0.0) > float(prev.get("score") or 0.0):
			best[uid] = item
	return sorted(best.values(), key=lambda item: float(item.get("score") or 0.0), reverse=True)


def discover_mode_candidates(
	result_root: Path | str,
	labels: list[str] | None = None,
	*,
	per_label: int = 6,
	max_uids: int | None = None,
) -> dict[str, Any]:
	root = Path(result_root).expanduser().resolve()
	manifest = _read_manifest(root)
	uids = [str(uid) for uid in manifest.get("uids", []) or []]
	if max_uids is not None and max_uids >= 0:
		uids = uids[: int(max_uids)]
	target_labels = labels or parse_mode_labels(None)
	selected: dict[str, list[dict[str, Any]]] = {}
	for label in target_labels:
		candidates: list[dict[str, Any]] = []
		for uid in uids:
			candidates.extend(_candidates_for_uid(root, uid, label))
		selected[label] = _best_per_uid(candidates)[: max(0, int(per_label))]
	return {
		"schema": "studio_agent_mode_candidates/v1",
		"batch": str(manifest.get("batch_name") or manifest.get("batch") or root.parent.name),
		"result_root": str(root),
		"uid_count_scanned": len(uids),
		"per_label": int(per_label),
		"labels": target_labels,
		"classes": selected,
		"annotation_plan": build_annotation_plan(selected),
	}


def _segment_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
	label = normalize_mode_label(candidate.get("label"))
	spec = MODE_LABELS[label]
	start = float(candidate["startTime"])
	end = float(candidate["endTime"])
	match_type = str(candidate.get("matchType") or "").strip()
	semantic_tags = [
		"workflow:multimode_labeling_v1",
		f"mode:{spec['status']}",
		f"class:{label}",
	]
	if match_type:
		semantic_tags.append(f"matcher:{match_type}")
	if label == "low_speed":
		semantic_tags.append("heuristic:od_low_speed")
	if label == "flight":
		semantic_tags.append("heuristic:od_high_speed_airport")
	return {
		"id": f"mode:{label}:{candidate.get('uid')}:{round(start)}-{round(end)}",
		"categoryId": spec["categoryId"],
		"categoryName": spec["categoryName"],
		"color": spec["color"],
		"startTime": start,
		"endTime": end,
		"semanticTags": semantic_tags,
		"reconstructionQuality": "uncertain" if candidate.get("needsHumanReview") else "accurate",
		"accuracyLabel": "review_needed" if candidate.get("needsHumanReview") else "accurate",
		"visualEvidenceRefs": [],
		"evidence": {
			"summary": str(candidate.get("evidenceMetric") or ""),
			"sourceFile": str(candidate.get("sourceFile") or ""),
			"segmentIdx": str(candidate.get("segmentIdx") or ""),
			"score": float(candidate.get("score") or 0.0),
		},
		"confidence": float(candidate.get("confidence") or 0.0),
		"needsHumanReview": bool(candidate.get("needsHumanReview")),
	}


def build_annotation_plan(classes: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
	plan: list[dict[str, Any]] = []
	for label, candidates in classes.items():
		for candidate in candidates:
			uid = str(candidate.get("uid") or "").strip()
			if not uid:
				continue
			plan.append(
				{
					"uid": uid,
					"label": normalize_mode_label(label),
					"candidate": candidate,
					"segment": _segment_for_candidate(candidate),
				}
			)
	return plan


def apply_annotation_plan(
	client: StudioAgentClient,
	plan_payload: dict[str, Any],
	*,
	batch: str | None,
	reviewer_id: str,
	reviewer_name: str,
	decision: str = "accept",
	notes: str = "studio-agent multimode labeling",
	dry_run: bool = False,
) -> dict[str, Any]:
	entries = plan_payload.get("annotation_plan")
	if not isinstance(entries, list):
		raise ValueError("plan payload requires annotation_plan list")
	by_uid: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for entry in entries:
		if not isinstance(entry, dict):
			continue
		uid = str(entry.get("uid") or "").strip()
		segment = entry.get("segment")
		if uid and isinstance(segment, dict):
			by_uid[uid].append(segment)
	if not by_uid:
		raise ValueError("annotation_plan did not contain any uid/segment entries")
	if dry_run:
		return {
			"status": "dry_run",
			"uid_count": len(by_uid),
			"segment_count": sum(len(v) for v in by_uid.values()),
			"uids": sorted(by_uid),
		}
	session = client.open_reviewer_session(
		display_name=reviewer_name,
		reviewer_id=reviewer_id,
		batch=batch,
	)
	applied: list[dict[str, Any]] = []
	for uid, segments in sorted(by_uid.items(), key=lambda item: item[0]):
		labels = sorted({
			normalize_mode_label(seg.get("categoryId") or seg.get("categoryName"))
			for seg in segments
			if str(seg.get("categoryId") or seg.get("categoryName") or "").strip()
		})
		review = client.submit_review(
			uid=uid,
			decision=decision,
			reviewer_id=reviewer_id,
			reviewer_name=reviewer_name,
			notes=f"{notes}; labels={','.join(labels)}",
			reference_source="studio_agent_mode_labeling",
			trajectory_tags=["studio_agent_mode_labeling_v1", *[f"contains:{label}" for label in labels]],
			batch=batch,
		)
		timeline = client.put_timeline(
			uid=uid,
			reviewer_id=reviewer_id,
			reviewer_name=reviewer_name,
			payload={
				"segmentPolicy": {"exclusiveMode": False, "intervalSemantics": "closed_interval"},
				"pins": [],
				"segments": segments,
			},
			batch=batch,
		)
		applied.append(
			{
				"uid": uid,
				"labels": labels,
				"segment_count": len(segments),
				"review": review.get("review"),
				"timeline_segment_count": len((timeline.get("annotations") or {}).get("segments") or []),
			}
		)
	return {
		"status": "applied",
		"reviewer": session.get("reviewer"),
		"uid_count": len(applied),
		"segment_count": sum(item["segment_count"] for item in applied),
		"applied": applied,
	}


__all__ = [
	"MODE_LABELS",
	"apply_annotation_plan",
	"build_annotation_plan",
	"discover_mode_candidates",
	"normalize_mode_label",
	"parse_mode_labels",
]
