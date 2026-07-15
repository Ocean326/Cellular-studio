#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
IMAGE_TAG="${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
IMAGE_TAR="${STUDIO_IMAGE_TAR:-$BUNDLE_ROOT/trajectory_annotation_studio_offline_image.tar}"
MIN_FREE_GB="${STUDIO_DOCKER_MIN_FREE_GB:-12}"

if docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
	echo "docker image already present: $IMAGE_TAG"
	exit 0
fi

if [[ ! -f "$IMAGE_TAR" ]]; then
	echo "image tar not found: $IMAGE_TAR" >&2
	echo "set STUDIO_IMAGE_TAR or place trajectory_annotation_studio_offline_image.tar at bundle root" >&2
	exit 1
fi

docker_root="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || true)"
if [[ -n "$docker_root" && -d "$docker_root" && "$MIN_FREE_GB" =~ ^[0-9]+$ ]]; then
	available_kb="$(df -Pk "$docker_root" | awk 'NR==2 {print $4}')"
	required_kb=$((MIN_FREE_GB * 1024 * 1024))
	if [[ "${available_kb:-0}" -lt "$required_kb" ]]; then
		echo "not enough free space under Docker root: $docker_root" >&2
		echo "available: $((available_kb / 1024 / 1024))GB, required: ${MIN_FREE_GB}GB" >&2
		exit 1
	fi
fi

echo "loading docker image from: $IMAGE_TAR"
docker load -i "$IMAGE_TAR"
echo "docker image ready: $IMAGE_TAG"
