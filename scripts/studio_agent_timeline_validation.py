#!/usr/bin/env python3
"""stdlib-only validation for vNext timeline annotation payloads."""

from __future__ import annotations

import math
from typing import Any


_QUALITY_ALIASES = {
	"accurate": "accurate",
	"inaccurate": "inaccurate",
	"uncertain": "uncertain",
	"review_needed": "review_needed",
	"review-needed": "review_needed",
	"needs_review": "review_needed",
	"needsreview": "review_needed",
	"reviewneeded": "review_needed",
}


def _normalize_quality_token(raw: Any) -> str | None:
	if raw is None:
		return None
	text = str(raw).strip()
	if not text:
		return None
	norm = text.lower().replace("-", "_").replace(" ", "_")
	while "__" in norm:
		norm = norm.replace("__", "_")
	return _QUALITY_ALIASES.get(norm, norm)


def _parse_bound(value: Any) -> float | None:
	if value is None:
		return None
	if isinstance(value, bool):
		return None
	if isinstance(value, (int, float)):
		if isinstance(value, float) and not math.isfinite(value):
			return None
		return float(value)
	if isinstance(value, str):
		stripped = value.strip()
		if not stripped:
			return None
		try:
			out = float(stripped)
		except ValueError:
			return None
		if not math.isfinite(out):
			return None
		return out
	return None


def _segment_time_bounds(seg: dict[str, Any]) -> tuple[float | None, float | None, list[str]]:
	warnings: list[str] = []
	st_t = _parse_bound(seg.get("startTime"))
	st_a = _parse_bound(seg.get("start"))
	en_t = _parse_bound(seg.get("endTime"))
	en_a = _parse_bound(seg.get("end"))
	if st_t is not None and st_a is not None and st_t != st_a:
		warnings.append("start and startTime disagree")
	if en_t is not None and en_a is not None and en_t != en_a:
		warnings.append("end and endTime disagree")
	start = st_t if st_t is not None else st_a
	end = en_t if en_t is not None else en_a
	return start, end, warnings


def _category_or_tags_ok(seg: dict[str, Any]) -> bool:
	cat_id = str(seg.get("categoryId") or "").strip()
	cat_name = str(seg.get("categoryName") or "").strip()
	if cat_id or cat_name:
		return True
	tags = seg.get("semanticTags")
	if isinstance(tags, list) and len(tags) > 0:
		return True
	return False


def _is_nonempty_evidence(evidence: Any) -> bool:
	if not isinstance(evidence, dict):
		return False
	return len(evidence) > 0


def _segment_is_inaccurate(seg: dict[str, Any]) -> bool:
	for key in ("reconstructionQuality", "accuracyLabel"):
		if key not in seg:
			continue
		token = _normalize_quality_token(seg.get(key))
		if token == "inaccurate":
			return True
	return False


_ALLOWED_QUALITIES = frozenset({"accurate", "inaccurate", "uncertain", "review_needed"})


def validate_timeline_payload(
	payload: Any,
	sample_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
	errors: list[str] = []
	warnings: list[str] = []

	if not isinstance(payload, dict):
		return {
			"ok": False,
			"errors": ["payload must be a JSON object"],
			"warnings": warnings,
			"segment_count": 0,
			"track_edit_ref_count": 0,
		}

	segments = payload.get("segments", [])
	if segments is None:
		errors.append("segments must be a list (got null)")
		segments = []
	elif not isinstance(segments, list):
		errors.append(f"segments must be a list (got {type(segments).__name__})")
		segments = []

	all_track_refs: set[str] = set()
	qualities_seen: list[tuple[int, str, str]] = []

	for idx, raw in enumerate(segments):
		prefix = f"segments[{idx}]"
		if not isinstance(raw, dict):
			errors.append(f"{prefix} must be an object")
			continue
		start, end, tw = _segment_time_bounds(raw)
		warnings.extend(f"{prefix}: {w}" for w in tw)
		if start is None or end is None:
			errors.append(f"{prefix} requires numeric startTime/endTime (or start/end)")
			continue
		if start >= end:
			errors.append(f"{prefix} requires start < end (got {start} >= {end})")

		if not _category_or_tags_ok(raw):
			errors.append(
				f"{prefix} needs categoryId/categoryName or non-empty semanticTags",
			)

		for list_key in ("semanticTags", "errorTypes", "visualEvidenceRefs", "trackEditRefs"):
			if list_key not in raw:
				continue
			val = raw.get(list_key)
			if not isinstance(val, list):
				errors.append(f"{prefix}.{list_key} must be a list when present")

		for qkey in ("reconstructionQuality", "accuracyLabel"):
			if qkey not in raw:
				continue
			if raw.get(qkey) is None or str(raw.get(qkey)).strip() == "":
				continue
			norm = _normalize_quality_token(raw.get(qkey))
			if norm is None:
				continue
			if norm not in _ALLOWED_QUALITIES:
				errors.append(f"{prefix}.{qkey} must be one of accurate/inaccurate/uncertain/review_needed (got {raw.get(qkey)!r})")
			else:
				qualities_seen.append((idx, qkey, norm))

		if "confidence" in raw:
			cval = raw.get("confidence")
			cnum: float | None = None
			if isinstance(cval, bool):
				errors.append(f"{prefix}.confidence must be numeric in [0,1]")
			elif isinstance(cval, (int, float)):
				if isinstance(cval, float) and not math.isfinite(cval):
					errors.append(f"{prefix}.confidence must be numeric in [0,1]")
				else:
					cnum = float(cval)
			elif isinstance(cval, str) and cval.strip():
				try:
					cnum = float(cval.strip())
				except ValueError:
					errors.append(f"{prefix}.confidence must be numeric in [0,1]")
					cnum = None
				if cnum is not None and not math.isfinite(cnum):
					errors.append(f"{prefix}.confidence must be numeric in [0,1]")
					cnum = None
			elif cval is not None:
				errors.append(f"{prefix}.confidence must be numeric in [0,1]")
			if cnum is not None and not (0.0 <= cnum <= 1.0):
				errors.append(f"{prefix}.confidence must be in [0,1] (got {cnum})")

		track_refs = raw.get("trackEditRefs")
		if isinstance(track_refs, list):
			seen_local: set[str] = set()
			dup = False
			for ent in track_refs:
				ref = str(ent or "").strip()
				if not ref:
					continue
				if ref in seen_local:
					dup = True
				seen_local.add(ref)
				all_track_refs.add(ref)
			if dup:
				errors.append(f"{prefix}.trackEditRefs must be unique (duplicate entries)")

		if _segment_is_inaccurate(raw):
			ev_ok = _is_nonempty_evidence(raw.get("evidence"))
			te = raw.get("trackEditRefs")
			te_ok = isinstance(te, list) and any(str(x or "").strip() for x in te)
			if not ev_ok and not te_ok:
				errors.append(
					f"{prefix} marked inaccurate must include evidence or trackEditRefs",
				)

	by_idx: dict[int, set[str]] = {}
	for idx, qkey, norm in qualities_seen:
		by_idx.setdefault(idx, set()).add(norm)
	for idx, norms in by_idx.items():
		if len(norms) > 1 and "accurate" in norms and "inaccurate" in norms:
			warnings.append(f"segments[{idx}]: reconstructionQuality/accuracyLabel disagree")

	if isinstance(sample_summary, dict):
		exp = sample_summary.get("segment_count")
		if isinstance(exp, int) and exp >= 0 and exp != len(segments):
			warnings.append(
				f"sample_summary.segment_count={exp} but payload has {len(segments)} segments",
			)

	ok = len(errors) == 0
	return {
		"ok": ok,
		"errors": errors,
		"warnings": warnings,
		"segment_count": len(segments),
		"track_edit_ref_count": len(all_track_refs),
	}
