#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${1:-$ROOT_DIR/delivery_out/trajectory_annotation_studio_offline_bundle_$STAMP}"
ARCHIVE_PATH="${OUTPUT_DIR}.tar.gz"
IMAGE_TAR_PATH="${IMAGE_TAR_PATH:-$ROOT_DIR/trajectory_annotation_studio_offline_image.tar}"
IMAGE_TAR_BASENAME="$(basename "$IMAGE_TAR_PATH")"

mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/my_history_methods/map_matching/vendor" "$OUTPUT_DIR/project_data" "$OUTPUT_DIR/runtime"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude '.runtime' \
	--exclude 'data' \
	--exclude 'test-results' \
	--exclude '_backup*' \
	"$ROOT_DIR/trajectory_annotation_studio/" \
	"$OUTPUT_DIR/trajectory_annotation_studio/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude 'data' \
	"$ROOT_DIR/my_history_methods/cellular_quality/" \
	"$OUTPUT_DIR/my_history_methods/cellular_quality/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	"$ROOT_DIR/my_history_methods/map_matching/vendor/fmm/" \
	"$OUTPUT_DIR/my_history_methods/map_matching/vendor/fmm/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	"$ROOT_DIR/project_data/map_assets/" \
	"$OUTPUT_DIR/project_data/map_assets/"

cat > "$OUTPUT_DIR/runtime/README.md" <<'EOF'
# Runtime Data Directory

这个目录用于容器运行时持久化：

- `incoming/`：用户上传原始 CSV
- `catalog/`：上传 / 资产 / 批次元数据
- `datasets/user_assets/`：上传处理后的资产结果
- `published/`：发布后的 batch
- `offline_tiles_cache/`：离线瓦片缓存

压缩包默认不携带任何真实信令数据。
EOF

if [[ -f "$IMAGE_TAR_PATH" ]]; then
	cp "$IMAGE_TAR_PATH" "$OUTPUT_DIR/$IMAGE_TAR_BASENAME"
fi

cat > "$OUTPUT_DIR/DELIVERY_MANIFEST.txt" <<EOF
Trajectory Annotation Studio Offline Delivery Bundle
==================================================

bundle_root=$(basename "$OUTPUT_DIR")
created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
image_tar_included=$([[ -f "$OUTPUT_DIR/$IMAGE_TAR_BASENAME" ]] && echo yes || echo no)
image_tar_name=$IMAGE_TAR_BASENAME

Quick start:
1. cd trajectory_annotation_studio/deploy/docker
2. edit bundle.env if you need to change port or intranet tile URL
3. bash start_bundle.sh
4. open http://127.0.0.1:\${HOST_STUDIO_PORT:-8016}/web/index.html

Stop:
  bash trajectory_annotation_studio/deploy/docker/stop_bundle.sh
EOF

(
	cd "$OUTPUT_DIR"
	shasum -a 256 $(find . -maxdepth 1 -type f | sed 's#^\./##' | LC_ALL=C sort) > SHA256SUMS.txt
)

tar -czf "$ARCHIVE_PATH" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"

echo "bundle directory: $OUTPUT_DIR"
echo "bundle archive:   $ARCHIVE_PATH"
