#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.bundle.yml"
ENV_FILE="${STUDIO_ENV_FILE:-$SCRIPT_DIR/bundle.env}"

docker compose \
	--env-file "$ENV_FILE" \
	-f "$COMPOSE_FILE" \
	down
