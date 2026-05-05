(function initTrajectoryStudioRuntimeConfig() {
	const existing = window.TrajectoryStudioRuntimeConfig || {};
	const deployment = window.TrajectoryStudioDeploymentConfig || {};
	const query = new URLSearchParams(window.location.search);
	const TILE_MODE_STORAGE_KEY = "trajectoryStudioTileModeV1";

	const DEFAULT_TILE_PRESETS = {
		online: {
			key: "online",
			label: "在线",
			description: "高德在线底图，适合有公网环境。",
			url: "https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}",
			attribution: "Gaode",
			coordinateSystem: "gcj02",
			minZoom: 3,
			maxNativeZoom: 18,
			maxZoom: 19,
			mapCenter: [39.9, 116.4],
			mapZoom: 11,
			bounds: [[39.4, 115.4], [41.1, 117.5]],
			detectRetina: false,
		},
		offline: {
			key: "offline",
			label: "离线",
			description: "本地离线渲染瓦片，适合无网环境。",
			url: "/offline_tiles/beijing/{z}/{x}/{y}.png",
			attribution: "Offline Beijing Basemap",
			coordinateSystem: "wgs84",
			minZoom: 3,
			maxNativeZoom: 16,
			maxZoom: 18,
			mapCenter: [39.9, 116.4],
			mapZoom: 11,
			bounds: [[39.4, 115.4], [41.1, 117.5]],
			detectRetina: false,
		},
		intranet: {
			key: "intranet",
			label: "内网",
			description: "接入内网 MapTiler/瓦片服务。",
			url: "http://192.110.14.224:8077/styles/basic/{z}/{x}/{y}.png",
			attribution: "© Map data © OpenStreetMap contributors | Tiles © MapTiler",
			coordinateSystem: "wgs84",
			minZoom: 3,
			maxNativeZoom: 19,
			maxZoom: 19,
			mapCenter: [39.9, 116.4],
			mapZoom: 11,
			bounds: [[39.4, 115.4], [41.1, 117.5]],
			detectRetina: true,
		},
	};

	function normalizeTileMode(value) {
		const text = String(value || "").trim().toLowerCase();
		if (!text) return "";
		if (text === "gaode") return "online";
		if (text === "local") return "offline";
		if (text === "lan") return "intranet";
		return text;
	}

	function cloneValue(value) {
		return JSON.parse(JSON.stringify(value));
	}

	function readStoredTileMode() {
		try {
			return String(window.localStorage?.getItem(TILE_MODE_STORAGE_KEY) || "").trim();
		} catch (_) {
			return "";
		}
	}

	function normalizeLatLngPair(value, fallback) {
		if (!Array.isArray(value) || value.length < 2) return fallback;
		return [Number(value[0]) || fallback[0], Number(value[1]) || fallback[1]];
	}

	function normalizeBounds(value, fallback) {
		if (!Array.isArray(value) || value.length < 2) return fallback;
		const southWest = normalizeLatLngPair(value[0], fallback[0]);
		const northEast = normalizeLatLngPair(value[1], fallback[1]);
		return [southWest, northEast];
	}

	function normalizePreset(key, preset, fallbackPreset) {
		const source = preset && typeof preset === "object" ? preset : {};
		const fallback = fallbackPreset && typeof fallbackPreset === "object" ? fallbackPreset : {};
		return {
			key,
			label: String(source.label || fallback.label || key).trim() || key,
			description: String(source.description || fallback.description || "").trim(),
			url: String(source.url || fallback.url || "").trim(),
			attribution: String(source.attribution || fallback.attribution || "").trim(),
			coordinateSystem: String(source.coordinateSystem || fallback.coordinateSystem || "wgs84").trim().toLowerCase(),
			minZoom: Number.isFinite(Number(source.minZoom)) ? Number(source.minZoom) : Number.isFinite(Number(fallback.minZoom)) ? Number(fallback.minZoom) : 3,
			maxNativeZoom: Number.isFinite(Number(source.maxNativeZoom)) ? Number(source.maxNativeZoom) : Number.isFinite(Number(fallback.maxNativeZoom)) ? Number(fallback.maxNativeZoom) : 16,
			maxZoom: Number.isFinite(Number(source.maxZoom)) ? Number(source.maxZoom) : Number.isFinite(Number(fallback.maxZoom)) ? Number(fallback.maxZoom) : 18,
			mapCenter: normalizeLatLngPair(source.mapCenter, normalizeLatLngPair(fallback.mapCenter, [39.9, 116.4])),
			mapZoom: Number.isFinite(Number(source.mapZoom)) ? Number(source.mapZoom) : Number.isFinite(Number(fallback.mapZoom)) ? Number(fallback.mapZoom) : 11,
			bounds: normalizeBounds(source.bounds, normalizeBounds(fallback.bounds, [[39.4, 115.4], [41.1, 117.5]])),
			errorTileUrl: String(source.errorTileUrl || fallback.errorTileUrl || "/web/assets/blank_tile.png").trim(),
			detectRetina: source.detectRetina != null ? Boolean(source.detectRetina) : Boolean(fallback.detectRetina),
		};
	}

	function buildTilePresets() {
		const presetSources = {
			...cloneValue(DEFAULT_TILE_PRESETS),
			...cloneValue(deployment.tilePresets || {}),
			...cloneValue(existing.tilePresets || {}),
		};
		const presets = {};
		Object.keys({ ...DEFAULT_TILE_PRESETS, ...presetSources }).forEach((rawKey) => {
			const key = normalizeTileMode(rawKey);
			if (!key) return;
			presets[key] = normalizePreset(
				key,
				presetSources[rawKey],
				DEFAULT_TILE_PRESETS[key] || DEFAULT_TILE_PRESETS.offline
			);
		});
		if (!presets.online) presets.online = normalizePreset("online", {}, DEFAULT_TILE_PRESETS.online);
		if (!presets.offline) presets.offline = normalizePreset("offline", {}, DEFAULT_TILE_PRESETS.offline);
		if (!presets.intranet) presets.intranet = normalizePreset("intranet", {}, DEFAULT_TILE_PRESETS.intranet);
		return presets;
	}

	const tilePresets = buildTilePresets();
	const storedMode = normalizeTileMode(readStoredTileMode());
	const requestedMode = normalizeTileMode(
		query.get("tileMode")
		|| existing.tileMode
		|| deployment.defaultTileMode
		|| storedMode
		|| "online"
	);
	const tileMode = tilePresets[requestedMode] ? requestedMode : "online";
	const activePreset = tilePresets[tileMode] || tilePresets.online || tilePresets.offline;

	const explicitTileUrl = String(query.get("tileUrl") || existing.tileUrl || "").trim();
	const explicitCoordinateSystem = String(
		query.get("tileCoordinateSystem")
		|| existing.tileCoordinateSystem
		|| ""
	).trim().toLowerCase();
	const explicitAttribution = String(query.get("tileAttribution") || existing.tileAttribution || "").trim();
	const explicitMinZoom = Number.isFinite(Number(query.get("tileMinZoom")))
		? Number(query.get("tileMinZoom"))
		: Number.isFinite(Number(existing.tileMinZoom))
			? Number(existing.tileMinZoom)
			: activePreset.minZoom;
	const explicitMaxNativeZoom = Number.isFinite(Number(query.get("tileMaxNativeZoom")))
		? Number(query.get("tileMaxNativeZoom"))
		: Number.isFinite(Number(existing.tileMaxNativeZoom))
			? Number(existing.tileMaxNativeZoom)
			: activePreset.maxNativeZoom;
	const explicitMaxZoom = Number.isFinite(Number(query.get("tileMaxZoom")))
		? Number(query.get("tileMaxZoom"))
		: Number.isFinite(Number(existing.tileMaxZoom))
			? Number(existing.tileMaxZoom)
			: activePreset.maxZoom;
	const explicitMapZoom = Number.isFinite(Number(query.get("mapZoom")))
		? Number(query.get("mapZoom"))
		: Number.isFinite(Number(existing.mapZoom))
			? Number(existing.mapZoom)
			: activePreset.mapZoom;
	const explicitMapCenter = normalizeLatLngPair(existing.mapCenter, activePreset.mapCenter);
	const explicitTileBounds = normalizeBounds(existing.tileBounds, activePreset.bounds);
	const explicitTileErrorTileUrl = String(
		query.get("tileErrorTileUrl")
		|| existing.tileErrorTileUrl
		|| activePreset.errorTileUrl
	).trim();
	const detectRetina = query.has("tileDetectRetina")
		? query.get("tileDetectRetina") !== "0"
		: existing.tileDetectRetina != null
			? Boolean(existing.tileDetectRetina)
			: Boolean(activePreset.detectRetina);

	window.TrajectoryStudioRuntimeConfig = Object.freeze({
		storageKeys: {
			tileMode: TILE_MODE_STORAGE_KEY,
		},
		tileMode,
		tilePresets: tilePresets,
		tileUrl: explicitTileUrl || activePreset.url,
		tileCoordinateSystem: explicitCoordinateSystem || activePreset.coordinateSystem,
		tileAttribution: explicitAttribution || activePreset.attribution,
		tileMinZoom: explicitMinZoom,
		tileMaxNativeZoom: explicitMaxNativeZoom,
		tileMaxZoom: explicitMaxZoom,
		tileBounds: explicitTileBounds,
		tileErrorTileUrl: explicitTileErrorTileUrl,
		tileDetectRetina: detectRetina,
		mapCenter: explicitMapCenter,
		mapZoom: explicitMapZoom,
	});
})();
