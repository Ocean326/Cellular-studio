from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def getenv_int(name: str, default: int) -> int:
	value = os.getenv(name, "").strip()
	if not value:
		return default
	try:
		return int(value)
	except ValueError:
		return default


def main() -> None:
	if len(sys.argv) != 2:
		raise SystemExit("usage: render_deployment_runtime_config.py <output-path>")

	output_path = Path(sys.argv[1]).expanduser().resolve()
	output_path.parent.mkdir(parents=True, exist_ok=True)

	default_mode = os.getenv("STUDIO_TILE_DEFAULT_MODE", "online").strip().lower() or "online"
	intranet_url = os.getenv(
		"STUDIO_TILE_INTRANET_URL",
		"http://192.110.14.224:8077/styles/basic/{z}/{x}/{y}.png",
	).strip()
	intranet_attribution = os.getenv(
		"STUDIO_TILE_INTRANET_ATTRIBUTION",
		"© Map data © OpenStreetMap contributors | Tiles © MapTiler",
	).strip()

	payload = {
		"defaultTileMode": default_mode,
		"tilePresets": {
			"online": {
				"label": "在线",
				"description": "公网高德在线底图",
			},
			"offline": {
				"label": "离线",
				"description": "容器内离线瓦片服务",
				"minZoom": getenv_int("STUDIO_TILE_OFFLINE_MIN_ZOOM", 3),
				"maxNativeZoom": getenv_int("STUDIO_TILE_OFFLINE_MAX_NATIVE_ZOOM", 16),
				"maxZoom": getenv_int("STUDIO_TILE_OFFLINE_MAX_ZOOM", 18),
			},
			"intranet": {
				"label": "内网",
				"description": "接入内网瓦片服务",
				"url": intranet_url,
				"attribution": intranet_attribution,
				"coordinateSystem": os.getenv("STUDIO_TILE_INTRANET_COORDINATE_SYSTEM", "wgs84").strip().lower() or "wgs84",
				"minZoom": getenv_int("STUDIO_TILE_INTRANET_MIN_ZOOM", 3),
				"maxNativeZoom": getenv_int("STUDIO_TILE_INTRANET_MAX_NATIVE_ZOOM", 19),
				"maxZoom": getenv_int("STUDIO_TILE_INTRANET_MAX_ZOOM", 19),
				"detectRetina": os.getenv("STUDIO_TILE_INTRANET_DETECT_RETINA", "1").strip() not in {"0", "false", "False"},
			},
		},
	}

	script = (
		"(function initTrajectoryStudioDeploymentConfig() {\n"
		f"\twindow.TrajectoryStudioDeploymentConfig = {json.dumps(payload, ensure_ascii=False, indent=2)};\n"
		"})();\n"
	)
	output_path.write_text(script, encoding="utf-8")


if __name__ == "__main__":
	main()
