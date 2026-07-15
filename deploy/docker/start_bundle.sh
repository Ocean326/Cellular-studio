#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.bundle.yml"
ENV_FILE="${STUDIO_ENV_FILE:-$SCRIPT_DIR/bundle.env}"

mkdir -p \
	"$BUNDLE_ROOT/runtime/incoming" \
	"$BUNDLE_ROOT/runtime/catalog/uploads" \
	"$BUNDLE_ROOT/runtime/catalog/assets" \
	"$BUNDLE_ROOT/runtime/catalog/batches" \
	"$BUNDLE_ROOT/runtime/datasets/user_assets" \
	"$BUNDLE_ROOT/runtime/published/public" \
	"$BUNDLE_ROOT/runtime/published/private" \
	"$BUNDLE_ROOT/runtime/offline_tiles_cache"

"$SCRIPT_DIR/load_bundle_image.sh"

docker compose \
	--env-file "$ENV_FILE" \
	-f "$COMPOSE_FILE" \
	up -d

HOST_PORT="$(
	awk -F= '$1=="HOST_STUDIO_PORT" {print $2}' "$ENV_FILE" 2>/dev/null | tail -n 1
)"
HOST_PORT="${HOST_PORT:-8016}"
echo "studio started: http://127.0.0.1:${HOST_PORT}/web/index.html"
