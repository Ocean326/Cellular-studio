#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CELLULAR_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"

BATCH_NAME="${BATCH_NAME:-signal_gps_v311_speed_sparsity_20260603}"
BATCH_LABEL="${BATCH_LABEL:-Signal GPS v311 speed-sparsity final demo}"
IMAGE_TAG="${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
OUTPUT_DIR="${1:-${OUTPUT_DIR:-$CELLULAR_ROOT/delivery_out/signal_studio_final_demo_assets_$STAMP}}"
ARCHIVE_PATH="${ARCHIVE_PATH:-$OUTPUT_DIR.tar.gz}"

FINAL_BATCH_DIR="$PROJECT_ROOT/data/batches/$BATCH_NAME"
TEST_INPUT_DIR="$PROJECT_ROOT/data/test"
CELLULAR_QUALITY_DIR="$CELLULAR_ROOT/my_history_methods/cellular_quality"
FMM_DIR="$CELLULAR_ROOT/my_history_methods/map_matching/vendor/fmm"
MAP_ASSETS_DIR="$CELLULAR_ROOT/project_data/map_assets"

require_dir() {
	local label="$1"
	local path="$2"
	if [[ ! -d "$path" ]]; then
		echo "missing $label: $path" >&2
		exit 1
	fi
}

require_dir "final batch" "$FINAL_BATCH_DIR"
require_dir "test input routes" "$TEST_INPUT_DIR"
require_dir "cellular quality runtime" "$CELLULAR_QUALITY_DIR"
require_dir "fmm source" "$FMM_DIR"
require_dir "map assets" "$MAP_ASSETS_DIR"

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR" \
	"$OUTPUT_DIR/my_history_methods/map_matching/vendor" \
	"$OUTPUT_DIR/project_data/map_assets" \
	"$OUTPUT_DIR/runtime/published" \
	"$OUTPUT_DIR/runtime/incoming" \
	"$OUTPUT_DIR/runtime/catalog/uploads" \
	"$OUTPUT_DIR/runtime/catalog/assets" \
	"$OUTPUT_DIR/runtime/catalog/batches" \
	"$OUTPUT_DIR/runtime/datasets/user_assets" \
	"$OUTPUT_DIR/runtime/offline_tiles_cache" \
	"$OUTPUT_DIR/input_trajectories" \
	"$OUTPUT_DIR/data/test"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude '.runtime' \
	--exclude '.runtime_*' \
	--exclude 'data' \
	--exclude 'tmp' \
	--exclude 'test-results' \
	--exclude '_backup*' \
	"$PROJECT_ROOT/" \
	"$OUTPUT_DIR/trajectory_annotation_studio/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude 'data' \
	"$CELLULAR_QUALITY_DIR/" \
	"$OUTPUT_DIR/my_history_methods/cellular_quality/"

for asset_name in beijing beijing_mainroad_weighted beijing_subway beijing_railway; do
	require_dir "map asset $asset_name" "$MAP_ASSETS_DIR/$asset_name"
	rsync -a --delete \
		--exclude '__pycache__' \
		--exclude '.DS_Store' \
		"$MAP_ASSETS_DIR/$asset_name/" \
		"$OUTPUT_DIR/project_data/map_assets/$asset_name/"
done

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	--exclude '.git' \
	--exclude 'build' \
	--exclude 'build-*' \
	--exclude 'build_mainroad' \
	"$FMM_DIR/" \
	"$OUTPUT_DIR/my_history_methods/map_matching/vendor/fmm/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	"$FINAL_BATCH_DIR/" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/"

rm -rf \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/review" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/accepted_assets" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/review_exports"
mkdir -p \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/review/system" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/review/reviewers" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/review/aggregate" \
	"$OUTPUT_DIR/runtime/published/$BATCH_NAME/accepted_assets"

python3 - "$OUTPUT_DIR" "$BATCH_NAME" "$PROJECT_ROOT" <<'PY'
import json
import sys
from pathlib import Path

bundle_root = Path(sys.argv[1])
batch_name = sys.argv[2]
project_root = Path(sys.argv[3]).resolve()
batch_dir = bundle_root / "runtime" / "published" / batch_name
meta_path = batch_dir / "batch_meta.json"

runtime_result = f"/opt/studio/runtime/published/{batch_name}/result"
mainroad_edges = "/opt/studio/project_data/map_assets/beijing_mainroad_weighted/edges.shp"
standard_edges = "/opt/studio/project_data/map_assets/beijing/edges.shp"

def sanitize(value, key=""):
    if isinstance(value, dict):
        return {k: sanitize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, key) for v in value]
    if not isinstance(value, str):
        return value
    if key == "source_result_root":
        return runtime_result
    if key == "fmm_edges":
        if "mainroad" in value:
            return mainroad_edges
        return standard_edges
    prefix = str(project_root)
    if value.startswith(prefix):
        rel = value[len(prefix):].lstrip("/")
        if rel.startswith(f"data/batches/{batch_name}/result"):
            return runtime_result + rel[len(f"data/batches/{batch_name}/result"):]
        if "beijing_mainroad_weighted/edges.shp" in rel:
            return mainroad_edges
        if "project_data/map_assets/beijing/edges.shp" in rel:
            return standard_edges
        return f"/opt/studio/trajectory_annotation_studio/{rel}"
    return value

if meta_path.exists():
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["name"] = batch_name
    meta["status"] = "prepared"
    meta["result_mode"] = "packaged_final_demo"
    meta["source_result_root"] = runtime_result
    meta = sanitize(meta)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

source_batch_path = batch_dir / "source_batch.json"
if source_batch_path.exists():
    source_batch = json.loads(source_batch_path.read_text(encoding="utf-8"))
    source_batch = sanitize(source_batch)
    source_batch_path.write_text(json.dumps(source_batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	"$TEST_INPUT_DIR/" \
	"$OUTPUT_DIR/input_trajectories/eight_routes/"

rsync -a --delete \
	--exclude '__pycache__' \
	--exclude '.DS_Store' \
	"$TEST_INPUT_DIR/" \
	"$OUTPUT_DIR/data/test/"

python3 - "$OUTPUT_DIR/input_trajectories/eight_routes" "$OUTPUT_DIR/input_trajectories/signal_triplet_8routes_input.zip" <<'PY'
import sys
import zipfile
from pathlib import Path

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            if "__pycache__" in path.parts or path.name == ".DS_Store":
                continue
            zf.write(path, path.relative_to(source).as_posix())
PY

cat > "$OUTPUT_DIR/final-demo.env" <<EOF
STUDIO_IMAGE_TAG=$IMAGE_TAG
STUDIO_CONTAINER_NAME=signal-studio-final-demo
STUDIO_FINAL_BATCH_NAME=$BATCH_NAME
HOST_STUDIO_PORT=8016
STUDIO_CONTAINER_CPUS=2.0
STUDIO_CONTAINER_MEM_LIMIT=4g
STUDIO_RUN_CONTAINER_RUNTIME_CHECK=0
STUDIO_VERIFY_IMAGE_TAR=0
STUDIO_RESTART_POLICY=no
STUDIO_DOCKER_MIN_FREE_GB=12
STUDIO_TILE_DEFAULT_MODE=online
STUDIO_TILE_INTRANET_URL=http://192.110.14.224:8077/styles/basic/{z}/{x}/{y}.png
STUDIO_TILE_INTRANET_ATTRIBUTION=Map data
STUDIO_TILE_INTRANET_COORDINATE_SYSTEM=wgs84
STUDIO_TILE_INTRANET_MIN_ZOOM=3
STUDIO_TILE_INTRANET_MAX_NATIVE_ZOOM=19
STUDIO_TILE_INTRANET_MAX_ZOOM=19
STUDIO_TILE_INTRANET_DETECT_RETINA=1
STUDIO_SIGNAL6_PIPELINE_MODE=v311
EOF

cat > "$OUTPUT_DIR/docker-compose.yml" <<'EOF'
services:
  studio:
    image: "${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
    container_name: "${STUDIO_CONTAINER_NAME:-signal-studio-final-demo}"
    ports:
      - "${HOST_STUDIO_PORT:-8016}:8016"
    cpus: "${STUDIO_CONTAINER_CPUS:-2.0}"
    mem_limit: "${STUDIO_CONTAINER_MEM_LIMIT:-4g}"
    environment:
      STUDIO_PORT: "8016"
      STUDIO_TILE_DEFAULT_MODE: "${STUDIO_TILE_DEFAULT_MODE:-online}"
      STUDIO_TILE_INTRANET_URL: "${STUDIO_TILE_INTRANET_URL:-http://192.110.14.224:8077/styles/basic/{z}/{x}/{y}.png}"
      STUDIO_TILE_INTRANET_ATTRIBUTION: "${STUDIO_TILE_INTRANET_ATTRIBUTION:-Map data}"
      STUDIO_TILE_INTRANET_COORDINATE_SYSTEM: "${STUDIO_TILE_INTRANET_COORDINATE_SYSTEM:-wgs84}"
      STUDIO_TILE_INTRANET_MIN_ZOOM: "${STUDIO_TILE_INTRANET_MIN_ZOOM:-3}"
      STUDIO_TILE_INTRANET_MAX_NATIVE_ZOOM: "${STUDIO_TILE_INTRANET_MAX_NATIVE_ZOOM:-19}"
      STUDIO_TILE_INTRANET_MAX_ZOOM: "${STUDIO_TILE_INTRANET_MAX_ZOOM:-19}"
      STUDIO_TILE_INTRANET_DETECT_RETINA: "${STUDIO_TILE_INTRANET_DETECT_RETINA:-1}"
      STUDIO_SIGNAL6_PIPELINE_MODE: "${STUDIO_SIGNAL6_PIPELINE_MODE:-v311}"
      PYTHONPATH: "/opt/studio"
    volumes:
      - ./trajectory_annotation_studio:/opt/studio/trajectory_annotation_studio:ro
      - ./my_history_methods/cellular_quality:/opt/studio/my_history_methods/cellular_quality:ro
      - ./project_data/map_assets:/opt/studio/project_data/map_assets:ro
      - ./runtime:/opt/studio/runtime
    restart: "${STUDIO_RESTART_POLICY:-no}"
EOF

cat > "$OUTPUT_DIR/verify_image_tar.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAR="${1:-${IMAGE_TAR:-}}"
if [[ -z "$IMAGE_TAR" || ! -f "$IMAGE_TAR" ]]; then
	echo "usage: $0 /path/to/trajectory_annotation_studio_offline_image_linux_amd64.tar" >&2
	exit 2
fi

python3 - "$IMAGE_TAR" <<'PY'
import json
import sys
import tarfile

image_tar = sys.argv[1]
required_paths = {
    "studio_entrypoint": "opt/studio/trajectory_annotation_studio/deploy/docker/entrypoint.sh",
    "fmm_original": "opt/studio/my_history_methods/map_matching/vendor/fmm/build/fmm",
    "ubodt_original": "opt/studio/my_history_methods/map_matching/vendor/fmm/build/ubodt_gen",
    "fmm_mainroad": "opt/studio/my_history_methods/map_matching/vendor/fmm/build_mainroad/fmm",
    "ubodt_mainroad": "opt/studio/my_history_methods/map_matching/vendor/fmm/build_mainroad/ubodt_gen",
}
required_modules = {
    "pandas": "site-packages/pandas/__init__.py",
    "geopandas": "site-packages/geopandas/__init__.py",
    "fiona": "site-packages/fiona/__init__.py",
    "pyproj": "site-packages/pyproj/__init__.py",
    "shapely": "site-packages/shapely/__init__.py",
    "sklearn": "site-packages/sklearn/__init__.py",
}
found_paths = {key: False for key in required_paths}
found_modules = {key: False for key in required_modules}

with tarfile.open(image_tar) as outer:
    manifest = json.load(outer.extractfile("manifest.json"))[0]
    config = json.load(outer.extractfile(manifest["Config"]))
    arch = config.get("architecture")
    os_name = config.get("os")
    tags = manifest.get("RepoTags") or []
    entrypoint = config.get("config", {}).get("Entrypoint")
    if arch != "amd64" or os_name != "linux":
        raise SystemExit(f"image platform mismatch: os={os_name!r}, architecture={arch!r}; expected linux/amd64")
    for layer in manifest["Layers"]:
        layer_file = outer.extractfile(layer)
        if layer_file is None:
            continue
        with tarfile.open(fileobj=layer_file, mode="r|*") as inner:
            for member in inner:
                name = member.name.lstrip("./")
                for key, expected in required_paths.items():
                    if name == expected:
                        found_paths[key] = True
                for key, marker in required_modules.items():
                    package_marker = marker.split("/", 1)[1]
                    if name.endswith(marker) or name.endswith("dist-packages/" + package_marker):
                        found_modules[key] = True
                if all(found_paths.values()) and all(found_modules.values()):
                    break
        if all(found_paths.values()) and all(found_modules.values()):
            break

missing_paths = [key for key, ok in found_paths.items() if not ok]
missing_modules = [key for key, ok in found_modules.items() if not ok]
print("repo_tags=", tags)
print("entrypoint=", entrypoint)
print("platform= linux/amd64")
if missing_paths or missing_modules:
    if missing_paths:
        print("missing runtime paths:", ", ".join(missing_paths))
    if missing_modules:
        print("missing python modules:", ", ".join(missing_modules))
    raise SystemExit(1)
print("image tar is compatible with the final-demo hot-update bundle")
PY
EOF

cat > "$OUTPUT_DIR/check_container_runtime.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${STUDIO_ENV_FILE:-$SCRIPT_DIR/final-demo.env}"
set -a
source "$ENV_FILE"
set +a
IMAGE_TAG="${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"
MIN_FREE_GB="${STUDIO_DOCKER_MIN_FREE_GB:-12}"
BATCH_NAME="${STUDIO_FINAL_BATCH_NAME:-signal_gps_v311_speed_sparsity_20260603}"

docker run -i --rm \
	--cpus "${STUDIO_CONTAINER_CPUS:-2.0}" \
	--memory "${STUDIO_CONTAINER_MEM_LIMIT:-4g}" \
	-v "$SCRIPT_DIR/trajectory_annotation_studio:/opt/studio/trajectory_annotation_studio:ro" \
	-v "$SCRIPT_DIR/my_history_methods/cellular_quality:/opt/studio/my_history_methods/cellular_quality:ro" \
	-v "$SCRIPT_DIR/project_data/map_assets:/opt/studio/project_data/map_assets:ro" \
	-v "$SCRIPT_DIR/runtime:/opt/studio/runtime" \
	-e PYTHONPATH=/opt/studio \
	-e STUDIO_FINAL_BATCH_NAME="$BATCH_NAME" \
	--entrypoint python3 \
	"$IMAGE_TAG" - <<'PY'
import importlib
import os
from pathlib import Path

for name in ["pandas", "geopandas", "fiona", "pyproj", "shapely", "sklearn"]:
    importlib.import_module(name)

batch_name = os.environ.get("STUDIO_FINAL_BATCH_NAME", "signal_gps_v311_speed_sparsity_20260603")
paths = [
    "/opt/studio/trajectory_annotation_studio/web/review_server.py",
    "/opt/studio/trajectory_annotation_studio/scripts/user_upload_adapter_lib.py",
    "/opt/studio/my_history_methods/cellular_quality/src/panzhi_pipline.py",
    "/opt/studio/my_history_methods/map_matching/vendor/fmm/build/fmm",
    "/opt/studio/my_history_methods/map_matching/vendor/fmm/build/ubodt_gen",
    "/opt/studio/my_history_methods/map_matching/vendor/fmm/build_mainroad/fmm",
    "/opt/studio/my_history_methods/map_matching/vendor/fmm/build_mainroad/ubodt_gen",
    "/opt/studio/project_data/map_assets/beijing/edges.shp",
    "/opt/studio/project_data/map_assets/beijing_mainroad_weighted/edges.shp",
    f"/opt/studio/runtime/published/{batch_name}/result/manifest.json",
]
missing = [path for path in paths if not Path(path).exists()]
not_executable = [path for path in paths[3:7] if Path(path).exists() and not os.access(path, os.X_OK)]
if missing:
    raise SystemExit("missing runtime paths: " + "; ".join(missing))
if not_executable:
    raise SystemExit("non-executable FMM binaries: " + "; ".join(not_executable))
print("container runtime check passed")
PY
EOF

cat > "$OUTPUT_DIR/start.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${STUDIO_ENV_FILE:-$SCRIPT_DIR/final-demo.env}"
set -a
source "$ENV_FILE"
set +a
IMAGE_TAG="${STUDIO_IMAGE_TAG:-trajectory-annotation-studio-offline:latest}"

mkdir -p \
	"$SCRIPT_DIR/runtime/incoming" \
	"$SCRIPT_DIR/runtime/catalog/uploads" \
	"$SCRIPT_DIR/runtime/catalog/assets" \
	"$SCRIPT_DIR/runtime/catalog/batches" \
	"$SCRIPT_DIR/runtime/datasets/user_assets" \
	"$SCRIPT_DIR/runtime/published/public" \
	"$SCRIPT_DIR/runtime/published/private" \
	"$SCRIPT_DIR/runtime/offline_tiles_cache"

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
	IMAGE_TAR="${IMAGE_TAR:-}"
	if [[ -z "$IMAGE_TAR" ]]; then
		for candidate in \
			"$SCRIPT_DIR/trajectory_annotation_studio_offline_image_linux_amd64.tar" \
			"$SCRIPT_DIR/trajectory_annotation_studio_offline_image.tar" \
			"$SCRIPT_DIR/../trajectory_annotation_studio_offline_image_linux_amd64.tar" \
			"$SCRIPT_DIR/../trajectory_annotation_studio_offline_image.tar"; do
			if [[ -f "$candidate" ]]; then
				IMAGE_TAR="$candidate"
				break
			fi
		done
	fi
	if [[ -z "$IMAGE_TAR" || ! -f "$IMAGE_TAR" ]]; then
		echo "Docker image is missing: $IMAGE_TAG" >&2
		echo "Place the compatible image tar next to this bundle, or set IMAGE_TAR=/path/to/image.tar" >&2
		exit 1
	fi
	if [[ "${STUDIO_VERIFY_IMAGE_TAR:-0}" == "1" ]]; then
		"$SCRIPT_DIR/verify_image_tar.sh" "$IMAGE_TAR"
	else
		echo "skipping deep image tar verification; set STUDIO_VERIFY_IMAGE_TAR=1 to scan the tar before docker load"
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
	load_output="$(docker load -i "$IMAGE_TAR")"
	echo "$load_output"
	if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
		loaded_tag="$(printf '%s\n' "$load_output" | awk -F': ' '/Loaded image:/ {print $2}' | tail -n 1)"
		if [[ -n "$loaded_tag" ]] && docker image inspect "$loaded_tag" >/dev/null 2>&1; then
			docker tag "$loaded_tag" "$IMAGE_TAG"
		fi
	fi
fi

if [[ "${STUDIO_RUN_CONTAINER_RUNTIME_CHECK:-0}" == "1" ]]; then
	"$SCRIPT_DIR/check_container_runtime.sh"
else
	echo "skipping container runtime check; set STUDIO_RUN_CONTAINER_RUNTIME_CHECK=1 to enable it"
fi

if docker compose version >/dev/null 2>&1; then
	COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
	COMPOSE=(docker-compose)
else
	echo "docker compose is required" >&2
	exit 1
fi

"${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.yml" up -d

HOST_PORT="${HOST_STUDIO_PORT:-8016}"
echo "studio started: http://127.0.0.1:${HOST_PORT}/web/index.html?batch=signal_gps_v311_speed_sparsity_20260603"
EOF

cat > "$OUTPUT_DIR/stop.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${STUDIO_ENV_FILE:-$SCRIPT_DIR/final-demo.env}"

if docker compose version >/dev/null 2>&1; then
	COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
	COMPOSE=(docker-compose)
else
	echo "docker compose is required" >&2
	exit 1
fi

"${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.yml" down
EOF

cat > "$OUTPUT_DIR/README_DEPLOY.md" <<EOF
# Signal Studio Final Demo Delivery

This is the source/assets bundle. Keep the Docker image tar as a separate file so
the application code and demo data can be hot-updated without rebuilding the
Python/FMM runtime image.

## Contents

- \`trajectory_annotation_studio/\`: Studio source for the final demo.
- \`my_history_methods/cellular_quality/\`: v311 signal reconstruction runtime code.
- \`my_history_methods/map_matching/vendor/fmm/\`: FMM source for rebuilding the
  Linux image. It is not mounted at runtime, so it will not hide the image's
  compiled Linux FMM binaries.
- \`project_data/map_assets/\`: required Beijing FMM network assets.
- \`runtime/published/$BATCH_NAME/\`: the only preloaded display batch.
- \`input_trajectories/eight_routes/\`: 8 uploadable route folders. Each folder has
  \`signal.csv\`, \`gate.csv\`, \`lbs.csv\`, and \`gps.csv\`.
- \`data/test/\`: the same 8 route folders, kept for the local test-data path
  used during development and acceptance.
- \`input_trajectories/signal_triplet_8routes_input.zip\`: upload-ready package for
  the Studio "signal + gate + LBS" upload flow.

## Image Compatibility

The separated image tar must be Linux AMD64 and must include:

- Python runtime dependencies: \`pandas/geopandas/fiona/pyproj/shapely/scikit-learn\`.
- Studio Docker entrypoint under \`/opt/studio/trajectory_annotation_studio/deploy/docker/entrypoint.sh\`.
- Linux FMM binaries:
  \`/opt/studio/my_history_methods/map_matching/vendor/fmm/build/{fmm,ubodt_gen}\`.
- Linux mainroad FMM binaries:
  \`/opt/studio/my_history_methods/map_matching/vendor/fmm/build_mainroad/{fmm,ubodt_gen}\`.

Check a candidate image tar before deployment:

\`\`\`bash
bash verify_image_tar.sh /path/to/trajectory_annotation_studio_offline_image_linux_amd64.tar
\`\`\`

The older \`trajectory-recovery-service-offline:latest\` image is not enough for
this final demo unless it is rebuilt with the Studio entrypoint, mainroad FMM,
and the geospatial Python packages above.

## Start

Put the compatible image tar next to this directory or set \`IMAGE_TAR\`, then run:

\`\`\`bash
bash start.sh
\`\`\`

Open:

\`\`\`text
http://127.0.0.1:8016/web/index.html?batch=$BATCH_NAME
\`\`\`

Stop:

\`\`\`bash
bash stop.sh
\`\`\`

For source hot update, replace files inside \`trajectory_annotation_studio/\` and
restart the container. The image tar usually does not need to change unless
Python dependencies or Linux FMM binaries change.
EOF

cat > "$OUTPUT_DIR/DELIVERY_MANIFEST.txt" <<EOF
Signal Studio Final Demo Assets
===============================

created_at_utc=$STAMP
batch_name=$BATCH_NAME
batch_label=$BATCH_LABEL
image_tag=$IMAGE_TAG
image_tar_included=no
image_tar_policy=separate_file

preloaded_batch=runtime/published/$BATCH_NAME
upload_input_dir=input_trajectories/eight_routes
upload_input_data_test=data/test
upload_input_zip=input_trajectories/signal_triplet_8routes_input.zip
start_script=start.sh
stop_script=stop.sh
image_check_script=verify_image_tar.sh
runtime_check_script=check_container_runtime.sh
EOF

chmod +x \
	"$OUTPUT_DIR/start.sh" \
	"$OUTPUT_DIR/stop.sh" \
	"$OUTPUT_DIR/verify_image_tar.sh" \
	"$OUTPUT_DIR/check_container_runtime.sh"

(
	cd "$OUTPUT_DIR"
	{
		echo "# Key file checksums"
		shasum -a 256 final-demo.env docker-compose.yml start.sh stop.sh verify_image_tar.sh check_container_runtime.sh README_DEPLOY.md DELIVERY_MANIFEST.txt
		shasum -a 256 "input_trajectories/signal_triplet_8routes_input.zip"
	} > SHA256SUMS.txt
)

rm -f "$ARCHIVE_PATH"
tar -czf "$ARCHIVE_PATH" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"

echo "asset bundle directory: $OUTPUT_DIR"
echo "asset bundle archive:   $ARCHIVE_PATH"
echo "image tar policy:       separate file"
echo "preloaded batch:        $BATCH_NAME"
