#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
IMAGE_TAG="${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
IMAGE_TAR="${STUDIO_IMAGE_TAR:-$BUNDLE_ROOT/trajectory_annotation_studio_offline_image.tar}"

if docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
	echo "docker image already present: $IMAGE_TAG"
	exit 0
fi

if [[ ! -f "$IMAGE_TAR" ]]; then
	echo "image tar not found: $IMAGE_TAR" >&2
	echo "set STUDIO_IMAGE_TAR or place trajectory_annotation_studio_offline_image.tar at bundle root" >&2
	exit 1
fi

echo "loading docker image from: $IMAGE_TAR"
docker load -i "$IMAGE_TAR"
echo "docker image ready: $IMAGE_TAG"
