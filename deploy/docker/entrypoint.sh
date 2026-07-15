#!/usr/bin/env bash
set -euo pipefail

STUDIO_HOME="${STUDIO_HOME:-/opt/studio}"
APP_ROOT="${STUDIO_APP_ROOT:-$STUDIO_HOME/trajectory_annotation_studio}"
RUNTIME_ROOT="${STUDIO_RUNTIME_ROOT:-$STUDIO_HOME/runtime}"
DEFAULT_BATCH_ROOT="${STUDIO_DEFAULT_BATCH_ROOT:-$RUNTIME_ROOT/default_batch}"
DEPLOYMENT_CONFIG_PATH="${STUDIO_DEPLOYMENT_CONFIG_PATH:-$APP_ROOT/web/runtime/deployment_runtime_config.js}"

mkdir -p \
	"$RUNTIME_ROOT/incoming" \
	"$RUNTIME_ROOT/offline_tiles_cache" \
	"$RUNTIME_ROOT/catalog/uploads" \
	"$RUNTIME_ROOT/catalog/assets" \
	"$RUNTIME_ROOT/catalog/batches" \
	"$RUNTIME_ROOT/datasets/user_assets" \
	"$RUNTIME_ROOT/published/private" \
	"$RUNTIME_ROOT/published/public" \
	"$DEFAULT_BATCH_ROOT/result" \
	"$DEFAULT_BATCH_ROOT/review/reviewers" \
	"$DEFAULT_BATCH_ROOT/review/aggregate" \
	"$DEFAULT_BATCH_ROOT/review/system" \
	"$DEFAULT_BATCH_ROOT/accepted_assets"

python3 "$APP_ROOT/deploy/docker/render_deployment_runtime_config.py" "$DEPLOYMENT_CONFIG_PATH"

exec python3 -m trajectory_annotation_studio.web.review_server \
	--host "${STUDIO_HOST:-0.0.0.0}" \
	--port "${STUDIO_PORT:-8016}" \
	--project-root "$APP_ROOT" \
	--result-root "$DEFAULT_BATCH_ROOT/result" \
	--review-root "$DEFAULT_BATCH_ROOT/review" \
	--export-root "$DEFAULT_BATCH_ROOT/accepted_assets" \
	--batches-root "$RUNTIME_ROOT/published" \
	--incoming-root "$RUNTIME_ROOT/incoming" \
	--offline-tile-cache-root "$RUNTIME_ROOT/offline_tiles_cache" \
	--signal6-pipeline-mode "${STUDIO_SIGNAL6_PIPELINE_MODE:-v311}"
