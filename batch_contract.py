from __future__ import annotations

from typing import Any


DEFAULT_RESULT_FILES = ("raw.csv", "snap.csv", "od.csv", "fmm.csv", "line.csv")
LEGACY_REVIEW_REFERENCE_FILES = ("line.csv", "fmm.csv")


def dedupe_preserve_order(items: list[str]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for item in items:
		value = str(item or "").strip()
		if not value or value in seen:
			continue
		seen.add(value)
		result.append(value)
	return result


def normalize_manifest_layer_specs(manifest_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
	layer_order = [
		str(item or "").strip()
		for item in manifest_payload.get("layers", []) or []
		if str(item or "").strip()
	]
	layer_specs = manifest_payload.get("layer_specs") if isinstance(manifest_payload.get("layer_specs"), dict) else {}
	legacy_layer_styles = (
		manifest_payload.get("layer_styles") if isinstance(manifest_payload.get("layer_styles"), dict) else {}
	)
	if not layer_order:
		layer_order = dedupe_preserve_order([*legacy_layer_styles.keys(), *layer_specs.keys()])
	specs: dict[str, dict[str, Any]] = {}
	for layer in layer_order:
		merged: dict[str, Any] = {}
		if isinstance(legacy_layer_styles.get(layer), dict):
			merged.update(legacy_layer_styles[layer])
		if isinstance(layer_specs.get(layer), dict):
			merged.update(layer_specs[layer])
		filename = str(merged.get("filename") or f"{layer}.csv").strip() or f"{layer}.csv"
		merged["filename"] = filename
		specs[layer] = merged
	return specs


def get_manifest_layer_filenames(manifest_payload: dict[str, Any]) -> list[str]:
	specs = normalize_manifest_layer_specs(manifest_payload)
	if specs:
		return dedupe_preserve_order([str(spec.get("filename") or "").strip() for spec in specs.values()])
	layers = [
		str(item or "").strip()
		for item in manifest_payload.get("layers", []) or []
		if str(item or "").strip()
	]
	if layers:
		return dedupe_preserve_order([f"{layer}.csv" for layer in layers])
	return list(DEFAULT_RESULT_FILES)


def get_manifest_review_reference_filenames(manifest_payload: dict[str, Any]) -> list[str]:
	if "review_reference_files" in manifest_payload and isinstance(manifest_payload.get("review_reference_files"), list):
		reference_files = [
			str(item or "").strip()
			for item in manifest_payload.get("review_reference_files", []) or []
			if str(item or "").strip()
		]
		return dedupe_preserve_order(reference_files)

	specs = normalize_manifest_layer_specs(manifest_payload)
	reference_layers = {
		str(item or "").strip()
		for item in manifest_payload.get("review_reference_layers", []) or []
		if str(item or "").strip()
	}
	from_specs = [
		str(spec.get("filename") or "").strip()
		for layer, spec in specs.items()
		if spec.get("review_reference") or layer in reference_layers
	]
	if from_specs:
		return dedupe_preserve_order(from_specs)
	return list(LEGACY_REVIEW_REFERENCE_FILES)
