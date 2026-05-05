#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
DEFAULT_OUTPUT_TAR="$ROOT_DIR/trajectory_annotation_studio_offline_image.tar"
OUTPUT_TAR="${OUTPUT_TAR:-$DEFAULT_OUTPUT_TAR}"
BUILD_CONTEXT_DIR="${BUILD_CONTEXT_DIR:-}"
SKIP_FMM="${SKIP_FMM:-0}"
DEFAULT_SIGNAL6_PIPELINE_MODE="${DEFAULT_SIGNAL6_PIPELINE_MODE:-v311}"
EXPORT_IMAGE_TAR="${EXPORT_IMAGE_TAR:-1}"
DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
DOCKER_BUILDER="${DOCKER_BUILDER:-}"
DOCKER_USE_BUILDX="${DOCKER_USE_BUILDX:-0}"
PYTHON_BASE_IMAGE="${PYTHON_BASE_IMAGE:-}"
FMM_BUILD_JOBS="${FMM_BUILD_JOBS:-}"
APT_MIRROR="${APT_MIRROR:-}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}"

if [[ -z "$PYTHON_BASE_IMAGE" ]]; then
	if docker image inspect python_local_cache:3.11-slim >/dev/null 2>&1; then
		PYTHON_BASE_IMAGE="python_local_cache:3.11-slim"
	else
		PYTHON_BASE_IMAGE="python:3.11-slim"
	fi
fi

platform_suffix() {
	local value="$1"
	value="${value//\//_}"
	value="${value//:/_}"
	echo "$value"
}

if [[ -n "$DOCKER_PLATFORM" ]]; then
	DOCKER_USE_BUILDX=1
	if [[ -z "$FMM_BUILD_JOBS" ]]; then
		FMM_BUILD_JOBS=1
	fi
	PLATFORM_SUFFIX="$(platform_suffix "$DOCKER_PLATFORM")"
	BASE_IMAGE="${IMAGE_TAG%:*}"
	IMAGE_NAME="${BASE_IMAGE##*/}"
	if [[ "$IMAGE_TAG" == *:* ]]; then
		IMAGE_TAG="${BASE_IMAGE}:${PLATFORM_SUFFIX}"
	else
		IMAGE_TAG="${IMAGE_TAG}_${PLATFORM_SUFFIX}"
	fi
	if [ "$OUTPUT_TAR" = "$DEFAULT_OUTPUT_TAR" ]; then
		OUTPUT_TAR="$ROOT_DIR/${IMAGE_NAME//-/_}_image_${PLATFORM_SUFFIX}.tar"
	fi
fi

# Adjust defaults for no-FMM builds
if [ "$SKIP_FMM" = "1" ]; then
	BASE_IMAGE="${IMAGE_TAG%:*}"
	IMAGE_TAG="${BASE_IMAGE}:no-fmm"
	DEFAULT_SIGNAL6_PIPELINE_MODE="legacy"
	if [ "$OUTPUT_TAR" = "$DEFAULT_OUTPUT_TAR" ]; then
		if [[ -n "${PLATFORM_SUFFIX:-}" ]]; then
			OUTPUT_TAR="$ROOT_DIR/trajectory_annotation_studio_offline_image_no_fmm_${PLATFORM_SUFFIX}.tar"
		else
			OUTPUT_TAR="$ROOT_DIR/trajectory_annotation_studio_offline_image_no_fmm.tar"
		fi
	fi
fi

cleanup() {
	if [[ -n "${TMP_BUILD_CONTEXT_DIR:-}" && -d "${TMP_BUILD_CONTEXT_DIR:-}" ]]; then
		rm -rf "$TMP_BUILD_CONTEXT_DIR"
	fi
}

if [[ -z "$BUILD_CONTEXT_DIR" ]]; then
	TMP_BUILD_CONTEXT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/studio-docker-build.XXXXXX")"
	BUILD_CONTEXT_DIR="$TMP_BUILD_CONTEXT_DIR"
	trap cleanup EXIT
fi

mkdir -p \
	"$BUILD_CONTEXT_DIR/my_history_methods/map_matching/vendor" \
	"$BUILD_CONTEXT_DIR/project_data"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude '.runtime' \
	--exclude 'data/batches' \
	--exclude 'data/source' \
	--exclude 'data/incoming' \
	--exclude 'data/catalog' \
	--exclude 'data/datasets' \
	--exclude 'test-results' \
	--exclude '_backup*' \
	"$ROOT_DIR/trajectory_annotation_studio/" \
	"$BUILD_CONTEXT_DIR/trajectory_annotation_studio/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	"$ROOT_DIR/my_history_methods/cellular_quality/" \
	"$BUILD_CONTEXT_DIR/my_history_methods/cellular_quality/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude 'build' \
	--exclude 'build-linux' \
	"$ROOT_DIR/my_history_methods/map_matching/vendor/fmm/" \
	"$BUILD_CONTEXT_DIR/my_history_methods/map_matching/vendor/fmm/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude 'cid2gps.csv' \
	"$ROOT_DIR/project_data/map_assets/" \
	"$BUILD_CONTEXT_DIR/project_data/map_assets/"

if [ "$DOCKER_USE_BUILDX" = "1" ]; then
	BUILD_CMD=(docker buildx build)
	if [[ -n "$DOCKER_BUILDER" ]]; then
		BUILD_CMD+=(--builder "$DOCKER_BUILDER")
	fi
	BUILD_CMD+=(
		--platform "$DOCKER_PLATFORM"
		--load
		-f "$BUILD_CONTEXT_DIR/trajectory_annotation_studio/deploy/docker/Dockerfile"
		-t "$IMAGE_TAG"
		--build-arg "PYTHON_BASE_IMAGE=$PYTHON_BASE_IMAGE"
		--build-arg "ENABLE_FMM_BUILD=$((1 - SKIP_FMM))"
		--build-arg "FMM_BUILD_JOBS=$FMM_BUILD_JOBS"
		--build-arg "DEFAULT_SIGNAL6_PIPELINE_MODE=$DEFAULT_SIGNAL6_PIPELINE_MODE"
		--build-arg "APT_MIRROR=$APT_MIRROR"
		--build-arg "PIP_INDEX_URL=$PIP_INDEX_URL"
		--build-arg "PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST"
		"$BUILD_CONTEXT_DIR"
	)
	DOCKER_BUILDKIT="$DOCKER_BUILDKIT" "${BUILD_CMD[@]}"
else
	DOCKER_BUILDKIT="$DOCKER_BUILDKIT" docker build \
		-f "$BUILD_CONTEXT_DIR/trajectory_annotation_studio/deploy/docker/Dockerfile" \
		-t "$IMAGE_TAG" \
		--build-arg PYTHON_BASE_IMAGE="$PYTHON_BASE_IMAGE" \
		--build-arg ENABLE_FMM_BUILD=$((1 - SKIP_FMM)) \
		--build-arg FMM_BUILD_JOBS="$FMM_BUILD_JOBS" \
		--build-arg DEFAULT_SIGNAL6_PIPELINE_MODE="$DEFAULT_SIGNAL6_PIPELINE_MODE" \
		--build-arg APT_MIRROR="$APT_MIRROR" \
		--build-arg PIP_INDEX_URL="$PIP_INDEX_URL" \
		--build-arg PIP_TRUSTED_HOST="$PIP_TRUSTED_HOST" \
		"$BUILD_CONTEXT_DIR"
fi

if [ "$EXPORT_IMAGE_TAR" = "1" ]; then
	docker save -o "$OUTPUT_TAR" "$IMAGE_TAG"
fi

echo "signal6 pipeline mode: $DEFAULT_SIGNAL6_PIPELINE_MODE"
echo "skip fmm build:        $SKIP_FMM"
echo "docker buildkit:       $DOCKER_BUILDKIT"
echo "docker buildx:         $DOCKER_USE_BUILDX"
echo "docker platform:       ${DOCKER_PLATFORM:-native}"
echo "docker builder:        ${DOCKER_BUILDER:-default}"
echo "python base image:     $PYTHON_BASE_IMAGE"
echo "fmm build jobs:        ${FMM_BUILD_JOBS:-auto}"
echo "apt mirror:            ${APT_MIRROR:-default}"
echo "pip index url:         ${PIP_INDEX_URL:-default}"
echo "pip trusted host:      ${PIP_TRUSTED_HOST:-default}"
echo "export image tar:      $EXPORT_IMAGE_TAR"
if [ "$EXPORT_IMAGE_TAR" = "1" ]; then
	echo "image exported: $OUTPUT_TAR"
else
	echo "image tar export skipped"
fi
