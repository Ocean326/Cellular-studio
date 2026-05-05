		function applyAnnotationUiSettings() {
			const scrubberControl = document.getElementById("time-scrubber-control");
			const previewRoot = document.getElementById("annotation-settings-panel");
			if (scrubberControl) {
				scrubberControl.style.setProperty("--scrubber-active-opacity", annotationSettings.focusOpacity.toFixed(2));
				scrubberControl.style.setProperty("--scrubber-idle-opacity", annotationSettings.idleOpacity.toFixed(2));
			}
			if (previewRoot) {
				previewRoot.style.setProperty("--preview-active-opacity", annotationSettings.focusOpacity.toFixed(2));
				previewRoot.style.setProperty("--preview-idle-opacity", annotationSettings.idleOpacity.toFixed(2));
			}
			const focusInput = document.getElementById("annotation-focus-opacity");
			const idleInput = document.getElementById("annotation-idle-opacity");
			const focusValue = document.getElementById("annotation-focus-opacity-value");
			const idleValue = document.getElementById("annotation-idle-opacity-value");
			const exclusiveModeInput = document.getElementById("annotation-exclusive-mode");
			if (focusInput) focusInput.value = annotationSettings.focusOpacity.toFixed(2);
			if (idleInput) idleInput.value = annotationSettings.idleOpacity.toFixed(2);
			if (exclusiveModeInput) exclusiveModeInput.checked = !!annotationSettings.exclusiveSegments;
			if (focusValue) focusValue.textContent = `${Math.round(annotationSettings.focusOpacity * 100)}%`;
			if (idleValue) idleValue.textContent = `${Math.round(annotationSettings.idleOpacity * 100)}%`;
			const previewSegment = document.getElementById("annotation-preview-segment");
			if (previewSegment) previewSegment.style.background = annotationSettings.categories[0]?.color || "#60a5fa";
			renderReviewTagOptions(getSelectedReviewTag());
			renderReviewShortcutHints();
			renderTimeScrubberContextMenuItems();
		}

		function renderAnnotationCategoryList() {
			const list = document.getElementById("annotation-category-list");
			if (!list) return;
			list.innerHTML = annotationSettings.categories.map((category, index) => `
				<div class="annotation-category-row" data-category-id="${escapeHtml(category.id)}" draggable="true">
					<div class="annotation-category-handle" title="拖动调整顺序">⋮⋮</div>
					<input class="annotation-category-color" data-field="color" type="color" value="${escapeHtml(category.color)}" />
					<input class="annotation-category-name" data-field="name" type="text" value="${escapeHtml(category.name)}" placeholder="类别 ${index + 1}" />
					<button class="annotation-category-delete" data-action="delete" type="button">删除</button>
				</div>
			`).join("");

			let draggingCategoryId = "";
			list.querySelectorAll(".annotation-category-row").forEach(row => {
				const categoryId = row.dataset.categoryId;
				row.querySelector('[data-field="color"]').addEventListener("input", (event) => {
					const category = getAnnotationCategoryById(categoryId);
					if (!category) return;
					category.color = event.target.value;
					persistAnnotationSettings();
					applyAnnotationUiSettings();
					renderTimeScrubberControl();
				});
				row.querySelector('[data-field="name"]').addEventListener("input", (event) => {
					const category = getAnnotationCategoryById(categoryId);
					if (!category) return;
					category.name = String(event.target.value || "").trimStart();
					persistAnnotationSettings();
					applyAnnotationUiSettings();
					renderTimeScrubberControl();
				});
				row.querySelector('[data-action="delete"]').addEventListener("click", () => {
					annotationSettings.categories = annotationSettings.categories.filter(item => item.id !== categoryId);
					annotationSettings = normalizeAnnotationSettings(annotationSettings);
					if (!getAnnotationCategoryById(segmentDraftState.categoryId)) cancelTimelineSegmentDraft({ silent: true });
					persistAnnotationSettings();
					renderAnnotationCategoryList();
					applyAnnotationUiSettings();
					renderTimeScrubberControl();
				});
				row.addEventListener("dragstart", () => {
					draggingCategoryId = categoryId || "";
					row.classList.add("dragging");
				});
				row.addEventListener("dragend", () => {
					row.classList.remove("dragging");
					list.querySelectorAll(".annotation-category-row").forEach(item => item.classList.remove("drag-over"));
				});
				row.addEventListener("dragover", (event) => {
					event.preventDefault();
				});
				row.addEventListener("drop", (event) => {
					event.preventDefault();
					const targetId = row.dataset.categoryId || "";
					if (!draggingCategoryId || draggingCategoryId === targetId) return;
					const fromIndex = annotationSettings.categories.findIndex(item => item.id === draggingCategoryId);
					const toIndex = annotationSettings.categories.findIndex(item => item.id === targetId);
					if (fromIndex < 0 || toIndex < 0) return;
					const [moved] = annotationSettings.categories.splice(fromIndex, 1);
					annotationSettings.categories.splice(toIndex, 0, moved);
					persistAnnotationSettings();
					renderAnnotationCategoryList();
					applyAnnotationUiSettings();
				});
			});
		}

		function renderAnnotationTagList() {
			const list = document.getElementById("annotation-tag-list");
			if (!list) return;
			list.innerHTML = annotationSettings.reviewTags.length ? annotationSettings.reviewTags.map((tag, index) => `
				<div class="annotation-tag-row" data-tag-index="${index}">
					<input class="annotation-tag-name" data-field="name" type="text" value="${escapeHtml(tag)}" placeholder="Tag ${index + 1}" />
					<button class="annotation-tag-delete" data-action="delete" type="button">删除</button>
				</div>
			`).join("") : `<div class="review-aggregate-empty">当前还没有整轨 tag，可在这里新增。</div>`;

			list.querySelectorAll(".annotation-tag-row").forEach(row => {
				const index = Number(row.dataset.tagIndex || -1);
				row.querySelector('[data-field="name"]').addEventListener("input", (event) => {
					if (index < 0 || index >= annotationSettings.reviewTags.length) return;
					annotationSettings.reviewTags[index] = String(event.target.value || "").trimStart();
					persistAnnotationSettings();
					renderReviewTagOptions(getSelectedReviewTag());
					syncReviewDirtyState();
				});
				row.querySelector('[data-field="name"]').addEventListener("change", (event) => {
					if (index < 0 || index >= annotationSettings.reviewTags.length) return;
					annotationSettings.reviewTags[index] = String(event.target.value || "").trimStart();
					annotationSettings = normalizeAnnotationSettings(annotationSettings);
					persistAnnotationSettings();
					renderAnnotationTagList();
					renderReviewTagOptions(getSelectedReviewTag());
					syncReviewDirtyState();
				});
				row.querySelector('[data-action="delete"]').addEventListener("click", () => {
					if (index < 0 || index >= annotationSettings.reviewTags.length) return;
					const removedTag = annotationSettings.reviewTags[index];
					annotationSettings.reviewTags = annotationSettings.reviewTags.filter((_, itemIndex) => itemIndex !== index);
					annotationSettings = normalizeAnnotationSettings(annotationSettings);
					persistAnnotationSettings();
					if (getSelectedReviewTag() === removedTag) renderReviewTagOptions("");
					renderAnnotationTagList();
					renderReviewTagOptions(getSelectedReviewTag());
					syncReviewDirtyState();
				});
			});
		}

		const REVIEW_SHORTCUT_ACTION_ORDER = ["accept", "reject", "skip", "save"];
		const REVIEW_SHORTCUT_ACTION_HINTS = {
			accept: "直接选中“保留”",
			reject: "直接选中“排除”",
			skip: "直接选中“跳过”",
			save: "直接保存当前整轨标注",
		};
		const DEFAULT_REVIEW_SHORTCUTS = Object.freeze({
			accept: "Digit1",
			reject: "Digit2",
			skip: "Digit3",
			save: "KeyS",
		});

		const REVIEW_SHORTCUT_MODIFIER_TOKENS = Object.freeze(["alt", "ctrl", "meta", "shift"]);
		const MODIFIER_ONLY_KEYBOARD_CODES = new Set([
			"ControlLeft", "ControlRight", "AltLeft", "AltRight",
			"MetaLeft", "MetaRight", "ShiftLeft", "ShiftRight",
		]);

		function normalizeSingleKeyBinding(raw) {
			const s = String(raw || "").trim();
			if (!s) return "";
			if (/^(Key[A-Z]|Digit[0-9]|Numpad[0-9]|Space|Enter|Tab|Backspace|Delete|Minus|Equal|BracketLeft|BracketRight|Backslash|Semicolon|Quote|Comma|Period|Slash|Backquote|ArrowLeft|ArrowRight|ArrowUp|ArrowDown)$/.test(s)) {
				return s;
			}
			const lower = s.toLowerCase();
			if (lower === "space" || s === " ") return "Space";
			if (lower === "enter") return "Enter";
			if (lower === "tab") return "Tab";
			if (lower === "backspace") return "Backspace";
			if (lower === "delete" || lower === "del") return "Delete";
			if (lower === "left" || lower === "arrowleft") return "ArrowLeft";
			if (lower === "right" || lower === "arrowright") return "ArrowRight";
			if (lower === "up" || lower === "arrowup") return "ArrowUp";
			if (lower === "down" || lower === "arrowdown") return "ArrowDown";
			if (/^[a-z]$/i.test(s)) return `Key${s.toUpperCase()}`;
			if (/^[0-9]$/.test(s)) return `Digit${s}`;
			return "";
		}

		function normalizeReviewShortcutBinding(value) {
			const raw = String(value || "").trim();
			if (!raw) return "";
			if (raw.includes("+")) {
				const segments = raw.split("+").map(part => String(part || "").trim()).filter(Boolean);
				if (segments.length < 2) return "";
				const keyToken = segments[segments.length - 1];
				const modTokens = segments.slice(0, -1).map(t => String(t || "").trim().toLowerCase());
				for (const m of modTokens) {
					if (!REVIEW_SHORTCUT_MODIFIER_TOKENS.includes(m)) return "";
				}
				const key = normalizeSingleKeyBinding(keyToken);
				if (!key) return "";
				const mods = [...new Set(modTokens)].sort();
				return `${mods.join("+")}+${key}`;
			}
			return normalizeSingleKeyBinding(raw);
		}

		function normalizeReviewShortcutSettings(shortcuts) {
			const normalized = {};
			const seen = new Set();
			REVIEW_SHORTCUT_ACTION_ORDER.forEach(action => {
				const hasCustom = Object.prototype.hasOwnProperty.call(shortcuts || {}, action);
				const candidate = normalizeReviewShortcutBinding(
					hasCustom ? shortcuts?.[action] : DEFAULT_REVIEW_SHORTCUTS[action]
				);
				if (!candidate || seen.has(candidate)) {
					const fallback = hasCustom ? "" : normalizeReviewShortcutBinding(DEFAULT_REVIEW_SHORTCUTS[action]);
					normalized[action] = fallback && !seen.has(fallback) ? fallback : "";
				}
				if (normalized[action]) {
					seen.add(normalized[action]);
					return;
				}
				if (candidate && !seen.has(candidate)) {
					normalized[action] = candidate;
					seen.add(candidate);
				}
			});
			return normalized;
		}

		function getReviewShortcutBinding(action) {
			return normalizeReviewShortcutBinding(annotationSettings.reviewShortcuts?.[action]);
		}

		function formatSingleKeyCodeForDisplay(code) {
			const normalized = normalizeSingleKeyBinding(code);
			if (!normalized) return "";
			if (normalized.startsWith("Key")) return normalized.slice(3);
			if (normalized.startsWith("Digit")) return normalized.slice(5);
			if (normalized.startsWith("Numpad")) return `Num ${normalized.slice(6)}`;
			const labels = {
				Space: "Space",
				Enter: "Enter",
				Tab: "Tab",
				Backspace: "Backspace",
				Delete: "Delete",
				Minus: "-",
				Equal: "=",
				BracketLeft: "[",
				BracketRight: "]",
				Backslash: "\\",
				Semicolon: ";",
				Quote: "'",
				Comma: ",",
				Period: ".",
				Slash: "/",
				Backquote: "`",
				ArrowLeft: "←",
				ArrowRight: "→",
				ArrowUp: "↑",
				ArrowDown: "↓",
			};
			return labels[normalized] || normalized;
		}

		function formatReviewShortcutBinding(binding) {
			const normalized = normalizeReviewShortcutBinding(binding);
			if (!normalized) return "未设置";
			if (normalized.includes("+")) {
				const parts = normalized.split("+");
				const key = parts.pop() || "";
				const mods = parts.filter(Boolean);
				const modLabels = { alt: "Alt", ctrl: "Ctrl", meta: "⌘", shift: "Shift" };
				const head = mods.map(m => modLabels[m] || m).join("+");
				const keyLabel = formatSingleKeyCodeForDisplay(key);
				return head ? `${head}+${keyLabel}` : keyLabel;
			}
			return formatSingleKeyCodeForDisplay(normalized);
		}

		function buildReviewChordBindingFromKeyboardEvent(event) {
			if (!event || event.isComposing) return "";
			const code = event.code || "";
			if (MODIFIER_ONLY_KEYBOARD_CODES.has(code)) return "";
			const base = normalizeSingleKeyBinding(code) || normalizeSingleKeyBinding(event.key);
			if (!base) return "";
			const mods = [];
			if (event.ctrlKey) mods.push("ctrl");
			if (event.altKey) mods.push("alt");
			if (event.metaKey) mods.push("meta");
			if (event.shiftKey) mods.push("shift");
			mods.sort();
			if (!mods.length) return base;
			return `${mods.join("+")}+${base}`;
		}

		function setReviewShortcutBinding(action, nextBinding) {
			if (!REVIEW_SHORTCUT_ACTION_ORDER.includes(action)) return;
			const normalizedBinding = normalizeReviewShortcutBinding(nextBinding);
			if (!annotationSettings.reviewShortcuts || typeof annotationSettings.reviewShortcuts !== "object") {
				annotationSettings.reviewShortcuts = normalizeReviewShortcutSettings({});
			}
			REVIEW_SHORTCUT_ACTION_ORDER.forEach(candidateAction => {
				if (candidateAction === action) return;
				if (annotationSettings.reviewShortcuts[candidateAction] === normalizedBinding && normalizedBinding) {
					annotationSettings.reviewShortcuts[candidateAction] = "";
				}
			});
			annotationSettings.reviewShortcuts[action] = normalizedBinding;
			annotationSettings = normalizeAnnotationSettings(annotationSettings);
			persistAnnotationSettings();
			applyAnnotationUiSettings();
			renderAnnotationShortcutList();
		}

		function renderReviewShortcutHints() {
			document.querySelectorAll(".review-decision-btn").forEach(btn => {
				const action = btn.dataset.decision;
				const binding = getReviewShortcutBinding(action);
				const label = getReviewDecisionLabel(action);
				btn.title = binding ? `${label}（快捷键 ${formatReviewShortcutBinding(binding)}）` : label;
				if (binding) {
					btn.dataset.reviewShortcut = formatReviewShortcutBinding(binding);
				} else {
					delete btn.dataset.reviewShortcut;
				}
			});
			const saveButton = document.getElementById("save-review-btn");
			if (saveButton) {
				const saveBinding = getReviewShortcutBinding("save");
				saveButton.title = saveBinding ? `保存（快捷键 ${formatReviewShortcutBinding(saveBinding)}）` : "保存";
				if (saveBinding) {
					saveButton.dataset.reviewShortcut = formatReviewShortcutBinding(saveBinding);
				} else {
					delete saveButton.dataset.reviewShortcut;
				}
			}
		}

		function renderAnnotationShortcutList() {
			const list = document.getElementById("annotation-shortcut-list");
			if (!list) return;
			list.innerHTML = REVIEW_SHORTCUT_ACTION_ORDER.map(action => `
				<div class="annotation-shortcut-row" data-shortcut-action="${escapeHtml(action)}">
					<div class="annotation-shortcut-meta">
						<div class="annotation-shortcut-label">${escapeHtml(action === "save" ? "保存" : getReviewDecisionLabel(action))}</div>
						<div class="annotation-shortcut-desc">${escapeHtml(REVIEW_SHORTCUT_ACTION_HINTS[action] || "")}</div>
					</div>
					<div class="annotation-shortcut-input-wrap">
						<input
							class="annotation-shortcut-input"
							type="text"
							readonly
							value="${escapeHtml(formatReviewShortcutBinding(getReviewShortcutBinding(action)))}"
							aria-label="${escapeHtml(action === "save" ? "保存快捷键" : `${getReviewDecisionLabel(action)} 快捷键`)}"
						/>
						<button class="annotation-shortcut-clear" type="button">清空</button>
					</div>
				</div>
			`).join("");

			list.querySelectorAll(".annotation-shortcut-row").forEach(row => {
				const action = row.dataset.shortcutAction || "";
				const input = row.querySelector(".annotation-shortcut-input");
				const clearButton = row.querySelector(".annotation-shortcut-clear");
				if (input) {
					input.addEventListener("click", () => {
						input.focus();
						input.select?.();
					});
					input.addEventListener("keydown", (event) => {
						if (event.key === "Tab" || event.key === "Escape") return;
						event.preventDefault();
						event.stopPropagation();
						if (event.key === "Backspace" || event.key === "Delete") {
							setReviewShortcutBinding(action, "");
							return;
						}
						const binding = buildReviewChordBindingFromKeyboardEvent(event);
						if (!binding) return;
						setReviewShortcutBinding(action, binding);
					});
				}
				clearButton?.addEventListener("click", () => {
					setReviewShortcutBinding(action, "");
				});
			});
		}

		function handleReviewShortcutKeyboardEvent(event) {
			if (!event || event.repeat) return false;
			if (trackEditState.enabled) return false;
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) return false;
			const binding = buildReviewChordBindingFromKeyboardEvent(event);
			if (!binding) return false;
			const action = REVIEW_SHORTCUT_ACTION_ORDER.find(candidate => getReviewShortcutBinding(candidate) === binding);
			if (!action) return false;
			event.preventDefault();
			if (action === "save") {
				void saveReview();
			} else {
				setDecisionButtons(action);
			}
			return true;
		}

		function openAnnotationSettings() {
			const overlay = document.getElementById("annotation-settings-overlay");
			if (document.getElementById("studio-management-overlay")?.classList.contains("open")) {
				closeStudioManagement();
			}
			hideTimeScrubberContextMenu();
			overlay.classList.add("open");
			overlay.setAttribute("aria-hidden", "false");
			renderAnnotationCategoryList();
			renderAnnotationTagList();
			renderAnnotationShortcutList();
			applyAnnotationUiSettings();
		}

		function closeAnnotationSettings() {
			const overlay = document.getElementById("annotation-settings-overlay");
			overlay.classList.remove("open");
			overlay.setAttribute("aria-hidden", "true");
		}

		let currentMapTileCoordinateSystem = getMapTileCoordinateSystem();

		function getResolvedMapTileConfig() {
			return typeof getMapTileConfig === "function" ? getMapTileConfig() : MAP_TILE_CONFIG;
		}

		function buildTileLayerOptions(config) {
			return {
				attribution: config.attribution || "Basemap",
				keepBuffer: 6,
				updateWhenIdle: true,
				updateWhenZooming: false,
				minZoom: config.minZoom,
				maxZoom: config.maxZoom,
				maxNativeZoom: config.maxNativeZoom,
				bounds: config.bounds,
				errorTileUrl: config.errorTileUrl || "",
				detectRetina: !!config.detectRetina,
				noWrap: false,
			};
		}

		function rebuildMapTileLayer(options = {}) {
			if (!map) return;
			const nextConfig = getResolvedMapTileConfig();
			const previousCoordinateSystem = String(
				options.previousCoordinateSystem || currentMapTileCoordinateSystem || nextConfig.coordinateSystem || "wgs84"
			).trim().toLowerCase();
			const nextCoordinateSystem = String(nextConfig.coordinateSystem || "wgs84").trim().toLowerCase();
			const shouldKeepView = options.keepView !== false;
			const center = shouldKeepView && typeof map.getCenter === "function" ? map.getCenter() : null;
			const zoom = shouldKeepView && typeof map.getZoom === "function"
				? map.getZoom()
				: (Number.isFinite(Number(nextConfig.mapZoom)) ? Number(nextConfig.mapZoom) : 11);
			if (tileLayer && typeof map.hasLayer === "function" && map.hasLayer(tileLayer)) {
				map.removeLayer(tileLayer);
			}
			tileLayer = nextConfig.url ? L.tileLayer(nextConfig.url, buildTileLayerOptions(nextConfig)) : null;
			if (tileLayer) tileLayer.addTo(map);
			currentMapTileCoordinateSystem = nextCoordinateSystem;
			if (!center) return;
			const [nextLat, nextLon] = convertLatLonBetweenTileSystems(
				center.lat,
				center.lng,
				previousCoordinateSystem,
				nextCoordinateSystem
			);
			if (typeof map.setView === "function") {
				map.setView([nextLat, nextLon], zoom, { animate: false });
			} else if (typeof map.panTo === "function") {
				map.panTo([nextLat, nextLon]);
				if (typeof map._zoom === "number") map._zoom = zoom;
			}
			syncTimeLabelScale();
		}

		function applyBasemapMode(mode, options = {}) {
			const previousConfig = { ...getResolvedMapTileConfig() };
			const nextConfig = applyMapTileMode(mode, { persist: options.persist !== false });
			rebuildMapTileLayer({
				keepView: options.keepView !== false,
				previousCoordinateSystem: previousConfig.coordinateSystem,
			});
			clearRenderedCache();
			if (currentUid) {
				void renderUid(currentUid, {
					forceFit: false,
					skipReviewReload: true,
					preserveScrubberTime: true,
					resetScrubberVisibleRange: false,
					resetTimeWindow: false,
				});
			}
			return nextConfig;
		}

		function initMap() {
			const mapTileConfig = getResolvedMapTileConfig();
			const initialCenter = Array.isArray(mapTileConfig.mapCenter) && mapTileConfig.mapCenter.length >= 2
				? [Number(mapTileConfig.mapCenter[0]) || 39.9, Number(mapTileConfig.mapCenter[1]) || 116.4]
				: [39.9, 116.4];
			const initialZoom = Number.isFinite(Number(mapTileConfig.mapZoom)) ? Number(mapTileConfig.mapZoom) : 11;
			map = L.map("map", { center: initialCenter, zoom: initialZoom, preferCanvas: true, keyboard: false });
			currentMapTileCoordinateSystem = String(mapTileConfig.coordinateSystem || "wgs84").trim().toLowerCase();
			rebuildMapTileLayer({ keepView: false, previousCoordinateSystem: currentMapTileCoordinateSystem });
			L.control.scale({ imperial: false }).addTo(map);
			syncTimeLabelScale();
			lastRenderZoomBucket = getCurrentRenderZoomBucket();
			map.on("zoom", syncTimeLabelScale);
			map.on("zoomend", () => {
				syncTimeLabelScale();
				maybeRerenderForZoomChange();
			});
			syncTrackEditMapInteractionLock();
		}

		function getCurrentRenderZoomBucket() {
			return Math.max(0, Math.round(map?.getZoom?.() ?? 11));
		}

		function maybeRerenderForZoomChange() {
			const nextBucket = getCurrentRenderZoomBucket();
			if (nextBucket === lastRenderZoomBucket) return;
			lastRenderZoomBucket = nextBucket;
			if (!currentUid || !map) return;
			// 仅按新缩放级别重绘地图（采样/聚合策略随 zoomBucket 变化）。不要调用 renderUid：
			// renderUid 会重新 fetch 数据并从服务端 loadTrackEditsForUid，成功响应会覆盖本地未保存的修正。
			renderMapDisplayFromCurrentState({ exists: currentExistsByLayer || {}, forceFit: false });
		}

		function getTimeLabelScaleForZoom(zoom) {
			const baseZoom = 11;
			const scale = Math.pow(1.12, Number(zoom ?? baseZoom) - baseZoom);
			return Math.max(0.72, Math.min(1.75, scale));
		}

		function syncTimeLabelScale() {
			if (!map) return;
			const container = map.getContainer();
			if (!container) return;
			container.style.setProperty("--time-label-scale", String(getTimeLabelScaleForZoom(map.getZoom())));
		}

		function normalizeStateValue(value, fallback = "") {
			const v = String(value ?? "").trim().toLowerCase();
			const normalized = ["unmatched", "unmatch", "none", "nan", ""].includes(v) ? "unmatch" : v;
			if (pointStatusTypes.includes(normalized)) return normalized;
			return fallback || pointStatusTypes[0] || normalized || "";
		}

		function buildTrackEditPatchRenderSignature(trackEdits = getCurrentTrackEdits()) {
			return (trackEdits?.pointPatches || [])
				.map((patch) => JSON.stringify([
					patch.pointId || "",
					patch.layerKey || "",
					patch.rowIndex ?? null,
					patch.timestamp ?? null,
					patch.position?.latitude ?? null,
					patch.position?.longitude ?? null,
					Object.entries(patch.metadata || {}).sort(([left], [right]) => left.localeCompare(right)),
				]))
				.join("|");
		}

		function getRenderSignature() {
			const trackEdits = getCurrentTrackEdits();
			return JSON.stringify({
				layerOrder,
				layerStyles,
				statusPointStyles,
				zoomBucket: getCurrentRenderZoomBucket(),
				trackEditStoreKey: getCurrentTrackEditStoreKey(),
				trackEditMode: !!trackEditState.enabled,
				trackEditSelection: [...(trackEditState.selectedPointIds || [])].sort(),
				trackEditUpdatedAt: trackEdits.updated_at || "",
				trackEditPatchCount: (trackEdits.pointPatches || []).length,
				trackEditPatchSignature: buildTrackEditPatchRenderSignature(trackEdits),
			});
		}

		let scheduledMapDisplayRefreshFrame = 0;
		let scheduledMapDisplayRefreshForceFit = false;
		let lastAppliedMapDisplaySignature = "";
		let renderUidRequestSequence = 0;
		let trackEditLoadRequestSequence = 0;
		let trackEditPersistRequestSequence = 0;
		let timelineAnnotationLoadRequestSequence = 0;
		const latestTrackEditLoadRequestByStoreKey = Object.create(null);
		const latestTrackEditPersistRequestByStoreKey = Object.create(null);
		const latestTimelineAnnotationLoadRequestByStoreKey = Object.create(null);

		function isRenderUidRequestCurrent(requestSequence) {
			return requestSequence === renderUidRequestSequence;
		}

		function cancelScheduledMapDisplayRefresh() {
			if (scheduledMapDisplayRefreshFrame) {
				cancelAnimationFrame(scheduledMapDisplayRefreshFrame);
				scheduledMapDisplayRefreshFrame = 0;
			}
			scheduledMapDisplayRefreshForceFit = false;
		}

		function clearRenderedCache() {
			renderedCache.clear();
			renderedCacheKeys = [];
		}

		function putRenderedCache(key, value) {
			if (!renderedCache.has(key)) renderedCacheKeys.push(key);
			renderedCache.set(key, value);
			while (renderedCacheKeys.length > CACHE_MAX) {
				const k = renderedCacheKeys.shift();
				renderedCache.delete(k);
			}
		}

		let timePlus8 = true;
		let mapViewFollowScrubber = false;
		function formatTime(ts) {
			if (ts == null || ts === "") return "";
			let t = parseFloat(ts);
			if (Number.isNaN(t)) return "";
			if (t > 1e12) t /= 1000;
			if (timePlus8) t += 8 * 3600;
			const d = new Date(t * 1000);
			return d.toISOString().slice(11, 19);
		}

		function parseNumericValue(value) {
			if (value == null || value === "") return null;
			const parsed = Number(value);
			return Number.isFinite(parsed) ? parsed : null;
		}

		function toBeijingDateParts(dayKey) {
			const [year, month, day] = String(dayKey || "").split("-").map(value => Number(value));
			if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
			return { year, month, day };
		}

		function beijingDayKeyFromUnix(value) {
			const parsed = parseNumericValue(value);
			if (parsed == null) return "";
			const seconds = parsed > 1e12 ? parsed / 1000 : parsed;
			const utcMillis = (seconds + 8 * 3600) * 1000;
			return new Date(utcMillis).toISOString().slice(0, 10);
		}

		function beijingDayStartUnix(dayKey) {
			const parts = toBeijingDateParts(dayKey);
			if (!parts) return null;
			return Math.floor(Date.UTC(parts.year, parts.month - 1, parts.day) / 1000) - 8 * 3600;
		}

		function buildInclusiveDayRange(startDay, endDay) {
			if (!startDay || !endDay) return [];
			const start = beijingDayStartUnix(startDay);
			const end = beijingDayStartUnix(endDay);
			if (start == null || end == null || start > end) return [];
			const days = [];
			for (let ts = start; ts <= end; ts += 86400) {
				days.push(beijingDayKeyFromUnix(ts));
			}
			return [...new Set(days)];
		}

		function getRowStartTimeValue(row) {
			if (!row || typeof row !== "object") return null;
			return [
				row.t_in,
				row.start_time,
				row.segment_start_time,
				row.procedureStart,
				row.timestamp_ms,
				row.timestamp,
				row.time,
			].map(parseNumericValue).find(value => value != null) ?? null;
		}

		function getRowEndTimeValue(row) {
			if (!row || typeof row !== "object") return null;
			return [
				row.t_out,
				row.end_time,
				row.segment_end_time,
				row.procedureEnd,
				row.timestamp_ms,
				row.timestamp,
				row.time,
			].map(parseNumericValue).find(value => value != null) ?? null;
		}

		function inferRowTimeBounds(row) {
			if (!row || typeof row !== "object") return null;
			const start = getRowStartTimeValue(row);
			const end = getRowEndTimeValue(row);
			if (start == null && end == null) return null;
			const normalizedStart = start != null ? start : end;
			const normalizedEnd = end != null ? end : start;
			return normalizedStart != null && normalizedEnd != null
				? { start: normalizedStart, end: normalizedEnd }
				: null;
		}

		function deriveAvailableDaysFromLayerData(dataByLayer) {
			const daySet = new Set();
			let minStart = null;
			let maxEnd = null;
			Object.values(dataByLayer || {}).forEach(rows => {
				(rows || []).forEach(row => {
					const bounds = inferRowTimeBounds(row);
					if (!bounds) return;
					const start = bounds.start > 1e12 ? bounds.start / 1000 : bounds.start;
					const end = bounds.end > 1e12 ? bounds.end / 1000 : bounds.end;
					if (minStart == null || start < minStart) minStart = start;
					if (maxEnd == null || end > maxEnd) maxEnd = end;
					const startDay = beijingDayKeyFromUnix(start);
					const endDay = beijingDayKeyFromUnix(end);
					if (startDay) daySet.add(startDay);
					if (endDay) daySet.add(endDay);
				});
			});
			if (!daySet.size && minStart != null && maxEnd != null) {
				return buildInclusiveDayRange(beijingDayKeyFromUnix(minStart), beijingDayKeyFromUnix(maxEnd));
			}
			if (!daySet.size) return [];
			const sorted = [...daySet].sort();
			if (sorted.length >= 2) return buildInclusiveDayRange(sorted[0], sorted[sorted.length - 1]);
			return sorted;
		}

		function getCurrentTimeWindowBounds() {
			if (!currentTimeWindow.enabled || !currentTimeWindow.startDay || !currentTimeWindow.endDay) return null;
			const windowStart = beijingDayStartUnix(currentTimeWindow.startDay);
			const windowEndStart = beijingDayStartUnix(currentTimeWindow.endDay);
			if (windowStart == null || windowEndStart == null) return null;
			return {
				start: windowStart,
				end: windowEndStart + 86400 - 1,
			};
		}

		function rowOverlapsTimeBounds(row, timeBounds) {
			if (!timeBounds) return true;
			const rowBounds = inferRowTimeBounds(row);
			if (!rowBounds) return true;
			const rowStart = normalizeUnixSeconds(rowBounds.start);
			const rowEnd = normalizeUnixSeconds(rowBounds.end);
			const effectiveStart = rowStart != null ? rowStart : rowEnd;
			const effectiveEnd = rowEnd != null ? rowEnd : rowStart;
			if (effectiveStart == null || effectiveEnd == null) return true;
			return effectiveEnd >= timeBounds.start && effectiveStart <= timeBounds.end;
		}

		function rowMatchesCurrentTimeWindow(row) {
			return rowOverlapsTimeBounds(row, getCurrentTimeWindowBounds());
		}

		function filterRowsByCurrentTimeWindow(rows) {
			return (rows || []).filter(rowMatchesCurrentTimeWindow);
		}

		function filterRowsByTimeBounds(rows, timeBounds) {
			return (rows || []).filter(row => rowOverlapsTimeBounds(row, timeBounds));
		}

		function getCurrentMapDisplayTimeBounds() {
			if (!timeScrubberState.enabled) return null;
			return getCurrentVisibleTimeBounds();
		}

		function getCurrentMapDisplaySignature() {
			const bounds = getCurrentMapDisplayTimeBounds();
			if (!bounds) return "display:all";
			return `display:${Math.round(bounds.start)}..${Math.round(bounds.end)}`;
		}

		function getCurrentMapDisplayDataByLayer(dataByLayer = currentFilteredDataByLayer) {
			const bounds = getCurrentMapDisplayTimeBounds();
			if (!bounds) return dataByLayer || {};
			return Object.fromEntries(
				Object.entries(dataByLayer || {}).map(([layerKey, rows]) => [layerKey, filterRowsByTimeBounds(rows || [], bounds)])
			);
		}

		function getTimeWindowSignature() {
			if (!currentTimeWindow.enabled) return "window:disabled";
			return `window:${currentTimeWindow.startDay}..${currentTimeWindow.endDay}`;
		}

		function getCurrentTimeWindowKey() {
			return `${currentTimeWindow.startDay || ""}..${currentTimeWindow.endDay || ""}`;
		}

		function clampFixedTimeWindowSpanDays(value, availableDays = currentTimeWindow.availableDays) {
			const parsed = Number(value);
			if (!Number.isFinite(parsed)) return 0;
			const maxSpanDays = Math.max(0, (availableDays || []).length);
			return Math.max(0, Math.min(maxSpanDays, Math.round(parsed)));
		}

		function getCurrentTimeWindowSpanDays() {
			const days = currentTimeWindow.availableDays || [];
			const startIndex = days.indexOf(currentTimeWindow.startDay);
			const endIndex = days.indexOf(currentTimeWindow.endDay);
			if (startIndex >= 0 && endIndex >= 0) return Math.max(1, endIndex - startIndex + 1);
			const bounds = getCurrentTimeWindowBounds();
			if (!bounds) return 0;
			return Math.max(1, Math.round((bounds.end - bounds.start + 1) / 86400));
		}

		function resolveTimeWindowRangeFromAnchor(anchorEdge, anchorDay, fixedSpanDays, availableDays = currentTimeWindow.availableDays) {
			if (!Array.isArray(availableDays) || !availableDays.length) {
				return { startDay: "", endDay: "", fixedSpanDays: 0 };
			}
			const spanDays = clampFixedTimeWindowSpanDays(fixedSpanDays, availableDays);
			if (spanDays <= 0) {
				return {
					startDay: availableDays[0],
					endDay: availableDays[availableDays.length - 1],
					fixedSpanDays: 0,
				};
			}
			const spanOffset = Math.max(0, spanDays - 1);
			const lastIndex = availableDays.length - 1;
			let anchorIndex = availableDays.indexOf(anchorDay);
			if (anchorIndex < 0) anchorIndex = anchorEdge === "end" ? lastIndex : 0;
			let startIndex = anchorEdge === "end" ? (anchorIndex - spanOffset) : anchorIndex;
			let endIndex = anchorEdge === "end" ? anchorIndex : (anchorIndex + spanOffset);
			if (startIndex < 0) {
				startIndex = 0;
				endIndex = Math.min(lastIndex, startIndex + spanOffset);
			}
			if (endIndex > lastIndex) {
				endIndex = lastIndex;
				startIndex = Math.max(0, endIndex - spanOffset);
			}
			return {
				startDay: availableDays[startIndex] || availableDays[0],
				endDay: availableDays[endIndex] || availableDays[lastIndex],
				fixedSpanDays: spanDays,
			};
		}

		function setDateWindowControlActive(nextActive) {
			document.getElementById("date-window-control").classList.toggle("active", !!nextActive);
		}

		function updateDateWindowEdgeStyles() {
			const startButton = document.getElementById("date-window-start");
			const endButton = document.getElementById("date-window-end");
			startButton.classList.toggle("active", currentTimeWindow.activeEdge === "start");
			endButton.classList.toggle("active", currentTimeWindow.activeEdge === "end");
			startButton.classList.toggle("hovered", currentTimeWindow.hoverEdge === "start");
			endButton.classList.toggle("hovered", currentTimeWindow.hoverEdge === "end");
		}

		function updateDateWindowControl() {
			const control = document.getElementById("date-window-control");
			const startButton = document.getElementById("date-window-start");
			const endButton = document.getElementById("date-window-end");
			const startDecreaseButton = document.getElementById("date-window-start-decrease");
			const startIncreaseButton = document.getElementById("date-window-start-increase");
			const endDecreaseButton = document.getElementById("date-window-end-decrease");
			const endIncreaseButton = document.getElementById("date-window-end-increase");
			const fixedSpanInput = document.getElementById("date-window-fixed-span");
			const quickCategorySelect = document.getElementById("date-window-quick-category");
			const quickToggleButton = document.getElementById("date-window-quick-toggle");
			const quickStatus = document.getElementById("date-window-quick-status");
			if (!currentTimeWindow.enabled || !currentTimeWindow.availableDays.length) {
				control.classList.add("hidden");
				startButton.textContent = "----";
				endButton.textContent = "----";
				startDecreaseButton.disabled = true;
				startIncreaseButton.disabled = true;
				endDecreaseButton.disabled = true;
				endIncreaseButton.disabled = true;
				if (fixedSpanInput) {
					fixedSpanInput.value = "0";
					fixedSpanInput.disabled = true;
				}
				if (quickCategorySelect) {
					quickCategorySelect.innerHTML = `<option value="">当前无可用整段标签</option>`;
					quickCategorySelect.disabled = true;
				}
				if (quickToggleButton) {
					quickToggleButton.textContent = "整段标记";
					quickToggleButton.disabled = true;
				}
				if (quickStatus) {
					quickStatus.textContent = "未标记";
					quickStatus.classList.remove("is-marked");
				}
				updateDateWindowEdgeStyles();
				return;
			}
			syncCurrentWindowQuickSegmentCategory();
			control.classList.remove("hidden");
			startButton.textContent = formatDayKeyWithWeekday(currentTimeWindow.startDay || currentTimeWindow.availableDays[0]);
			endButton.textContent = formatDayKeyWithWeekday(currentTimeWindow.endDay || currentTimeWindow.availableDays[currentTimeWindow.availableDays.length - 1]);
			control.title = `当前轨迹日期范围 ${currentTimeWindow.availableDays[0]} -- ${currentTimeWindow.availableDays[currentTimeWindow.availableDays.length - 1]}；点击起始/结束日期调整区间`;
			const days = currentTimeWindow.availableDays;
			const fixedSpanDays = clampFixedTimeWindowSpanDays(currentTimeWindow.fixedSpanDays, days);
			currentTimeWindow.fixedSpanDays = fixedSpanDays;
			const startIndex = Math.max(0, days.indexOf(currentTimeWindow.startDay));
			const endIndex = Math.max(0, days.indexOf(currentTimeWindow.endDay));
			const spanLocked = fixedSpanDays > 0;
			startDecreaseButton.disabled = startIndex <= 0;
			startIncreaseButton.disabled = spanLocked ? (endIndex >= days.length - 1) : (startIndex >= endIndex);
			endDecreaseButton.disabled = spanLocked ? (startIndex <= 0) : (endIndex <= startIndex);
			endIncreaseButton.disabled = endIndex >= days.length - 1;
			if (fixedSpanInput) {
				fixedSpanInput.disabled = false;
				fixedSpanInput.max = String(Math.max(0, days.length));
				fixedSpanInput.value = String(fixedSpanDays);
			}
			if (quickCategorySelect) {
				if (annotationSettings.categories.length) {
					quickCategorySelect.innerHTML = annotationSettings.categories.map(category => `
						<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)}</option>
					`).join("");
					quickCategorySelect.value = getAnnotationCategoryById(currentTimeWindow.quickSegmentCategoryId)
						? currentTimeWindow.quickSegmentCategoryId
						: (annotationSettings.categories[0]?.id || "");
				} else {
					quickCategorySelect.innerHTML = `<option value="">先在设置里新增段落标签</option>`;
				}
			}
			const quickActionState = getCurrentWindowQuickSegmentActionState();
			if (quickCategorySelect) quickCategorySelect.disabled = !annotationSettings.categories.length || !currentTimeWindow.enabled;
			if (quickToggleButton) {
				quickToggleButton.textContent = quickActionState.buttonLabel;
				quickToggleButton.disabled = quickActionState.disabled;
				quickToggleButton.title = quickActionState.statusText;
			}
			if (quickStatus) {
				quickStatus.textContent = quickActionState.statusText;
				quickStatus.classList.toggle("is-marked", !!quickActionState.existingSegment);
			}
			updateDateWindowEdgeStyles();
		}

		function resetCurrentTimeWindow() {
			currentTimeWindow = {
				availableDays: [],
				startDay: "",
				endDay: "",
				activeEdge: "start",
				hoverEdge: "",
				fixedSpanDays: 0,
				quickSegmentCategoryId: "",
				enabled: false,
			};
			updateDateWindowControl();
		}

		function syncTimeWindowFromLayerData(dataByLayer, options = {}) {
			const availableDays = deriveAvailableDaysFromLayerData(dataByLayer);
			if (!availableDays.length) {
				resetCurrentTimeWindow();
				return false;
			}
			const shouldReset = options.resetSelection
				|| !currentTimeWindow.enabled
				|| !currentTimeWindow.availableDays.length
				|| currentTimeWindow.availableDays[0] !== availableDays[0]
				|| currentTimeWindow.availableDays[currentTimeWindow.availableDays.length - 1] !== availableDays[availableDays.length - 1];
			currentTimeWindow.availableDays = availableDays;
			currentTimeWindow.enabled = true;
			currentTimeWindow.fixedSpanDays = clampFixedTimeWindowSpanDays(currentTimeWindow.fixedSpanDays, availableDays);
			if (shouldReset) {
				if (currentTimeWindow.fixedSpanDays > 0) {
					const nextRange = resolveTimeWindowRangeFromAnchor("start", availableDays[0], currentTimeWindow.fixedSpanDays, availableDays);
					currentTimeWindow.startDay = nextRange.startDay;
					currentTimeWindow.endDay = nextRange.endDay;
				} else {
					currentTimeWindow.startDay = availableDays[0];
					currentTimeWindow.endDay = availableDays[availableDays.length - 1];
				}
				currentTimeWindow.activeEdge = "start";
			} else {
				if (currentTimeWindow.fixedSpanDays > 0) {
					const anchorEdge = currentTimeWindow.activeEdge === "end" ? "end" : "start";
					const anchorDay = anchorEdge === "end"
						? (availableDays.includes(currentTimeWindow.endDay) ? currentTimeWindow.endDay : availableDays[availableDays.length - 1])
						: (availableDays.includes(currentTimeWindow.startDay) ? currentTimeWindow.startDay : availableDays[0]);
					const nextRange = resolveTimeWindowRangeFromAnchor(anchorEdge, anchorDay, currentTimeWindow.fixedSpanDays, availableDays);
					currentTimeWindow.startDay = nextRange.startDay;
					currentTimeWindow.endDay = nextRange.endDay;
				} else {
					if (!availableDays.includes(currentTimeWindow.startDay)) currentTimeWindow.startDay = availableDays[0];
					if (!availableDays.includes(currentTimeWindow.endDay)) currentTimeWindow.endDay = availableDays[availableDays.length - 1];
					if (availableDays.indexOf(currentTimeWindow.startDay) > availableDays.indexOf(currentTimeWindow.endDay)) {
						currentTimeWindow.endDay = currentTimeWindow.startDay;
					}
				}
			}
			updateDateWindowControl();
			return true;
		}

		async function setCurrentTimeWindowFixedSpanDays(nextValue, options = {}) {
			const availableDays = currentTimeWindow.availableDays || [];
			const nextSpanDays = clampFixedTimeWindowSpanDays(nextValue, availableDays);
			const prevSpanDays = currentTimeWindow.fixedSpanDays || 0;
			const prevWindowKey = getCurrentTimeWindowKey();
			currentTimeWindow.fixedSpanDays = nextSpanDays;
			if (currentTimeWindow.enabled && availableDays.length) {
				if (nextSpanDays > 0) {
					const anchorEdge = options.anchorEdge || currentTimeWindow.activeEdge || "start";
					const anchorDay = anchorEdge === "end" ? currentTimeWindow.endDay : currentTimeWindow.startDay;
					const nextRange = resolveTimeWindowRangeFromAnchor(anchorEdge, anchorDay, nextSpanDays, availableDays);
					currentTimeWindow.startDay = nextRange.startDay;
					currentTimeWindow.endDay = nextRange.endDay;
				} else {
					currentTimeWindow.startDay = availableDays[0];
					currentTimeWindow.endDay = availableDays[availableDays.length - 1];
				}
			}
			updateDateWindowControl();
			syncCurrentWindowQuickSegmentCategory({ preferExisting: true });
			const nextWindowKey = getCurrentTimeWindowKey();
			if ((prevSpanDays !== nextSpanDays || prevWindowKey !== nextWindowKey) && options.render !== false && currentUid) {
				await renderUid(currentUid, {
					forceFit: true,
					skipReviewReload: true,
					resetTimeWindow: false,
					resetScrubberVisibleRange: true,
				});
			}
		}

		async function nudgeTimeWindow(edge, delta) {
			if (!currentUid || !currentTimeWindow.enabled || !currentTimeWindow.availableDays.length || !delta) return;
			const days = currentTimeWindow.availableDays;
			const currentValue = edge === "end" ? currentTimeWindow.endDay : currentTimeWindow.startDay;
			const currentIndex = Math.max(0, days.indexOf(currentValue));
			const nextIndex = Math.max(0, Math.min(days.length - 1, currentIndex + delta));
			const nextDay = days[nextIndex];
			if (!nextDay || nextDay === currentValue) return;
			const prevWindowKey = getCurrentTimeWindowKey();
			if (currentTimeWindow.fixedSpanDays > 0) {
				const nextRange = resolveTimeWindowRangeFromAnchor(edge, nextDay, currentTimeWindow.fixedSpanDays, days);
				currentTimeWindow.startDay = nextRange.startDay;
				currentTimeWindow.endDay = nextRange.endDay;
			} else {
				if (edge === "start") {
					currentTimeWindow.startDay = nextDay;
					if (days.indexOf(currentTimeWindow.startDay) > days.indexOf(currentTimeWindow.endDay)) {
						currentTimeWindow.endDay = currentTimeWindow.startDay;
					}
				} else {
					currentTimeWindow.endDay = nextDay;
					if (days.indexOf(currentTimeWindow.endDay) < days.indexOf(currentTimeWindow.startDay)) {
						currentTimeWindow.startDay = currentTimeWindow.endDay;
					}
				}
			}
			currentTimeWindow.activeEdge = edge;
			updateDateWindowControl();
			syncCurrentWindowQuickSegmentCategory({ preferExisting: true });
			if (prevWindowKey === getCurrentTimeWindowKey()) return;
			await renderUid(currentUid, { forceFit: true, skipReviewReload: true, resetTimeWindow: false });
		}

		function normalizeUnixSeconds(value) {
			const parsed = parseNumericValue(value);
			if (parsed == null) return null;
			return parsed > 1e12 ? parsed / 1000 : parsed;
		}

		function formatDateTime(ts) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return "";
			const shifted = timePlus8 ? normalized + 8 * 3600 : normalized;
			return new Date(shifted * 1000).toISOString().slice(0, 19).replace("T", " ");
		}

		function getDisplayOffsetSeconds() {
			return timePlus8 ? 8 * 3600 : 0;
		}

		function formatDisplayClock(ts, options = {}) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return "";
			const shifted = normalized + getDisplayOffsetSeconds();
			const iso = new Date(shifted * 1000).toISOString();
			return options.includeSeconds ? iso.slice(11, 19) : iso.slice(11, 16);
		}

		function getWeekdayShort(ts) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return "";
			const shifted = normalized + getDisplayOffsetSeconds();
			return WEEKDAY_SHORT[new Date(shifted * 1000).getUTCDay()] || "";
		}

		function formatDayKeyWithWeekday(dayKey) {
			if (!dayKey) return "";
			const dayStart = beijingDayStartUnix(dayKey);
			if (dayStart == null) return dayKey;
			return `${dayKey} ${getWeekdayShort(dayStart)}`;
		}

		function formatDisplayDate(ts, options = {}) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return "";
			const shifted = normalized + getDisplayOffsetSeconds();
			const iso = new Date(shifted * 1000).toISOString().slice(0, 10);
			const base = options.short ? iso.slice(5) : iso;
			if (options.weekday) return `${base} ${getWeekdayShort(normalized)}`;
			return base;
		}

		function normalizeAnnotationCategories(categories) {
			const fallback = deepClone(DEFAULT_ANNOTATION_CATEGORIES);
			if (!Array.isArray(categories) || !categories.length) return fallback;
			const normalized = categories.map((item, index) => {
				const rawName = String(item?.name || "").trim();
				return {
					id: String(item?.id || `annotation-category-${index + 1}`).trim() || `annotation-category-${index + 1}`,
					name: rawName || `类别 ${index + 1}`,
					color: /^#[0-9a-f]{6}$/i.test(String(item?.color || "").trim()) ? String(item.color).trim() : fallback[index % fallback.length].color,
				};
			}).filter(Boolean);
			return normalized.length ? normalized : fallback;
		}

		function normalizeReviewTagOptions(tags) {
			if (!Array.isArray(tags) || !tags.length) return [...DEFAULT_REVIEW_TAG_OPTIONS];
			return dedupePreserveOrder(tags);
		}

		function normalizeAnnotationSettings(settings) {
			const parsedFocus = parseNumericValue(settings?.focusOpacity);
			const parsedIdle = parseNumericValue(settings?.idleOpacity);
			const focusOpacity = Math.max(0.5, Math.min(1, parsedFocus ?? 0.98));
			const idleOpacity = Math.max(0.5, Math.min(focusOpacity, parsedIdle ?? 0.76));
			return {
				focusOpacity,
				idleOpacity,
				exclusiveSegments: !!settings?.exclusiveSegments,
				categories: normalizeAnnotationCategories(settings?.categories),
				reviewTags: normalizeReviewTagOptions(settings?.reviewTags),
				reviewShortcuts: normalizeReviewShortcutSettings(settings?.reviewShortcuts),
			};
		}

		function loadAnnotationSettings() {
			try {
				const raw = localStorage.getItem(ANNOTATION_SETTINGS_STORAGE_KEY);
				if (!raw) return normalizeAnnotationSettings({});
				return normalizeAnnotationSettings(JSON.parse(raw));
			} catch (_) {
				return normalizeAnnotationSettings({});
			}
		}

		function persistAnnotationSettings() {
			try {
				localStorage.setItem(ANNOTATION_SETTINGS_STORAGE_KEY, JSON.stringify(annotationSettings));
			} catch (_) {}
		}

		function loadTimelineAnnotationStore(storageKey) {
			try {
				const raw = localStorage.getItem(storageKey);
				if (!raw) return {};
				const parsed = JSON.parse(raw);
				return parsed && typeof parsed === "object" ? parsed : {};
			} catch (_) {
				return {};
			}
		}

		function persistTimelineAnnotationStore(storageKey, payload) {
			try {
				localStorage.setItem(storageKey, JSON.stringify(payload || {}));
			} catch (_) {}
		}

		function getAnnotationCategoryById(categoryId) {
			return annotationSettings.categories.find(item => item.id === categoryId) || null;
		}

		function getAnnotationCategoryLabel(categoryId) {
			return String(getAnnotationCategoryById(categoryId)?.name || "").trim() || "未命名标签";
		}

		function getReviewDecisionLabel(decision) {
			return REVIEW_DECISION_LABELS[String(decision || "").trim().toLowerCase()] || String(decision || "").trim() || "未设置";
		}

		function normalizeReviewTags(value) {
			if (Array.isArray(value)) return dedupePreserveOrder(value);
			const single = String(value || "").trim();
			return single ? [single] : [];
		}

		function getReviewTags(review) {
			return normalizeReviewTags(review?.trajectory_tags || review?.tags || review?.tag);
		}

		function getSelectedReviewTag() {
			const select = document.getElementById("review-tag-select");
			return String(select?.value || "").trim();
		}

		function renderReviewTagOptions(selectedTag = "") {
			const select = document.getElementById("review-tag-select");
			if (!select) return;
			const availableTags = normalizeReviewTagOptions(annotationSettings.reviewTags);
			const mergedTags = selectedTag && !availableTags.includes(selectedTag)
				? [selectedTag, ...availableTags]
				: availableTags;
			const normalizedSelected = selectedTag && mergedTags.includes(selectedTag) ? selectedTag : "";
			const options = [
				`<option value="">无标签</option>`,
				...mergedTags.map(tag => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`),
			];
			select.innerHTML = options.join("");
			select.value = normalizedSelected;
			select.disabled = mergedTags.length === 0;
		}

		function getFallbackLayerColor(layerName, fallbackIndex = 0) {
			const normalized = String(layerName || "").trim().toLowerCase();
			if (!normalized) return DEFAULT_LAYER_COLOR_PALETTE[fallbackIndex % DEFAULT_LAYER_COLOR_PALETTE.length];
			let hash = 0;
			for (let index = 0; index < normalized.length; index++) {
				hash = ((hash * 33) + normalized.charCodeAt(index)) >>> 0;
			}
			return DEFAULT_LAYER_COLOR_PALETTE[(hash + Math.max(0, fallbackIndex)) % DEFAULT_LAYER_COLOR_PALETTE.length];
		}

		function floorToDisplayStep(ts, stepSeconds) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return null;
			const offset = getDisplayOffsetSeconds();
			return Math.floor((normalized + offset) / stepSeconds) * stepSeconds - offset;
		}

		function ceilToDisplayStep(ts, stepSeconds) {
			const normalized = normalizeUnixSeconds(ts);
			if (normalized == null) return null;
			const offset = getDisplayOffsetSeconds();
			return Math.ceil((normalized + offset) / stepSeconds) * stepSeconds - offset;
		}

		function getAdaptiveHourStepSeconds(visibleStartTime, visibleEndTime, maxLabels = 10) {
			const spanSeconds = Math.max(1, (visibleEndTime ?? 0) - (visibleStartTime ?? 0));
			const candidateHours = [2, 4, 6, 8, 12, 24, 48, 72];
			for (const hours of candidateHours) {
				const stepSeconds = hours * 3600;
				const start = ceilToDisplayStep(visibleStartTime, stepSeconds);
				if (start == null) continue;
				const labelCount = Math.floor((visibleEndTime - start) / stepSeconds) + 1;
				if (labelCount <= maxLabels) return stepSeconds;
			}
			const roughStepHours = Math.ceil((spanSeconds / 3600) / Math.max(1, maxLabels));
			return Math.max(2, roughStepHours) * 3600;
		}

		function getTimeScrubberPointCoordinate(layerKey, row) {
			return getRowCoordinate(row);
		}

		function canUseTimeScrubberLayer(layerKey, exists = currentExistsByLayer) {
			if (!exists?.[layerKey]) return false;
			const cfg = layerConfig[layerKey] || {};
			if (cfg.lineOnly) return false;
			if (cfg.kind === "stations") return false;
			return true;
		}

		function getTimeScrubberLayerCandidates(exists = currentExistsByLayer) {
			return layerOrder.filter(layer => canUseTimeScrubberLayer(layer, exists));
		}

		function chooseDefaultTimeScrubberLayer(candidates) {
			if (!Array.isArray(candidates) || !candidates.length) return "";
			const configuredPreferred = currentTimeScrubberPreferredLayers.find(layer => candidates.includes(layer));
			if (configuredPreferred) return configuredPreferred;
			const preferred = ["fmm", "raw", "snap", "signal", "gps", "od"];
			const visiblePreferred = preferred.find(layer => candidates.includes(layer) && layerStyles[layer]?.visible !== false);
			if (visiblePreferred) return visiblePreferred;
			const anyPreferred = preferred.find(layer => candidates.includes(layer));
			return anyPreferred || candidates[0];
		}

		function getTimeScrubberVisibleCount(total = timeScrubberState.allPoints.length) {
			const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, Math.max(0, total || 0));
			if (!maxVisible) return 0;
			const requested = Math.round(timeScrubberState.visibleCount || maxVisible);
			return Math.max(1, Math.min(maxVisible, requested));
		}

		function getTimeScrubberMaxStart(total = timeScrubberState.allPoints.length) {
			return Math.max(0, total - getTimeScrubberVisibleCount(total));
		}

		function clampTimeScrubberVisibleStart(nextStart, total = timeScrubberState.allPoints.length) {
			return Math.max(0, Math.min(getTimeScrubberMaxStart(total), Math.round(nextStart || 0)));
		}

		function getTimeScrubberVisiblePoints() {
			if (!timeScrubberState.enabled) return [];
			const visibleCount = getTimeScrubberVisibleCount();
			return timeScrubberState.allPoints.slice(
				timeScrubberState.visibleStartIndex,
				timeScrubberState.visibleStartIndex + visibleCount
			);
		}

		function getActiveTimeScrubberPoint() {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return null;
			return timeScrubberState.allPoints[timeScrubberState.selectedIndex] || null;
		}

		function findNearestTimeScrubberPointIndex(points, targetTime) {
			if (!Array.isArray(points) || !points.length || targetTime == null) return 0;
			let lo = 0;
			let hi = points.length - 1;
			while (lo < hi) {
				const mid = Math.floor((lo + hi) / 2);
				if (points[mid].time < targetTime) lo = mid + 1;
				else hi = mid;
			}
			if (lo <= 0) return 0;
			const prev = points[lo - 1];
			const next = points[lo];
			return Math.abs((prev?.time ?? 0) - targetTime) <= Math.abs((next?.time ?? 0) - targetTime) ? lo - 1 : lo;
		}

		function computeTimeScrubberViewAfterLayerSwitch(points, options = {}) {
			const {
				previousSelectedTime = null,
				windowStartTime = null,
				windowEndTime = null,
				previousVisibleCount = null,
			} = options;
			const len = points.length;
			if (!len) {
				return { selectedIndex: 0, visibleStartIndex: 0, visibleCount: 0 };
			}
			const maxWin = Math.min(TIME_SCRUBBER_MAX_POINTS, len);
			const minWin = Math.max(1, Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxWin));

			let selectedIndex = previousSelectedTime != null && Number.isFinite(previousSelectedTime)
				? findNearestTimeScrubberPointIndex(points, previousSelectedTime)
				: 0;
			selectedIndex = Math.max(0, Math.min(len - 1, selectedIndex));

			const hasWindowTimes = windowStartTime != null && windowEndTime != null
				&& Number.isFinite(windowStartTime) && Number.isFinite(windowEndTime);

			if (!hasWindowTimes) {
				const prevVc = Math.max(1, Math.round(previousVisibleCount != null ? previousVisibleCount : 1));
				const visibleCount = Math.min(maxWin, Math.max(minWin, prevVc));
				let visibleStartIndex = Math.max(0, Math.min(selectedIndex - Math.floor(visibleCount / 2), len - visibleCount));
				if (selectedIndex < visibleStartIndex) selectedIndex = visibleStartIndex;
				if (selectedIndex > visibleStartIndex + visibleCount - 1) {
					selectedIndex = visibleStartIndex + visibleCount - 1;
				}
				return { selectedIndex, visibleStartIndex, visibleCount };
			}

			let i0 = findNearestTimeScrubberPointIndex(points, windowStartTime);
			let i1 = findNearestTimeScrubberPointIndex(points, windowEndTime);
			if (i0 > i1) {
				const t = i0;
				i0 = i1;
				i1 = t;
			}
			const span = i1 - i0 + 1;

			let visibleCount;
			let visibleStartIndex;

			if (span > maxWin) {
				visibleCount = maxWin;
				const lo = Math.max(0, i1 - maxWin + 1);
				const hi = Math.min(i0, len - maxWin);
				if (lo <= hi) {
					const prefer = Math.floor((i0 + i1) / 2) - Math.floor(visibleCount / 2);
					visibleStartIndex = Math.max(lo, Math.min(hi, prefer));
				} else {
					visibleStartIndex = Math.max(0, Math.min(selectedIndex - Math.floor(visibleCount / 2), len - maxWin));
				}
			} else if (span < minWin) {
				visibleCount = minWin;
				const mid = Math.floor((i0 + i1) / 2);
				visibleStartIndex = mid - Math.floor((visibleCount - 1) / 2);
				visibleStartIndex = Math.max(0, Math.min(visibleStartIndex, len - visibleCount));
			} else {
				visibleCount = span;
				visibleStartIndex = i0;
			}

			visibleStartIndex = Math.max(0, Math.min(visibleStartIndex, len - visibleCount));
			if (selectedIndex < visibleStartIndex) selectedIndex = visibleStartIndex;
			if (selectedIndex > visibleStartIndex + visibleCount - 1) {
				selectedIndex = visibleStartIndex + visibleCount - 1;
			}
			return { selectedIndex, visibleStartIndex, visibleCount };
		}

		function normalizeSegmentTimeBounds(segment) {
			if (!segment || segment.startTime == null || segment.endTime == null) return null;
			return {
				start: Math.min(segment.startTime, segment.endTime),
				end: Math.max(segment.startTime, segment.endTime),
			};
		}

		function getLargestCommittedSegmentTimeBounds() {
			const segments = getActiveTimelineSegmentsForDisplay();
			let best = null;
			let bestSpan = -1;
			segments.forEach(segment => {
				const b = normalizeSegmentTimeBounds(segment);
				if (!b) return;
				const span = b.end - b.start;
				if (span > bestSpan) {
					bestSpan = span;
					best = b;
				}
			});
			return best;
		}

		function getUnionAnnotationTimeBoundsForViewport() {
			let tMin = Infinity;
			let tMax = -Infinity;
			getActiveTimelineSegmentsForDisplay().forEach(segment => {
				const b = normalizeSegmentTimeBounds(segment);
				if (!b) return;
				tMin = Math.min(tMin, b.start);
				tMax = Math.max(tMax, b.end);
			});
			if (segmentDraftState.active && segmentDraftState.startTime != null && segmentDraftState.previewTime != null) {
				const a = Math.min(segmentDraftState.startTime, segmentDraftState.previewTime);
				const b = Math.max(segmentDraftState.startTime, segmentDraftState.previewTime);
				tMin = Math.min(tMin, a);
				tMax = Math.max(tMax, b);
			}
			if (!Number.isFinite(tMin) || !Number.isFinite(tMax)) return null;
			return { start: tMin, end: tMax };
		}

		function mergeTimeBounds(a, b) {
			if (!a) return b;
			if (!b) return a;
			return { start: Math.min(a.start, b.start), end: Math.max(a.end, b.end) };
		}

		function timeBoundsCoverInner(outer, inner) {
			if (!outer || !inner) return false;
			return outer.start <= inner.start && outer.end >= inner.end;
		}

		function expandTimeScrubberViewToCoverAnnotationBounds(points, view, annotationBounds) {
			if (!annotationBounds || !points.length || !view.visibleCount) return view;
			const visStart = view.visibleStartIndex;
			const visEnd = Math.min(points.length - 1, visStart + view.visibleCount - 1);
			const wStart = points[visStart]?.time;
			const wEnd = points[visEnd]?.time;
			if (wStart == null || wEnd == null) return view;
			const cur = { start: Math.min(wStart, wEnd), end: Math.max(wStart, wEnd) };
			if (timeBoundsCoverInner(cur, annotationBounds)) return view;
			const merged = mergeTimeBounds(cur, annotationBounds);
			const selTime = points[Math.max(0, Math.min(points.length - 1, view.selectedIndex))]?.time ?? null;
			return computeTimeScrubberViewAfterLayerSwitch(points, {
				previousSelectedTime: selTime,
				windowStartTime: merged.start,
				windowEndTime: merged.end,
				previousVisibleCount: view.visibleCount,
			});
		}

		function buildTimeScrubberPoints(layerKey, rows) {
			return (rows || []).map((row, rowIndex) => {
				const bounds = inferRowTimeBounds(row);
				const coord = getTimeScrubberPointCoordinate(layerKey, row);
				if (!bounds || !coord) return null;
				const start = normalizeUnixSeconds(bounds.start);
				const end = normalizeUnixSeconds(bounds.end);
				if (start == null && end == null) return null;
				const effectiveStart = start != null ? start : end;
				const effectiveEnd = end != null ? end : start;
				const time = effectiveStart != null && effectiveEnd != null ? (effectiveStart + effectiveEnd) / 2 : (effectiveStart ?? effectiveEnd);
				if (time == null) return null;
				return {
					layerKey,
					row,
					rowIndex,
					time,
					start: effectiveStart,
					end: effectiveEnd,
					lat: coord.lat,
					lon: coord.lon,
				};
			}).filter(Boolean).sort((a, b) => (a.time - b.time) || (a.rowIndex - b.rowIndex));
		}

		function getRowMidTimeSeconds(row) {
			const bounds = inferRowTimeBounds(row);
			if (!bounds) return null;
			const start = normalizeUnixSeconds(bounds.start);
			const end = normalizeUnixSeconds(bounds.end);
			if (start == null && end == null) return null;
			const effectiveStart = start != null ? start : end;
			const effectiveEnd = end != null ? end : start;
			return effectiveStart != null && effectiveEnd != null
				? (effectiveStart + effectiveEnd) / 2
				: (effectiveStart ?? effectiveEnd);
		}

		function pickTimeScrubberTargetTimeFromRows(rows, preferredTime = null) {
			if (!Array.isArray(rows) || !rows.length) return null;
			if (preferredTime == null || !Number.isFinite(preferredTime)) {
				for (const row of rows) {
					const rowTime = getRowMidTimeSeconds(row);
					if (rowTime != null) return rowTime;
				}
				return null;
			}
			let bestTime = null;
			let bestDistance = Infinity;
			rows.forEach(row => {
				const rowTime = getRowMidTimeSeconds(row);
				if (rowTime == null) return;
				const distance = Math.abs(rowTime - preferredTime);
				if (distance < bestDistance) {
					bestDistance = distance;
					bestTime = rowTime;
				}
			});
			return bestTime;
		}

		function alignTimeScrubberToTime(targetTime, options = {}) {
			if (targetTime == null || !Number.isFinite(targetTime)) return false;
			const candidates = getTimeScrubberLayerCandidates(currentExistsByLayer);
			if (!candidates.length) return false;
			const requestedLayer = options.layerKey;
			const nextLayer = candidates.includes(requestedLayer)
				? requestedLayer
				: (candidates.includes(timeScrubberState.selectedLayer)
					? timeScrubberState.selectedLayer
					: chooseDefaultTimeScrubberLayer(candidates));
			if (nextLayer && nextLayer !== timeScrubberState.selectedLayer) {
				setTimeScrubberLayer(nextLayer);
			}
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return false;
			const nextIndex = findNearestTimeScrubberPointIndex(timeScrubberState.allPoints, targetTime);
			setTimeScrubberSelectedIndex(nextIndex, {
				keepWindow: options.keepWindow === true,
				followView: options.followView === true,
			});
			setTimeScrubberActive(true);
			return true;
		}

		function alignTimeScrubberToBucket(layerKey, bucket, options = {}) {
			const preferredTime = options.preferredTime ?? (getActiveTimeScrubberPoint()?.time ?? null);
			const targetTime = pickTimeScrubberTargetTimeFromRows(bucket?.rows || [], preferredTime);
			return alignTimeScrubberToTime(targetTime, {
				layerKey,
				keepWindow: options.keepWindow === true,
				followView: options.followView === true,
			});
		}

		function getTimeScrubberGpsStatusSamples() {
			const gpsRows = currentFilteredDataByLayer.gps || [];
			if (
				timeScrubberStyleContextCache.batchName === currentBatchName
				&& timeScrubberStyleContextCache.uid === currentUid
				&& timeScrubberStyleContextCache.gpsRowsRef === gpsRows
			) {
				return timeScrubberStyleContextCache.gpsSamples;
			}
			const gpsSamples = gpsRows
				.map(row => ({
					time: getRowMidTimeSeconds(row),
					statusKey: getRowStatusStyleKey(row),
				}))
				.filter(sample => sample.time != null && sample.statusKey);
			timeScrubberStyleContextCache = {
				batchName: currentBatchName,
				uid: currentUid,
				gpsRowsRef: gpsRows,
				gpsSamples,
			};
			return gpsSamples;
		}

		function findNearestTimeScrubberGpsStatusKey(targetTime) {
			const gpsSamples = getTimeScrubberGpsStatusSamples();
			if (!gpsSamples.length || targetTime == null) return "";
			let lo = 0;
			let hi = gpsSamples.length - 1;
			while (lo < hi) {
				const mid = Math.floor((lo + hi) / 2);
				if ((gpsSamples[mid]?.time ?? 0) < targetTime) lo = mid + 1;
				else hi = mid;
			}
			const current = gpsSamples[lo];
			const previous = gpsSamples[Math.max(0, lo - 1)];
			if (!previous) return current?.statusKey || "";
			if (!current) return previous?.statusKey || "";
			return Math.abs((previous.time ?? 0) - targetTime) <= Math.abs((current.time ?? 0) - targetTime)
				? previous.statusKey
				: current.statusKey;
		}

		function getSignalTimeScrubberStatusKey(point) {
			if (!point) return "";
			const directStatus = getRowStatusStyleKey(point.row);
			if (directStatus) return directStatus;
			const signalRows = currentFilteredDataByLayer[point.layerKey] || [];
			const currentRow = signalRows[point.rowIndex] || point.row;
			const previousRow = signalRows[point.rowIndex - 1];
			const previousPreviousRow = signalRows[point.rowIndex - 2];
			const currentCid = String(currentRow?.CID ?? currentRow?.cid ?? "").trim();
			const previousCid = String(previousRow?.CID ?? previousRow?.cid ?? "").trim();
			const previousPreviousCid = String(previousPreviousRow?.CID ?? previousPreviousRow?.cid ?? "").trim();
			if (currentCid && previousCid && previousPreviousCid && currentCid === previousPreviousCid && currentCid !== previousCid) {
				return "ping_pong";
			}
			const currentCoord = getRowCoordinate(currentRow);
			const previousCoord = getRowCoordinate(previousRow);
			const longJumpThreshold = Number(currentManifest?.long_jump_threshold_m || 3000);
			if (
				currentCoord
				&& previousCoord
				&& Number.isFinite(longJumpThreshold)
				&& haversineMeters(previousCoord.lat, previousCoord.lon, currentCoord.lat, currentCoord.lon) >= longJumpThreshold
			) {
				return "long_jump";
			}
			return findNearestTimeScrubberGpsStatusKey(point.time);
		}

		function getTimeScrubberPointColor(point) {
			if (!point) return "#f8fafc";
			const cfg = layerConfig[point.layerKey] || {};
			if (cfg.kind === "signal") {
				const statusKey = getSignalTimeScrubberStatusKey(point);
				return statusPointStyles[statusKey]?.color || layerStyles[point.layerKey]?.color || cfg.defaultColor || "#f8fafc";
			}
			if (cfg.kind === "gps") {
				const statusKey = getRowStatusStyleKey(point.row);
				return statusPointStyles[statusKey]?.color || layerStyles[point.layerKey]?.color || cfg.defaultColor || "#f8fafc";
			}
			if (point.layerKey === "fmm" || point.layerKey === "line") {
				const matchType = normalizeStatusStyleKey(point.row?.match_type, "unmatch");
				return statusPointStyles[matchType]?.color || layerStyles[point.layerKey]?.color || cfg.defaultColor || "#f8fafc";
			}
			return getPointColor(point.layerKey, point.row);
		}

		function buildTimeScrubberLayerOptions() {
			const select = document.getElementById("time-scrubber-layer-select");
			if (!select) return;
			const options = timeScrubberState.focusLayers.map(layer => `
				<option value="${escapeHtml(layer)}">${escapeHtml(getLayerLabel(layer))}</option>
			`).join("");
			select.innerHTML = options;
			select.value = timeScrubberState.selectedLayer || timeScrubberState.focusLayers[0] || "";
			select.disabled = timeScrubberState.focusLayers.length <= 1;
		}

		function buildReviewerScopedStoreKey(context = {}) {
			const batchName = String(context.batchName ?? currentBatchName ?? "").trim() || "__default__";
			const reviewerId = String(context.reviewerId ?? getCurrentReviewerId() ?? "").trim() || "__no_reviewer__";
			const uid = String(context.uid ?? currentUid ?? "").trim() || "__none__";
			return `${batchName}::${reviewerId}::${uid}`;
		}

		function buildReviewerScopedContext(context = {}) {
			const uid = String(context.uid ?? currentUid ?? "").trim();
			const reviewerId = String(context.reviewerId ?? getCurrentReviewerId() ?? "").trim();
			const reviewerName = String(context.reviewerName ?? getCurrentReviewerName() ?? "").trim();
			const batchName = String(context.batchName ?? currentBatchName ?? "").trim();
			return {
				uid,
				reviewerId,
				reviewerName,
				batchName,
				storeKey: buildReviewerScopedStoreKey({ uid, reviewerId, batchName }),
			};
		}

		function isReviewerScopedContextCurrent(context = {}) {
			return buildReviewerScopedStoreKey(context) === buildReviewerScopedStoreKey();
		}

		function buildReplayTimelineState(overrides = {}) {
			return {
				enabled: false,
				uid: "",
				batchName: "",
				reviewerId: "",
				reviewerName: "",
				pins: [],
				segments: [],
				segmentPolicy: null,
				updatedAt: "",
				sourceLabel: "",
				...overrides,
			};
		}

		function buildReplayTimelineSourceLabel(context = {}) {
			const reviewerId = String(context.reviewerId ?? replayTimelineState.reviewerId ?? "").trim();
			const reviewerName = String(context.reviewerName ?? replayTimelineState.reviewerName ?? "").trim();
			if (reviewerName && reviewerId && reviewerName !== reviewerId) return `${reviewerName} (${reviewerId})`;
			return reviewerName || reviewerId || "";
		}

		function isReplayTimelineActiveForContext(context = {}) {
			const uid = String(context.uid ?? currentUid ?? "").trim();
			const batchName = String(context.batchName ?? currentBatchName ?? "").trim();
			return !!replayTimelineState.enabled
				&& !!String(replayTimelineState.reviewerId || "").trim()
				&& String(replayTimelineState.uid || "").trim() === uid
				&& String(replayTimelineState.batchName || "").trim() === batchName;
		}

		function isReplayTimelineActiveForReviewer(reviewerId) {
			return isReplayTimelineActiveForContext()
				&& String(replayTimelineState.reviewerId || "").trim() === String(reviewerId || "").trim();
		}

		function getReplayTimelineSourceLabel() {
			if (!isReplayTimelineActiveForContext()) return "";
			return String(replayTimelineState.sourceLabel || "").trim() || buildReplayTimelineSourceLabel();
		}

		function getTimelineAnnotationReadOnlyMessage() {
			const replayLabel = getReplayTimelineSourceLabel();
			return replayLabel
				? `当前正在回放 ${replayLabel} 的分段，关闭回放后可编辑`
				: "当前分段回放为只读模式";
		}

		function isTimelineAnnotationReadOnly() {
			return isReplayTimelineActiveForContext();
		}

		function getActiveTimelinePinsForDisplay(context = {}) {
			if (isReplayTimelineActiveForContext(context)) {
				return Array.isArray(replayTimelineState.pins) ? replayTimelineState.pins : [];
			}
			return getCurrentTimelinePins(context);
		}

		function getActiveTimelineSegmentsForDisplay(context = {}) {
			if (isReplayTimelineActiveForContext(context)) {
				return Array.isArray(replayTimelineState.segments) ? replayTimelineState.segments : [];
			}
			return getCurrentTimelineSegments(context);
		}

		function clearReplayTimelineState(options = {}) {
			const previousReadOnlyMessage = getTimelineAnnotationReadOnlyMessage();
			replayTimelineState = buildReplayTimelineState();
			if (trackEditState.statusMessage === previousReadOnlyMessage) {
				setTrackEditStatus(trackEditState.enabled ? "编辑模式已开启" : "编辑关闭", trackEditState.enabled ? "active" : "idle");
			}
			if (options.render !== false) {
				renderTimeScrubberControl();
				renderTrackEditPanel();
			}
			return true;
		}

		function reconcileReplayTimelineStateForCurrentSelection(context = {}) {
			if (!replayTimelineState.enabled) return false;
			if (isReplayTimelineActiveForContext(context)) return false;
			clearReplayTimelineState({ render: false });
			return true;
		}

		async function loadReplayTimelineAnnotationsForUid(uid, context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid,
			});
			if (!scopedContext.uid || !scopedContext.reviewerId) return false;
			try {
				const response = await fetch(buildTimelineAnnotationsApiUrl({ uid: scopedContext.uid }, scopedContext));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const annotations = payload.annotations || {};
				replayTimelineState = buildReplayTimelineState({
					enabled: true,
					uid: scopedContext.uid,
					batchName: scopedContext.batchName,
					reviewerId: scopedContext.reviewerId,
					reviewerName: scopedContext.reviewerName,
					pins: Array.isArray(annotations.pins) ? annotations.pins : [],
					segments: Array.isArray(annotations.segments) ? annotations.segments : [],
					segmentPolicy: annotations.segmentPolicy || null,
					updatedAt: String(annotations.updated_at || "").trim(),
					sourceLabel: buildReplayTimelineSourceLabel(scopedContext),
				});
				if (trackEditState.enabled) setTrackEditModeEnabled(false);
				setTrackEditStatus(getTimelineAnnotationReadOnlyMessage(), "warn");
				resetSegmentDraftState();
				hideTimeScrubberContextMenu();
				syncTimeScrubberFromCurrentData({ preserveTime: false, resetVisibleRange: true });
				renderTimeScrubberControl();
				renderTrackEditPanel();
				return true;
			} catch (error) {
				clearReplayTimelineState({ render: false });
				setReviewStatus(`回放分段读取失败：${error?.message || error}`, true);
				renderTimeScrubberControl();
				renderTrackEditPanel();
				return false;
			}
		}

		function ensureTimelineAnnotationsWritable(options = {}) {
			if (isTimelineAnnotationReadOnly()) {
				if (options.prompt !== false) setReviewStatus(getTimelineAnnotationReadOnlyMessage(), true);
				if (options.render !== false) renderTrackEditPanel();
				return false;
			}
			return ensureAnnotationSessionReady(options);
		}

		function getCurrentTrackEditStoreKey(context = {}) {
			return buildReviewerScopedStoreKey(context);
		}

		function buildTrackEditsApiUrl(extraParams = {}, context = {}) {
			const scopedContext = buildReviewerScopedContext(context);
			return buildReviewApiUrl("/track-edits", {
				...extraParams,
				reviewer_id: scopedContext.reviewerId,
			});
		}

		function buildEmptyTrackEdits(uid = currentUid, reviewerId = getCurrentReviewerId(), reviewerName = getCurrentReviewerName()) {
			const normalizedUid = String(uid || "").trim();
			return {
				schema_version: 1,
				uid: normalizedUid,
				sample_id: normalizedUid,
				reviewer_id: String(reviewerId || "").trim(),
				reviewer_name: String(reviewerName || "").trim(),
				reviewer: String(reviewerName || "").trim(),
				updated_at: "",
				pointPatches: [],
			};
		}

		function buildTrackPointId(uid, layerKey, rowIndex, timestamp = null) {
			const normalizedUid = String(uid || "").trim() || "__none__";
			const normalizedLayer = String(layerKey || "").trim() || "layer";
			const normalizedIndex = Math.max(0, Math.round(parseNumericValue(rowIndex) ?? 0));
			const normalizedTimestamp = timestamp == null ? "na" : String(Math.round(timestamp * 1000));
			return `${normalizedLayer}:${normalizedUid}:${normalizedTimestamp}:${normalizedIndex}`;
		}

		function getTrackEditMetadataFieldForLayer(layerKey) {
			const cfg = layerConfig[layerKey] || {};
			if (layerKey === "fmm" || layerKey === "line") return "match_type";
			if (cfg.kind === "gps") return "status";
			return "";
		}

		function getTrackEditMetadataOptionsForLayer(layerKey) {
			const field = getTrackEditMetadataFieldForLayer(layerKey);
			if (!field) return [];
			return dedupePreserveOrder(pointStatusTypes || []);
		}

		function isTrackEditLayerEditable(layerKey) {
			if (!layerKey || currentUiConfig.annotationEnabled === false) return false;
			const cfg = layerConfig[layerKey] || {};
			if (cfg.kind === "stations") return false;
			if (isOdLayer(layerKey)) return false;
			return true;
		}

		function normalizeTrackEditLocalPatch(patch) {
			if (!patch || typeof patch !== "object") return null;
			const pointId = String(patch.pointId || "").trim();
			const layerKey = String(patch.layerKey || "").trim();
			if (!pointId || !layerKey) return null;
			const rowIndex = parseNumericValue(patch.rowIndex);
			const timestamp = parseNumericValue(patch.timestamp);
			const latitude = parseNumericValue(patch.position?.latitude);
			const longitude = parseNumericValue(patch.position?.longitude);
			const metadata = {};
			if (patch.metadata && typeof patch.metadata === "object" && !Array.isArray(patch.metadata)) {
				Object.entries(patch.metadata).forEach(([key, value]) => {
					if (!String(key || "").trim()) return;
					if (value == null) return;
					metadata[String(key).trim()] = value;
				});
			}
			const normalized = {
				pointId,
				layerKey,
				rowIndex: rowIndex == null ? 0 : Math.max(0, Math.round(rowIndex)),
				timestamp: timestamp == null ? null : timestamp,
				metadata,
			};
			if (latitude != null && longitude != null) {
				normalized.position = {
					latitude,
					longitude,
				};
			}
			return normalized;
		}

		function mergeTrackEditLocalPatch(existingPatch, incomingPatch) {
			const normalizedExisting = normalizeTrackEditLocalPatch(existingPatch);
			const normalizedIncoming = normalizeTrackEditLocalPatch(incomingPatch);
			if (!normalizedExisting) return normalizedIncoming;
			if (!normalizedIncoming) return normalizedExisting;
			return normalizeTrackEditLocalPatch({
				...normalizedExisting,
				...normalizedIncoming,
				position: normalizedIncoming.position || normalizedExisting.position,
				metadata: {
					...(normalizedExisting.metadata || {}),
					...(normalizedIncoming.metadata || {}),
				},
			});
		}

		function compareTrackEditPatchOrder(leftPatch, rightPatch) {
			const leftLayer = String(leftPatch?.layerKey || "");
			const rightLayer = String(rightPatch?.layerKey || "");
			const layerComparison = leftLayer.localeCompare(rightLayer);
			if (layerComparison) return layerComparison;
			const leftRowIndex = Math.max(0, Math.round(parseNumericValue(leftPatch?.rowIndex) ?? 0));
			const rightRowIndex = Math.max(0, Math.round(parseNumericValue(rightPatch?.rowIndex) ?? 0));
			if (leftRowIndex !== rightRowIndex) return leftRowIndex - rightRowIndex;
			const leftTimestamp = parseNumericValue(leftPatch?.timestamp) ?? 0;
			const rightTimestamp = parseNumericValue(rightPatch?.timestamp) ?? 0;
			if (leftTimestamp !== rightTimestamp) return leftTimestamp - rightTimestamp;
			return String(leftPatch?.pointId || "").localeCompare(String(rightPatch?.pointId || ""));
		}

		function buildSortedTrackEditPatches(patches = []) {
			return [...(patches || [])].sort(compareTrackEditPatchOrder);
		}

		function areTrackEditNumbersEquivalent(leftValue, rightValue) {
			if (leftValue == null || rightValue == null) return false;
			return Math.abs(Number(leftValue) - Number(rightValue)) <= 1e-9;
		}

		function getBaseTrackEditRowForPatch(patch) {
			const normalizedPatch = normalizeTrackEditLocalPatch(patch);
			if (!normalizedPatch) return null;
			const layerRows = currentBaseRawDataByLayer?.[normalizedPatch.layerKey] || [];
			if (!layerRows.length) return null;
			return layerRows.find((row) => String(row?.__studioPointId || "").trim() === normalizedPatch.pointId)
				|| layerRows.find((row) => Math.max(0, Math.round(parseNumericValue(row?.__studioBaseRowIndex) ?? -1)) === normalizedPatch.rowIndex)
				|| null;
		}

		function compactTrackEditPatchAgainstBase(patch) {
			const normalizedPatch = normalizeTrackEditLocalPatch(patch);
			if (!normalizedPatch) return null;
			const baseRow = getBaseTrackEditRowForPatch(normalizedPatch);
			if (!baseRow) return normalizedPatch;
			const compactedPatch = {
				pointId: normalizedPatch.pointId,
				layerKey: normalizedPatch.layerKey,
				rowIndex: normalizedPatch.rowIndex,
				timestamp: normalizedPatch.timestamp,
			};
			if (normalizedPatch.position) {
				const baseCoord = getRowCoordinate(baseRow);
				if (
					!baseCoord
					|| !areTrackEditNumbersEquivalent(normalizedPatch.position.latitude, baseCoord.lat)
					|| !areTrackEditNumbersEquivalent(normalizedPatch.position.longitude, baseCoord.lon)
				) {
					compactedPatch.position = normalizedPatch.position;
				}
			}
			const compactedMetadata = {};
			Object.entries(normalizedPatch.metadata || {}).forEach(([key, value]) => {
				if (value == null) return;
				if (String(baseRow?.[key] ?? "").trim() === String(value).trim()) return;
				compactedMetadata[key] = value;
			});
			if (Object.keys(compactedMetadata).length) {
				compactedPatch.metadata = compactedMetadata;
			}
			return compactedPatch.position || Object.keys(compactedPatch.metadata || {}).length
				? compactedPatch
				: null;
		}

		function normalizeTrackEditsLocalRecord(record, context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid: record?.uid || record?.sample_id || context.uid,
				reviewerId: record?.reviewer_id || record?.reviewerId || context.reviewerId,
				reviewerName: record?.reviewer_name || record?.reviewerName || record?.reviewer || context.reviewerName,
			});
			const empty = buildEmptyTrackEdits(
				scopedContext.uid,
				scopedContext.reviewerId,
				scopedContext.reviewerName,
			);
			const mergedPatchesById = new Map();
			const patchItems = Array.isArray(record?.pointPatches)
				? record.pointPatches
				: Array.isArray(record?.patches)
					? record.patches
					: Array.isArray(record?.trackEdits)
						? record.trackEdits
						: [];
			patchItems.forEach((item) => {
				const normalized = normalizeTrackEditLocalPatch(item);
				if (!normalized) return;
				mergedPatchesById.set(
					normalized.pointId,
					mergeTrackEditLocalPatch(mergedPatchesById.get(normalized.pointId), normalized),
				);
			});
			return {
				...empty,
				schema_version: 1,
				updated_at: String(record?.updated_at || record?.updatedAt || "").trim(),
				pointPatches: buildSortedTrackEditPatches([...mergedPatchesById.values()]),
			};
		}

		function getCurrentTrackEdits(context = {}) {
			const scopedContext = buildReviewerScopedContext(context);
			if (!scopedContext.uid) {
				return buildEmptyTrackEdits(scopedContext.uid, scopedContext.reviewerId, scopedContext.reviewerName);
			}
			return normalizeTrackEditsLocalRecord(
				trackEditsByTrack[getCurrentTrackEditStoreKey(scopedContext)],
				scopedContext,
			);
		}

		function setCurrentTrackEditsRecord(record, context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid: record?.uid || record?.sample_id || context.uid,
				reviewerId: record?.reviewer_id || record?.reviewerId || context.reviewerId,
				reviewerName: record?.reviewer_name || record?.reviewerName || record?.reviewer || context.reviewerName,
			});
			if (!scopedContext.uid) {
				return buildEmptyTrackEdits(scopedContext.uid, scopedContext.reviewerId, scopedContext.reviewerName);
			}
			const normalized = normalizeTrackEditsLocalRecord({
				...record,
				uid: record?.uid || record?.sample_id || scopedContext.uid,
				sample_id: record?.sample_id || record?.uid || scopedContext.uid,
				reviewer_id: record?.reviewer_id || record?.reviewerId || scopedContext.reviewerId,
				reviewer_name: record?.reviewer_name || record?.reviewerName || scopedContext.reviewerName,
				reviewer: record?.reviewer || scopedContext.reviewerName,
			}, scopedContext);
			trackEditsByTrack[getCurrentTrackEditStoreKey(scopedContext)] = normalized;
			persistTimelineAnnotationStore(TRACK_EDITS_STORAGE_KEY, trackEditsByTrack);
			return normalized;
		}

		function inferTrackRowCoordinateKeys(row) {
			const latKey = row?.latitude != null ? "latitude" : row?.start_latitude != null ? "start_latitude" : row?.lat != null ? "lat" : "";
			const lonKey = row?.longitude != null ? "longitude" : row?.start_longitude != null ? "start_longitude" : row?.lng != null ? "lng" : row?.lon != null ? "lon" : "";
			return { latKey, lonKey };
		}

		function decorateTrackRowsWithPointMeta(uid, layerKey, rows) {
			return (rows || []).map((row, rowIndex) => {
				if (!row || typeof row !== "object") return row;
				const timestamp = getRowMidTimeSeconds(row);
				const { latKey, lonKey } = inferTrackRowCoordinateKeys(row);
				row.__studioBaseRowIndex = rowIndex;
				row.__studioLayerKey = layerKey;
				row.__studioPointTimestamp = timestamp;
				row.__studioLatKey = latKey;
				row.__studioLonKey = lonKey;
				row.__studioPointId = buildTrackPointId(uid, layerKey, rowIndex, timestamp);
				return row;
			});
		}

		function buildTrackPointReference(uid, layerKey, row, rowIndex) {
			if (!row || typeof row !== "object") return null;
			const coord = getRowCoordinate(row);
			if (!coord) return null;
			const normalizedRowIndex = Math.max(0, Math.round(parseNumericValue(row?.__studioBaseRowIndex) ?? rowIndex ?? 0));
			const timestamp = parseNumericValue(row?.__studioPointTimestamp ?? getRowMidTimeSeconds(row));
			const pointId = String(row?.__studioPointId || buildTrackPointId(uid, layerKey, normalizedRowIndex, timestamp)).trim();
			if (!pointId) return null;
			return {
				pointId,
				layerKey,
				row,
				rowIndex: normalizedRowIndex,
				timestamp,
				position: {
					latitude: coord.lat,
					longitude: coord.lon,
				},
				metadataField: getTrackEditMetadataFieldForLayer(layerKey),
				metadataValue: getTrackEditMetadataFieldForLayer(layerKey)
					? row?.[getTrackEditMetadataFieldForLayer(layerKey)]
					: "",
			};
		}

		function buildTrackEditPatchMap(record = getCurrentTrackEdits()) {
			return new Map(
				(record?.pointPatches || [])
					.map((item) => normalizeTrackEditLocalPatch(item))
					.filter(Boolean)
					.map((item) => [item.pointId, item])
			);
		}

		function applyTrackEditPatchToRow(row, patch) {
			if (!patch) return row;
			const nextRow = { ...row };
			if (patch.position) {
				const latKey = row?.__studioLatKey || inferTrackRowCoordinateKeys(row).latKey;
				const lonKey = row?.__studioLonKey || inferTrackRowCoordinateKeys(row).lonKey;
				if (latKey) nextRow[latKey] = patch.position.latitude;
				if (lonKey) nextRow[lonKey] = patch.position.longitude;
			}
			Object.entries(patch.metadata || {}).forEach(([key, value]) => {
				nextRow[key] = value;
			});
			return nextRow;
		}

		function applyTrackEditsToLayerRows(layerKey, rows, patchMap) {
			return (rows || []).map((row, rowIndex) => {
				const pointRef = buildTrackPointReference(currentUid, layerKey, row, rowIndex);
				if (!pointRef) return row;
				const patch = patchMap.get(pointRef.pointId);
				return patch ? applyTrackEditPatchToRow(row, patch) : row;
			});
		}

		function applyTrackEditsToDataByLayer(dataByLayer = currentBaseRawDataByLayer) {
			const patchMap = buildTrackEditPatchMap();
			return Object.fromEntries(
				Object.entries(dataByLayer || {}).map(([layerKey, rows]) => [
					layerKey,
					isTrackEditLayerEditable(layerKey)
						? applyTrackEditsToLayerRows(layerKey, rows || [], patchMap)
						: (rows || []),
				])
			);
		}

		function rebuildTrackEditPointIndex() {
			const nextRefsById = {};
			const nextIdsByLayer = {};
			Object.entries(currentRawDataByLayer || {}).forEach(([layerKey, rows]) => {
				if (!isTrackEditLayerEditable(layerKey)) return;
				(rows || []).forEach((row, rowIndex) => {
					const pointRef = buildTrackPointReference(currentUid, layerKey, row, rowIndex);
					if (!pointRef) return;
					nextRefsById[pointRef.pointId] = pointRef;
					(nextIdsByLayer[layerKey] ||= []).push(pointRef.pointId);
				});
			});
			trackEditState.pointRefsById = nextRefsById;
			trackEditState.pointIdsByLayer = nextIdsByLayer;
			if (!trackEditState.anchorPointId || !nextRefsById[trackEditState.anchorPointId]) {
				trackEditState.anchorPointId = "";
			}
			if (!trackEditState.lastTouchedPointId || !nextRefsById[trackEditState.lastTouchedPointId]) {
				trackEditState.lastTouchedPointId = "";
			}
		}

		function updateTrackEditSelectionLayerKey() {
			const selectedLayers = [...new Set(
				(trackEditState.selectedPointIds || [])
					.map((pointId) => trackEditState.pointRefsById[pointId]?.layerKey || "")
					.filter(Boolean)
			)];
			trackEditState.selectionLayerKey = selectedLayers.length === 1 ? selectedLayers[0] : "";
		}

		function getTrackEditSelectionPointRefs() {
			return (trackEditState.selectedPointIds || [])
				.map((pointId) => trackEditState.pointRefsById[pointId])
				.filter(Boolean);
		}

		function reconcileTrackEditSelection() {
			trackEditState.selectedPointIds = (trackEditState.selectedPointIds || [])
				.filter((pointId) => !!trackEditState.pointRefsById[pointId]);
			if (trackEditState.anchorPointId && !trackEditState.pointRefsById[trackEditState.anchorPointId]) {
				trackEditState.anchorPointId = "";
			}
			if (!trackEditState.selectedPointIds.length) {
				trackEditState.contextPointId = "";
				trackEditState.contextField = "";
				trackEditState.contextValue = "";
			}
			updateTrackEditSelectionLayerKey();
		}

		function setTrackEditStatus(message, tone = "idle") {
			trackEditState.statusMessage = String(message || "").trim();
			trackEditState.statusTone = tone || "idle";
		}

		function buildTrackEditRecordSignature(record = getCurrentTrackEdits()) {
			return buildTrackEditPatchRenderSignature(record);
		}

		function cloneTrackEditRecord(record = getCurrentTrackEdits()) {
			return normalizeTrackEditsLocalRecord(deepClone(record));
		}

		function markTrackEditRecordAsSaved(record = getCurrentTrackEdits()) {
			trackEditState.savedBaselineSignature = buildTrackEditRecordSignature(record);
			trackEditState.dirty = false;
		}

		function syncTrackEditDirtyState(record = getCurrentTrackEdits()) {
			trackEditState.dirty = buildTrackEditRecordSignature(record) !== (trackEditState.savedBaselineSignature || "");
		}

		function resetTrackEditHistoryState(record = getCurrentTrackEdits()) {
			trackEditState.undoStack = [];
			trackEditState.redoStack = [];
			markTrackEditRecordAsSaved(record);
		}

		function pushTrackEditUndoSnapshot(record = getCurrentTrackEdits()) {
			trackEditState.undoStack.push(cloneTrackEditRecord(record));
			if (trackEditState.undoStack.length > 60) {
				trackEditState.undoStack.shift();
			}
			trackEditState.redoStack = [];
		}

		function buildTrackEditCoordinateSummary(selectionRefs) {
			return selectionRefs
				.slice(0, 3)
				.map((item) => `${getLayerLabel(item.layerKey)} #${item.rowIndex + 1}: ${Number(item.position?.latitude || 0).toFixed(6)}, ${Number(item.position?.longitude || 0).toFixed(6)}`)
				.join(" | ");
		}

		function getTrackEditEffectiveStatusText(defaultText) {
			const dirtyText = trackEditState.dirty ? " · 有未保存修改" : "";
			const spaceText = trackEditState.enabled && !trackEditState.spaceModifierActive
				? " · 按住空格平移地图，滚轮/双击可缩放"
				: trackEditState.enabled && trackEditState.spaceModifierActive
					? " · 当前可平移地图"
					: "";
			return `${defaultText}${dirtyText}${spaceText}`;
		}

		function setMapHandlerEnabled(handler, nextEnabled) {
			if (!handler) return;
			try {
				if (nextEnabled) handler.enable?.();
				else handler.disable?.();
			} catch (_) {}
		}

		function syncTrackEditMapInteractionLock() {
			if (!map) return;
			const mapPanningEnabled = !trackEditState.enabled || !!trackEditState.spaceModifierActive;
			const mapZoomEnabled = !trackEditState.scrollWheelSuppressed;
			setMapHandlerEnabled(map.dragging, mapPanningEnabled);
			setMapHandlerEnabled(map.touchZoom, true);
			setMapHandlerEnabled(map.doubleClickZoom, true);
			setMapHandlerEnabled(map.scrollWheelZoom, mapZoomEnabled);
			setMapHandlerEnabled(map.boxZoom, !trackEditState.enabled);
			map.getContainer?.()?.classList?.toggle?.(
				"track-edit-map-locked",
				!!trackEditState.enabled && !trackEditState.spaceModifierActive,
			);
		}

		function setTrackEditSpaceModifierActive(nextActive, options = {}) {
			const effectiveValue = !!trackEditState.enabled && !!nextActive;
			if (trackEditState.spaceModifierActive === effectiveValue) return false;
			trackEditState.spaceModifierActive = effectiveValue;
			syncTrackEditMapInteractionLock();
			if (options.render !== false) renderTrackEditPanel();
			return true;
		}

		function renderTrackEditPanel() {
			const panel = document.getElementById("track-edit-panel");
			const editModeButton = document.getElementById("track-edit-toggle");
			const annotationModeButton = document.getElementById("review-mode-annotation-btn");
			const reviewPanel = document.getElementById("review-panel");
			const annotationPanel = document.getElementById("review-annotation-mode-panel");
			const clearButton = document.getElementById("track-edit-clear-selection");
			const undoButton = document.getElementById("track-edit-undo-btn");
			const redoButton = document.getElementById("track-edit-redo-btn");
			const saveButton = document.getElementById("track-edit-save-btn");
			const saveOptionsButton = document.getElementById("track-edit-save-options-btn");
			const coordinateToggle = document.getElementById("track-edit-show-coordinates");
			const coordinateSummary = document.getElementById("track-edit-coordinate-summary");
			const statusEl = document.getElementById("track-edit-status");
			const selectionEl = document.getElementById("track-edit-selection");
			if (!panel || !editModeButton || !annotationModeButton || !clearButton || !statusEl || !selectionEl) return;
			const annotationEnabled = currentUiConfig.annotationEnabled !== false;
			if (!trackEditState.enabled && trackEditState.saveMenuOpen) closeTrackEditSaveMenu();
			if (!trackEditState.enabled && trackEditState.spaceModifierActive) {
				trackEditState.spaceModifierActive = false;
			}
			panel.hidden = !annotationEnabled || !trackEditState.enabled;
			if (annotationPanel) annotationPanel.hidden = !annotationEnabled || !!trackEditState.enabled;
			if (reviewPanel) reviewPanel.dataset.mode = trackEditState.enabled ? "edit" : "review";
			if (!annotationEnabled) return;
			const hasReviewer = !!getCurrentReviewerId();
			const replayReadOnly = isTimelineAnnotationReadOnly();
			const replayLabel = getReplayTimelineSourceLabel();
			const editableLayerCount = Object.keys(trackEditState.pointIdsByLayer || {}).length;
			const canEnterEditMode = !!currentUid && hasReviewer && editableLayerCount > 0 && !replayReadOnly;
			editModeButton.disabled = !currentUid || !hasReviewer || editableLayerCount <= 0 || replayReadOnly;
			editModeButton.classList.toggle("active", !!trackEditState.enabled);
			editModeButton.setAttribute("aria-pressed", trackEditState.enabled ? "true" : "false");
			annotationModeButton.classList.toggle("active", !trackEditState.enabled);
			annotationModeButton.setAttribute("aria-pressed", trackEditState.enabled ? "false" : "true");
			clearButton.disabled = !trackEditState.selectedPointIds.length;
			if (undoButton) undoButton.disabled = !trackEditState.undoStack.length;
			if (redoButton) redoButton.disabled = !trackEditState.redoStack.length;
			if (saveButton) saveButton.disabled = !currentUid || !hasReviewer || !trackEditState.dirty;
			if (saveOptionsButton) {
				saveOptionsButton.disabled = !currentUid || !hasReviewer;
				saveOptionsButton.setAttribute("aria-expanded", trackEditState.saveMenuOpen ? "true" : "false");
			}
			if (coordinateToggle) {
				coordinateToggle.checked = !!trackEditState.showCoordinates;
				coordinateToggle.disabled = !trackEditState.enabled;
			}
			const selectionRefs = getTrackEditSelectionPointRefs();
			if (!currentUid) {
				selectionEl.textContent = "请先选择 UID";
			} else if (!hasReviewer) {
				selectionEl.textContent = "请先设置当前标注者";
			} else if (replayReadOnly) {
				selectionEl.textContent = replayLabel ? `当前回放 ${replayLabel} · 轨迹编辑已锁定` : "当前回放只读，轨迹编辑已锁定";
			} else if (!editableLayerCount) {
				selectionEl.textContent = "当前轨迹没有可编辑点图层";
			} else if (!selectionRefs.length) {
				selectionEl.textContent = "未选中任何点";
			} else {
				const layerNames = [...new Set(selectionRefs.map((item) => getLayerLabel(item.layerKey)))];
				selectionEl.textContent = `已选 ${selectionRefs.length} 个点${layerNames.length ? ` · ${layerNames.join(" / ")}` : ""}`;
			}
			if (!trackEditState.statusMessage) {
				if (!currentUid) setTrackEditStatus("请选择要编辑的轨迹", "idle");
				else if (!hasReviewer) setTrackEditStatus("设置标注者后即可进入编辑模式", "warn");
				else if (replayReadOnly) setTrackEditStatus(getTimelineAnnotationReadOnlyMessage(), "warn");
				else if (!editableLayerCount) setTrackEditStatus("当前时间窗口内没有可编辑点", "warn");
				else if (trackEditState.enabled && canEnterEditMode) setTrackEditStatus("编辑模式已开启", "active");
				else setTrackEditStatus("编辑关闭", "idle");
			}
			statusEl.textContent = getTrackEditEffectiveStatusText(trackEditState.statusMessage);
			statusEl.dataset.tone = trackEditState.statusTone || "idle";
			if (coordinateSummary) {
				const shouldShowCoordinates = !!trackEditState.enabled && !!trackEditState.showCoordinates && !!selectionRefs.length;
				coordinateSummary.hidden = !shouldShowCoordinates;
				coordinateSummary.textContent = shouldShowCoordinates
					? buildTrackEditCoordinateSummary(selectionRefs)
					: "";
			}
			syncTrackEditMapInteractionLock();
		}

		function closeTrackEditContextMenu() {
			trackEditState.contextMenuOpen = false;
			const menu = document.getElementById("track-edit-context-menu");
			if (!menu) return;
			menu.classList.remove("open");
			menu.setAttribute("aria-hidden", "true");
		}

		function closeTrackEditSaveMenu() {
			trackEditState.saveMenuOpen = false;
			const menu = document.getElementById("track-edit-save-menu");
			if (!menu) return;
			menu.classList.remove("open");
			menu.setAttribute("aria-hidden", "true");
		}

		function openTrackEditSaveMenu(anchorEl) {
			const menu = document.getElementById("track-edit-save-menu");
			if (!menu || !anchorEl) return;
			closeTrackEditContextMenu();
			trackEditState.saveMenuOpen = true;
			menu.classList.add("open");
			menu.setAttribute("aria-hidden", "false");
			const anchorRect = anchorEl.getBoundingClientRect();
			const menuRect = menu.getBoundingClientRect();
			const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
			const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
			const margin = 10;
			let left = anchorRect.right - menuRect.width;
			let top = anchorRect.bottom + 8;
			if (left + menuRect.width > viewportWidth - margin) left = viewportWidth - menuRect.width - margin;
			if (left < margin) left = margin;
			if (top + menuRect.height > viewportHeight - margin) top = anchorRect.top - menuRect.height - 8;
			if (top < margin) top = margin;
			menu.style.left = `${left}px`;
			menu.style.top = `${top}px`;
		}

		function getTrackEditRangePointIds(anchorPointId, targetPointId) {
			const anchorRef = trackEditState.pointRefsById[anchorPointId];
			const targetRef = trackEditState.pointRefsById[targetPointId];
			if (!anchorRef || !targetRef || anchorRef.layerKey !== targetRef.layerKey) return targetPointId ? [targetPointId] : [];
			const layerPointIds = trackEditState.pointIdsByLayer[anchorRef.layerKey] || [];
			const startIndex = layerPointIds.indexOf(anchorPointId);
			const endIndex = layerPointIds.indexOf(targetPointId);
			if (startIndex < 0 || endIndex < 0) return [targetPointId];
			const left = Math.min(startIndex, endIndex);
			const right = Math.max(startIndex, endIndex);
			return layerPointIds.slice(left, right + 1);
		}

		function selectTrackEditPoint(pointId, options = {}) {
			if (!trackEditState.enabled) return false;
			const pointRef = trackEditState.pointRefsById[pointId];
			if (!pointRef) return false;
			const toggle = options.toggle === true || options.additive === true;
			const range = options.range === true;
			const currentSelection = (trackEditState.selectedPointIds || []).filter((candidate) => !!trackEditState.pointRefsById[candidate]);
			let nextSelection = currentSelection;
			const effectiveAnchor = trackEditState.anchorPointId
				&& currentSelection.includes(trackEditState.anchorPointId)
				&& trackEditState.pointRefsById[trackEditState.anchorPointId]
				? trackEditState.anchorPointId
				: (currentSelection[currentSelection.length - 1] || pointId);
			if (range && effectiveAnchor) {
				const rangeIds = getTrackEditRangePointIds(effectiveAnchor, pointId);
				nextSelection = toggle
					? dedupePreserveOrder([...currentSelection, ...rangeIds])
					: rangeIds;
			} else if (toggle) {
				nextSelection = currentSelection.includes(pointId)
					? currentSelection.filter((candidate) => candidate !== pointId)
					: dedupePreserveOrder([...currentSelection, pointId]);
				if (nextSelection.includes(pointId)) trackEditState.anchorPointId = pointId;
			} else {
				nextSelection = [pointId];
				trackEditState.anchorPointId = pointId;
			}
			if (!range && !toggle) {
				trackEditState.anchorPointId = pointId;
			}
			trackEditState.lastTouchedPointId = pointId;
			trackEditState.selectedPointIds = nextSelection;
			if (!trackEditState.selectedPointIds.includes(trackEditState.anchorPointId)) {
				trackEditState.anchorPointId = trackEditState.selectedPointIds.includes(pointId)
					? pointId
					: (trackEditState.selectedPointIds[trackEditState.selectedPointIds.length - 1] || "");
			}
			updateTrackEditSelectionLayerKey();
			closeTrackEditContextMenu();
			if (options.syncTimeScrubber !== false) {
				alignTimeScrubberToTime(pointRef.timestamp, {
					layerKey: pointRef.layerKey,
					keepWindow: true,
					followView: false,
				});
			}
			clearRenderedCache();
			renderMapDisplayFromCurrentState({ exists: currentExistsByLayer, forceFit: false });
			renderTrackEditPanel();
			return true;
		}

		function clearTrackEditSelection(options = {}) {
			trackEditState.selectedPointIds = [];
			trackEditState.anchorPointId = "";
			trackEditState.lastTouchedPointId = "";
			trackEditState.selectionLayerKey = "";
			if (options.closeMenu !== false) closeTrackEditContextMenu();
			if (options.render !== false) {
				clearRenderedCache();
				renderMapDisplayFromCurrentState({ exists: currentExistsByLayer, forceFit: false });
				renderTrackEditPanel();
			}
		}

		function clearTrackEditInteractionState(options = {}) {
			trackEditState.enabled = false;
			trackEditState.dragging = false;
			trackEditState.dragPointId = "";
			trackEditState.dragOriginDisplayLat = null;
			trackEditState.dragOriginDisplayLon = null;
			trackEditState.dragSnapshot = [];
			trackEditState.dragSuppressClickUntil = 0;
			trackEditState.spaceModifierActive = false;
			clearTrackEditSelection({ render: false, closeMenu: false });
			closeTrackEditContextMenu();
			closeTrackEditSaveMenu();
			if (options.resetHistory === true) {
				trackEditState.undoStack = [];
				trackEditState.redoStack = [];
				trackEditState.dirty = false;
				trackEditState.savedBaselineSignature = "";
			}
			if (options.resetStatus !== false) {
				setTrackEditStatus(options.statusMessage || "编辑关闭", options.statusTone || "idle");
			}
			syncTrackEditMapInteractionLock();
			if (options.render === true) {
				clearRenderedCache();
				renderMapDisplayFromCurrentState({ exists: currentExistsByLayer, forceFit: false });
				renderTrackEditPanel();
			}
		}

		function getTrackEditContextConfig() {
			const selectionRefs = getTrackEditSelectionPointRefs();
			if (!selectionRefs.length) {
				return {
					enabled: false,
					title: "批量修改轨迹点",
					subtitle: "当前未选中点",
					fieldLabel: "标签字段",
					options: [],
					value: "",
					reason: "请先选中要修改的轨迹点",
				};
			}
			const layerKeys = [...new Set(selectionRefs.map((item) => item.layerKey))];
			if (layerKeys.length !== 1) {
				return {
					enabled: false,
					title: "批量修改轨迹点",
					subtitle: `已选 ${selectionRefs.length} 个点`,
					fieldLabel: "标签字段",
					options: [],
					value: "",
					reason: "批量改标签目前只支持同一图层的选点",
				};
			}
			const layerKey = layerKeys[0];
			const field = getTrackEditMetadataFieldForLayer(layerKey);
			const options = getTrackEditMetadataOptionsForLayer(layerKey);
			if (!field || !options.length) {
				return {
					enabled: false,
					title: `${getLayerLabel(layerKey)} 批量编辑`,
					subtitle: `已选 ${selectionRefs.length} 个点`,
					fieldLabel: "标签字段",
					options: [],
					value: "",
					reason: "当前图层暂时只支持位置编辑",
				};
			}
			const uniqueValues = dedupePreserveOrder(selectionRefs.map((item) => String(item.row?.[field] || "").trim()));
			const hasMixedValue = uniqueValues.length > 1;
			const currentValue = hasMixedValue ? "" : String(trackEditState.contextValue || selectionRefs[0].row?.[field] || "").trim();
			return {
				enabled: true,
				layerKey,
				field,
				title: `${getLayerLabel(layerKey)} 批量编辑`,
				subtitle: hasMixedValue
					? `已选 ${selectionRefs.length} 个点 · ${field} 当前值不一致`
					: `已选 ${selectionRefs.length} 个点 · 修改 ${field}`,
				fieldLabel: field,
				options,
				value: options.includes(currentValue) ? currentValue : "",
				mixedValue: hasMixedValue,
				placeholderLabel: hasMixedValue ? `当前选中 ${field} 不一致，请选择新的统一值` : "",
				reason: "",
			};
		}

		function renderTrackEditContextMenu() {
			const titleEl = document.getElementById("track-edit-context-title");
			const subtitleEl = document.getElementById("track-edit-context-subtitle");
			const fieldLabelEl = document.getElementById("track-edit-context-field-label");
			const valueSelect = document.getElementById("track-edit-context-value");
			const applyButton = document.getElementById("track-edit-context-apply");
			if (!titleEl || !subtitleEl || !fieldLabelEl || !valueSelect || !applyButton) return;
			const config = getTrackEditContextConfig();
			titleEl.textContent = config.title;
			subtitleEl.textContent = config.enabled
				? config.subtitle
				: config.reason || config.subtitle;
			fieldLabelEl.textContent = config.fieldLabel;
			const optionMarkup = [];
			if (config.enabled && config.mixedValue) {
				optionMarkup.push(`<option value="" disabled selected>${escapeHtml(config.placeholderLabel || "当前值不一致，请选择新的统一值")}</option>`);
			}
			optionMarkup.push(...config.options.map((option) => `
				<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>
			`));
			valueSelect.innerHTML = optionMarkup.join("");
			valueSelect.disabled = !config.enabled;
			applyButton.disabled = !config.enabled || !config.value;
			if (config.enabled) {
				valueSelect.value = config.value;
				trackEditState.contextField = config.field;
				trackEditState.contextValue = config.value;
			} else {
				trackEditState.contextField = "";
				trackEditState.contextValue = "";
			}
		}

		function openTrackEditContextMenu(clientX, clientY, pointId = "") {
			const menu = document.getElementById("track-edit-context-menu");
			if (!menu) return;
			closeTrackEditSaveMenu();
			if (pointId) trackEditState.contextPointId = pointId;
			trackEditState.contextMenuOpen = true;
			renderTrackEditContextMenu();
			menu.classList.add("open");
			menu.setAttribute("aria-hidden", "false");
			const menuRect = menu.getBoundingClientRect();
			const margin = 10;
			const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
			const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
			let left = clientX + 10;
			let top = clientY + 10;
			if (clientX + 10 + menuRect.width > viewportWidth - margin) left = clientX - menuRect.width - 10;
			if (clientY + 10 + menuRect.height > viewportHeight - margin) top = clientY - menuRect.height - 10;
			left = Math.max(margin, Math.min(viewportWidth - menuRect.width - margin, left));
			top = Math.max(margin, Math.min(viewportHeight - menuRect.height - margin, top));
			menu.style.left = `${left}px`;
			menu.style.top = `${top}px`;
		}

		function buildTrackEditPatchFromRef(pointRef, payload = {}) {
			if (!pointRef) return null;
			const patch = {
				pointId: pointRef.pointId,
				layerKey: pointRef.layerKey,
				rowIndex: pointRef.rowIndex,
				timestamp: pointRef.timestamp,
			};
			if (payload.position) patch.position = payload.position;
			if (payload.metadata) patch.metadata = payload.metadata;
			return normalizeTrackEditLocalPatch(patch);
		}

		async function persistCurrentTrackEditsToServer(record = getCurrentTrackEdits(), context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid: record?.uid || record?.sample_id || context.uid,
				reviewerId: record?.reviewer_id || record?.reviewerId || context.reviewerId,
				reviewerName: record?.reviewer_name || record?.reviewerName || record?.reviewer || context.reviewerName,
			});
			if (!scopedContext.uid || !scopedContext.reviewerId || isReplayTimelineActiveForContext(scopedContext)) return null;
			const storeKey = getCurrentTrackEditStoreKey(scopedContext);
			const requestSequence = ++trackEditPersistRequestSequence;
			latestTrackEditPersistRequestByStoreKey[storeKey] = requestSequence;
			try {
				const response = await fetch(buildTrackEditsApiUrl({}, scopedContext), {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						uid: scopedContext.uid,
						sample_id: scopedContext.uid,
						reviewer_id: scopedContext.reviewerId,
						reviewer_name: scopedContext.reviewerName,
						patches: record.pointPatches || [],
						pointPatches: record.pointPatches || [],
						overwrite: context.overwrite === true,
					}),
				});
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const nextRecord = normalizeTrackEditsLocalRecord(
					payload.track_edits || payload.trackEdits || payload.trackEditsRecord || record,
					scopedContext,
				);
				if (latestTrackEditPersistRequestByStoreKey[storeKey] !== requestSequence) return nextRecord;
				setCurrentTrackEditsRecord(nextRecord, scopedContext);
				if (!isReviewerScopedContextCurrent(scopedContext)) return nextRecord;
				trackEditState.lastSavedAt = nextRecord.updated_at || "";
				markTrackEditRecordAsSaved(nextRecord);
				setTrackEditStatus(
					String(context.successMessage || "").trim() || `已保存 ${nextRecord.pointPatches.length} 个轨迹点修正`,
					"active",
				);
				renderTrackEditPanel();
				return nextRecord;
			} catch (error) {
				if (latestTrackEditPersistRequestByStoreKey[storeKey] !== requestSequence) return null;
				if (!isReviewerScopedContextCurrent(scopedContext)) return null;
				setTrackEditStatus(
					String(context.failureMessage || "").trim() || `轨迹修正保存失败：${error?.message || error}`,
					"error",
				);
				renderTrackEditPanel();
				return null;
			}
		}

		function applyCurrentTrackEditsToCurrentData(options = {}) {
			const nextRawDataByLayer = applyTrackEditsToDataByLayer(currentBaseRawDataByLayer);
			const nextFilteredDataByLayer = Object.fromEntries(
				Object.entries(nextRawDataByLayer || {}).map(([layerKey, rows]) => [
					layerKey,
					filterRowsByCurrentTimeWindow(rows || []),
				])
			);
			currentRawDataByLayer = nextRawDataByLayer;
			currentFilteredDataByLayer = nextFilteredDataByLayer;
			rebuildTrackEditPointIndex();
			reconcileTrackEditSelection();
			if (options.syncTimeScrubber !== false) {
				syncTimeScrubberFromCurrentData({
					preserveTime: options.preserveScrubberTime !== false,
					resetVisibleRange: options.resetVisibleRange === true,
				});
			}
			clearRenderedCache();
			renderMapDisplayFromCurrentState({
				exists: currentExistsByLayer,
				forceFit: !!options.forceFit,
			});
			renderTrackEditPanel();
		}

		function upsertCurrentTrackEditPatches(patches, options = {}) {
			if (!currentUid || !getCurrentReviewerId() || isTimelineAnnotationReadOnly()) return false;
			const normalizedPatches = (patches || [])
				.map((item) => normalizeTrackEditLocalPatch(item))
				.filter(Boolean);
			if (!normalizedPatches.length) return false;
			const currentRecord = getCurrentTrackEdits();
			const patchMap = buildTrackEditPatchMap(currentRecord);
			normalizedPatches.forEach((patch) => {
				const mergedPatch = mergeTrackEditLocalPatch(patchMap.get(patch.pointId), patch);
				const compactedPatch = compactTrackEditPatchAgainstBase(mergedPatch);
				if (compactedPatch) patchMap.set(compactedPatch.pointId, compactedPatch);
				else patchMap.delete(patch.pointId);
			});
			const nextRecord = normalizeTrackEditsLocalRecord({
				...currentRecord,
				uid: currentUid,
				sample_id: currentUid,
				reviewer_id: getCurrentReviewerId(),
				reviewer_name: getCurrentReviewerName(),
				reviewer: getCurrentReviewerName(),
				updated_at: new Date().toISOString(),
				pointPatches: buildSortedTrackEditPatches([...patchMap.values()]),
			});
			if (buildTrackEditRecordSignature(nextRecord) === buildTrackEditRecordSignature(currentRecord)) {
				return false;
			}
			pushTrackEditUndoSnapshot(currentRecord);
			setCurrentTrackEditsRecord(nextRecord);
			syncTrackEditDirtyState(nextRecord);
			setTrackEditStatus(
				String(options.statusMessage || "").trim() || `已更新 ${normalizedPatches.length} 个轨迹点，待保存`,
				options.statusTone || "warn",
			);
			applyCurrentTrackEditsToCurrentData({
				preserveScrubberTime: options.preserveScrubberTime !== false,
				forceFit: !!options.forceFit,
			});
			if (options.persist === true) {
				void persistCurrentTrackEditsToServer(nextRecord, options.persistContext || {});
			}
			return true;
		}

		async function loadTrackEditsForUid(uid, context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid,
			});
			if (!scopedContext.uid) {
				return buildEmptyTrackEdits(scopedContext.uid, scopedContext.reviewerId, scopedContext.reviewerName);
			}
			const storeKey = getCurrentTrackEditStoreKey(scopedContext);
			const requestSequence = ++trackEditLoadRequestSequence;
			latestTrackEditLoadRequestByStoreKey[storeKey] = requestSequence;
			if (currentUiConfig.annotationEnabled === false || !scopedContext.reviewerId) {
				const empty = buildEmptyTrackEdits(scopedContext.uid, scopedContext.reviewerId, scopedContext.reviewerName);
				setCurrentTrackEditsRecord(empty, scopedContext);
				if (isReviewerScopedContextCurrent(scopedContext)) {
					trackEditState.lastSavedAt = "";
					resetTrackEditHistoryState(empty);
					trackEditState.spaceModifierActive = false;
					closeTrackEditSaveMenu();
				}
				return empty;
			}
			let nextRecord;
			try {
				const response = await fetch(buildTrackEditsApiUrl({ uid: scopedContext.uid }, scopedContext));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				nextRecord = normalizeTrackEditsLocalRecord(
					payload.track_edits || payload.trackEdits || payload.trackEditsRecord || {},
					scopedContext,
				);
			} catch (_) {
				nextRecord = normalizeTrackEditsLocalRecord(
					trackEditsByTrack[storeKey] || buildEmptyTrackEdits(scopedContext.uid, scopedContext.reviewerId, scopedContext.reviewerName),
					scopedContext,
				);
			}
			if (latestTrackEditLoadRequestByStoreKey[storeKey] !== requestSequence) return nextRecord;
			setCurrentTrackEditsRecord(nextRecord, scopedContext);
			if (isReviewerScopedContextCurrent(scopedContext)) {
				trackEditState.lastSavedAt = nextRecord.updated_at || "";
				resetTrackEditHistoryState(nextRecord);
				trackEditState.spaceModifierActive = false;
				closeTrackEditSaveMenu();
			}
			return nextRecord;
		}

		function undoTrackEditChange() {
			if (!trackEditState.undoStack.length) return false;
			const currentRecord = cloneTrackEditRecord(getCurrentTrackEdits());
			const previousRecord = cloneTrackEditRecord(trackEditState.undoStack.pop());
			trackEditState.redoStack.push(currentRecord);
			if (trackEditState.redoStack.length > 60) {
				trackEditState.redoStack.shift();
			}
			setCurrentTrackEditsRecord(previousRecord);
			syncTrackEditDirtyState(previousRecord);
			closeTrackEditSaveMenu();
			setTrackEditStatus("已撤销最近一次编辑", "active");
			applyCurrentTrackEditsToCurrentData({
				preserveScrubberTime: true,
				forceFit: false,
			});
			return true;
		}

		function redoTrackEditChange() {
			if (!trackEditState.redoStack.length) return false;
			const currentRecord = cloneTrackEditRecord(getCurrentTrackEdits());
			const nextRecord = cloneTrackEditRecord(trackEditState.redoStack.pop());
			trackEditState.undoStack.push(currentRecord);
			if (trackEditState.undoStack.length > 60) {
				trackEditState.undoStack.shift();
			}
			setCurrentTrackEditsRecord(nextRecord);
			syncTrackEditDirtyState(nextRecord);
			closeTrackEditSaveMenu();
			setTrackEditStatus("已恢复最近一次编辑", "active");
			applyCurrentTrackEditsToCurrentData({
				preserveScrubberTime: true,
				forceFit: false,
			});
			return true;
		}

		async function saveCurrentTrackEdits(options = {}) {
			if (!currentUid) {
				setTrackEditStatus("请先选择要编辑的轨迹", "warn");
				renderTrackEditPanel();
				return null;
			}
			if (isTimelineAnnotationReadOnly()) {
				setTrackEditStatus(getTimelineAnnotationReadOnlyMessage(), "warn");
				renderTrackEditPanel();
				return null;
			}
			if (!ensureAnnotationSessionReady({ prompt: true })) {
				renderTrackEditPanel();
				return null;
			}
			const overwrite = options.overwrite === true;
			const currentRecord = getCurrentTrackEdits();
			closeTrackEditSaveMenu();
			if (!trackEditState.dirty && !overwrite) {
				setTrackEditStatus("当前轨迹修正已是最新，无需重复保存", "idle");
				renderTrackEditPanel();
				return currentRecord;
			}
			setTrackEditStatus(overwrite ? "正在覆盖当前轨迹修正..." : "正在保存轨迹修正...", "active");
			renderTrackEditPanel();
			return persistCurrentTrackEditsToServer(currentRecord, {
				overwrite,
				successMessage: overwrite
					? `已覆盖当前轨迹修正（${currentRecord.pointPatches.length} 个点）`
					: `已保存 ${currentRecord.pointPatches.length} 个轨迹点修正`,
			});
		}

		function downloadCurrentTrackEditsAsJson() {
			if (!currentUid) {
				setTrackEditStatus("请先选择要导出的轨迹", "warn");
				renderTrackEditPanel();
				return null;
			}
			if (!ensureAnnotationSessionReady({ prompt: true })) {
				renderTrackEditPanel();
				return null;
			}
			const currentRecord = getCurrentTrackEdits();
			const payload = {
				...currentRecord,
				patches: currentRecord.pointPatches || [],
				batch_name: currentBatchName || "",
				store_key: getCurrentTrackEditStoreKey(),
				exported_at: new Date().toISOString(),
			};
			const filename = [
				currentUid || "track",
				getCurrentReviewerId() || "reviewer",
				"track-edits",
			].join("_") + ".json";
			const downloadUrl = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(payload, null, 2))}`;
			const anchor = document.createElement ? document.createElement("a") : null;
			if (anchor) {
				anchor.href = downloadUrl;
				anchor.download = filename;
				anchor.rel = "noopener";
				anchor.style.display = "none";
				document.body?.appendChild?.(anchor);
				anchor.click?.();
				anchor.remove?.();
			} else if (typeof location !== "undefined") {
				location.href = downloadUrl;
			}
			window.__lastTrackEditDownloadUrl = downloadUrl;
			window.__lastTrackEditDownloadFilename = filename;
			closeTrackEditSaveMenu();
			setTrackEditStatus(`已准备导出 ${filename}`, "active");
			renderTrackEditPanel();
			return payload;
		}

		function setTrackEditModeEnabled(nextEnabled) {
			if (nextEnabled) {
				if (isTimelineAnnotationReadOnly()) {
					setTrackEditStatus(getTimelineAnnotationReadOnlyMessage(), "warn");
					renderTrackEditPanel();
					return false;
				}
				if (!ensureAnnotationSessionReady({ prompt: true })) return false;
				if (!currentUid) {
					setTrackEditStatus("请先选择要编辑的轨迹", "warn");
					renderTrackEditPanel();
					return false;
				}
				if (!Object.keys(trackEditState.pointIdsByLayer || {}).length) {
					setTrackEditStatus("当前时间窗口内没有可编辑点", "warn");
					renderTrackEditPanel();
					return false;
				}
				trackEditState.enabled = true;
				trackEditState.spaceModifierActive = false;
				setTrackEditStatus(
					trackEditState.dirty ? "编辑模式已开启，当前有未保存修改" : "编辑模式已开启",
					trackEditState.dirty ? "warn" : "active",
				);
			} else {
				clearTrackEditInteractionState({
					resetStatus: true,
					statusMessage: trackEditState.dirty ? "已退出编辑模式，修改仍未保存" : "编辑关闭",
					statusTone: trackEditState.dirty ? "warn" : "idle",
				});
			}
			clearRenderedCache();
			renderMapDisplayFromCurrentState({ exists: currentExistsByLayer, forceFit: false });
			renderTrackEditPanel();
			return true;
		}

		function toggleTrackEditMode() {
			return setTrackEditModeEnabled(!trackEditState.enabled);
		}

		function beginTrackEditMarkerDrag(pointId, marker) {
			if (!trackEditState.enabled || !marker) return;
			if (!trackEditState.selectedPointIds.includes(pointId)) {
				trackEditState.selectedPointIds = [pointId];
				trackEditState.anchorPointId = pointId;
				trackEditState.lastTouchedPointId = pointId;
				updateTrackEditSelectionLayerKey();
				const pointRef = trackEditState.pointRefsById[pointId];
				if (pointRef) {
					alignTimeScrubberToTime(pointRef.timestamp, {
						layerKey: pointRef.layerKey,
						keepWindow: true,
						followView: false,
					});
				}
				renderTrackEditPanel();
			}
			const dragMarker = marker;
			const dragLatLng = dragMarker.getLatLng?.();
			if (!dragLatLng) return;
			const dragSnapshot = getTrackEditSelectionPointRefs()
				.map((pointRef) => {
					const targetMarker = pointRef.pointId === pointId
						? dragMarker
						: trackEditState.renderedMarkersByPointId[pointRef.pointId];
					const markerLatLng = targetMarker?.getLatLng?.();
					if (!targetMarker || !markerLatLng) return null;
					return {
						pointId: pointRef.pointId,
						marker: targetMarker,
						displayLat: markerLatLng.lat,
						displayLon: markerLatLng.lng,
					};
				})
				.filter(Boolean);
			if (!dragSnapshot.length) return;
			trackEditState.dragging = true;
			trackEditState.dragPointId = pointId;
			trackEditState.dragOriginDisplayLat = dragLatLng.lat;
			trackEditState.dragOriginDisplayLon = dragLatLng.lng;
			trackEditState.dragSnapshot = dragSnapshot;
			closeTrackEditContextMenu();
			setTrackEditStatus(`正在拖动 ${dragSnapshot.length} 个点`, "active");
			renderTrackEditPanel();
		}

		function updateTrackEditMarkerDrag(pointId, marker) {
			if (!trackEditState.dragging || trackEditState.dragPointId !== pointId || !marker) return;
			const currentLatLng = marker.getLatLng?.();
			if (!currentLatLng) return;
			const deltaLat = currentLatLng.lat - (trackEditState.dragOriginDisplayLat ?? currentLatLng.lat);
			const deltaLon = currentLatLng.lng - (trackEditState.dragOriginDisplayLon ?? currentLatLng.lng);
			(trackEditState.dragSnapshot || []).forEach((item) => {
				if (item.pointId === pointId) return;
				item.marker?.setLatLng?.([item.displayLat + deltaLat, item.displayLon + deltaLon]);
			});
		}

		function commitTrackEditMarkerDrag(pointId, marker) {
			if (!trackEditState.dragging || trackEditState.dragPointId !== pointId || !marker) return;
			const currentLatLng = marker.getLatLng?.();
			const originLat = trackEditState.dragOriginDisplayLat;
			const originLon = trackEditState.dragOriginDisplayLon;
			const snapshot = [...(trackEditState.dragSnapshot || [])];
			trackEditState.dragging = false;
			trackEditState.dragPointId = "";
			trackEditState.dragOriginDisplayLat = null;
			trackEditState.dragOriginDisplayLon = null;
			trackEditState.dragSnapshot = [];
			trackEditState.dragSuppressClickUntil = Date.now() + 220;
			if (!currentLatLng || originLat == null || originLon == null || !snapshot.length) {
				setTrackEditStatus("拖动已取消", "warn");
				renderTrackEditPanel();
				return;
			}
			const deltaLat = currentLatLng.lat - originLat;
			const deltaLon = currentLatLng.lng - originLon;
			const patches = snapshot.map((item) => {
				const pointRef = trackEditState.pointRefsById[item.pointId];
				if (!pointRef) return null;
				const [latitude, longitude] = convertLatLonBetweenTileSystems(
					item.displayLat + deltaLat,
					item.displayLon + deltaLon,
					getMapTileCoordinateSystem(),
					"wgs84"
				);
				return buildTrackEditPatchFromRef(pointRef, {
					position: { latitude, longitude },
				});
			}).filter(Boolean);
			if (!patches.length) {
				setTrackEditStatus("拖动已取消", "warn");
				renderTrackEditPanel();
				return;
			}
			upsertCurrentTrackEditPatches(patches, {
				statusMessage: `已更新 ${patches.length} 个点的位置，待保存`,
				statusTone: "warn",
				preserveScrubberTime: true,
			});
		}

		function applyTrackEditMetadataPatch(value) {
			const config = getTrackEditContextConfig();
			if (!config.enabled || !config.field) return false;
			const normalizedValue = String(value || "").trim();
			if (!normalizedValue) return false;
			const patches = getTrackEditSelectionPointRefs()
				.map((pointRef) => buildTrackEditPatchFromRef(pointRef, {
					metadata: {
						[config.field]: normalizedValue,
					},
				}))
				.filter(Boolean);
			if (!patches.length) return false;
			closeTrackEditContextMenu();
			upsertCurrentTrackEditPatches(patches, {
				statusMessage: `已批量更新 ${patches.length} 个点的 ${config.field}，待保存`,
				statusTone: "warn",
				preserveScrubberTime: true,
			});
			return true;
		}

		function setTimeScrubberActive(nextActive) {
			document.getElementById("time-scrubber-control").classList.toggle("active", !!nextActive);
		}

		function isKeyboardTargetBlockingReviewShortcuts(target) {
			if (!target) return false;
			if (target instanceof HTMLElement && target.isContentEditable) return true;
			if (typeof target.closest !== "function") return false;
			if (target.closest('[contenteditable]:not([contenteditable="false"])')) return true;
			if (target.closest("textarea")) return true;
			const input = target.closest("input");
			if (!input || input.disabled) return false;
			if (input.readOnly) return false;
			const type = String(input.type || "text").toLowerCase();
			if (["button", "submit", "reset", "checkbox", "radio", "file", "color", "range", "hidden"].includes(type)) return false;
			return true;
		}

		function isEditableKeyboardTarget(target) {
			if (!target) return false;
			if (target instanceof HTMLElement && target.isContentEditable) return true;
			return typeof target.closest === "function"
				&& !!target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])');
		}

		function clearTimeFocusMarker() {
			if (timeFocusMarker && map?.hasLayer?.(timeFocusMarker)) map.removeLayer(timeFocusMarker);
			timeFocusMarker = null;
		}

		function buildTimeFocusTooltipHtml(point) {
			if (!point) return "";
			const title = `${getLayerLabel(point.layerKey)} | ${formatDateTime(point.time)}`;
			const entry = buildLayerEntryText(point.layerKey, point.row, point.rowIndex);
			return `
				<div class="focus-title">${escapeHtml(title)}</div>
				<div>${escapeHtml(entry)}</div>
				<div class="focus-sub">${escapeHtml(`坐标 ${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}`)}</div>
			`;
		}

		function buildTimeFocusBubbleHtml(point) {
			const layerText = getLayerLabel(point?.layerKey || "").slice(0, 3) || "T";
			const color = point ? getTimeScrubberPointColor(point) : "#111827";
			return `<div class="time-focus-bubble" style="--focus-color:${escapeHtml(color)}"><span>${escapeHtml(layerText)}</span></div>`;
		}

		function getCurrentTimelinePinStoreKey(context = {}) {
			return buildReviewerScopedStoreKey(context);
		}

		function getCurrentTimelinePins(context = {}) {
			const scopedContext = buildReviewerScopedContext(context);
			if (currentUiConfig.annotationEnabled === false || !scopedContext.uid || !scopedContext.reviewerId) return [];
			return timelinePinsByTrack[getCurrentTimelinePinStoreKey(scopedContext)] || [];
		}

		function saveCurrentTimelinePins(pins) {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId() || isTimelineAnnotationReadOnly()) return;
			timelinePinsByTrack[getCurrentTimelinePinStoreKey()] = Array.isArray(pins) ? pins : [];
			persistTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY, timelinePinsByTrack);
			void persistCurrentTimelineAnnotationsToServer();
		}

		function getCurrentTimelineSegments(context = {}) {
			const scopedContext = buildReviewerScopedContext(context);
			if (currentUiConfig.annotationEnabled === false || !scopedContext.uid || !scopedContext.reviewerId) return [];
			return timelineSegmentsByTrack[getCurrentTimelinePinStoreKey(scopedContext)] || [];
		}

		function isExclusiveTimelineSegmentModeEnabled() {
			if (isReplayTimelineActiveForContext()) {
				return !!replayTimelineState.segmentPolicy?.exclusiveMode;
			}
			return !!annotationSettings.exclusiveSegments;
		}

		function buildTimelineSegmentPolicyPayload() {
			return {
				exclusiveMode: isExclusiveTimelineSegmentModeEnabled(),
				intervalSemantics: isExclusiveTimelineSegmentModeEnabled()
					? "left_open_right_closed"
					: "closed_interval",
			};
		}

		function buildTimelineSegmentId(categoryId, startTime, endTime, fallbackId = "") {
			const normalizedCategoryId = String(categoryId || "").trim() || "segment";
			const leftTime = Math.round(Math.min(startTime, endTime));
			const rightTime = Math.round(Math.max(startTime, endTime));
			return fallbackId || `${normalizedCategoryId}:${leftTime}:${rightTime}`;
		}

		function buildNormalizedTimelineSegment(segment, startTime, endTime, options = {}) {
			const leftTime = Math.min(startTime, endTime);
			const rightTime = Math.max(startTime, endTime);
			if (!(rightTime > leftTime)) return null;
			return {
				...segment,
				startTime: leftTime,
				endTime: rightTime,
				id: buildTimelineSegmentId(
					options.categoryId ?? segment?.categoryId,
					leftTime,
					rightTime,
					options.preserveId === true ? String(segment?.id || "").trim() : ""
				),
			};
		}

		function normalizeExclusiveTimelineSegments(segments = []) {
			const normalized = [];
			(segments || []).forEach((segment) => {
				if (!segment || typeof segment !== "object") return;
				const startTime = parseNumericValue(segment.startTime);
				const endTime = parseNumericValue(segment.endTime);
				if (startTime == null || endTime == null) return;
				let candidate = buildNormalizedTimelineSegment(segment, startTime, endTime);
				if (!candidate) return;
				for (const existingSegment of normalized) {
					if (existingSegment.startTime < candidate.startTime && candidate.startTime < existingSegment.endTime) {
						candidate = buildNormalizedTimelineSegment(
							candidate,
							existingSegment.endTime,
							candidate.endTime,
							{ categoryId: candidate.categoryId }
						);
						break;
					}
				}
				if (!candidate) return;
				const trimmedExisting = [];
				normalized.forEach((existingSegment) => {
					if (existingSegment.endTime <= candidate.startTime || existingSegment.startTime >= candidate.endTime) {
						trimmedExisting.push(existingSegment);
						return;
					}
					if (existingSegment.startTime < candidate.startTime) {
						const leftRemainder = buildNormalizedTimelineSegment(
							existingSegment,
							existingSegment.startTime,
							candidate.startTime
						);
						if (leftRemainder) trimmedExisting.push(leftRemainder);
					}
					if (existingSegment.endTime > candidate.endTime) {
						const rightRemainder = buildNormalizedTimelineSegment(
							existingSegment,
							candidate.endTime,
							existingSegment.endTime
						);
						if (rightRemainder) trimmedExisting.push(rightRemainder);
					}
				});
				trimmedExisting.push(candidate);
				normalized.length = 0;
				trimmedExisting
					.sort((a, b) => (a.startTime - b.startTime) || (a.endTime - b.endTime) || String(a.categoryId || "").localeCompare(String(b.categoryId || "")))
					.forEach((item) => normalized.push(item));
			});
			return normalized;
		}

		function snapTimelineSegmentStartForExclusiveMode(segments, startTime, endTime) {
			const leftTime = Math.min(startTime, endTime);
			const rightTime = Math.max(startTime, endTime);
			const containingSegment = (segments || []).find((segment) =>
				leftTime > segment.startTime && leftTime < segment.endTime
			);
			if (!containingSegment) {
				return { startTime: leftTime, endTime: rightTime };
			}
			return {
				startTime: containingSegment.endTime,
				endTime: rightTime,
			};
		}

		function saveCurrentTimelineSegments(segments) {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId() || isTimelineAnnotationReadOnly()) return;
			const nextSegments = Array.isArray(segments) ? segments : [];
			timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] = isExclusiveTimelineSegmentModeEnabled()
				? normalizeExclusiveTimelineSegments(nextSegments)
				: nextSegments;
			persistTimelineAnnotationStore(TIMELINE_SEGMENTS_STORAGE_KEY, timelineSegmentsByTrack);
			void persistCurrentTimelineAnnotationsToServer();
		}

		function autoSelectAcceptDecisionAfterAnnotation() {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) return;
			if (typeof setDecisionButtons !== "function") return;
			if (selectedDecision === "accept") return;
			setDecisionButtons("accept");
		}

		function resetSegmentDraftState() {
			segmentDraftState = {
				active: false,
				categoryId: "",
				startTime: null,
				previewTime: null,
				startIndex: null,
				previewIndex: null,
			};
		}

		function cancelTimelineSegmentDraft(options = {}) {
			resetSegmentDraftState();
			if (options.silent !== true) renderTimeScrubberControl();
		}

		function startTimelineSegmentDraft(categoryId, pointIndex) {
			if (!ensureTimelineAnnotationsWritable({ prompt: true })) return;
			const point = (timeScrubberState.allPoints || [])[Math.max(0, Math.min((timeScrubberState.allPoints || []).length - 1, pointIndex ?? timeScrubberState.selectedIndex ?? 0))];
			if (!point || !getAnnotationCategoryById(categoryId)) return;
			segmentDraftState = {
				active: true,
				categoryId,
				startTime: point.time,
				previewTime: point.time,
				startIndex: timeScrubberState.selectedIndex,
				previewIndex: timeScrubberState.selectedIndex,
			};
			hideTimeScrubberContextMenu();
			renderTimeScrubberControl();
		}

		function updateTimelineSegmentDraftFromIndex(pointIndex) {
			if (!segmentDraftState.active) return;
			const points = timeScrubberState.allPoints || [];
			const clampedIndex = Math.max(0, Math.min(points.length - 1, Math.round(pointIndex ?? timeScrubberState.selectedIndex ?? 0)));
			const point = points[clampedIndex];
			if (!point) return;
			segmentDraftState.previewIndex = clampedIndex;
			segmentDraftState.previewTime = point.time;
		}

		function commitTimelineSegmentDraft(pointIndex) {
			if (!segmentDraftState.active) return;
			if (!ensureTimelineAnnotationsWritable({ prompt: false, render: false })) {
				cancelTimelineSegmentDraft({ silent: true });
				return;
			}
			updateTimelineSegmentDraftFromIndex(pointIndex);
			const category = getAnnotationCategoryById(segmentDraftState.categoryId);
			if (!category) {
				cancelTimelineSegmentDraft();
				return;
			}
			const startTime = segmentDraftState.startTime;
			const endTime = segmentDraftState.previewTime;
			if (startTime == null || endTime == null) {
				cancelTimelineSegmentDraft();
				return;
			}
			const leftTime = Math.min(startTime, endTime);
			const rightTime = Math.max(startTime, endTime);
			const existing = getCurrentTimelineSegments();
			const snappedBounds = isExclusiveTimelineSegmentModeEnabled()
				? snapTimelineSegmentStartForExclusiveMode(existing, leftTime, rightTime)
				: { startTime: leftTime, endTime: rightTime };
			const nextSegment = buildNormalizedTimelineSegment(
				{
					categoryId: category.id,
					categoryName: category.name,
					color: category.color,
					entryMode: "manual",
					segmentScope: "custom",
					sourceLayerKey: timeScrubberState.selectedLayer || "",
				},
				snappedBounds.startTime,
				snappedBounds.endTime,
				{ categoryId: category.id }
			);
			if (nextSegment) {
				if (isExclusiveTimelineSegmentModeEnabled()) {
					saveCurrentTimelineSegments([...existing, nextSegment]);
				} else if (!existing.some(item => item.id === nextSegment.id)) {
					saveCurrentTimelineSegments([
						...existing,
						nextSegment,
					]);
				}
				autoSelectAcceptDecisionAfterAnnotation();
			}
			resetSegmentDraftState();
			renderTimeScrubberControl();
		}

		function getRenderableTimelineSegments(options = {}) {
			const entries = getActiveTimelineSegmentsForDisplay().map(segment => ({
				...segment,
				isDraft: false,
			}));
			if (options.includeDraft !== false && segmentDraftState.active && segmentDraftState.startTime != null && segmentDraftState.previewTime != null) {
				const category = getAnnotationCategoryById(segmentDraftState.categoryId);
				if (category) {
					entries.push({
						id: "__draft__",
						categoryId: category.id,
						categoryName: category.name,
						color: category.color,
						startTime: Math.min(segmentDraftState.startTime, segmentDraftState.previewTime),
						endTime: Math.max(segmentDraftState.startTime, segmentDraftState.previewTime),
						isDraft: true,
					});
				}
			}
			return entries.sort((a, b) => (a.startTime - b.startTime) || (a.endTime - b.endTime));
		}

		function assignTimelineSegmentLanes(segments, maxLanes = 3) {
			const laneEnds = Array.from({ length: Math.max(1, maxLanes) }, () => -Infinity);
			return segments.map(segment => {
				let laneIndex = laneEnds.findIndex(endTime => segment.startTime >= endTime);
				if (laneIndex === -1) {
					return { ...segment, laneIndex: -1, renderMode: "cover" };
				}
				laneEnds[laneIndex] = segment.endTime;
				return { ...segment, laneIndex, renderMode: "lane" };
			});
		}

		function buildTimelineAnnotationsApiUrl(extraParams = {}, context = {}) {
			const scopedContext = buildReviewerScopedContext(context);
			return buildReviewApiUrl("/timeline-annotations", {
				...extraParams,
				reviewer_id: scopedContext.reviewerId,
			});
		}

		async function loadTimelineAnnotationsForUid(uid, context = {}) {
			const scopedContext = buildReviewerScopedContext({
				...context,
				uid,
			});
			if (!scopedContext.uid) return;
			const storeKey = getCurrentTimelinePinStoreKey(scopedContext);
			const requestSequence = ++timelineAnnotationLoadRequestSequence;
			latestTimelineAnnotationLoadRequestByStoreKey[storeKey] = requestSequence;
			if (currentUiConfig.annotationEnabled === false || !scopedContext.reviewerId) {
				timelinePinsByTrack[storeKey] = [];
				timelineSegmentsByTrack[storeKey] = [];
				persistTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY, timelinePinsByTrack);
				persistTimelineAnnotationStore(TIMELINE_SEGMENTS_STORAGE_KEY, timelineSegmentsByTrack);
				return;
			}
			try {
				const response = await fetch(buildTimelineAnnotationsApiUrl({ uid: scopedContext.uid }, scopedContext));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const annotations = payload.annotations || {};
				if (latestTimelineAnnotationLoadRequestByStoreKey[storeKey] !== requestSequence) return;
				if (typeof annotations.segmentPolicy?.exclusiveMode === "boolean" && isReviewerScopedContextCurrent(scopedContext)) {
					annotationSettings.exclusiveSegments = annotations.segmentPolicy.exclusiveMode;
					persistAnnotationSettings();
				}
				timelinePinsByTrack[storeKey] = Array.isArray(annotations.pins) ? annotations.pins : [];
				timelineSegmentsByTrack[storeKey] = Array.isArray(annotations.segments) ? annotations.segments : [];
				persistTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY, timelinePinsByTrack);
				persistTimelineAnnotationStore(TIMELINE_SEGMENTS_STORAGE_KEY, timelineSegmentsByTrack);
			} catch (_) {}
		}

		async function persistCurrentTimelineAnnotationsToServer() {
			const scopedContext = buildReviewerScopedContext();
			if (
				currentUiConfig.annotationEnabled === false
				|| !scopedContext.uid
				|| !scopedContext.reviewerId
				|| isReplayTimelineActiveForContext(scopedContext)
			) return;
			try {
				await fetch(buildTimelineAnnotationsApiUrl({}, scopedContext), {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						uid: scopedContext.uid,
						sample_id: scopedContext.uid,
						reviewer_id: scopedContext.reviewerId,
						reviewer_name: scopedContext.reviewerName,
						segmentPolicy: buildTimelineSegmentPolicyPayload(),
						pins: getCurrentTimelinePins(scopedContext),
						segments: getCurrentTimelineSegments(scopedContext),
					}),
				});
			} catch (_) {}
		}

		function timelineSegmentContainsTime(segment, targetTime, epsilon = 0) {
			if (!segment || targetTime == null) return false;
			if (segment.startTime === segment.endTime) {
				return Math.abs(targetTime - segment.endTime) <= epsilon;
			}
			if (isExclusiveTimelineSegmentModeEnabled()) {
				return targetTime > segment.startTime && targetTime <= (segment.endTime + epsilon);
			}
			return targetTime >= (segment.startTime - epsilon) && targetTime <= (segment.endTime + epsilon);
		}

		function getTimelineSegmentsAtTime(targetTime, options = {}) {
			if (targetTime == null) return [];
			const epsilon = options.epsilon ?? 0;
			return getActiveTimelineSegmentsForDisplay()
				.filter(segment => timelineSegmentContainsTime(segment, targetTime, epsilon))
				.sort((a, b) => (b.endTime - b.startTime) - (a.endTime - a.startTime) || (b.startTime - a.startTime));
		}

		function removeTimelineSegmentById(segmentId) {
			if (!segmentId || currentUiConfig.annotationEnabled === false || !getCurrentReviewerId()) return;
			if (!ensureTimelineAnnotationsWritable({ prompt: true, render: false })) return;
			saveCurrentTimelineSegments(getCurrentTimelineSegments().filter(segment => segment.id !== segmentId));
			renderTimeScrubberControl();
		}

		function hideTimeScrubberContextMenu() {
			timeScrubberContextMenuState = {
				open: false,
				pointIndex: null,
				clientX: 0,
				clientY: 0,
			};
			const menu = document.getElementById("time-scrubber-context-menu");
			if (!menu) return;
			menu.classList.remove("open");
			menu.setAttribute("aria-hidden", "true");
		}

		function showTimeScrubberContextMenu(clientX, clientY, pointIndex) {
			const menu = document.getElementById("time-scrubber-context-menu");
			if (!menu) return;
			timeScrubberContextMenuState = {
				open: true,
				pointIndex,
				clientX,
				clientY,
			};
			renderTimeScrubberContextMenuItems();
			menu.classList.add("open");
			menu.setAttribute("aria-hidden", "false");
			const menuRect = menu.getBoundingClientRect();
			const margin = 10;
			const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
			const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
			let left = clientX + 10;
			let top = clientY + 10;
			if (clientX + 10 + menuRect.width > viewportWidth - margin) {
				left = clientX - menuRect.width - 10;
			}
			if (clientY + 10 + menuRect.height > viewportHeight - margin) {
				top = clientY - menuRect.height - 10;
			}
			left = Math.max(margin, Math.min(viewportWidth - menuRect.width - margin, left));
			top = Math.max(margin, Math.min(viewportHeight - menuRect.height - margin, top));
			menu.style.left = `${left}px`;
			menu.style.top = `${top}px`;
		}

		function renderTimeScrubberContextMenuItems() {
			const menu = document.getElementById("time-scrubber-context-menu");
			if (!menu) return;
			if (isTimelineAnnotationReadOnly()) {
				menu.innerHTML = `
					<div class="time-scrubber-menu-section-label">只读回放</div>
					<div class="review-aggregate-empty">${escapeHtml(getTimelineAnnotationReadOnlyMessage())}</div>
				`;
				return;
			}
			const contextPoint = (timeScrubberState.allPoints || [])[Math.max(0, Math.min((timeScrubberState.allPoints || []).length - 1, timeScrubberContextMenuState.pointIndex ?? timeScrubberState.selectedIndex ?? 0))];
			const deleteSegmentItems = contextPoint
				? getTimelineSegmentsAtTime(contextPoint.time).map(segment => `
					<button class="time-scrubber-menu-item" type="button" data-action="delete-segment" data-segment-id="${escapeHtml(segment.id)}" style="color:${escapeHtml(segment.color || "#f87171")}">
						<span class="time-scrubber-menu-swatch" aria-hidden="true"></span>
						<span class="time-scrubber-menu-item-label">删除标记段：${escapeHtml(segment.categoryName || "未命名标签")}</span>
					</button>
				`).join("")
				: "";
			const segmentItems = annotationSettings.categories.map(category => `
				<button class="time-scrubber-menu-item" type="button" data-action="segment" data-category-id="${escapeHtml(category.id)}" style="color:${escapeHtml(category.color)}">
					<span class="time-scrubber-menu-swatch" aria-hidden="true"></span>
					<span class="time-scrubber-menu-item-label">开始段落：${escapeHtml(String(category.name || "").trim() || "未命名标签")}</span>
				</button>
			`).join("");
			menu.innerHTML = `
				<button class="time-scrubber-menu-item" type="button" data-action="pin">
					<span class="time-scrubber-menu-swatch" aria-hidden="true" style="background:rgba(255,255,255,0.92); color:rgba(255,255,255,0.92)"></span>
					<span class="time-scrubber-menu-item-label">打单点标签</span>
				</button>
				${deleteSegmentItems ? `<div class="time-scrubber-menu-separator" aria-hidden="true"></div><div class="time-scrubber-menu-section-label">删除已有标记</div>${deleteSegmentItems}` : ""}
				<div class="time-scrubber-menu-separator" aria-hidden="true"></div>
				<div class="time-scrubber-menu-section-label">段落标签</div>
				${segmentItems}
			`;
		}

		function addTimelinePinAtIndex(pointIndex) {
			if (!ensureTimelineAnnotationsWritable({ prompt: true })) return;
			const points = timeScrubberState.allPoints || [];
			const clampedIndex = Math.max(0, Math.min(points.length - 1, Math.round(pointIndex ?? timeScrubberState.selectedIndex ?? 0)));
			const point = points[clampedIndex];
			if (!point) return;
			const pinId = `${Math.round(point.time)}-${clampedIndex}`;
			const existingPins = getCurrentTimelinePins();
			if (existingPins.some(pin => pin.id === pinId)) {
				hideTimeScrubberContextMenu();
				return;
			}
			saveCurrentTimelinePins([
				...existingPins,
				{
					id: pinId,
					time: point.time,
					layerKey: point.layerKey,
					label: formatDateTime(point.time),
				},
			]);
			autoSelectAcceptDecisionAfterAnnotation();
			hideTimeScrubberContextMenu();
			renderTimeScrubberControl();
		}

		function getCurrentWindowQuickSegment() {
			if (!currentTimeWindow.enabled || !currentTimeWindow.startDay || !currentTimeWindow.endDay) return null;
			return getCurrentTimelineSegments().find(segment =>
				segment.entryMode === "window_quick"
				&& segment.segmentScope === "date_window"
				&& segment.windowStartDay === currentTimeWindow.startDay
				&& segment.windowEndDay === currentTimeWindow.endDay
			) || null;
		}

		function syncCurrentWindowQuickSegmentCategory(options = {}) {
			const existingQuickSegment = getCurrentWindowQuickSegment();
			if (existingQuickSegment && getAnnotationCategoryById(existingQuickSegment.categoryId) && options.preferExisting !== false) {
				currentTimeWindow.quickSegmentCategoryId = existingQuickSegment.categoryId;
				return currentTimeWindow.quickSegmentCategoryId;
			}
			if (getAnnotationCategoryById(currentTimeWindow.quickSegmentCategoryId)) {
				return currentTimeWindow.quickSegmentCategoryId;
			}
			currentTimeWindow.quickSegmentCategoryId = annotationSettings.categories[0]?.id || "";
			return currentTimeWindow.quickSegmentCategoryId;
		}

		function getCurrentTimeWindowDataBounds() {
			const windowBounds = getCurrentTimeWindowBounds();
			if (!windowBounds) return null;
			let minStart = null;
			let maxEnd = null;
			Object.values(currentRawDataByLayer || {}).forEach(rows => {
				(rows || []).forEach(row => {
					const rowBounds = inferRowTimeBounds(row);
					if (!rowBounds) return;
					const normalizedStart = normalizeUnixSeconds(rowBounds.start);
					const normalizedEnd = normalizeUnixSeconds(rowBounds.end);
					if (normalizedStart == null && normalizedEnd == null) return;
					const effectiveStart = normalizedStart != null ? normalizedStart : normalizedEnd;
					const effectiveEnd = normalizedEnd != null ? normalizedEnd : normalizedStart;
					if (effectiveStart == null || effectiveEnd == null) return;
					const overlapStart = Math.max(effectiveStart, windowBounds.start);
					const overlapEnd = Math.min(effectiveEnd, windowBounds.end);
					if (overlapEnd < overlapStart) return;
					if (minStart == null || overlapStart < minStart) minStart = overlapStart;
					if (maxEnd == null || overlapEnd > maxEnd) maxEnd = overlapEnd;
				});
			});
			return minStart == null || maxEnd == null ? null : { start: minStart, end: maxEnd };
		}

		function getCurrentWindowQuickSegmentSourceLayerKey() {
			if (timeScrubberState.selectedLayer && (currentFilteredDataByLayer[timeScrubberState.selectedLayer] || []).length) {
				return timeScrubberState.selectedLayer;
			}
			const firstLayer = Object.entries(currentFilteredDataByLayer || {}).find(([, rows]) => Array.isArray(rows) && rows.length);
			return firstLayer?.[0] || "";
		}

		function buildCurrentWindowQuickSegment(category, bounds, existingSegment = null) {
			const startDay = currentTimeWindow.startDay;
			const endDay = currentTimeWindow.endDay;
			return {
				id: existingSegment?.id || `window:${startDay}:${endDay}`,
				categoryId: category.id,
				categoryName: category.name,
				color: category.color,
				startTime: bounds.start,
				endTime: bounds.end,
				entryMode: "window_quick",
				segmentScope: "date_window",
				windowStartDay: startDay,
				windowEndDay: endDay,
				fixedSpanDays: clampFixedTimeWindowSpanDays(currentTimeWindow.fixedSpanDays),
				sourceLayerKey: getCurrentWindowQuickSegmentSourceLayerKey(),
			};
		}

		function getCurrentWindowQuickSegmentActionState() {
			if (currentUiConfig.annotationEnabled === false) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: "当前批次为只读模式",
					disabled: true,
					existingSegment: null,
				};
			}
			if (isTimelineAnnotationReadOnly()) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: getTimelineAnnotationReadOnlyMessage(),
					disabled: true,
					existingSegment: null,
				};
			}
			if (!currentTimeWindow.enabled || !currentTimeWindow.startDay || !currentTimeWindow.endDay) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: "请选择日期窗口",
					disabled: true,
					existingSegment: null,
				};
			}
			if (!annotationSettings.categories.length) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: "请先在设置里新增段落标签",
					disabled: true,
					existingSegment: null,
				};
			}
			const bounds = getCurrentTimeWindowDataBounds();
			if (!bounds) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: "当前窗口内无可标记时间",
					disabled: true,
					existingSegment: null,
				};
			}
			const selectedCategoryId = syncCurrentWindowQuickSegmentCategory({ preferExisting: false });
			const selectedCategory = getAnnotationCategoryById(selectedCategoryId);
			if (!selectedCategory) {
				return {
					action: "disabled",
					buttonLabel: "整段标记",
					statusText: "当前整段标签不可用",
					disabled: true,
					existingSegment: null,
				};
			}
			const existingSegment = getCurrentWindowQuickSegment();
			if (existingSegment) {
				return existingSegment.categoryId === selectedCategory.id
					? {
						action: "delete",
						buttonLabel: "取消整段标记",
						statusText: `已标记：${existingSegment.categoryName || "未命名标签"}`,
						disabled: false,
						existingSegment,
						selectedCategory,
						bounds,
					}
					: {
						action: "update",
						buttonLabel: "更新整段标签",
						statusText: `已标记：${existingSegment.categoryName || "未命名标签"}`,
						disabled: false,
						existingSegment,
						selectedCategory,
						bounds,
					};
			}
			return {
				action: "create",
				buttonLabel: "整段标记",
				statusText: "未标记",
				disabled: false,
				existingSegment: null,
				selectedCategory,
				bounds,
			};
		}

		function upsertCurrentWindowQuickSegment() {
			if (!ensureTimelineAnnotationsWritable({ prompt: true })) return;
			const actionState = getCurrentWindowQuickSegmentActionState();
			if (actionState.disabled || !actionState.selectedCategory || !actionState.bounds) return;
			const nextSegment = buildCurrentWindowQuickSegment(
				actionState.selectedCategory,
				actionState.bounds,
				actionState.existingSegment,
			);
			const remainingSegments = getCurrentTimelineSegments().filter(segment => segment.id !== nextSegment.id);
			if (isExclusiveTimelineSegmentModeEnabled()) {
				const snappedBounds = snapTimelineSegmentStartForExclusiveMode(
					remainingSegments,
					nextSegment.startTime,
					nextSegment.endTime,
				);
				const normalizedSegment = buildNormalizedTimelineSegment(
					nextSegment,
					snappedBounds.startTime,
					snappedBounds.endTime,
					{ categoryId: nextSegment.categoryId }
				);
				if (!normalizedSegment) return;
				saveCurrentTimelineSegments([...remainingSegments, normalizedSegment]);
			} else {
				saveCurrentTimelineSegments([...remainingSegments, nextSegment]);
			}
			autoSelectAcceptDecisionAfterAnnotation();
			renderTimeScrubberControl();
		}

		function removeCurrentWindowQuickSegment() {
			const existingSegment = getCurrentWindowQuickSegment();
			if (!existingSegment) return;
			removeTimelineSegmentById(existingSegment.id);
		}

		function toggleCurrentWindowQuickSegment() {
			const actionState = getCurrentWindowQuickSegmentActionState();
			if (actionState.disabled) return;
			if (actionState.action === "delete") {
				removeCurrentWindowQuickSegment();
				return;
			}
			upsertCurrentWindowQuickSegment();
		}

		function getTimeScrubberOverviewHitMode(pointerX, scale, visibleBounds) {
			if (!scale || !visibleBounds) return "";
			const startX = scale.getXForTime(visibleBounds.start);
			const endX = scale.getXForTime(visibleBounds.end);
			const leftX = Math.min(startX, endX);
			const rightX = Math.max(startX, endX);
			if (Math.abs(pointerX - leftX) <= TIME_SCRUBBER_OVERVIEW_EDGE_PAD) return "resize-start";
			if (Math.abs(pointerX - rightX) <= TIME_SCRUBBER_OVERVIEW_EDGE_PAD) return "resize-end";
			if (pointerX >= leftX && pointerX <= rightX) return "move";
			return "";
		}

		function updateTimeScrubberOverviewCursor(hitMode = "") {
			const canvas = document.getElementById("time-scrubber-overview-canvas");
			if (!canvas) return;
			if (timeScrubberState.isOverviewDragging) {
				canvas.style.cursor = timeScrubberState.overviewDragMode === "move" ? "grabbing" : "ew-resize";
				return;
			}
			canvas.style.cursor = hitMode === "resize-start" || hitMode === "resize-end" ? "ew-resize" : "grab";
		}

		function updateTimeFocusMarker() {
			const point = getActiveTimeScrubberPoint();
			if (!map || !point) {
				clearTimeFocusMarker();
				return;
			}
			const [glat, glon] = toGcj(point.lat, point.lon);
			const icon = L.divIcon({
				className: "time-focus-bubble-icon",
				html: buildTimeFocusBubbleHtml(point),
				iconSize: [28, 36],
				iconAnchor: [14, 32],
			});
			if (!timeFocusMarker) {
				timeFocusMarker = L.marker([glat, glon], {
					icon,
					zIndexOffset: 1000,
					keyboard: false,
				}).addTo(map);
				timeFocusMarker.bindTooltip(buildTimeFocusTooltipHtml(point), {
					permanent: true,
					direction: "top",
					offset: [0, -28],
					className: "time-focus-tooltip",
					opacity: 0.96,
				});
			} else {
				timeFocusMarker.setLatLng([glat, glon]);
				timeFocusMarker.setIcon(icon);
				if (timeFocusMarker.getTooltip()) timeFocusMarker.setTooltipContent(buildTimeFocusTooltipHtml(point));
				else {
				timeFocusMarker.bindTooltip(buildTimeFocusTooltipHtml(point), {
					permanent: true,
					direction: "top",
					offset: [0, -28],
					className: "time-focus-tooltip",
					opacity: 0.96,
				});
				}
			}
			const markerEl = timeFocusMarker.getElement?.();
			if (markerEl) markerEl.style.opacity = (timeScrubberState.isDragging || timeScrubberState.isOverviewDragging) ? "0.72" : "1";
			const tooltipEl = timeFocusMarker.getTooltip?.()?.getElement?.();
			if (tooltipEl) tooltipEl.classList.toggle("dimmed", !!(timeScrubberState.isDragging || timeScrubberState.isOverviewDragging));
			if (mapViewFollowScrubber && (timeScrubberState.isDragging || timeScrubberState.followSelectionOnUpdate)) {
				map.panTo([glat, glon], { animate: false });
			}
			timeScrubberState.followSelectionOnUpdate = false;
		}

		function resetTimeScrubber() {
			timeScrubberState = {
				enabled: false,
				selectedLayer: "",
				focusLayers: [],
				allPoints: [],
				visibleStartIndex: 0,
				visibleCount: 0,
				selectedIndex: 0,
				followSelectionOnUpdate: false,
				isDragging: false,
				isOverviewDragging: false,
				overviewDragMode: "",
				overviewDragOffsetSeconds: 0,
			};
			hideTimeScrubberContextMenu();
			resetSegmentDraftState();
			clearTimeFocusMarker();
			const control = document.getElementById("time-scrubber-control");
			control.classList.add("hidden");
			document.getElementById("time-scrubber-status").textContent = "时间轴未启用";
			document.getElementById("time-scrubber-range").textContent = "当前日期区间内暂无可定位时间点";
			const select = document.getElementById("time-scrubber-layer-select");
			select.innerHTML = "";
			select.disabled = true;
			const overviewCanvas = document.getElementById("time-scrubber-overview-canvas");
			if (overviewCanvas) overviewCanvas.classList.remove("dragging");
			renderTrackEditPanel();
		}

		function ensureTimeScrubberSelectionVisible() {
			const total = timeScrubberState.allPoints.length;
			if (!total) return;
			const visibleCount = getTimeScrubberVisibleCount(total);
			const minStart = timeScrubberState.selectedIndex - Math.floor(visibleCount * 0.5);
			if (timeScrubberState.selectedIndex < timeScrubberState.visibleStartIndex
				|| timeScrubberState.selectedIndex >= timeScrubberState.visibleStartIndex + visibleCount) {
				timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(minStart, total);
			} else {
				timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(timeScrubberState.visibleStartIndex, total);
			}
		}

		function setTimeScrubberVisibleStart(nextStart, options = {}) {
			const total = timeScrubberState.allPoints.length;
			timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(nextStart, total);
			if (options.keepSelection !== true) {
				const visibleCount = getTimeScrubberVisibleCount(total);
				const windowEnd = timeScrubberState.visibleStartIndex + Math.max(0, visibleCount - 1);
				if (timeScrubberState.selectedIndex < timeScrubberState.visibleStartIndex) {
					timeScrubberState.selectedIndex = timeScrubberState.visibleStartIndex;
				}
				if (timeScrubberState.selectedIndex > windowEnd) {
					timeScrubberState.selectedIndex = Math.max(timeScrubberState.visibleStartIndex, windowEnd);
				}
			}
			renderTimeScrubberControl();
			scheduleMapDisplayRefreshForTimeScrubber();
		}

		function setTimeScrubberVisibleCount(nextCount, options = {}) {
			const total = timeScrubberState.allPoints.length;
			const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, Math.max(0, total || 0));
			if (!maxVisible) return;
			const minVisible = Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxVisible);
			const clampedCount = Math.max(minVisible, Math.min(maxVisible, Math.round(nextCount || maxVisible)));
			timeScrubberState.visibleCount = clampedCount;
			timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(timeScrubberState.visibleStartIndex, total);
			if (options.keepSelection !== true) {
				const windowEnd = timeScrubberState.visibleStartIndex + clampedCount - 1;
				if (timeScrubberState.selectedIndex < timeScrubberState.visibleStartIndex) {
					timeScrubberState.selectedIndex = timeScrubberState.visibleStartIndex;
				}
				if (timeScrubberState.selectedIndex > windowEnd) {
					timeScrubberState.selectedIndex = Math.max(timeScrubberState.visibleStartIndex, windowEnd);
				}
			}
			renderTimeScrubberControl();
			scheduleMapDisplayRefreshForTimeScrubber();
		}

		function createTimeScrubberScale(visiblePoints, width, height) {
			const leftPad = 16;
			const rightPad = 16;
			const usableWidth = Math.max(1, width - leftPad - rightPad);
			const minTime = visiblePoints[0]?.time ?? 0;
			const maxTime = visiblePoints[visiblePoints.length - 1]?.time ?? minTime;
			const span = Math.max(1, maxTime - minTime);
			return {
				leftPad,
				rightPad,
				usableWidth,
				minTime,
				maxTime,
				getXForTime(time) {
					if (visiblePoints.length <= 1) return leftPad + usableWidth / 2;
					return leftPad + ((time - minTime) / span) * usableWidth;
				},
				getTimeForX(x) {
					const clamped = Math.max(leftPad, Math.min(width - rightPad, x));
					const ratio = usableWidth <= 0 ? 0 : (clamped - leftPad) / usableWidth;
					return minTime + ratio * span;
				},
			};
		}

		function findTimeScrubberStartIndexForTime(points, targetTime) {
			if (!Array.isArray(points) || !points.length) return 0;
			if (targetTime == null) return 0;
			let lo = 0;
			let hi = points.length;
			while (lo < hi) {
				const mid = Math.floor((lo + hi) / 2);
				if ((points[mid]?.time ?? 0) < targetTime) lo = mid + 1;
				else hi = mid;
			}
			return Math.max(0, Math.min(points.length - 1, lo));
		}

		function getCurrentVisibleTimeBounds() {
			const visiblePoints = getTimeScrubberVisiblePoints();
			if (!visiblePoints.length) return null;
			return {
				start: visiblePoints[0].time,
				end: visiblePoints[visiblePoints.length - 1].time,
			};
		}

		function getVisibleTimelineSegmentEntries(visibleStartTime, visibleEndTime, options = {}) {
			return assignTimelineSegmentLanes(
				getRenderableTimelineSegments(options).filter(segment => segment.endTime >= visibleStartTime && segment.startTime <= visibleEndTime),
				options.maxLanes || 3
			);
		}

		function getTimelineSegmentById(segmentId, options = {}) {
			if (!segmentId) return null;
			return getRenderableTimelineSegments({ includeDraft: options.includeDraft !== false })
				.find(segment => segment.id === segmentId) || null;
		}

		function buildTimeScrubberSegmentStripModel(width, height, options = {}) {
			const visiblePoints = getTimeScrubberVisiblePoints();
			if (!visiblePoints.length || width <= 0 || height <= 0) return null;
			const scale = createTimeScrubberScale(visiblePoints, width, height);
			const maxLanes = Math.max(1, Math.round(options.maxLanes || 4));
			const insetY = 2;
			const laneGap = 2;
			const laneAreaHeight = Math.max(8, height - insetY * 2);
			const laneHeight = Math.max(4, (laneAreaHeight - laneGap * (maxLanes - 1)) / maxLanes);
			const entries = getVisibleTimelineSegmentEntries(scale.minTime, scale.maxTime, {
				maxLanes,
				includeDraft: options.includeDraft !== false,
			}).map(segment => {
				const leftTime = Math.max(scale.minTime, segment.startTime);
				const rightTime = Math.min(scale.maxTime, segment.endTime);
				const startX = scale.getXForTime(leftTime);
				const endX = scale.getXForTime(rightTime);
				const x = Math.min(startX, endX);
				const widthPx = Math.max(6, Math.abs(endX - startX));
				const y = segment.renderMode === "cover"
					? insetY
					: (insetY + Math.max(0, segment.laneIndex) * (laneHeight + laneGap));
				const heightPx = segment.renderMode === "cover" ? laneAreaHeight : laneHeight;
				return {
					segment,
					x,
					y,
					widthPx,
					heightPx,
				};
			});
			return {
				scale,
				entries,
			};
		}

		function getTimeScrubberSegmentHitAtClientPoint(clientX, clientY) {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return null;
			const canvas = document.getElementById("time-scrubber-segment-canvas");
			if (!canvas) return null;
			const rect = canvas.getBoundingClientRect();
			if (rect.width <= 0 || rect.height <= 0) return null;
			const model = buildTimeScrubberSegmentStripModel(rect.width, rect.height);
			if (!model?.entries?.length) return null;
			const targetX = clientX - rect.left;
			const targetY = clientY - rect.top;
			const hits = model.entries.filter(entry =>
				targetX >= entry.x
				&& targetX <= (entry.x + entry.widthPx)
				&& targetY >= entry.y
				&& targetY <= (entry.y + entry.heightPx)
			);
			if (!hits.length) return null;
			hits.sort((left, right) => {
				const leftPriority = left.segment.renderMode === "lane" ? 0 : 1;
				const rightPriority = right.segment.renderMode === "lane" ? 0 : 1;
				if (leftPriority !== rightPriority) return leftPriority - rightPriority;
				const leftDuration = (left.segment.endTime || 0) - (left.segment.startTime || 0);
				const rightDuration = (right.segment.endTime || 0) - (right.segment.startTime || 0);
				return leftDuration - rightDuration;
			});
			return hits[0];
		}

		function clearTimeScrubberHoveredSegment(options = {}) {
			if (!timeScrubberState.hoveredSegmentId) return false;
			timeScrubberState.hoveredSegmentId = "";
			if (options.render !== false) renderTimeScrubberControl();
			return true;
		}

		function updateTimeScrubberHoveredSegmentFromClientPoint(clientX, clientY) {
			const hit = getTimeScrubberSegmentHitAtClientPoint(clientX, clientY);
			const nextId = hit?.segment?.id || "";
			if (nextId === (timeScrubberState.hoveredSegmentId || "")) return false;
			timeScrubberState.hoveredSegmentId = nextId;
			renderTimeScrubberControl();
			return true;
		}

		function setTimeScrubberSelectedSegment(segmentId, options = {}) {
			const segment = getTimelineSegmentById(segmentId, { includeDraft: options.includeDraft !== false });
			const resolvedId = segment?.id || "";
			const selectionChanged = resolvedId !== (timeScrubberState.selectedSegmentId || "");
			timeScrubberState.selectedSegmentId = resolvedId;
			if (!segment) {
				if (selectionChanged && options.render !== false) renderTimeScrubberControl();
				return selectionChanged;
			}
			if (options.syncSelection === true && Array.isArray(timeScrubberState.allPoints) && timeScrubberState.allPoints.length) {
				const midpointTime = segment.startTime === segment.endTime
					? segment.startTime
					: (segment.startTime + segment.endTime) * 0.5;
				const nearestIndex = findNearestTimeScrubberPointIndex(timeScrubberState.allPoints, midpointTime);
				setTimeScrubberSelectedIndex(nearestIndex, { followView: true });
				return true;
			}
			if (selectionChanged && options.render !== false) renderTimeScrubberControl();
			return selectionChanged;
		}

		function selectTimeScrubberSegmentFromClientPoint(clientX, clientY) {
			const hit = getTimeScrubberSegmentHitAtClientPoint(clientX, clientY);
			const nextId = hit?.segment?.id || "";
			const hoverChanged = nextId !== (timeScrubberState.hoveredSegmentId || "");
			timeScrubberState.hoveredSegmentId = nextId;
			if (nextId) {
				setTimeScrubberSelectedSegment(nextId, { syncSelection: true });
				return true;
			}
			const selectionChanged = !!timeScrubberState.selectedSegmentId;
			timeScrubberState.selectedSegmentId = "";
			if (hoverChanged || selectionChanged) renderTimeScrubberControl();
			return hoverChanged || selectionChanged;
		}

		function setTimeScrubberWindowFromStartTime(targetStartTime, options = {}) {
			const points = timeScrubberState.allPoints;
			if (!Array.isArray(points) || !points.length) return;
			const nextIndex = findTimeScrubberStartIndexForTime(points, targetStartTime);
			setTimeScrubberVisibleStart(nextIndex, options);
		}

		function drawTimeScrubberCanvas() {
			const canvas = document.getElementById("time-scrubber-canvas");
			const visiblePoints = getTimeScrubberVisiblePoints();
			const width = Math.max(32, canvas.clientWidth || canvas.offsetWidth || 0);
			const height = Math.max(32, canvas.clientHeight || canvas.offsetHeight || 0);
			const dpr = window.devicePixelRatio || 1;
			canvas.width = Math.round(width * dpr);
			canvas.height = Math.round(height * dpr);
			const ctx = canvas.getContext("2d");
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
			ctx.clearRect(0, 0, width, height);
			if (!visiblePoints.length) return;

			const activePoint = getActiveTimeScrubberPoint() || visiblePoints[0];
			const scale = createTimeScrubberScale(visiblePoints, width, height);
			const pointCount = visiblePoints.length;
			const baseY = 40;
			const topDateY = 9;
			const segmentBaseY = 20;
			const segmentLaneHeight = 8;
			const bottomHourY = 58;
			const bottomSelectedY = 75;
			const visibleStartTime = scale.minTime;
			const visibleEndTime = scale.maxTime;
			const daySeconds = 24 * 3600;
			const hourStepSeconds = getAdaptiveHourStepSeconds(visibleStartTime, visibleEndTime, 10);
			const visiblePins = getActiveTimelinePinsForDisplay().filter(pin => pin.time >= visibleStartTime && pin.time <= visibleEndTime);
			const visibleSegments = getVisibleTimelineSegmentEntries(visibleStartTime, visibleEndTime, { maxLanes: 3 });

			ctx.strokeStyle = "rgba(226,232,240,0.35)";
			ctx.lineWidth = 2;
			ctx.lineCap = "round";
			ctx.beginPath();
			ctx.moveTo(scale.leftPad, baseY);
			ctx.lineTo(width - scale.rightPad, baseY);
			ctx.stroke();

			const dayStart = floorToDisplayStep(visibleStartTime, daySeconds);
			if (dayStart != null) {
				const visibleDays = buildInclusiveDayRange(
					beijingDayKeyFromUnix(visibleStartTime),
					beijingDayKeyFromUnix(visibleEndTime)
				);
				ctx.fillStyle = "rgba(248,250,252,0.94)";
				ctx.font = "600 10px system-ui";
				visibleDays.forEach((dayKey, dayIndex) => {
					const startTs = beijingDayStartUnix(dayKey);
					if (startTs == null) return;
					const x = startTs <= visibleStartTime
						? scale.leftPad
						: scale.getXForTime(Math.max(visibleStartTime, Math.min(visibleEndTime, startTs)));
					const labelX = Math.max(scale.leftPad, Math.min(width - scale.rightPad - 54, x + (dayIndex === 0 && startTs < visibleStartTime ? 0 : 3)));
					ctx.textAlign = "left";
					ctx.fillText(formatDisplayDate(startTs, { short: true, weekday: true }), labelX, topDateY);
				});
			}

			visibleSegments.forEach(segment => {
				const leftTime = Math.max(visibleStartTime, segment.startTime);
				const rightTime = Math.min(visibleEndTime, segment.endTime);
				const startX = scale.getXForTime(leftTime);
				const endX = scale.getXForTime(rightTime);
				const x = Math.min(startX, endX);
				const widthPx = Math.max(10, Math.abs(endX - startX));
				const isCover = segment.renderMode === "cover";
				const y = isCover ? segmentBaseY : (segmentBaseY + Math.max(0, segment.laneIndex) * segmentLaneHeight);
				const heightPx = isCover ? (segmentLaneHeight * 3 - 2) : 5.5;
				ctx.save();
				ctx.globalAlpha = segment.isDraft ? (isCover ? 0.48 : 0.55) : (isCover ? 0.3 : 0.38);
				ctx.fillStyle = segment.color || "#60a5fa";
				ctx.strokeStyle = segment.color || "#60a5fa";
				ctx.lineWidth = segment.isDraft ? 1.6 : (isCover ? 0.8 : 1.1);
				if (segment.isDraft) ctx.setLineDash([5, 3]);
				ctx.beginPath();
				if (typeof ctx.roundRect === "function") {
					ctx.roundRect(x, y, widthPx, heightPx, 999);
				} else {
					ctx.rect(x, y, widthPx, heightPx);
				}
				ctx.fill();
				ctx.stroke();
				ctx.restore();
				if (widthPx >= 42 && (isCover || segment.laneIndex <= 0)) {
					ctx.fillStyle = "rgba(248,250,252,0.92)";
					ctx.font = "600 9px system-ui";
					ctx.textAlign = "left";
					ctx.fillText(segment.categoryName || "标签", x + 6, y + heightPx + 8);
				}
			});

			const tickStart = ceilToDisplayStep(visibleStartTime, hourStepSeconds);
			if (tickStart != null) {
				for (let tick = tickStart; tick <= visibleEndTime; tick += hourStepSeconds) {
					const x = scale.getXForTime(tick);
					const isMidnight = formatDisplayClock(tick) === "00:00";
					ctx.strokeStyle = isMidnight ? "rgba(248,250,252,0.42)" : "rgba(226,232,240,0.24)";
					ctx.lineWidth = isMidnight ? 1.2 : 1;
					ctx.beginPath();
					ctx.moveTo(x, baseY - (isMidnight ? 14 : 10));
					ctx.lineTo(x, baseY + 6);
					ctx.stroke();

					ctx.textAlign = "center";
					ctx.fillStyle = isMidnight ? "rgba(248,250,252,0.96)" : "rgba(226,232,240,0.84)";
					ctx.font = isMidnight ? "600 10px system-ui" : "500 10px system-ui";
					ctx.fillText(formatDisplayClock(tick), x, bottomHourY);
				}
			}

			visiblePoints.forEach((point, index) => {
				const x = scale.getXForTime(point.time);
				const active = timeScrubberState.visibleStartIndex + index === timeScrubberState.selectedIndex;
				const tickHeight = active ? 18 : (index % 5 === 0 ? 10 : 7);
				const pointColor = getTimeScrubberPointColor(point);
				ctx.save();
				ctx.strokeStyle = pointColor;
				ctx.globalAlpha = active ? 0.96 : 0.72;
				ctx.lineWidth = active ? 1.45 : 1.15;
				ctx.beginPath();
				ctx.moveTo(x, baseY - tickHeight);
				ctx.lineTo(x, baseY + (active ? 8 : 5));
				ctx.stroke();
				if (active) {
					ctx.fillStyle = pointColor;
					ctx.beginPath();
					ctx.arc(x, baseY - 16, 5.5, 0, Math.PI * 2);
					ctx.fill();
					ctx.fillStyle = "rgba(248,250,252,0.96)";
					ctx.beginPath();
					ctx.arc(x, baseY - 16, 2.1, 0, Math.PI * 2);
					ctx.fill();
				}
				ctx.restore();
			});

			visiblePins.forEach(pin => {
				const x = scale.getXForTime(pin.time);
				ctx.strokeStyle = "rgba(248,250,252,0.9)";
				ctx.lineWidth = 1.4;
				ctx.beginPath();
				ctx.moveTo(x, baseY - 28);
				ctx.lineTo(x, baseY - 12);
				ctx.stroke();
				ctx.fillStyle = "rgba(255,255,255,0.96)";
				ctx.beginPath();
				ctx.arc(x, baseY - 30, 3.5, 0, Math.PI * 2);
				ctx.fill();
				ctx.fillStyle = "rgba(15,23,42,0.94)";
				ctx.beginPath();
				ctx.arc(x, baseY - 30, 1.4, 0, Math.PI * 2);
				ctx.fill();
			});

			const selectedVisibleIndex = Math.max(0, Math.min(pointCount - 1, timeScrubberState.selectedIndex - timeScrubberState.visibleStartIndex));
			const selectedPoint = visiblePoints[selectedVisibleIndex];
			if (selectedPoint) {
				const x = scale.getXForTime(selectedPoint.time);
				ctx.fillStyle = getTimeScrubberPointColor(selectedPoint);
				ctx.font = "600 11px system-ui";
				ctx.textAlign = "center";
				ctx.fillText(formatDisplayClock(selectedPoint.time, { includeSeconds: true }), x, bottomSelectedY);
			}
		}

		function drawTimeScrubberSegmentCanvas() {
			const canvas = document.getElementById("time-scrubber-segment-canvas");
			if (!canvas) return;
			const width = Math.max(32, canvas.clientWidth || canvas.offsetWidth || 0);
			const height = Math.max(18, canvas.clientHeight || canvas.offsetHeight || 0);
			const dpr = window.devicePixelRatio || 1;
			canvas.width = Math.round(width * dpr);
			canvas.height = Math.round(height * dpr);
			const ctx = canvas.getContext("2d");
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
			ctx.clearRect(0, 0, width, height);
			const maxLanes = 4;
			const insetY = 2;
			const laneGap = 3;
			const laneAreaHeight = Math.max(8, height - insetY * 2);
			const laneHeight = Math.max(4, (laneAreaHeight - laneGap * (maxLanes - 1)) / maxLanes);
			for (let laneIndex = 0; laneIndex < maxLanes; laneIndex += 1) {
				const laneY = insetY + laneIndex * (laneHeight + laneGap);
				ctx.fillStyle = laneIndex % 2 === 0 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.03)";
				ctx.beginPath();
				if (typeof ctx.roundRect === "function") {
					ctx.roundRect(0, laneY, width, laneHeight, 999);
				} else {
					ctx.rect(0, laneY, width, laneHeight);
				}
				ctx.fill();
			}
			const model = buildTimeScrubberSegmentStripModel(width, height, { maxLanes });
			if (!model?.entries?.length) {
				if (width >= 160) {
					ctx.fillStyle = "rgba(226,232,240,0.7)";
					ctx.font = "600 11px system-ui";
					ctx.textAlign = "center";
					ctx.fillText("当前窗口无分段", width / 2, height / 2 + 4);
				}
				return;
			}
			model.entries.forEach(entry => {
				const segment = entry.segment;
				const isHovered = segment.id && segment.id === timeScrubberState.hoveredSegmentId;
				const isSelected = segment.id && segment.id === timeScrubberState.selectedSegmentId;
				const fillAlpha = segment.isDraft ? 0.76 : (segment.renderMode === "cover" ? 0.74 : 0.94);
				const strokeAlpha = isHovered ? 1 : (isSelected ? 0.96 : 0.88);
				const innerWidth = Math.max(0, entry.widthPx - 2);
				const innerHeight = Math.max(0, Math.min(entry.heightPx - 2, Math.max(4, entry.heightPx * 0.48)));
				ctx.save();
				ctx.globalAlpha = fillAlpha;
				ctx.fillStyle = segment.color || "#60a5fa";
				ctx.strokeStyle = isHovered
					? `rgba(255,255,255,${strokeAlpha})`
					: (isSelected ? `rgba(248,250,252,${strokeAlpha})` : "rgba(15,23,42,0.9)");
				ctx.lineWidth = isHovered ? 2.2 : (isSelected ? 1.8 : 1.15);
				ctx.shadowColor = isHovered
					? "rgba(255,255,255,0.38)"
					: (isSelected ? "rgba(148,163,184,0.26)" : "transparent");
				ctx.shadowBlur = isHovered ? 10 : (isSelected ? 6 : 0);
				if (segment.isDraft) ctx.setLineDash([5, 3]);
				ctx.beginPath();
				if (typeof ctx.roundRect === "function") {
					ctx.roundRect(entry.x, entry.y, entry.widthPx, entry.heightPx, 999);
				} else {
					ctx.rect(entry.x, entry.y, entry.widthPx, entry.heightPx);
				}
				ctx.fill();
				ctx.stroke();
				if (innerWidth > 0 && innerHeight > 0) {
					ctx.shadowBlur = 0;
					ctx.globalAlpha = isHovered ? 0.28 : (isSelected ? 0.2 : 0.14);
					ctx.fillStyle = "rgba(255,255,255,1)";
					ctx.beginPath();
					if (typeof ctx.roundRect === "function") {
						ctx.roundRect(entry.x + 1, entry.y + 1, innerWidth, innerHeight, 999);
					} else {
						ctx.rect(entry.x + 1, entry.y + 1, innerWidth, innerHeight);
					}
					ctx.fill();
				}
				ctx.restore();
			});
		}

		function renderTimeScrubberSegmentDetail() {
			const detail = document.getElementById("time-scrubber-segment-detail");
			if (!detail) return;
			if (!timeScrubberState.focusLayers.length || !timeScrubberState.enabled || !timeScrubberState.allPoints.length) {
				detail.textContent = "";
				return;
			}
			const visibleBounds = getCurrentVisibleTimeBounds();
			const visibleSegments = visibleBounds
				? getVisibleTimelineSegmentEntries(visibleBounds.start, visibleBounds.end, { maxLanes: 4 })
				: [];
			const hoveredSegment = getTimelineSegmentById(timeScrubberState.hoveredSegmentId);
			const selectedSegment = getTimelineSegmentById(timeScrubberState.selectedSegmentId);
			const replayLabel = getReplayTimelineSourceLabel();
			if (timeScrubberState.hoveredSegmentId && !hoveredSegment) timeScrubberState.hoveredSegmentId = "";
			if (timeScrubberState.selectedSegmentId && !selectedSegment) timeScrubberState.selectedSegmentId = "";
			const targetSegment = hoveredSegment || selectedSegment;
			const summaryText = visibleSegments.length ? `当前窗口 ${visibleSegments.length} 段` : "当前窗口无分段";
			const replayText = replayLabel ? ` | 回放 ${replayLabel}` : "";
			if (!targetSegment) {
				detail.innerHTML = `
					<span class="time-scrubber-segment-detail-chip" style="background:rgba(148,163,184,0.88)"></span>
					<span class="time-scrubber-segment-detail-title">分段层</span>
					<span class="time-scrubber-segment-detail-text">${escapeHtml(`${summaryText}${replayText} | 悬停或点击下方色块查看`)}</span>
				`;
				return;
			}
			const modeLabel = hoveredSegment ? "悬停分段" : "选中分段";
			detail.innerHTML = `
				<span class="time-scrubber-segment-detail-chip" style="background:${escapeHtml(targetSegment.color || "#60a5fa")}"></span>
				<span class="time-scrubber-segment-detail-title">${escapeHtml(targetSegment.categoryName || "未命名标签")}</span>
				<span class="time-scrubber-segment-detail-text">${escapeHtml(`${modeLabel}${replayText} | ${formatTimeWindow(targetSegment.startTime, targetSegment.endTime)} | ${summaryText}`)}</span>
			`;
		}

		function drawTimeScrubberOverviewCanvas() {
			const canvas = document.getElementById("time-scrubber-overview-canvas");
			const points = timeScrubberState.allPoints || [];
			const width = Math.max(32, canvas.clientWidth || canvas.offsetWidth || 0);
			const height = Math.max(16, canvas.clientHeight || canvas.offsetHeight || 0);
			const dpr = window.devicePixelRatio || 1;
			canvas.width = Math.round(width * dpr);
			canvas.height = Math.round(height * dpr);
			const ctx = canvas.getContext("2d");
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
			ctx.clearRect(0, 0, width, height);
			if (!points.length) return;

			const scale = createTimeScrubberScale(points, width, height);
			const visibleBounds = getCurrentVisibleTimeBounds();
			const activePoint = getActiveTimeScrubberPoint();
			const color = getTimeScrubberPointColor(activePoint || points[0]);
			const centerY = height / 2;
			const marks = sampleEvenly(points, 1200);
			const pins = getActiveTimelinePinsForDisplay();
			const segments = assignTimelineSegmentLanes(getRenderableTimelineSegments({ includeDraft: true }), 2);

			ctx.strokeStyle = "rgba(226,232,240,0.34)";
			ctx.lineWidth = 4;
			ctx.lineCap = "round";
			ctx.beginPath();
			ctx.moveTo(scale.leftPad, centerY);
			ctx.lineTo(width - scale.rightPad, centerY);
			ctx.stroke();

			marks.forEach(point => {
				const x = scale.getXForTime(point.time);
				ctx.save();
				ctx.strokeStyle = getTimeScrubberPointColor(point);
				ctx.globalAlpha = 0.52;
				ctx.lineWidth = 1;
				ctx.beginPath();
				ctx.moveTo(x, centerY - 6);
				ctx.lineTo(x, centerY + 6);
				ctx.stroke();
				ctx.restore();
			});

			segments.forEach(segment => {
				const startX = scale.getXForTime(segment.startTime);
				const endX = scale.getXForTime(segment.endTime);
				const x = Math.min(startX, endX);
				const widthPx = Math.max(6, Math.abs(endX - startX));
				const y = centerY - 8 + segment.laneIndex * 6;
				ctx.save();
				ctx.globalAlpha = segment.isDraft ? 0.52 : 0.34;
				ctx.fillStyle = segment.color || "#60a5fa";
				ctx.beginPath();
				if (typeof ctx.roundRect === "function") {
					ctx.roundRect(x, y, widthPx, 4.2, 999);
				} else {
					ctx.rect(x, y, widthPx, 4.2);
				}
				ctx.fill();
				ctx.restore();
			});

			if (visibleBounds) {
				const startX = scale.getXForTime(visibleBounds.start);
				const endX = scale.getXForTime(visibleBounds.end);
				const rectX = Math.min(startX, endX);
				const rectWidth = Math.max(12, Math.abs(endX - startX));
				ctx.fillStyle = "rgba(255,255,255,0.18)";
				ctx.strokeStyle = "rgba(248,250,252,0.88)";
				ctx.lineWidth = 1.6;
				const rectY = 1.5;
				const rectH = height - 3;
				ctx.beginPath();
				if (typeof ctx.roundRect === "function") {
					ctx.roundRect(rectX, rectY, rectWidth, rectH, 8);
				} else {
					ctx.rect(rectX, rectY, rectWidth, rectH);
				}
				ctx.fill();
				ctx.stroke();

				ctx.strokeStyle = "rgba(248,250,252,0.92)";
				ctx.lineWidth = 2;
				ctx.beginPath();
				ctx.moveTo(rectX + 4, rectY + 4);
				ctx.lineTo(rectX + 4, rectY + rectH - 4);
				ctx.moveTo(rectX + rectWidth - 4, rectY + 4);
				ctx.lineTo(rectX + rectWidth - 4, rectY + rectH - 4);
				ctx.stroke();

				ctx.fillStyle = "rgba(248,250,252,0.98)";
				ctx.beginPath();
				ctx.arc(rectX + 4, centerY, 2.3, 0, Math.PI * 2);
				ctx.arc(rectX + rectWidth - 4, centerY, 2.3, 0, Math.PI * 2);
				ctx.fill();
			}

			if (activePoint) {
				const x = scale.getXForTime(activePoint.time);
				ctx.fillStyle = color;
				ctx.beginPath();
				ctx.arc(x, centerY, 4, 0, Math.PI * 2);
				ctx.fill();
				ctx.fillStyle = "rgba(248,250,252,0.98)";
				ctx.beginPath();
				ctx.arc(x, centerY, 1.6, 0, Math.PI * 2);
				ctx.fill();
			}

			pins.forEach(pin => {
				const x = scale.getXForTime(pin.time);
				ctx.strokeStyle = "rgba(255,255,255,0.9)";
				ctx.lineWidth = 1.2;
				ctx.beginPath();
				ctx.moveTo(x, 2);
				ctx.lineTo(x, height - 2);
				ctx.stroke();
			});
		}

		function renderTimeScrubberControl() {
			const control = document.getElementById("time-scrubber-control");
			const stepPrevBtn = document.getElementById("time-scrubber-step-prev");
			const stepNextBtn = document.getElementById("time-scrubber-step-next");
			const leftBtn = document.getElementById("time-scrubber-left");
			const rightBtn = document.getElementById("time-scrubber-right");
			const zoomOutBtn = document.getElementById("time-scrubber-zoom-out");
			const zoomInBtn = document.getElementById("time-scrubber-zoom-in");
			const overviewCanvas = document.getElementById("time-scrubber-overview-canvas");
			const replayLabel = getReplayTimelineSourceLabel();
			updateDateWindowControl();
			if (!timeScrubberState.focusLayers.length) {
				hideTimeScrubberContextMenu();
				control.classList.add("hidden");
				overviewCanvas.classList.remove("dragging");
				updateTimeScrubberOverviewCursor();
				renderTimeScrubberSegmentDetail();
				clearTimeFocusMarker();
				return;
			}
			control.classList.remove("hidden");
			buildTimeScrubberLayerOptions();
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) {
				hideTimeScrubberContextMenu();
				document.getElementById("time-scrubber-status").textContent = replayLabel
					? `${getLayerLabel(timeScrubberState.selectedLayer)} | 当前日期区间内无可定位时间点 | 回放 ${replayLabel}`
					: `${getLayerLabel(timeScrubberState.selectedLayer)} | 当前日期区间内无可定位时间点`;
				document.getElementById("time-scrubber-range").textContent = replayLabel
					? `日期区间 ${currentTimeWindow.startDay || "--"} -- ${currentTimeWindow.endDay || "--"} | 可切换其他图层继续查看 | 只读回放`
					: `日期区间 ${currentTimeWindow.startDay || "--"} -- ${currentTimeWindow.endDay || "--"} | 可切换其他图层继续查看`;
				stepPrevBtn.disabled = true;
				stepNextBtn.disabled = true;
				leftBtn.disabled = true;
				rightBtn.disabled = true;
				zoomOutBtn.disabled = true;
				zoomInBtn.disabled = true;
				overviewCanvas.classList.remove("dragging");
				updateTimeScrubberOverviewCursor();
				drawTimeScrubberCanvas();
				drawTimeScrubberSegmentCanvas();
				drawTimeScrubberOverviewCanvas();
				renderTimeScrubberSegmentDetail();
				clearTimeFocusMarker();
				return;
			}
			const total = timeScrubberState.allPoints.length;
			const visibleCount = getTimeScrubberVisibleCount(total);
			const startIndex = timeScrubberState.visibleStartIndex;
			const endIndex = Math.min(total - 1, startIndex + visibleCount - 1);
			const selectedPoint = getActiveTimeScrubberPoint();
			const statusText = selectedPoint
				? `${getLayerLabel(timeScrubberState.selectedLayer)} | 当前 ${formatDateTime(selectedPoint.time)} | 第 ${timeScrubberState.selectedIndex + 1} / ${total} 点`
				: `${getLayerLabel(timeScrubberState.selectedLayer)} | 共 ${total} 点`;
			document.getElementById("time-scrubber-status").textContent = replayLabel
				? `${statusText} | 回放 ${replayLabel}`
				: statusText;
			document.getElementById("time-scrubber-range").textContent = segmentDraftState.active
				? `正在标记 ${getAnnotationCategoryLabel(segmentDraftState.categoryId)} | 起点 ${formatDateTime(segmentDraftState.startTime)} | 预览终点 ${formatDateTime(segmentDraftState.previewTime)}`
				: replayLabel
					? `日期区间 ${currentTimeWindow.startDay || "--"} -- ${currentTimeWindow.endDay || "--"} | 当前窗口 ${startIndex + 1}-${endIndex + 1} / ${total} | 只读回放`
					: `日期区间 ${currentTimeWindow.startDay || "--"} -- ${currentTimeWindow.endDay || "--"} | 当前窗口 ${startIndex + 1}-${endIndex + 1} / ${total}`;
			stepPrevBtn.disabled = timeScrubberState.selectedIndex <= 0;
			stepNextBtn.disabled = timeScrubberState.selectedIndex >= total - 1;
			const maxStart = getTimeScrubberMaxStart(total);
			leftBtn.disabled = timeScrubberState.visibleStartIndex <= 0;
			rightBtn.disabled = timeScrubberState.visibleStartIndex >= maxStart;
			const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, total);
			const minVisible = Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxVisible);
			zoomOutBtn.disabled = visibleCount >= maxVisible;
			zoomInBtn.disabled = visibleCount <= minVisible;
			overviewCanvas.classList.toggle("dragging", !!timeScrubberState.isOverviewDragging);
			updateTimeScrubberOverviewCursor();
			drawTimeScrubberCanvas();
			drawTimeScrubberSegmentCanvas();
			drawTimeScrubberOverviewCanvas();
			renderTimeScrubberSegmentDetail();
			updateTimeFocusMarker();
		}

		function setTimeScrubberSelectedIndex(nextIndex, options = {}) {
			const total = timeScrubberState.allPoints.length;
			if (!total) return;
			const previousVisibleStartIndex = timeScrubberState.visibleStartIndex;
			const clampedIndex = Math.max(0, Math.min(total - 1, Math.round(nextIndex || 0)));
			const selectionChanged = clampedIndex !== timeScrubberState.selectedIndex;
			timeScrubberState.selectedIndex = clampedIndex;
			if (selectionChanged && options.followView === true) {
				timeScrubberState.followSelectionOnUpdate = true;
			}
			if (options.keepWindow !== true) ensureTimeScrubberSelectionVisible();
			renderTimeScrubberControl();
			if (timeScrubberState.visibleStartIndex !== previousVisibleStartIndex) {
				scheduleMapDisplayRefreshForTimeScrubber();
			}
		}

		function stepTimeScrubberSelection(direction) {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length || !direction) return false;
			const currentIndex = Math.max(0, Math.min(timeScrubberState.allPoints.length - 1, Math.round(timeScrubberState.selectedIndex || 0)));
			const total = timeScrubberState.allPoints.length;
			const nextIndex = Math.max(0, Math.min(total - 1, currentIndex + (direction > 0 ? 1 : -1)));
			if (nextIndex === currentIndex) return false;
			setTimeScrubberSelectedIndex(nextIndex, { followView: true });
			if (segmentDraftState.active) updateTimelineSegmentDraftFromIndex(timeScrubberState.selectedIndex);
			return true;
		}

		function panTimeScrubberWindow(direction) {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length || !direction) return;
			const total = timeScrubberState.allPoints.length;
			const visibleCount = getTimeScrubberVisibleCount(total);
			const delta = Math.max(1, Math.floor(visibleCount * TIME_SCRUBBER_SHIFT_RATIO)) * (direction > 0 ? 1 : -1);
			setTimeScrubberVisibleStart(timeScrubberState.visibleStartIndex + delta);
		}

		function zoomTimeScrubberWindow(multiplier) {
			const total = timeScrubberState.allPoints.length;
			if (!timeScrubberState.enabled || !total || !Number.isFinite(multiplier) || multiplier <= 0) return;
			const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, total);
			const minVisible = Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxVisible);
			const currentCount = getTimeScrubberVisibleCount(total);
			let nextCount = Math.round(currentCount * multiplier);
			if (nextCount === currentCount) nextCount += multiplier > 1 ? 1 : -1;
			nextCount = Math.max(minVisible, Math.min(maxVisible, nextCount));
			if (nextCount === currentCount) return;
			const centerIndex = Math.max(0, Math.min(total - 1, timeScrubberState.selectedIndex));
			timeScrubberState.visibleCount = nextCount;
			timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(
				centerIndex - Math.floor((nextCount - 1) / 2),
				total
			);
			renderTimeScrubberControl();
			scheduleMapDisplayRefreshForTimeScrubber();
		}

		function handleTimeScrubberWheel(event) {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return;
			event.preventDefault();
			event.stopPropagation();
			setTimeScrubberActive(true);
			const multiplier = event.deltaY > 0 ? (1 + TIME_SCRUBBER_ZOOM_STEP) : (1 - TIME_SCRUBBER_ZOOM_STEP);
			zoomTimeScrubberWindow(multiplier);
		}

		function updateTimeScrubberSelectionFromClientX(clientX) {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return;
			const canvas = document.getElementById("time-scrubber-canvas");
			const rect = canvas.getBoundingClientRect();
			const visiblePoints = getTimeScrubberVisiblePoints();
			if (!visiblePoints.length || rect.width <= 0) return;
			const scale = createTimeScrubberScale(visiblePoints, rect.width, rect.height);
			const targetTime = scale.getTimeForX(clientX - rect.left);
			const visibleIndex = findNearestTimeScrubberPointIndex(visiblePoints, targetTime);
			setTimeScrubberSelectedIndex(timeScrubberState.visibleStartIndex + visibleIndex, { keepWindow: true });
		}

		function setTimeScrubberLayer(nextLayer) {
			const candidates = getTimeScrubberLayerCandidates(currentExistsByLayer);
			if (!candidates.includes(nextLayer)) return;
			const previousTime = getActiveTimeScrubberPoint()?.time ?? null;
			const previousVisibleCount = getTimeScrubberVisibleCount();
			const visibleSlice = getTimeScrubberVisiblePoints();
			let windowStartTime = null;
			let windowEndTime = null;
			if (visibleSlice.length) {
				windowStartTime = visibleSlice[0]?.time ?? null;
				windowEndTime = visibleSlice[visibleSlice.length - 1]?.time ?? null;
			}
			const points = buildTimeScrubberPoints(nextLayer, currentFilteredDataByLayer[nextLayer] || []);
			timeScrubberState.focusLayers = candidates;
			timeScrubberState.selectedLayer = nextLayer;
			timeScrubberState.allPoints = points;
			timeScrubberState.enabled = points.length > 0;
			if (!points.length) {
				timeScrubberState.visibleStartIndex = 0;
				timeScrubberState.visibleCount = 0;
				timeScrubberState.selectedIndex = 0;
				renderTimeScrubberControl();
				return;
			}
			let view = computeTimeScrubberViewAfterLayerSwitch(points, {
				previousSelectedTime: previousTime,
				windowStartTime,
				windowEndTime,
				previousVisibleCount,
			});
			const annBounds = getUnionAnnotationTimeBoundsForViewport();
			if (annBounds) {
				view = expandTimeScrubberViewToCoverAnnotationBounds(points, view, annBounds);
			}
			timeScrubberState.selectedIndex = view.selectedIndex;
			timeScrubberState.visibleCount = view.visibleCount;
			timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(view.visibleStartIndex, points.length);
			renderTimeScrubberControl();
			scheduleMapDisplayRefreshForTimeScrubber();
		}

		function syncTimeScrubberFromCurrentData(options = {}) {
			const candidates = getTimeScrubberLayerCandidates(currentExistsByLayer);
			if (!candidates.length) {
				resetTimeScrubber();
				return;
			}
			const previousLayer = timeScrubberState.selectedLayer;
			const previousTime = options.preserveTime === false ? null : (getActiveTimeScrubberPoint()?.time ?? null);
			const previousVisibleCount = getTimeScrubberVisibleCount();
			let selectedLayer = candidates.includes(previousLayer) ? previousLayer : chooseDefaultTimeScrubberLayer(candidates);
			let points = buildTimeScrubberPoints(selectedLayer, currentFilteredDataByLayer[selectedLayer] || []);
			if (!points.length) {
				for (const candidate of candidates) {
					const nextPoints = buildTimeScrubberPoints(candidate, currentFilteredDataByLayer[candidate] || []);
					if (!nextPoints.length) continue;
					selectedLayer = candidate;
					points = nextPoints;
					break;
				}
			}
			if (!points.length) {
				resetTimeScrubber();
				return;
			}
			timeScrubberState.enabled = true;
			timeScrubberState.focusLayers = candidates;
			timeScrubberState.selectedLayer = selectedLayer;
			timeScrubberState.allPoints = points;
			const shouldDefaultToFullVisible = options.preserveTime === false || options.resetVisibleRange === true;
			const largestSegmentBounds = getLargestCommittedSegmentTimeBounds();
			if (shouldDefaultToFullVisible && largestSegmentBounds) {
				const centerTime = (largestSegmentBounds.start + largestSegmentBounds.end) / 2;
				let view = computeTimeScrubberViewAfterLayerSwitch(points, {
					previousSelectedTime: previousTime != null ? previousTime : centerTime,
					windowStartTime: largestSegmentBounds.start,
					windowEndTime: largestSegmentBounds.end,
					previousVisibleCount: Math.min(TIME_SCRUBBER_MAX_POINTS, Math.max(1, previousVisibleCount || points.length)),
				});
				const annUnion = getUnionAnnotationTimeBoundsForViewport();
				if (annUnion) {
					view = expandTimeScrubberViewToCoverAnnotationBounds(points, view, annUnion);
				}
				timeScrubberState.selectedIndex = view.selectedIndex;
				timeScrubberState.visibleCount = view.visibleCount;
				timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(view.visibleStartIndex, points.length);
			} else {
				timeScrubberState.visibleCount = shouldDefaultToFullVisible
					? points.length
					: Math.min(TIME_SCRUBBER_MAX_POINTS, Math.max(1, previousVisibleCount || points.length));
				timeScrubberState.selectedIndex = previousTime != null ? findNearestTimeScrubberPointIndex(points, previousTime) : 0;
				timeScrubberState.visibleStartIndex = clampTimeScrubberVisibleStart(
					timeScrubberState.selectedIndex - Math.floor(getTimeScrubberVisibleCount(points.length) * 0.5),
					points.length
				);
			}
			renderTimeScrubberControl();
		}

		function formatDuration(seconds) {
			const totalSeconds = Math.max(0, Math.round(parseNumericValue(seconds) || 0));
			const hours = Math.floor(totalSeconds / 3600);
			const minutes = Math.floor((totalSeconds % 3600) / 60);
			const secs = totalSeconds % 60;
			if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
			if (minutes > 0) return `${minutes}m ${String(secs).padStart(2, "0")}s`;
			return `${secs}s`;
		}

		function formatTimeWindow(startValue, endValue) {
			const start = parseNumericValue(startValue);
			const end = parseNumericValue(endValue);
			if (start == null && end == null) return "时间未知";
			if (start != null && end != null) {
				return `${formatTime(start)}-${formatTime(end)} | 停留 ${formatDuration(end - start)}`;
			}
			const single = start != null ? start : end;
			return `${formatTime(single)} | 停留未知`;
		}

		function getRowStationId(row) {
			const cid = row.cid ?? row.CID;
			const text = String(cid ?? "").trim();
			return text && text !== "-1" ? text : "";
		}

		function getRowTimeValue(row) {
			return getRowStartTimeValue(row);
		}

		function isRenderableCoordinate(lat, lon) {
			if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
			if (Math.abs(lat + 1) < 1e-9 || Math.abs(lon + 1) < 1e-9) return false;
			if (lat <= 0 || lon <= 0) return false;
			return true;
		}

		function getRowCoordinate(row) {
			const lat = parseNumericValue(row?.latitude ?? row?.start_latitude ?? row?.lat);
			const lon = parseNumericValue(row?.longitude ?? row?.start_longitude ?? row?.lng ?? row?.lon);
			if (lat == null || lon == null || !isRenderableCoordinate(lat, lon)) return null;
			return { lat, lon };
		}

		function sampleEvenly(items, maxCount) {
			if (!Array.isArray(items)) return [];
			if (!Number.isFinite(maxCount) || maxCount <= 0 || items.length <= maxCount) return [...items];
			if (maxCount === 1) return [items[0]];
			const result = [];
			const lastIndex = items.length - 1;
			for (let i = 0; i < maxCount; i += 1) {
				const rawIndex = Math.round((i * lastIndex) / (maxCount - 1));
				if (result[result.length - 1] !== items[rawIndex]) result.push(items[rawIndex]);
			}
			return result;
		}

		function isOdLayer(layerKey) {
			const cfg = layerConfig[layerKey] || {};
			const normalizedKind = String(cfg.kind || "").trim().toLowerCase();
			return !!cfg.isOD || normalizedKind === "od" || layerKey === "od";
		}

		function getLayerRenderProfile(layerKey, rowCount) {
			const cfg = layerConfig[layerKey] || {};
			const zoom = getCurrentRenderZoomBucket();
			const profile = {
				maxPolylinePoints: Number.POSITIVE_INFINITY,
				maxBuckets: Number.POSITIVE_INFINITY,
				maxArrows: 0,
				maxTooltipBuckets: Number.POSITIVE_INFINITY,
				gridStep: 0,
				maxBucketEntries: MAX_BUCKET_DETAIL_ROWS,
			};
			if (!rowCount) return profile;

			if (cfg.lineOnly) {
				profile.maxPolylinePoints = zoom >= 15 ? 3200 : zoom >= 13 ? 1800 : zoom >= 11 ? 1100 : 700;
				profile.maxArrows = zoom >= 15 ? 80 : zoom >= 13 ? 56 : zoom >= 11 ? 32 : 20;
				return profile;
			}
			if (isOdLayer(layerKey)) {
				profile.maxBuckets = zoom >= 15 ? 240 : zoom >= 13 ? 160 : 100;
				return profile;
			}
			if (cfg.kind === "stations") {
				profile.maxBuckets = zoom >= 15 ? 180 : zoom >= 13 ? 120 : 80;
				profile.maxTooltipBuckets = zoom >= 15 ? 48 : 28;
				return profile;
			}

			const isRawLike = layerKey === "raw" || cfg.kind === "signal";
			const isMatchedLike = layerKey === "fmm" || cfg.kind === "gps";
			profile.maxPolylinePoints = zoom >= 15 ? 5200 : zoom >= 13 ? 2600 : zoom >= 11 ? 1400 : 800;
			profile.maxBuckets = zoom >= 15 ? 1200 : zoom >= 13 ? 520 : zoom >= 11 ? 240 : 120;
			profile.maxArrows = cfg.hasLine ? (zoom >= 15 ? 64 : zoom >= 13 ? 32 : zoom >= 11 ? 18 : 10) : 0;
			profile.maxTooltipBuckets = zoom >= 15 ? 72 : zoom >= 13 ? 36 : zoom >= 11 ? 18 : 8;

			if (isRawLike) {
				profile.maxPolylinePoints = zoom >= 15 ? 2600 : zoom >= 13 ? 1200 : zoom >= 11 ? 700 : 400;
				profile.maxBuckets = zoom >= 15 ? 600 : zoom >= 13 ? 260 : zoom >= 11 ? 120 : 60;
				profile.maxArrows = cfg.hasLine ? (zoom >= 15 ? 28 : zoom >= 13 ? 14 : zoom >= 11 ? 8 : 0) : 0;
				profile.maxTooltipBuckets = zoom >= 15 ? 36 : zoom >= 13 ? 18 : zoom >= 11 ? 10 : 4;
			} else if (isMatchedLike) {
				profile.maxPolylinePoints = zoom >= 15 ? 7000 : zoom >= 13 ? 3600 : zoom >= 11 ? 1800 : 1000;
				profile.maxBuckets = zoom >= 15 ? 1500 : zoom >= 13 ? 760 : zoom >= 11 ? 340 : 160;
				profile.maxArrows = cfg.hasLine ? (zoom >= 15 ? 72 : zoom >= 13 ? 40 : zoom >= 11 ? 24 : 12) : 0;
				profile.maxTooltipBuckets = zoom >= 15 ? 84 : zoom >= 13 ? 40 : zoom >= 11 ? 20 : 10;
			}

			if (rowCount > profile.maxBuckets && Number.isFinite(profile.maxBuckets) && profile.maxBuckets > 0) {
				const densityRatio = rowCount / profile.maxBuckets;
				const baseStep = zoom >= 15 ? 0.00008 : zoom >= 13 ? 0.00018 : zoom >= 11 ? 0.00045 : 0.0011;
				profile.gridStep = baseStep * Math.min(10, Math.sqrt(densityRatio));
			}
			return profile;
		}

		function getLayerLabelKey(layerKey, row, index, lat, lon) {
			const baseCoord = `${lat.toFixed(6)}|${lon.toFixed(6)}`;
			if (layerKey === "raw" || layerKey === "snap" || (layerConfig[layerKey] || {}).kind === "signal") {
				return baseCoord;
			}
			if ((layerConfig[layerKey] || {}).kind === "stations") return baseCoord;
			return `${baseCoord}|${index}`;
		}

		function supportsInlineLabels(layerKey) {
			const cfg = layerConfig[layerKey] || {};
			return !cfg.lineOnly;
		}

		function buildLayerEntryText(layerKey, row, index) {
			const cfg = layerConfig[layerKey] || {};
			if (cfg.kind === "stations") {
				const cid = getRowStationId(row);
				return `CID ${cid || String(index + 1)}`;
			}
			if (cfg.kind === "gps") {
				const status = normalizeStateValue(row.status) || "-";
				return `${status} | ${formatTime(row.timestamp_ms)}`;
			}
			if (cfg.kind === "signal") {
				const cid = getRowStationId(row);
				return `CID ${cid || "-"} | ${formatTimeWindow(getRowStartTimeValue(row), getRowEndTimeValue(row))}`;
			}
			if (isOdLayer(layerKey)) {
				const isStay = row.is_stationary === true || String(row.is_stationary).toLowerCase() === "true";
				return `${isStay ? "stay" : "move"} | ${formatTimeWindow(getRowStartTimeValue(row), getRowEndTimeValue(row))}`;
			}
			if (layerKey === "raw" || layerKey === "snap") {
				const cid = getRowStationId(row);
				return `CID ${cid || "-"} | ${formatTimeWindow(getRowStartTimeValue(row), getRowEndTimeValue(row))}`;
			}
			const matchType = row.match_type ? `${layerKey}:${row.match_type}` : layerKey;
			return `${matchType} | ${formatTimeWindow(getRowStartTimeValue(row), getRowEndTimeValue(row))}`;
		}

		function buildLayerHeaderText(layerKey, bucket) {
			const label = getLayerLabel(layerKey);
			if (layerKey === "raw" || layerKey === "snap" || (layerConfig[layerKey] || {}).kind === "signal") {
				const stationIds = [...new Set(bucket.rows.map(getRowStationId).filter(Boolean))];
				const stationText = stationIds.length ? ` | 基站 ${stationIds.join(", ")}` : "";
				return `${label}${stationText} | ${bucket.rows.length} 条`;
			}
			if ((layerConfig[layerKey] || {}).kind === "stations") {
				const stationIds = [...new Set(bucket.rows.map(getRowStationId).filter(Boolean))];
				return `${label} | ${stationIds.join(", ") || bucket.rows.length}`;
			}
			return `${label} | ${bucket.rows.length} 条`;
		}

		function buildBucketHtml(layerKey, bucket, options = {}) {
			const maxEntries = options.maxEntries ?? MAX_BUCKET_DETAIL_ROWS;
			const rows = bucket.rows.slice(0, Math.max(1, maxEntries));
			const headerHtml = `<div class="time-label-header">${escapeHtml(buildLayerHeaderText(layerKey, bucket))}</div>`;
			const entriesHtml = rows.map((row, index) => `
				<div class="time-label-entry">${escapeHtml(String(index + 1))}. ${escapeHtml(buildLayerEntryText(layerKey, row, index))}</div>
			`).join("");
			const hiddenCount = Math.max(0, bucket.rows.length - rows.length);
			const hiddenHtml = hiddenCount > 0
				? `<div class="time-label-entry">... 其余 ${escapeHtml(String(hiddenCount))} 条已折叠</div>`
				: "";
			return `${headerHtml}${entriesHtml}${hiddenHtml}`;
		}

		function buildBucketTooltipHtml(layerKey, bucket) {
			return buildBucketHtml(layerKey, bucket, { maxEntries: 4 });
		}

		function groupRowsIntoBuckets(layerKey, data, latCol, lonCol, profile = null) {
			const renderProfile = profile || getLayerRenderProfile(layerKey, data?.length || 0);
			const buckets = new Map();
			data.forEach((row, index) => {
				const lat = parseFloat(row[latCol]);
				const lon = parseFloat(row[lonCol]);
				if (Number.isNaN(lat) || Number.isNaN(lon)) return;
				const bucketKey = renderProfile.gridStep > 0
					? `${Math.round(lat / renderProfile.gridStep)}|${Math.round(lon / renderProfile.gridStep)}`
					: getLayerLabelKey(layerKey, row, index, lat, lon);
				if (!buckets.has(bucketKey)) {
					buckets.set(bucketKey, { key: bucketKey, lat, lon, rows: [], firstRow: row });
				}
				buckets.get(bucketKey).rows.push(row);
			});
			for (const bucket of buckets.values()) {
				bucket.rows.sort((a, b) => {
					const aStart = getRowTimeValue(a);
					const bStart = getRowTimeValue(b);
					return (aStart ?? 0) - (bStart ?? 0);
				});
				bucket.firstRow = bucket.rows[0];
			}
			let result = [...buckets.values()];
			if (Number.isFinite(renderProfile.maxBuckets) && result.length > renderProfile.maxBuckets) {
				result = sampleEvenly(result, renderProfile.maxBuckets);
			}
			return result;
		}

		function attachMarkerContent(marker, layerKey, bucket, contentHtml, options = {}) {
			const popupHtml = contentHtml || buildBucketHtml(layerKey, bucket);
			marker.__studioLayerKey = layerKey;
			marker.__studioBucket = bucket;
			marker.bindPopup(popupHtml, { maxWidth: 320 });
			if (options.syncTimeScrubber !== false) {
				marker.on("click", () => {
					alignTimeScrubberToBucket(layerKey, bucket, { keepWindow: false, followView: false });
				});
			}
			if (layerStyles[layerKey]?.showLabels && options.allowTooltip !== false) {
				marker.bindTooltip(buildBucketTooltipHtml(layerKey, bucket), {
					permanent: true,
					direction: "top",
					className: "time-label-tooltip",
					offset: [0, -6],
					opacity: 0.88,
				});
			}
		}

		function getPointColor(layerKey, row) {
			const cfg = layerConfig[layerKey] || {};
			if (cfg.kind === "gps") {
				const status = normalizeStateValue(row.status);
				return statusPointStyles[status]?.color || layerStyles[layerKey]?.color || cfg.defaultColor;
			}
			if (layerKey !== "fmm" && layerKey !== "line") return layerStyles[layerKey]?.color || cfg.defaultColor;
			const mt = normalizeStateValue(row.match_type, "unmatch");
			return statusPointStyles[mt]?.color || layerStyles[layerKey]?.color || cfg.defaultColor;
		}

		function getPointSize(layerKey, row) {
			const cfg = layerConfig[layerKey] || {};
			if (cfg.kind === "stations") return cfg.pointRadius || 4;
			if (cfg.kind === "gps") {
				const status = normalizeStateValue(row.status);
				return statusPointStyles[status]?.size || 4;
			}
			if (layerKey === "raw") return 3;
			if (layerKey === "snap") return 2;
			if (isOdLayer(layerKey)) return cfg.pointRadius || 4;
			const mt = normalizeStateValue(row.match_type, "unmatch");
			return statusPointStyles[mt]?.size || 5;
		}

		const ARROW_INTERVAL = 5;
		function addSegmentArrows(coords, color, opacity, targetGroup, maxArrows = 0) {
			if (!Array.isArray(coords) || coords.length < 2 || maxArrows <= 0) return 0;
			const interval = Math.max(ARROW_INTERVAL, Math.ceil((coords.length - 1) / maxArrows));
			let added = 0;
			for (let i = 0; i < coords.length - 1; i += interval) {
				const a = coords[i];
				const b = coords[i + 1];
				if (!a || !b) continue;
				const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
				const dlat = b[0] - a[0];
				const dlon = b[1] - a[1];
				const angle = Math.atan2(dlon, dlat) * 180 / Math.PI - 90;
				const icon = L.divIcon({
					className: "seg-arrow",
					html: `<div style="transform: rotate(${angle}deg); color:${color}; opacity:${opacity};">▶</div>`,
					iconSize: [10, 10],
					iconAnchor: [5, 5]
				});
				L.marker(mid, { icon, interactive: false }).addTo(targetGroup);
				added += 1;
			}
			return added;
		}

		function sampleCoordinates(coords, maxPoints) {
			if (!Array.isArray(coords)) return [];
			return sampleEvenly(coords, maxPoints);
		}

		function pickTooltipBucketKeys(buckets, maxTooltipBuckets) {
			if (!Array.isArray(buckets) || !buckets.length) return new Set();
			if (!Number.isFinite(maxTooltipBuckets) || maxTooltipBuckets <= 0) return new Set();
			return new Set(sampleEvenly(buckets, maxTooltipBuckets).map(bucket => bucket.key));
		}

		function buildTrackEditMarkerIcon(layerKey, row, pointId) {
			const pointColor = getPointColor(layerKey, row);
			const markerSize = Math.max(12, (getPointSize(layerKey, row) * 2) + 4);
			const classNames = ["track-edit-marker"];
			if (trackEditState.selectedPointIds.includes(pointId)) classNames.push("selected");
			if (trackEditState.anchorPointId === pointId) classNames.push("anchor");
			if (trackEditState.selectedPointIds.length > 1 && trackEditState.selectedPointIds.includes(pointId)) {
				classNames.push("multi");
			}
			return L.divIcon({
				className: "track-edit-marker-wrap",
				html: `<div class="${classNames.join(" ")}" style="--track-edit-color:${escapeHtml(pointColor)};--track-edit-size:${markerSize}px"></div>`,
				iconSize: [markerSize, markerSize],
				iconAnchor: [markerSize / 2, markerSize / 2],
			});
		}

		function bindTrackEditMarkerEvents(marker, pointRef) {
			marker.__studioPointId = pointRef.pointId;
			marker.__studioTrackPointRef = pointRef;
			marker.on("click", (event) => {
				if (!trackEditState.enabled || Date.now() < (trackEditState.dragSuppressClickUntil || 0)) return;
				const originalEvent = event?.originalEvent || {};
				selectTrackEditPoint(pointRef.pointId, {
					toggle: !!(originalEvent.ctrlKey || originalEvent.metaKey),
					range: !!originalEvent.shiftKey,
				});
			});
			marker.on("contextmenu", (event) => {
				if (!trackEditState.enabled) return;
				const originalEvent = event?.originalEvent || {};
				originalEvent.preventDefault?.();
				originalEvent.stopPropagation?.();
				if (!trackEditState.selectedPointIds.includes(pointRef.pointId)) {
					selectTrackEditPoint(pointRef.pointId, { syncTimeScrubber: false });
				}
				openTrackEditContextMenu(
					originalEvent.clientX || 0,
					originalEvent.clientY || 0,
					pointRef.pointId,
				);
			});
			marker.on("dragstart", () => beginTrackEditMarkerDrag(pointRef.pointId, marker));
			marker.on("drag", () => updateTrackEditMarkerDrag(pointRef.pointId, marker));
			marker.on("dragend", () => commitTrackEditMarkerDrag(pointRef.pointId, marker));
		}

		function renderEditableTrackLayer(layerKey, data, targetGroup, renderStats, options = {}) {
			const cfg = layerConfig[layerKey] || {};
			const style = layerStyles[layerKey] || {};
			const trackEditMarkersById = options.trackEditMarkersById || {};
			const rows = data || [];
			if (!rows.length) return renderStats;
			const rowsBySegment = {};
			const orderedRows = [];
			rows.forEach((row, rowIndex) => {
				const pointRef = buildTrackPointReference(currentUid, layerKey, row, rowIndex);
				if (!pointRef) return;
				orderedRows.push({ row, pointRef });
				if (cfg.lineOnly && (row.segment_idx != null || row.point_order != null)) {
					const segmentKey = row.segment_idx != null ? row.segment_idx : 0;
					(rowsBySegment[segmentKey] ||= []).push(row);
				}
			});

			if (cfg.lineOnly && Object.keys(rowsBySegment).length) {
				Object.values(rowsBySegment).forEach((segmentRows) => {
					segmentRows.sort((a, b) => (Number(a.point_order || 0) - Number(b.point_order || 0)));
					const coords = segmentRows
						.map((row) => {
							const coord = getRowCoordinate(row);
							return coord ? toGcj(coord.lat, coord.lon) : null;
						})
						.filter(Boolean);
					renderStats.polylinePoints += coords.length;
					if (coords.length >= 2) {
						L.polyline(coords, { color: style.color, weight: 3, opacity: style.opacity }).addTo(targetGroup);
						renderStats.arrowCount += addSegmentArrows(coords, style.color, style.opacity, targetGroup, coords.length);
					}
				});
			} else if (cfg.hasLine) {
				const coords = orderedRows
					.map(({ row }) => {
						const coord = getRowCoordinate(row);
						return coord ? toGcj(coord.lat, coord.lon) : null;
					})
					.filter(Boolean);
				renderStats.polylinePoints = coords.length;
				if (coords.length >= 2) {
					L.polyline(coords, {
						color: style.color,
						weight: cfg.kind === "gps" ? 2 : 2,
						opacity: style.opacity,
						dashArray: cfg.dashArray || undefined,
					}).addTo(targetGroup);
					renderStats.arrowCount += addSegmentArrows(coords, style.color, style.opacity, targetGroup, coords.length);
				}
			}

			orderedRows.forEach(({ row, pointRef }) => {
				const coord = getRowCoordinate(row);
				if (!coord) return;
				const [displayLat, displayLon] = toGcj(coord.lat, coord.lon);
				const bucket = { key: pointRef.pointId, rows: [row], firstRow: row, lat: coord.lat, lon: coord.lon };
				const marker = L.marker([displayLat, displayLon], {
					icon: buildTrackEditMarkerIcon(layerKey, row, pointRef.pointId),
					draggable: !!trackEditState.enabled,
					keyboard: false,
					zIndexOffset: trackEditState.selectedPointIds.includes(pointRef.pointId) ? 900 : 0,
				}).addTo(targetGroup);
				marker.__studioLayerKey = layerKey;
				marker.__studioBucket = bucket;
				bindTrackEditMarkerEvents(marker, pointRef);
				trackEditMarkersById[pointRef.pointId] = marker;
				renderStats.markerBuckets += 1;
			});
			renderStats.reduced = false;
			return renderStats;
		}

		function renderOneLayer(layerKey, data, targetGroup, options = {}) {
			const cfg = layerConfig[layerKey];
			const style = layerStyles[layerKey];
			const profile = getLayerRenderProfile(layerKey, data?.length || 0);
			const renderStats = {
				layerKey,
				totalRows: data?.length || 0,
				polylinePoints: 0,
				markerBuckets: 0,
				arrowCount: 0,
				reduced: false,
			};
			if (!data || !data.length || !style || !style.visible) return renderStats;
			if (trackEditState.enabled && isTrackEditLayerEditable(layerKey)) {
				return renderEditableTrackLayer(layerKey, data, targetGroup, renderStats, options);
			}

			if (isOdLayer(layerKey)) {
				const rows = sampleEvenly(data, profile.maxBuckets);
				renderStats.markerBuckets = rows.length;
				renderStats.reduced = rows.length < data.length;
				for (const row of rows) {
					const slat = parseFloat(row.start_latitude);
					const slon = parseFloat(row.start_longitude);
					const elat = parseFloat(row.end_latitude);
					const elon = parseFloat(row.end_longitude);
					if (Number.isNaN(slat) || Number.isNaN(slon)) continue;
					const [gslat, gslon] = toGcj(slat, slon);
					const isStay = row.is_stationary === true || String(row.is_stationary).toLowerCase() === "true";
					const c = isStay ? "#795548" : "#f44336";
					const startMarker = L.circleMarker([gslat, gslon], {
						radius: getPointSize(layerKey, row), color: c, fillColor: c, fillOpacity: style.opacity, weight: 1
					}).addTo(targetGroup);
					attachMarkerContent(startMarker, layerKey, { rows: [row], firstRow: row }, buildBucketHtml(layerKey, { rows: [row] }));
					if (!Number.isNaN(elat) && !Number.isNaN(elon)) {
						const [gelat, gelon] = toGcj(elat, elon);
						const endMarker = L.circleMarker([gelat, gelon], {
							radius: getPointSize(layerKey, row), color: c, fillColor: c, fillOpacity: style.opacity, weight: 1
						}).addTo(targetGroup);
						attachMarkerContent(endMarker, layerKey, { rows: [row], firstRow: row }, buildBucketHtml(layerKey, { rows: [row] }));
					}
				}
				return renderStats;
			}

			if (cfg.kind === "stations") {
				const stationLatCol = data[0].latitude != null ? "latitude" : data[0].lat != null ? "lat" : "start_latitude";
				const stationLonCol = data[0].longitude != null ? "longitude" : data[0].lon != null ? "lon" : "start_longitude";
				const stationBuckets = groupRowsIntoBuckets(layerKey, data, stationLatCol, stationLonCol, profile);
				const tooltipKeys = pickTooltipBucketKeys(stationBuckets, profile.maxTooltipBuckets);
				renderStats.markerBuckets = stationBuckets.length;
				renderStats.reduced = stationBuckets.length < data.length;
				stationBuckets.forEach(bucket => {
					const [ga, go] = toGcj(bucket.lat, bucket.lon);
					const marker = L.circleMarker([ga, go], {
						radius: getPointSize(layerKey, bucket.firstRow),
						color: style.color,
						fillColor: style.color,
						fillOpacity: style.opacity,
						weight: 1,
					}).addTo(targetGroup);
					attachMarkerContent(marker, layerKey, bucket, buildBucketHtml(layerKey, bucket), { allowTooltip: tooltipKeys.has(bucket.key) });
				});
				return renderStats;
			}

			if (cfg.lineOnly && (data[0].segment_idx != null || data[0].point_order != null)) {
				const bySeg = {};
				data.forEach(row => {
					const seg = row.segment_idx != null ? row.segment_idx : 0;
					if (!bySeg[seg]) bySeg[seg] = [];
					bySeg[seg].push(row);
				});
				Object.values(bySeg).forEach(pts => {
					pts.sort((a, b) => (Number(a.point_order || 0) - Number(b.point_order || 0)));
					const coords = sampleCoordinates(pts.map(p => {
						const coord = getRowCoordinate(p);
						if (!coord) return null;
						return toGcj(coord.lat, coord.lon);
					}).filter(Boolean), profile.maxPolylinePoints);
					renderStats.polylinePoints += coords.length;
					if (coords.length >= 2) {
						L.polyline(coords, { color: style.color, weight: 3, opacity: style.opacity }).addTo(targetGroup);
						renderStats.arrowCount += addSegmentArrows(coords, style.color, style.opacity, targetGroup, profile.maxArrows);
					}
				});
				renderStats.reduced = renderStats.polylinePoints < data.length;
				return renderStats;
			}

			if (cfg.kind === "gps") {
				const coords = [];
				data.forEach(row => {
					const coord = getRowCoordinate(row);
					if (!coord) return;
					coords.push(toGcj(coord.lat, coord.lon));
				});
				const sampledCoords = sampleCoordinates(coords, profile.maxPolylinePoints);
				renderStats.polylinePoints = sampledCoords.length;
				if (cfg.hasLine && sampledCoords.length >= 2) {
					L.polyline(sampledCoords, {
						color: style.color, weight: 2, opacity: style.opacity, dashArray: cfg.dashArray || undefined
					}).addTo(targetGroup);
					renderStats.arrowCount += addSegmentArrows(sampledCoords, style.color, style.opacity, targetGroup, profile.maxArrows);
				}
				const gpsLatCol = data[0].latitude != null ? "latitude" : data[0].lat != null ? "lat" : "start_latitude";
				const gpsLonCol = data[0].longitude != null ? "longitude" : data[0].lon != null ? "lon" : "start_longitude";
				const gpsBuckets = groupRowsIntoBuckets(layerKey, data, gpsLatCol, gpsLonCol, profile);
				const tooltipKeys = pickTooltipBucketKeys(gpsBuckets, profile.maxTooltipBuckets);
				renderStats.markerBuckets = gpsBuckets.length;
				gpsBuckets.forEach(bucket => {
					const row = bucket.firstRow;
					const [ga, go] = toGcj(bucket.lat, bucket.lon);
					const color = getPointColor(layerKey, row);
					const marker = L.circleMarker([ga, go], {
						radius: getPointSize(layerKey, row), color, fillColor: color, fillOpacity: style.opacity, weight: 1
					}).addTo(targetGroup);
					attachMarkerContent(marker, layerKey, bucket, buildBucketHtml(layerKey, bucket), { allowTooltip: tooltipKeys.has(bucket.key) });
				});
				renderStats.reduced = sampledCoords.length < coords.length || gpsBuckets.length < data.length;
				return renderStats;
			}

			if (cfg.kind === "signal") {
				const coords = [];
				data.forEach(row => {
					const coord = getRowCoordinate(row);
					if (!coord) return;
					coords.push(toGcj(coord.lat, coord.lon));
				});
				const sampledCoords = sampleCoordinates(coords, profile.maxPolylinePoints);
				renderStats.polylinePoints = sampledCoords.length;
				if (cfg.hasLine && sampledCoords.length >= 2) {
					L.polyline(sampledCoords, {
						color: style.color, weight: 2, opacity: style.opacity, dashArray: cfg.dashArray || undefined
					}).addTo(targetGroup);
					renderStats.arrowCount += addSegmentArrows(sampledCoords, style.color, style.opacity, targetGroup, profile.maxArrows);
				}
				const signalLatCol = data[0].latitude != null ? "latitude" : data[0].lat != null ? "lat" : "start_latitude";
				const signalLonCol = data[0].longitude != null ? "longitude" : data[0].lon != null ? "lon" : "start_longitude";
				const signalBuckets = groupRowsIntoBuckets(layerKey, data, signalLatCol, signalLonCol, profile);
				const tooltipKeys = pickTooltipBucketKeys(signalBuckets, profile.maxTooltipBuckets);
				renderStats.markerBuckets = signalBuckets.length;
				signalBuckets.forEach(bucket => {
					const [ga, go] = toGcj(bucket.lat, bucket.lon);
					const marker = L.circleMarker([ga, go], {
						radius: 3, color: style.color, fillColor: style.color, fillOpacity: style.opacity, weight: 1
					}).addTo(targetGroup);
					attachMarkerContent(marker, layerKey, bucket, buildBucketHtml(layerKey, bucket), { allowTooltip: tooltipKeys.has(bucket.key) });
				});
				renderStats.reduced = sampledCoords.length < coords.length || signalBuckets.length < data.length;
				return renderStats;
			}

			const latCol = data[0].latitude != null ? "latitude" : data[0].lat != null ? "lat" : "start_latitude";
			const lonCol = data[0].longitude != null ? "longitude" : data[0].lon != null ? "lon" : "start_longitude";
			const coords = [];
			data.forEach(row => {
				const la = parseFloat(row[latCol]);
				const lo = parseFloat(row[lonCol]);
				if (!isRenderableCoordinate(la, lo)) return;
				coords.push(toGcj(la, lo));
			});
			const sampledCoords = sampleCoordinates(coords, profile.maxPolylinePoints);
			renderStats.polylinePoints = sampledCoords.length;
			if (cfg.hasLine && sampledCoords.length >= 2) {
				L.polyline(sampledCoords, {
					color: style.color, weight: 2, opacity: style.opacity, dashArray: cfg.dashArray || undefined
				}).addTo(targetGroup);
				renderStats.arrowCount += addSegmentArrows(sampledCoords, style.color, style.opacity, targetGroup, profile.maxArrows);
			}
			const pointBuckets = groupRowsIntoBuckets(layerKey, data, latCol, lonCol, profile);
			const tooltipKeys = pickTooltipBucketKeys(pointBuckets, profile.maxTooltipBuckets);
			renderStats.markerBuckets = pointBuckets.length;
			pointBuckets.forEach(bucket => {
				const row = bucket.firstRow;
				const [ga, go] = toGcj(bucket.lat, bucket.lon);
				const color = getPointColor(layerKey, row);
				const marker = L.circleMarker([ga, go], {
					radius: getPointSize(layerKey, row), color, fillColor: color, fillOpacity: style.opacity, weight: 1
				}).addTo(targetGroup);
				attachMarkerContent(marker, layerKey, bucket, buildBucketHtml(layerKey, bucket), { allowTooltip: tooltipKeys.has(bucket.key) });
			});
			renderStats.reduced = sampledCoords.length < coords.length || pointBuckets.length < data.length;
			return renderStats;
		}

		function getBoundsFromGroup(group) {
			const points = [];
			group.eachLayer(layer => {
				if (layer.getLatLng) points.push(layer.getLatLng());
				if (layer.getLatLngs) {
					const latlngs = layer.getLatLngs().flat(3);
					latlngs.forEach(item => {
						if (item && typeof item.lat === "number" && typeof item.lng === "number") points.push(item);
					});
				}
			});
			if (!points.length) return null;
			return L.latLngBounds(points);
		}

		function buildLayerStatusText(uid, exists, renderStatsList = []) {
			const windowLabel = currentTimeWindow.enabled
				? ` | 窗口 ${currentTimeWindow.startDay} -- ${currentTimeWindow.endDay}`
				: "";
			const displayBounds = getCurrentMapDisplayTimeBounds();
			const displayLabel = displayBounds
				? ` | 地图显示 ${formatDateTime(displayBounds.start)} -- ${formatDateTime(displayBounds.end)}`
				: "";
			const reducedLayers = (renderStatsList || []).filter(item => item?.reduced).map(item => getLayerLabel(item.layerKey));
			const perfLabel = reducedLayers.length ? ` | 轻量渲染: ${reducedLayers.join(", ")}` : "";
			return `UID ${uid}，检测到: ${Object.keys(exists).filter(k => exists[k]).map(getLayerLabel).join(", ") || "无"}${windowLabel}${displayLabel}${perfLabel}`;
		}

		function renderMapDisplayFromCurrentState(options = {}) {
			if (!currentUid || !map) return null;
			const exists = options.exists || currentExistsByLayer || {};
			const toLoad = layerOrder.filter(layer => exists[layer]);
			const displayDataByLayer = options.dataByLayer || getCurrentMapDisplayDataByLayer(currentFilteredDataByLayer);
			const signature = `${getRenderSignature()}::${getTimeWindowSignature()}::${getCurrentMapDisplaySignature()}`;
			const cacheKey = `${currentUid}::${signature}`;
			let cached = renderedCache.get(cacheKey);

			if (!cached) {
				const group = L.layerGroup();
				const renderStatsList = [];
				const trackEditMarkersById = {};
				for (const layer of toLoad) {
					renderStatsList.push(renderOneLayer(layer, displayDataByLayer[layer], group, { trackEditMarkersById }));
				}
				const bounds = getBoundsFromGroup(group);
				cached = { group, bounds, renderStatsList, trackEditMarkersById };
				putRenderedCache(cacheKey, cached);
			}

			clearActiveGroup();
			activeGroup = cached.group;
			trackEditState.renderedMarkersByPointId = cached.trackEditMarkersById || {};
			activeGroup.addTo(map);
			if (cached.bounds && options.forceFit) map.fitBounds(cached.bounds, { padding: [20, 20] });
			lastAppliedMapDisplaySignature = cacheKey;
			document.getElementById("layer-status").textContent = buildLayerStatusText(currentUid, exists, cached.renderStatsList);
			return cached;
		}

		function scheduleMapDisplayRefreshForTimeScrubber(options = {}) {
			if (!currentUid || !map || !Object.keys(currentExistsByLayer || {}).length) return;
			const nextSignature = `${currentUid}::${getRenderSignature()}::${getTimeWindowSignature()}::${getCurrentMapDisplaySignature()}`;
			const forceFit = !!options.forceFit;
			if (!forceFit && nextSignature === lastAppliedMapDisplaySignature) return;
			scheduledMapDisplayRefreshForceFit = scheduledMapDisplayRefreshForceFit || forceFit;
			if (scheduledMapDisplayRefreshFrame) return;
			scheduledMapDisplayRefreshFrame = requestAnimationFrame(() => {
				scheduledMapDisplayRefreshFrame = 0;
				const shouldForceFit = scheduledMapDisplayRefreshForceFit;
				scheduledMapDisplayRefreshForceFit = false;
				const latestSignature = `${currentUid}::${getRenderSignature()}::${getTimeWindowSignature()}::${getCurrentMapDisplaySignature()}`;
				if (!shouldForceFit && latestSignature === lastAppliedMapDisplaySignature) return;
				renderMapDisplayFromCurrentState({ forceFit: shouldForceFit });
			});
		}

		async function renderUid(uid, options = {}) {
			const requestSequence = ++renderUidRequestSequence;
			const prevUid = currentUid;
			currentUid = uid;
			reconcileReplayTimelineStateForCurrentSelection({ uid, batchName: currentBatchName });
			if (prevUid !== uid && segmentDraftState.active) cancelTimelineSegmentDraft({ silent: true });
			if (prevUid !== uid) clearTrackEditSelection({ render: false });
			if (options.resetTrackEditState) {
				clearTrackEditInteractionState({ resetStatus: true });
			}
			cancelScheduledMapDisplayRefresh();
			clearActiveGroup();
			const scopedContext = buildReviewerScopedContext({ uid });

			const meta = await ensureUidMeta(uid);
			if (!isRenderUidRequestCurrent(requestSequence)) return;
			const exists = meta.exists;
			const toLoad = layerOrder.filter(l => exists[l]);
			const baseRawDataByLayer = Object.fromEntries(
				await Promise.all(toLoad.map(async (l) => [l, decorateTrackRowsWithPointMeta(uid, l, await fetchCsv(uid, l))]))
			);
			if (!isRenderUidRequestCurrent(requestSequence)) return;
			currentBaseRawDataByLayer = baseRawDataByLayer;
			await loadTrackEditsForUid(uid, scopedContext);
			if (!isRenderUidRequestCurrent(requestSequence)) return;
			const rawDataByLayer = applyTrackEditsToDataByLayer(baseRawDataByLayer);
			syncTimeWindowFromLayerData(rawDataByLayer, {
				resetSelection: options.resetTimeWindow ?? (prevUid !== uid),
			});
			const filteredDataByLayer = Object.fromEntries(
				toLoad.map(layer => [layer, filterRowsByCurrentTimeWindow(rawDataByLayer[layer] || [])])
			);
			currentRawDataByLayer = rawDataByLayer;
			currentFilteredDataByLayer = filteredDataByLayer;
			currentExistsByLayer = exists;
			rebuildTrackEditPointIndex();
			reconcileTrackEditSelection();
			await loadTimelineAnnotationsForUid(uid, scopedContext);
			if (!isRenderUidRequestCurrent(requestSequence)) return;
			syncCurrentWindowQuickSegmentCategory({ preferExisting: true });
			syncTimeScrubberFromCurrentData({
				preserveTime: options.preserveScrubberTime ?? (prevUid === uid),
				resetVisibleRange: options.resetScrubberVisibleRange ?? (prevUid !== uid),
			});
			renderMapDisplayFromCurrentState({ exists, forceFit: prevUid !== uid || options.forceFit });
			if (!options.skipReviewReload) {
				await loadReviewForUid(uid, exists);
				if (!isRenderUidRequestCurrent(requestSequence)) return;
			}
			renderTriageBoard({ resetVisibleCounts: false });
			renderTrackEditPanel();
		}

		function renderLayerControls(exists) {
			const html = layerOrder.map(layer => {
				if (!exists[layer]) return `<div class="layer-row empty-layer">${escapeHtml(getLayerLabel(layer))}: 无数据</div>`;
				const s = layerStyles[layer];
				return `<div class="layer-row" data-layer="${layer}" draggable="true">
					<span class="drag-handle" title="拖动调整顺序">⋮⋮</span>
					<input type="checkbox" data-opt="visible" ${s.visible ? "checked" : ""} />
					<label>${escapeHtml(getLayerLabel(layer))}</label>
					${supportsInlineLabels(layer) ? `<label class="layer-inline-toggle" title="默认直接显示该图层的时间/信息标签">
						<input type="checkbox" data-opt="show-labels" ${s.showLabels ? "checked" : ""} />
						<span>标</span>
					</label>` : `<span class="layer-inline-toggle" title="该图层不支持标签常显"><span>标</span></span>`}
					<input type="color" data-opt="color" value="${s.color}" />
					<input type="range" data-opt="opacity" min="0" max="1" step="0.05" value="${s.opacity}" />
					<span class="opacity-val">${Math.round(s.opacity * 100)}%</span>
				</div>`;
			}).join("");
			document.getElementById("layer-controls").innerHTML = html;

			let draggingLayer = null;
			document.querySelectorAll("#layer-controls .layer-row[data-layer]").forEach(row => {
				const layer = row.dataset.layer;
				row.querySelector('input[data-opt="visible"]').addEventListener("change", e => {
					layerStyles[layer].visible = e.target.checked;
					clearRenderedCache();
					renderUid(currentUid);
				});
				const labelToggle = row.querySelector('input[data-opt="show-labels"]');
				if (labelToggle) {
					labelToggle.addEventListener("change", e => {
						layerStyles[layer].showLabels = e.target.checked;
						clearRenderedCache();
						renderUid(currentUid);
					});
				}
				row.querySelector('input[data-opt="color"]').addEventListener("input", e => {
					layerStyles[layer].color = e.target.value;
					clearRenderedCache();
					renderUid(currentUid);
				});
				row.querySelector('input[data-opt="opacity"]').addEventListener("input", e => {
					layerStyles[layer].opacity = parseFloat(e.target.value);
					row.querySelector(".opacity-val").textContent = `${Math.round(layerStyles[layer].opacity * 100)}%`;
					clearRenderedCache();
					renderUid(currentUid);
				});

				row.addEventListener("dragstart", () => {
					draggingLayer = layer;
					row.classList.add("dragging");
				});
				row.addEventListener("dragend", () => {
					row.classList.remove("dragging");
					document.querySelectorAll("#layer-controls .layer-row").forEach(r => r.classList.remove("drag-over"));
				});
				row.addEventListener("dragover", e => {
					e.preventDefault();
					row.classList.add("drag-over");
				});
				row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
				row.addEventListener("drop", async (e) => {
					e.preventDefault();
					row.classList.remove("drag-over");
					const targetLayer = layer;
					if (!draggingLayer || draggingLayer === targetLayer) return;
					const from = layerOrder.indexOf(draggingLayer);
					const to = layerOrder.indexOf(targetLayer);
					layerOrder.splice(from, 1);
					layerOrder.splice(to, 0, draggingLayer);
					clearRenderedCache();
					const meta = await ensureUidMeta(currentUid);
					renderLayerControls(meta.exists);
					renderStatusStyleControls();
					await renderUid(currentUid);
				});
			});
		}

		function renderStatusStyleControls() {
			const html = pointStatusTypes.map(mt => {
				const s = statusPointStyles[mt] || { color: "#546e7a", size: 4 };
				statusPointStyles[mt] = s;
				return `<div class="status-style-row" data-mt="${mt}">
					<span class="name">${mt}</span>
					<input type="color" data-opt="color" value="${s.color}" />
					<input type="range" data-opt="size" min="2" max="10" step="1" value="${s.size}" />
					<span class="size-val">${s.size}</span>
				</div>`;
			}).join("");
			document.getElementById("status-style-controls").innerHTML = html;
			document.querySelectorAll("#status-style-controls .status-style-row").forEach(row => {
				const mt = row.dataset.mt;
				row.querySelector('input[data-opt="color"]').addEventListener("input", e => {
					statusPointStyles[mt].color = e.target.value;
					clearRenderedCache();
					renderUid(currentUid);
				});
				row.querySelector('input[data-opt="size"]').addEventListener("input", e => {
					statusPointStyles[mt].size = parseInt(e.target.value, 10);
					row.querySelector(".size-val").textContent = String(statusPointStyles[mt].size);
					clearRenderedCache();
					renderUid(currentUid);
				});
			});
		}

		async function selectUid(uid, options = {}) {
			if (!uid) return;
			if (uid !== currentUid && !options.skipDirtyCheck && !confirmDiscardReviewChanges()) return;
			const meta = await ensureUidMeta(uid);
			renderLayerControls(meta.exists);
			renderStatusStyleControls();
			await renderUid(uid);
		}

		function initDefaultStyles() {
			layerStyles = {};
			Object.keys(layerConfig).forEach(layer => {
				layerStyles[layer] = {
					color: layerConfig[layer].defaultColor,
					opacity: layerConfig[layer].defaultOpacity,
					visible: currentUiConfig.layerVisibility[layer] !== false,
					showLabels: false
				};
			});
		}
