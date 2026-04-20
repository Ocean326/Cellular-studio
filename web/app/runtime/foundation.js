		function outOfChina(lon, lat) {
			return lon < 72.004 || lon > 137.8347 || lat < 0.8293 || lat > 55.8271;
		}
		function transformLat(x, y) {
			let ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
			ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
			ret += (20 * Math.sin(y * Math.PI) + 40 * Math.sin(y / 3 * Math.PI)) * 2 / 3;
			ret += (160 * Math.sin(y / 12 * Math.PI) + 320 * Math.sin(y * Math.PI / 30)) * 2 / 3;
			return ret;
		}
		function transformLon(x, y) {
			let ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
			ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
			ret += (20 * Math.sin(x * Math.PI) + 40 * Math.sin(x / 3 * Math.PI)) * 2 / 3;
			ret += (150 * Math.sin(x / 12 * Math.PI) + 300 * Math.sin(x / 30 * Math.PI)) * 2 / 3;
			return ret;
		}
		function wgs84ToGcj02(lat, lon) {
			if (outOfChina(lon, lat)) return [lat, lon];
			const a = 6378245.0, ee = 0.00669342162296594323;
			const dLat = transformLat(lon - 105, lat - 35);
			const dLon = transformLon(lon - 105, lat - 35);
			const radLat = lat / 180 * Math.PI;
			let magic = Math.sin(radLat);
			magic = 1 - ee * magic * magic;
			const sqrtMagic = Math.sqrt(magic);
			const dLatDeg = (dLat * 180) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
			const dLonDeg = (dLon * 180) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);
			return [lat + dLatDeg, lon + dLonDeg];
		}
		const toGcj = wgs84ToGcj02;

		function deepClone(value) {
			return JSON.parse(JSON.stringify(value));
		}

		function dedupePreserveOrder(items) {
			const seen = new Set();
			const result = [];
			(items || []).forEach(item => {
				const value = String(item || "").trim();
				if (!value || seen.has(value)) return;
				seen.add(value);
				result.push(value);
			});
			return result;
		}

		const trajectoryStudioBootstrap = window.TrajectoryStudioBootstrap;
		if (!trajectoryStudioBootstrap) {
			throw new Error("trajectory studio bootstrap failed to load");
		}
		const {
			ANNOTATION_SETTINGS_STORAGE_KEY,
			BOARD_PAGE_SIZE,
			CACHE_MAX,
			CHAIN2_TRIAGE_COLUMNS,
			CHAIN2_UI_PRESET,
			DEFAULT_ANNOTATION_CATEGORIES,
			DEFAULT_LAYER_COLOR_PALETTE,
			DEFAULT_REVIEW_TAG_OPTIONS,
			GAODE_TILE,
			INITIAL_BATCH_NAME,
			MAX_BUCKET_DETAIL_ROWS,
			QUERY,
			REVIEWER_SESSION_STORAGE_KEY,
			REVIEW_API_BASE,
			REVIEW_DECISION_LABELS,
			SHOW_REVIEW_AGGREGATE,
			SIM_SIGNAL_UI_PRESET,
			STATIC_DATA_BASE,
			TIMELINE_PINS_STORAGE_KEY,
			TIMELINE_SEGMENTS_STORAGE_KEY,
			TIME_SCRUBBER_MAX_POINTS,
			TIME_SCRUBBER_MIN_VISIBLE_POINTS,
			TIME_SCRUBBER_OVERVIEW_EDGE_PAD,
			TIME_SCRUBBER_SHIFT_RATIO,
			TIME_SCRUBBER_ZOOM_STEP,
			TRAJECTORY_LAYERS_UI_PRESET,
			TRIAGE_STACK_WIDTH_THRESHOLD,
			WEEKDAY_SHORT,
		} = trajectoryStudioBootstrap;
		const STUDIO_ADMIN_CORE = window.TrajectoryStudioModules?.studioAdminCore;
		if (!STUDIO_ADMIN_CORE) {
			throw new Error("studio management core failed to load");
		}

		function getCurrentDataBase() {
			if (currentDataBase) return currentDataBase;
			if (STATIC_DATA_BASE) return STATIC_DATA_BASE;
			if (currentBatchName) return `/batch-data/${currentBatchName}`;
			return "/batch-data/current";
		}

		function getBackendLabel() {
			return `${getCurrentDataBase()}${currentBatchName ? ` | batch=${currentBatchName}` : ""}`;
		}

		function buildDataUrl(relativePath) {
			const normalized = String(relativePath || "").replace(/^\/+/, "");
			return `${getCurrentDataBase()}/${normalized}`;
		}

		function buildReviewApiUrl(path, extraParams = {}) {
			const url = new URL(`${REVIEW_API_BASE}${path}`, window.location.origin);
			if (currentBatchName) url.searchParams.set("batch", currentBatchName);
			Object.entries(extraParams).forEach(([key, value]) => {
				if (value == null || value === "") return;
				url.searchParams.set(key, value);
			});
			return `${url.pathname}${url.search}`;
		}

		function loadReviewerSession() {
			try {
				const raw = localStorage.getItem(REVIEWER_SESSION_STORAGE_KEY);
				if (!raw) return null;
				const parsed = JSON.parse(raw);
				if (!parsed || typeof parsed !== "object") return null;
				const reviewerId = String(parsed.reviewer_id || "").trim();
				const reviewerName = String(parsed.reviewer_name || parsed.display_name || "").trim();
				if (!reviewerId || !reviewerName) return null;
				return {
					reviewer_id: reviewerId,
					reviewer_name: reviewerName,
					display_name: reviewerName,
					last_selected_at: String(parsed.last_selected_at || "").trim(),
				};
			} catch (_) {
				return null;
			}
		}

		function persistReviewerSession(session) {
			currentReviewerSession = session ? {
				reviewer_id: String(session.reviewer_id || "").trim(),
				reviewer_name: String(session.reviewer_name || session.display_name || "").trim(),
				display_name: String(session.reviewer_name || session.display_name || "").trim(),
				last_selected_at: new Date().toISOString(),
			} : null;
			try {
				if (!currentReviewerSession) localStorage.removeItem(REVIEWER_SESSION_STORAGE_KEY);
				else localStorage.setItem(REVIEWER_SESSION_STORAGE_KEY, JSON.stringify(currentReviewerSession));
			} catch (_) {}
			renderReviewerIdentity();
		}

		function getCurrentReviewerId() {
			return String(currentReviewerSession?.reviewer_id || "").trim();
		}

		function getCurrentReviewerName() {
			return String(currentReviewerSession?.reviewer_name || currentReviewerSession?.display_name || "").trim();
		}

		function buildReviewerScopedParams(extraParams = {}) {
			return {
				...extraParams,
				reviewer_id: getCurrentReviewerId(),
			};
		}

		function setReviewerSessionStatus(message, isError = false) {
			const el = document.getElementById("reviewer-session-status");
			el.textContent = message;
			el.style.color = isError ? "#c62828" : "#64748b";
		}


		function normalizeStateValue(value, fallback = "") {
			const v = String(value ?? "").trim().toLowerCase();
			const normalized = ["unmatched", "unmatch", "none", "nan", ""].includes(v) ? "unmatch" : v;
			if (pointStatusTypes.includes(normalized)) return normalized;
			return fallback || pointStatusTypes[0] || normalized || "";
		}

		function normalizeStatusStyleKey(value, fallback = "") {
			const raw = String(value ?? "").trim().toLowerCase();
			if (!raw) return fallback || "";
			return ["unmatched", "unmatch", "none", "nan"].includes(raw) ? "unmatch" : raw;
		}

		function getRowStatusStyleKey(row, fallback = "") {
			if (!row || typeof row !== "object") return fallback || "";
			const candidates = [row.status, row.state, row.result, row.result_status, row.label];
			for (const candidate of candidates) {
				const normalized = normalizeStatusStyleKey(candidate);
				if (normalized) return normalized;
			}
			return fallback || "";
		}

		function escapeHtml(value) {
			return String(value ?? "")
				.replaceAll("&", "&amp;")
				.replaceAll("<", "&lt;")
				.replaceAll(">", "&gt;")
				.replaceAll('"', "&quot;")
				.replaceAll("'", "&#39;");
		}

		function pickFirstString(...values) {
			for (const value of values) {
				if (typeof value === "string" && value.trim()) return value.trim();
			}
			return "";
		}

		function firstArray(payload) {
			if (Array.isArray(payload)) return payload;
			if (Array.isArray(payload?.items)) return payload.items;
			if (Array.isArray(payload?.uploads)) return payload.uploads;
			return [];
		}

		function formatBytes(value) {
			const parsed = Number(value);
			if (!Number.isFinite(parsed) || parsed < 0) return "-";
			const units = ["B", "KB", "MB", "GB", "TB"];
			let size = parsed;
			let unitIndex = 0;
			while (size >= 1024 && unitIndex < units.length - 1) {
				size /= 1024;
				unitIndex += 1;
			}
			return `${size.toFixed(size >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
		}

		function formatStudioDateTime(value) {
			const text = String(value ?? "").trim();
			if (!text) return "-";
			const numeric = Number(text);
			if (Number.isFinite(numeric)) {
				const millis = Math.abs(numeric) >= 1e12 ? numeric : numeric * 1000;
				return new Date(millis).toLocaleString("zh-CN", { hour12: false });
			}
			const parsedDate = new Date(text);
			if (Number.isNaN(parsedDate.getTime())) return text;
			return parsedDate.toLocaleString("zh-CN", { hour12: false });
		}

		async function readJsonPayload(response) {
			const rawText = await response.text();
			if (!rawText) return {};
			try {
				return JSON.parse(rawText);
			} catch (_) {
				return { raw: rawText };
			}
		}

		async function apiFetchJson(url, options = {}) {
			const response = await fetch(url, {
				credentials: "same-origin",
				...options,
			});
			const payload = await readJsonPayload(response);
			if (!response.ok) {
				throw new Error(
					pickFirstString(
						payload?.error,
						payload?.message,
						payload?.detail,
						typeof payload?.raw === "string" ? payload.raw : "",
						`请求失败: ${response.status}`
					)
				);
			}
			return payload;
		}

		function formatStudioVisibilityScope(value) {
			const normalized = String(value || "").trim().toLowerCase();
			if (normalized === "owner_only" || normalized === "private") return "仅自己";
			if (normalized === "public") return "公开";
			return normalized || "-";
		}

		function formatStudioAnnotationMode(value) {
			const normalized = String(value || "").trim().toLowerCase();
			if (normalized === "annotatable") return "可标注";
			if (normalized === "view_only") return "仅查看";
			return normalized || "-";
		}
		
		function debounce(fn, ms) {
			let t;
			return (...args) => {
				clearTimeout(t);
				t = setTimeout(() => fn(...args), ms);
			};
		}
