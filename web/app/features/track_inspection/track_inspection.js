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
			if (focusInput) focusInput.value = annotationSettings.focusOpacity.toFixed(2);
			if (idleInput) idleInput.value = annotationSettings.idleOpacity.toFixed(2);
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

		function initMap() {
			map = L.map("map", { center: [39.9, 116.4], zoom: 11, preferCanvas: true, keyboard: false });
			tileLayer = L.tileLayer(GAODE_TILE, { attribution: "Gaode", keepBuffer: 6, updateWhenIdle: true, updateWhenZooming: false });
			tileLayer.addTo(map);
			L.control.scale({ imperial: false }).addTo(map);
			syncTimeLabelScale();
			lastRenderZoomBucket = getCurrentRenderZoomBucket();
			map.on("zoom", syncTimeLabelScale);
			map.on("zoomend", () => {
				syncTimeLabelScale();
				maybeRerenderForZoomChange();
			});
		}

		function getCurrentRenderZoomBucket() {
			return Math.max(0, Math.round(map?.getZoom?.() ?? 11));
		}

		function maybeRerenderForZoomChange() {
			const nextBucket = getCurrentRenderZoomBucket();
			if (nextBucket === lastRenderZoomBucket) return;
			lastRenderZoomBucket = nextBucket;
			if (!currentUid) return;
			void renderUid(currentUid, { forceFit: false, skipReviewReload: true, resetTimeWindow: false });
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

		function getRenderSignature() {
			return JSON.stringify({ layerOrder, layerStyles, statusPointStyles, zoomBucket: getCurrentRenderZoomBucket() });
		}

		let scheduledMapDisplayRefreshFrame = 0;
		let scheduledMapDisplayRefreshForceFit = false;
		let lastAppliedMapDisplaySignature = "";

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
			const segments = getCurrentTimelineSegments();
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
			getCurrentTimelineSegments().forEach(segment => {
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

		function getCurrentTimelinePinStoreKey() {
			return `${currentBatchName || "__default__"}::${getCurrentReviewerId() || "__no_reviewer__"}::${currentUid || "__none__"}`;
		}

		function getCurrentTimelinePins() {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId()) return [];
			return timelinePinsByTrack[getCurrentTimelinePinStoreKey()] || [];
		}

		function saveCurrentTimelinePins(pins) {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId()) return;
			timelinePinsByTrack[getCurrentTimelinePinStoreKey()] = Array.isArray(pins) ? pins : [];
			persistTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY, timelinePinsByTrack);
			void persistCurrentTimelineAnnotationsToServer();
		}

		function getCurrentTimelineSegments() {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId()) return [];
			return timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] || [];
		}

		function saveCurrentTimelineSegments(segments) {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId()) return;
			timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] = Array.isArray(segments) ? segments : [];
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
			if (!ensureAnnotationSessionReady({ prompt: true })) return;
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
			if (!ensureAnnotationSessionReady({ prompt: false })) {
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
			const id = `${category.id}:${Math.round(leftTime)}:${Math.round(rightTime)}`;
			const existing = getCurrentTimelineSegments();
			if (!existing.some(item => item.id === id)) {
				saveCurrentTimelineSegments([
					...existing,
					{
						id,
						categoryId: category.id,
						categoryName: category.name,
						color: category.color,
						startTime: leftTime,
						endTime: rightTime,
						entryMode: "manual",
						segmentScope: "custom",
						sourceLayerKey: timeScrubberState.selectedLayer || "",
					},
				]);
				autoSelectAcceptDecisionAfterAnnotation();
			}
			resetSegmentDraftState();
			renderTimeScrubberControl();
		}

		function getRenderableTimelineSegments(options = {}) {
			const entries = getCurrentTimelineSegments().map(segment => ({
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
				laneEnds[laneIndex] = segment.endTime + 1;
				return { ...segment, laneIndex, renderMode: "lane" };
			});
		}

		function buildTimelineAnnotationsApiUrl(extraParams = {}) {
			return buildReviewApiUrl("/timeline-annotations", buildReviewerScopedParams(extraParams));
		}

		async function loadTimelineAnnotationsForUid(uid) {
			if (!uid) return;
			if (currentUiConfig.annotationEnabled === false || !getCurrentReviewerId()) {
				timelinePinsByTrack[getCurrentTimelinePinStoreKey()] = [];
				timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] = [];
				return;
			}
			try {
				const response = await fetch(buildTimelineAnnotationsApiUrl({ uid }));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const annotations = payload.annotations || {};
				timelinePinsByTrack[getCurrentTimelinePinStoreKey()] = Array.isArray(annotations.pins) ? annotations.pins : [];
				timelineSegmentsByTrack[getCurrentTimelinePinStoreKey()] = Array.isArray(annotations.segments) ? annotations.segments : [];
				persistTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY, timelinePinsByTrack);
				persistTimelineAnnotationStore(TIMELINE_SEGMENTS_STORAGE_KEY, timelineSegmentsByTrack);
			} catch (_) {}
		}

		async function persistCurrentTimelineAnnotationsToServer() {
			if (currentUiConfig.annotationEnabled === false || !currentUid || !getCurrentReviewerId()) return;
			try {
				await fetch(buildTimelineAnnotationsApiUrl(), {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						uid: currentUid,
						sample_id: currentUid,
						reviewer_id: getCurrentReviewerId(),
						reviewer_name: getCurrentReviewerName(),
						pins: getCurrentTimelinePins(),
						segments: getCurrentTimelineSegments(),
					}),
				});
			} catch (_) {}
		}

		function getTimelineSegmentsAtTime(targetTime, options = {}) {
			if (targetTime == null) return [];
			const epsilon = options.epsilon ?? 0;
			return getCurrentTimelineSegments()
				.filter(segment => targetTime >= (segment.startTime - epsilon) && targetTime <= (segment.endTime + epsilon))
				.sort((a, b) => (b.endTime - b.startTime) - (a.endTime - a.startTime) || (b.startTime - a.startTime));
		}

		function removeTimelineSegmentById(segmentId) {
			if (!segmentId || currentUiConfig.annotationEnabled === false || !getCurrentReviewerId()) return;
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
			if (!ensureAnnotationSessionReady({ prompt: true })) return;
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
			if (!ensureAnnotationSessionReady({ prompt: true })) return;
			const actionState = getCurrentWindowQuickSegmentActionState();
			if (actionState.disabled || !actionState.selectedCategory || !actionState.bounds) return;
			const nextSegment = buildCurrentWindowQuickSegment(
				actionState.selectedCategory,
				actionState.bounds,
				actionState.existingSegment,
			);
			const remainingSegments = getCurrentTimelineSegments().filter(segment => segment.id !== nextSegment.id);
			saveCurrentTimelineSegments([...remainingSegments, nextSegment]);
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
			const visiblePins = getCurrentTimelinePins().filter(pin => pin.time >= visibleStartTime && pin.time <= visibleEndTime);
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
			const pins = getCurrentTimelinePins();
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
			updateDateWindowControl();
			if (!timeScrubberState.focusLayers.length) {
				hideTimeScrubberContextMenu();
				control.classList.add("hidden");
				overviewCanvas.classList.remove("dragging");
				updateTimeScrubberOverviewCursor();
				clearTimeFocusMarker();
				return;
			}
			control.classList.remove("hidden");
			buildTimeScrubberLayerOptions();
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) {
				hideTimeScrubberContextMenu();
				document.getElementById("time-scrubber-status").textContent = `${getLayerLabel(timeScrubberState.selectedLayer)} | 当前日期区间内无可定位时间点`;
				document.getElementById("time-scrubber-range").textContent = `日期区间 ${currentTimeWindow.startDay || "--"} -- ${currentTimeWindow.endDay || "--"} | 可切换其他图层继续查看`;
				stepPrevBtn.disabled = true;
				stepNextBtn.disabled = true;
				leftBtn.disabled = true;
				rightBtn.disabled = true;
				zoomOutBtn.disabled = true;
				zoomInBtn.disabled = true;
				overviewCanvas.classList.remove("dragging");
				updateTimeScrubberOverviewCursor();
				drawTimeScrubberCanvas();
				drawTimeScrubberOverviewCanvas();
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
			document.getElementById("time-scrubber-status").textContent = statusText;
			document.getElementById("time-scrubber-range").textContent = segmentDraftState.active
				? `正在标记 ${getAnnotationCategoryLabel(segmentDraftState.categoryId)} | 起点 ${formatDateTime(segmentDraftState.startTime)} | 预览终点 ${formatDateTime(segmentDraftState.previewTime)}`
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
			drawTimeScrubberOverviewCanvas();
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

		function renderOneLayer(layerKey, data, targetGroup) {
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
				for (const layer of toLoad) {
					renderStatsList.push(renderOneLayer(layer, displayDataByLayer[layer], group));
				}
				const bounds = getBoundsFromGroup(group);
				cached = { group, bounds, renderStatsList };
				putRenderedCache(cacheKey, cached);
			}

			clearActiveGroup();
			activeGroup = cached.group;
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
			const prevUid = currentUid;
			currentUid = uid;
			if (prevUid !== uid && segmentDraftState.active) cancelTimelineSegmentDraft({ silent: true });
			cancelScheduledMapDisplayRefresh();
			clearActiveGroup();

			const meta = await ensureUidMeta(uid);
			const exists = meta.exists;
			const toLoad = layerOrder.filter(l => exists[l]);
			const rawDataByLayer = Object.fromEntries(
				await Promise.all(toLoad.map(async (l) => [l, await fetchCsv(uid, l)]))
			);
			syncTimeWindowFromLayerData(rawDataByLayer, {
				resetSelection: options.resetTimeWindow ?? (prevUid !== uid),
			});
			const filteredDataByLayer = Object.fromEntries(
				toLoad.map(layer => [layer, filterRowsByCurrentTimeWindow(rawDataByLayer[layer] || [])])
			);
			currentRawDataByLayer = rawDataByLayer;
			currentFilteredDataByLayer = filteredDataByLayer;
			currentExistsByLayer = exists;
			await loadTimelineAnnotationsForUid(uid);
			syncCurrentWindowQuickSegmentCategory({ preferExisting: true });
			syncTimeScrubberFromCurrentData({
				preserveTime: options.preserveScrubberTime ?? (prevUid === uid),
				resetVisibleRange: options.resetScrubberVisibleRange ?? (prevUid !== uid),
			});
			renderMapDisplayFromCurrentState({ exists, forceFit: prevUid !== uid || options.forceFit });
			if (!options.skipReviewReload) {
				await loadReviewForUid(uid, exists);
			}
			renderTriageBoard({ resetVisibleCounts: false });
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
