		function applyManifestUiConfig(manifest = null) {
			const batchUiConfig = getBatchUiConfig();
			const requestedMode = String(
				batchUiConfig?.ui_mode || manifest?.ui_mode || QUERY.get("uiMode") || currentUiMode || "chain2"
			).trim().toLowerCase();
			const mode = requestedMode === "sim_signal"
				? "sim_signal"
				: requestedMode === "trajectory_layers"
					? "trajectory_layers"
					: "chain2";
			const preset = deepClone(getUiPresetForMode(mode));
			currentUiMode = mode;
			currentUiConfig = deepClone(preset);
			currentUiConfig.mode = mode;

			const manifestLayerSpecs = manifest?.layer_specs && typeof manifest.layer_specs === "object" ? manifest.layer_specs : {};
			const batchLayerSpecs = batchUiConfig?.layer_specs && typeof batchUiConfig.layer_specs === "object" ? batchUiConfig.layer_specs : {};
			const manifestLayerConfig = manifest?.layer_styles && typeof manifest.layer_styles === "object" ? manifest.layer_styles : {};
			const batchLayerConfig = batchUiConfig?.layer_styles && typeof batchUiConfig.layer_styles === "object" ? batchUiConfig.layer_styles : {};
			const configuredLayers = Array.isArray(batchUiConfig?.layers) && batchUiConfig.layers.length
				? batchUiConfig.layers
				: Array.isArray(manifest?.layers) && manifest.layers.length
					? manifest.layers
					: Object.keys(batchLayerSpecs).length
						? Object.keys(batchLayerSpecs)
						: Object.keys(batchLayerConfig).length
							? Object.keys(batchLayerConfig)
							: Object.keys(manifestLayerSpecs).length
								? Object.keys(manifestLayerSpecs)
								: Object.keys(manifestLayerConfig).length
									? Object.keys(manifestLayerConfig)
									: preset.layerOrder;
			const nextLayerOrder = dedupePreserveOrder(configuredLayers);
			const mergedLayerConfig = {};
			nextLayerOrder.forEach((layer, index) => {
				const fallbackColor = getFallbackLayerColor(layer, index);
				mergedLayerConfig[layer] = {
					defaultColor: fallbackColor,
					defaultOpacity: 0.7,
					hasLine: true,
					kind: "default",
					...(preset.layerConfig[layer] || {}),
					...(manifestLayerSpecs[layer] || {}),
					...(manifestLayerConfig[layer] || {}),
					...(batchLayerSpecs[layer] || {}),
					...(batchLayerConfig[layer] || {}),
				};
				const mergedCfg = mergedLayerConfig[layer];
				const normalizedKind = String(mergedCfg.kind || "default").trim().toLowerCase() || "default";
				const hasExplicitHasLine = Object.prototype.hasOwnProperty.call(preset.layerConfig[layer] || {}, "hasLine")
					|| Object.prototype.hasOwnProperty.call(manifestLayerSpecs[layer] || {}, "hasLine")
					|| Object.prototype.hasOwnProperty.call(manifestLayerConfig[layer] || {}, "hasLine")
					|| Object.prototype.hasOwnProperty.call(batchLayerSpecs[layer] || {}, "hasLine")
					|| Object.prototype.hasOwnProperty.call(batchLayerConfig[layer] || {}, "hasLine");
				mergedCfg.defaultColor = /^#[0-9a-f]{6}$/i.test(String(mergedCfg.defaultColor || "").trim())
					? String(mergedCfg.defaultColor).trim()
					: fallbackColor;
				mergedCfg.defaultOpacity = Math.max(0.15, Math.min(1, parseNumericValue(mergedCfg.defaultOpacity) ?? 0.7));
				mergedCfg.kind = normalizedKind;
				if (normalizedKind === "od") {
					mergedCfg.isOD = true;
					if (!hasExplicitHasLine) mergedCfg.hasLine = false;
				}
			});
			currentLayerFileMap = Object.fromEntries(
				nextLayerOrder.map(layer => {
					const configured = String(mergedLayerConfig[layer]?.filename || `${layer}.csv`).trim() || `${layer}.csv`;
					mergedLayerConfig[layer].filename = configured;
					return [layer, configured];
				})
			);
			const configuredReviewReferenceFiles = Array.isArray(batchUiConfig?.review_reference_files)
				? batchUiConfig.review_reference_files
				: Array.isArray(manifest?.review_reference_files)
					? manifest.review_reference_files
					: [];
			const configuredReviewReferenceLayers = Array.isArray(batchUiConfig?.review_reference_layers)
				? batchUiConfig.review_reference_layers
				: Array.isArray(manifest?.review_reference_layers)
					? manifest.review_reference_layers
					: [];
			const reviewReferenceFiles = dedupePreserveOrder([
				...(configuredReviewReferenceFiles),
				...(configuredReviewReferenceLayers.map(layer => currentLayerFileMap[layer] || "")),
				...nextLayerOrder
					.filter(layer => !!mergedLayerConfig[layer]?.review_reference)
					.map(layer => currentLayerFileMap[layer] || ""),
			]);
			const hasExplicitReviewReferenceConfig = Array.isArray(batchUiConfig?.review_reference_files)
				|| Array.isArray(batchUiConfig?.review_reference_layers)
				|| Array.isArray(manifest?.review_reference_files)
				|| Array.isArray(manifest?.review_reference_layers)
				|| nextLayerOrder.some(layer => mergedLayerConfig[layer]?.review_reference);
			currentReviewReferenceFiles = hasExplicitReviewReferenceConfig
				? reviewReferenceFiles
				: ["line.csv", "fmm.csv"];
			currentTimeScrubberPreferredLayers = Array.isArray(batchUiConfig?.time_scrubber_preferred_layers)
				? batchUiConfig.time_scrubber_preferred_layers.map(item => String(item || "").trim()).filter(Boolean)
				: Array.isArray(manifest?.time_scrubber_preferred_layers)
					? manifest.time_scrubber_preferred_layers.map(item => String(item || "").trim()).filter(Boolean)
				: [];

			currentUiConfig.layerOrder = nextLayerOrder;
			currentUiConfig.filterStateOptions = Array.isArray(batchUiConfig?.filter_state_options) && batchUiConfig.filter_state_options.length
				? batchUiConfig.filter_state_options.map(item => String(item || "").trim()).filter(Boolean)
				: Array.isArray(manifest?.filter_state_options) && manifest.filter_state_options.length
					? manifest.filter_state_options.map(item => String(item || "").trim()).filter(Boolean)
				: preset.filterStateOptions;
			currentUiConfig.pointStatusTypes = Array.isArray(batchUiConfig?.point_status_types) && batchUiConfig.point_status_types.length
				? batchUiConfig.point_status_types.map(item => String(item || "").trim()).filter(Boolean)
				: Array.isArray(manifest?.point_status_types) && manifest.point_status_types.length
					? manifest.point_status_types.map(item => String(item || "").trim()).filter(Boolean)
				: preset.pointStatusTypes;
			currentUiConfig.layerLabels = {
				...preset.layerLabels,
				...(manifest?.layer_labels && typeof manifest.layer_labels === "object" ? manifest.layer_labels : {}),
				...(batchUiConfig?.layer_labels && typeof batchUiConfig.layer_labels === "object" ? batchUiConfig.layer_labels : {}),
			};
			currentUiConfig.layerConfig = mergedLayerConfig;
			currentUiConfig.layerVisibility = {
				...preset.layerVisibility,
				...(manifest?.layer_visibility && typeof manifest.layer_visibility === "object" ? manifest.layer_visibility : {}),
				...(batchUiConfig?.layer_visibility && typeof batchUiConfig.layer_visibility === "object" ? batchUiConfig.layer_visibility : {}),
			};
			currentUiConfig.pointStatusStyles = deepClone(preset.pointStatusStyles);
			if (manifest?.point_status_styles && typeof manifest.point_status_styles === "object") {
				Object.entries(manifest.point_status_styles).forEach(([key, value]) => {
					currentUiConfig.pointStatusStyles[key] = {
						...(currentUiConfig.pointStatusStyles[key] || { color: "#546e7a", size: 4 }),
						...(value || {}),
					};
				});
			}
			if (batchUiConfig?.point_status_styles && typeof batchUiConfig.point_status_styles === "object") {
				Object.entries(batchUiConfig.point_status_styles).forEach(([key, value]) => {
					currentUiConfig.pointStatusStyles[key] = {
						...(currentUiConfig.pointStatusStyles[key] || { color: "#546e7a", size: 4 }),
						...(value || {}),
					};
				});
			}
			currentUiConfig.title = batchUiConfig?.title || manifest?.title || preset.title;
			currentUiConfig.searchPlaceholder = batchUiConfig?.search_placeholder || manifest?.search_placeholder || preset.searchPlaceholder;
			currentUiConfig.filterTitle = batchUiConfig?.filter_title || manifest?.filter_title || preset.filterTitle;
			currentUiConfig.statusStyleTitle = batchUiConfig?.status_style_title || manifest?.status_style_title || preset.statusStyleTitle;
			currentUiConfig.hideReviewPanel = false;
			currentUiConfig.annotationEnabled = true;
			currentUiConfig.helpContentHtml = batchUiConfig?.help_content_html || manifest?.help_content_html || preset.helpContentHtml;
			const configuredTriageColumns = Array.isArray(batchUiConfig?.triage_columns) && batchUiConfig.triage_columns.length
				? batchUiConfig.triage_columns
				: Array.isArray(manifest?.triage_columns) && manifest.triage_columns.length
					? manifest.triage_columns
					: null;
			currentUiConfig.triageColumns = configuredTriageColumns
				? configuredTriageColumns.map((item, index) => ({
					key: String(item?.key || `column_${index + 1}`).trim() || `column_${index + 1}`,
					title: String(item?.title || `列 ${index + 1}`).trim() || `列 ${index + 1}`,
					subtitle: String(item?.subtitle || "").trim(),
				}))
				: preset.triageColumns;
			const triageColumnKeySet = new Set((currentUiConfig.triageColumns || []).map(item => item.key));
			if (!triageColumnKeySet.has("pending") || !triageColumnKeySet.has("accept") || !triageColumnKeySet.has("other")) {
				currentUiConfig.triageColumns = deepClone(CHAIN2_TRIAGE_COLUMNS);
			}
			const filterSource = String(batchUiConfig?.filter_source_label || manifest?.filter_source_label || "").trim();
			if (filterSource) {
				currentUiConfig.filterTitle = `按状态筛选 UID（来源: ${filterSource}）`;
			}

			layerOrder = [...currentUiConfig.layerOrder];
			filterStateOptions = [...currentUiConfig.filterStateOptions];
			pointStatusTypes = [...currentUiConfig.pointStatusTypes];
			layerLabels = deepClone(currentUiConfig.layerLabels);
			layerConfig = deepClone(currentUiConfig.layerConfig);
			triageColumns = deepClone(currentUiConfig.triageColumns);
			activeTriageColumnKey = triageColumns[0]?.key || "";
			statusPointStyles = deepClone(currentUiConfig.pointStatusStyles);
			initDefaultStyles();
			renderStatusFilterOptions();
			applyUiChrome();
			resetColumnVisibleCounts();
		}

		function setBatchStatus(message, isError = false) {
			const el = document.getElementById("batch-status");
			el.textContent = message;
			el.style.color = isError ? "#c62828" : "#666";
		}

		function renderBatchOptions() {
			const select = document.getElementById("batch-select");
			select.innerHTML = batchList.map(batch => `
				<option value="${escapeHtml(batch.name)}">${escapeHtml(batch.label || batch.name)}</option>
			`).join("");
			select.value = currentBatchName || (batchList[0]?.name || "");
			select.disabled = batchList.length <= 1;
		}

		function updateBatchStatusText() {
			if (!currentBatchMeta) {
				setBatchStatus("批次：未加载", true);
				return;
			}
			const version = currentBatchMeta.version ? ` | ${currentBatchMeta.version}` : "";
			const uidCount = Number.isFinite(currentBatchMeta.uid_count) ? ` | UID ${currentBatchMeta.uid_count}` : "";
			setBatchStatus(`批次：${currentBatchMeta.label || currentBatchMeta.name}${version}${uidCount}`);
		}

		async function loadBatchList() {
			try {
				const response = await fetch(`${REVIEW_API_BASE}/batches`);
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const batches = Array.isArray(payload.batches) ? payload.batches : [];
				if (!batches.length) throw new Error("No batches returned");
				batchList = batches;
				currentBatchName = INITIAL_BATCH_NAME && batches.some(batch => batch.name === INITIAL_BATCH_NAME)
					? INITIAL_BATCH_NAME
					: (payload.current_batch || batches[0].name);
				currentBatchMeta = batches.find(batch => batch.name === currentBatchName) || batches[0];
				currentDataBase = currentBatchMeta.data_base || STATIC_DATA_BASE || `/batch-data/${currentBatchName}`;
				renderBatchOptions();
				updateBatchStatusText();
				return true;
			} catch (_) {
				const fallbackName = INITIAL_BATCH_NAME || "current";
				batchList = [{
					name: fallbackName,
					label: fallbackName,
					data_base: STATIC_DATA_BASE || `/batch-data/${fallbackName}`,
					version: "",
					uid_count: null
				}];
				currentBatchName = fallbackName;
				currentBatchMeta = batchList[0];
				currentDataBase = currentBatchMeta.data_base;
				renderBatchOptions();
				updateBatchStatusText();
				return false;
			}
		}

		async function refreshBatchListPreservingCurrent(options = {}) {
			const response = await fetch(`${REVIEW_API_BASE}/batches`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const payload = await response.json();
			const batches = Array.isArray(payload.batches) ? payload.batches : [];
			if (!batches.length) throw new Error("No batches returned");
			batchList = batches;
			if (currentBatchName && batches.some(batch => batch.name === currentBatchName)) {
				currentBatchMeta = batches.find(batch => batch.name === currentBatchName) || currentBatchMeta;
				currentDataBase = currentBatchMeta.data_base || STATIC_DATA_BASE || `/batch-data/${currentBatchName}`;
				renderBatchOptions();
				updateBatchStatusText();
				return { switched: false, currentBatchAvailable: true };
			}
			const fallbackName = String(options.preferredBatchName || "").trim();
			const nextBatchName = fallbackName && batches.some(batch => batch.name === fallbackName)
				? fallbackName
				: (payload.current_batch || batches[0].name);
			if (!nextBatchName) return { switched: false, currentBatchAvailable: false };
			await switchBatch(nextBatchName, { skipDirtyCheck: true, preserveUid: false });
			return { switched: true, currentBatchAvailable: false };
		}

		function resetBatchCaches() {
			csvCache = {};
			uidMetaCache = {};
			uidStatesCache = {};
			precomputedStates = null;
			currentRawDataByLayer = {};
			currentFilteredDataByLayer = {};
			currentExistsByLayer = {};
			reviewIndex = { reviews: {}, counts: {}, aggregate_counts_by_uid: {} };
			currentUidAggregate = null;
			uidList = [];
			filteredUidList = [];
			currentUid = null;
			otherReviewFilterValue = "all";
			activeTriageColumnKey = triageColumns[0]?.key || "";
			resetCurrentTimeWindow();
			resetTimeScrubber();
			clearRenderedCache();
			clearActiveGroup();
			renderTriageBoard({ resetVisibleCounts: true });
		}

		function resetBatchViewState() {
			clearActiveGroup();
			currentUid = null;
			currentUidAggregate = null;
			resetCurrentTimeWindow();
			resetTimeScrubber();
			document.getElementById("layer-status").textContent = "请选择 UID";
			populateReviewForm("", {}, null);
			renderReviewAggregatePanel(null);
			renderLayerControls({});
			renderStatusStyleControls();
		}

		async function loadManifest() {
			try {
				const r = await fetch(buildDataUrl("manifest.json"));
				if (r.ok) {
					const m = await r.json();
					currentManifest = m;
					applyManifestUiConfig(m);
					if (m.states && typeof m.states === "object") precomputedStates = m.states;
					return m.uids || [];
				}
			} catch (_) {}
			currentManifest = null;
			applyManifestUiConfig(null);
			return [];
		}

		async function loadStatesIndex() {
			if (precomputedStates) return;
			try {
				const r = await fetch(buildDataUrl("states_index.json"));
				if (r.ok) {
					const m = await r.json();
					if (m && typeof m === "object") precomputedStates = m;
				}
			} catch (_) {}
		}

		async function discoverUids() {
			const fromManifest = await loadManifest();
			if (fromManifest.length) {
				await loadStatesIndex();
				return fromManifest;
			}
			try {
				const r = await fetch(`${getCurrentDataBase()}/`);
				if (!r.ok) return [];
				const text = await r.text();
				const matches = text.match(/href="([^"/]+)\//g) || [];
				return [...new Set(matches.map(m => m.replace(/href="|\//g, "")))].filter(Boolean).sort();
			} catch (_) {
				return [];
			}
		}

		document.getElementById("filter-status").textContent = `筛选：未启用 | backend: ${getBackendLabel()}`;
		renderFilterPanelChrome();

		async function checkLayers(uid) {
			const layerNames = [...layerOrder];
			const results = await Promise.all(layerNames.map(async (layer) => {
				try {
					const filename = currentLayerFileMap[layer] || `${layer}.csv`;
					const r = await fetch(buildDataUrl(`${uid}/${filename}`), { method: "HEAD" });
					return [layer, r.ok];
				} catch (_) {
					return [layer, false];
				}
			}));
			return Object.fromEntries(results);
		}

		async function fetchCsv(uid, layer) {
			const key = `${uid}/${layer}`;
			if (csvCache[key]) return csvCache[key];
			const filename = currentLayerFileMap[layer] || `${layer}.csv`;
			const url = buildDataUrl(`${uid}/${filename}`);
			try {
				const r = await fetch(url);
				if (!r.ok) return null;
				const text = await r.text();
				const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
				csvCache[key] = parsed.data;
				return parsed.data;
			} catch (_) {
				return null;
			}
		}

		async function ensureUidMeta(uid) {
			if (uidMetaCache[uid]) return uidMetaCache[uid];
			const exists = await checkLayers(uid);
			uidMetaCache[uid] = { exists };
			return uidMetaCache[uid];
		}

		function getUidStatesFromPrecomputed(uid) {
			const arr = precomputedStates && precomputedStates[uid];
			return Array.isArray(arr) ? new Set(arr) : null;
		}

		function haversineMeters(lat1, lon1, lat2, lon2) {
			const toRad = value => value * Math.PI / 180;
			const dLat = toRad(lat2 - lat1);
			const dLon = toRad(lon2 - lon1);
			const a = Math.sin(dLat / 2) ** 2
				+ Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
			return 6371000 * 2 * Math.asin(Math.sqrt(a));
		}

		async function getUidStates(uid) {
			const fromCache = getUidStatesFromPrecomputed(uid);
			if (fromCache) return fromCache;
			if (uidStatesCache[uid]) return uidStatesCache[uid];
			const states = new Set();
			if (isSimMode()) {
				const gps = await fetchCsv(uid, "gps");
				if (gps) {
					gps.forEach(row => {
						const status = normalizeStateValue(row.status);
						if (status) states.add(status);
					});
				}
				const signal = await fetchCsv(uid, "signal");
				if (signal) {
					let prevCid = null;
					let prevPrevCid = null;
					let prevCoord = null;
					const longJumpThreshold = Number(currentManifest?.long_jump_threshold_m || 3000);
					signal.forEach(row => {
						const cid = String(row.CID || "").trim();
						const lat = parseFloat(row.latitude);
						const lon = parseFloat(row.longitude);
						if (prevPrevCid && prevCid && cid && cid === prevPrevCid && cid !== prevCid) states.add("ping_pong");
						if (prevCoord && isRenderableCoordinate(lat, lon)) {
							const distance = haversineMeters(prevCoord.lat, prevCoord.lon, lat, lon);
							if (distance >= longJumpThreshold) states.add("long_jump");
						}
						if (isRenderableCoordinate(lat, lon)) prevCoord = { lat, lon };
						prevPrevCid = prevCid;
						prevCid = cid || prevCid;
					});
				}
			} else {
				const fmm = await fetchCsv(uid, "fmm");
				if (fmm) fmm.forEach(row => states.add(normalizeStateValue(row.match_type, "unmatch")));
				const line = await fetchCsv(uid, "line");
				if (line) line.forEach(row => states.add(normalizeStateValue(row.match_type, "unmatch")));
				const od = await fetchCsv(uid, "od");
				if (od) {
					od.forEach(row => {
						const isStay = row.is_stationary === true || String(row.is_stationary).toLowerCase() === "true";
						states.add(isStay ? "stay" : "road");
					});
				}
			}
			uidStatesCache[uid] = states;
			return states;
		}

		function matchesGlobalSearch(uid, searchTerm) {
			if (!searchTerm) return true;
			const review = getReviewForUid(uid);
			const reviewTagsText = getReviewTags(review).join(" ");
			const precomputedStateText = [...(getUidStatesFromPrecomputed(uid) || new Set())].join(" ");
			const haystacks = [
				String(uid || ""),
				String(review?.reviewer || ""),
				String(review?.reviewer_name || ""),
				String(review?.reviewer_id || ""),
				String(review?.notes || ""),
				reviewTagsText,
				precomputedStateText
			].map(item => item.toLowerCase());
			return haystacks.some(item => item.includes(searchTerm));
		}

		function buildTriageBuckets(uids, options = {}) {
			const applyOtherReviewFilter = !!options.applyOtherReviewFilter;
			const buckets = Object.fromEntries(triageColumns.map(column => [column.key, []]));
			uids.forEach(uid => {
				const bucketKey = getReviewBucketKey(uid);
				if (bucketKey === "other" && applyOtherReviewFilter && otherReviewFilterValue !== "all") {
					const review = getReviewForUid(uid);
					if (review?.decision !== otherReviewFilterValue) return;
				}
				buckets[bucketKey].push(uid);
			});
			return buckets;
		}

		function computeBoardState() {
			return {
				totalBuckets: buildTriageBuckets(uidList),
				filteredBuckets: buildTriageBuckets(filteredUidList, { applyOtherReviewFilter: true }),
				filteredSequence: [...filteredUidList]
			};
		}

		function resetColumnVisibleCounts() {
			columnVisibleCounts = Object.fromEntries(triageColumns.map(column => [column.key, BOARD_PAGE_SIZE]));
		}

		function getSidebarEffectiveWidth() {
			const sidebar = document.getElementById("sidebar");
			if (!sidebar || sidebar.classList.contains("collapsed")) return 0;
			return Math.round(sidebar.getBoundingClientRect().width || 0);
		}

		function getTriageLayoutMode() {
			if (triageColumns.length <= 1) return "stack";
			return getSidebarEffectiveWidth() < TRIAGE_STACK_WIDTH_THRESHOLD ? "stack" : "grid";
		}

		function resolveActiveTriageColumnKey() {
			const validKeys = triageColumns.map(column => column.key);
			if (!validKeys.length) return "";
			if (
				triageLayoutMode === "stack"
				&& validKeys.includes(activeTriageColumnKey)
			) {
				return activeTriageColumnKey;
			}
			if (currentUid) {
				const currentBucketKey = getReviewBucketKey(currentUid);
				if (
					validKeys.includes(currentBucketKey)
					&& (boardState?.filteredBuckets?.[currentBucketKey] || []).includes(currentUid)
				) {
					return currentBucketKey;
				}
			}
			if (
				validKeys.includes(activeTriageColumnKey)
				&& (boardState?.filteredBuckets?.[activeTriageColumnKey] || []).length
			) {
				return activeTriageColumnKey;
			}
			return validKeys.find(key => (boardState?.filteredBuckets?.[key] || []).length) || validKeys[0];
		}

		function renderTriageToolbar() {
			const summaryEl = document.getElementById("triage-board-summary");
			if (summaryEl) {
				summaryEl.textContent = uidList.length
					? `当前筛选 ${filteredUidList.length} / ${uidList.length}`
					: "暂无轨迹";
			}
			const tabsEl = document.getElementById("triage-column-tabs");
			if (!tabsEl) return;
			const useTabs = triageLayoutMode === "stack" && triageColumns.length > 1;
			tabsEl.classList.toggle("visible", useTabs);
			if (!useTabs) {
				tabsEl.innerHTML = "";
				return;
			}
			tabsEl.innerHTML = triageColumns.map(column => {
				const count = boardState?.filteredBuckets?.[column.key]?.length || 0;
				return `
					<button type="button" class="triage-tab ${activeTriageColumnKey === column.key ? "active" : ""}" data-column="${escapeHtml(column.key)}">
						<span>${escapeHtml(column.title)}</span>
						<span class="triage-tab-count">${count}</span>
					</button>
				`;
			}).join("");
		}

		function maybeSyncTriageLayoutMode() {
			const nextMode = getTriageLayoutMode();
			if (nextMode === triageLayoutMode) return;
			triageLayoutMode = nextMode;
			renderTriageBoard({ resetVisibleCounts: false });
		}

		function renderTriageColumn(column) {
			const totalCount = boardState?.totalBuckets?.[column.key]?.length || 0;
			const filteredUids = boardState?.filteredBuckets?.[column.key] || [];
			const visibleCount = columnVisibleCounts[column.key] || BOARD_PAGE_SIZE;
			const visibleUids = filteredUids.slice(0, visibleCount);
			const hasMore = filteredUids.length > visibleUids.length;
			const filterControl = column.key === "other" ? `
				<select class="triage-filter" id="other-review-filter">
					<option value="all" ${otherReviewFilterValue === "all" ? "selected" : ""}>全部</option>
					<option value="reject" ${otherReviewFilterValue === "reject" ? "selected" : ""}>仅 reject</option>
					<option value="skip" ${otherReviewFilterValue === "skip" ? "selected" : ""}>仅 skip</option>
				</select>
			` : "";
			const cardsHtml = visibleUids.length ? visibleUids.map(uid => {
				const review = getReviewForUid(uid);
				return `
					<button type="button" class="triage-card ${currentUid === uid ? "active" : ""}" data-uid="${escapeHtml(uid)}">
						<div class="triage-card-top">
							<span class="uid-label">${escapeHtml(uid)}</span>
							${getReviewBadgeHtml(review)}
						</div>
						${buildReviewCardMetaHtml(uid)}
					</button>
				`;
			}).join("") : `<div class="triage-empty">${escapeHtml(column.title)}列当前没有轨迹</div>`;
			const loadMoreHtml = hasMore
				? `<button type="button" class="load-more-btn" data-column="${column.key}">加载更多 (${filteredUids.length - visibleUids.length} 个)</button>`
				: "";
			return `
				<section class="triage-column" data-column="${column.key}">
					<div class="triage-column-header">
						<div class="triage-title-row">
							<span class="triage-title">${escapeHtml(column.title)}</span>
							<span class="triage-count">显示 ${filteredUids.length} / 共 ${totalCount}</span>
						</div>
						<div class="triage-subtitle">${escapeHtml(column.subtitle)}</div>
						${filterControl}
					</div>
					<div class="triage-card-list">${cardsHtml}</div>
					${loadMoreHtml}
				</section>
			`;
		}

		function renderTriageBoard(options = {}) {
			if (options.resetVisibleCounts) resetColumnVisibleCounts();
			boardState = computeBoardState();
			triageLayoutMode = getTriageLayoutMode();
			activeTriageColumnKey = resolveActiveTriageColumnKey();
			renderTriageToolbar();
			const boardEl = document.getElementById("triage-board");
			boardEl.className = triageLayoutMode === "stack" ? "mode-stack" : "mode-grid";
			const columnsToRender = triageLayoutMode === "stack"
				? triageColumns.filter(column => column.key === activeTriageColumnKey)
				: triageColumns;
			boardEl.innerHTML = columnsToRender.map(renderTriageColumn).join("");
			renderFilterPanelChrome();
			updatePendingNavigation();
		}

		function getNextPendingUid(uid) {
			const primaryKey = triageColumns[0]?.key || "pending";
			const pendingSet = new Set(boardState?.filteredBuckets?.[primaryKey] || []);
			const sequence = boardState?.filteredSequence || [];
			if (!pendingSet.size) return null;
			const currentIndex = sequence.indexOf(uid);
			if (currentIndex === -1) return sequence.find(candidate => pendingSet.has(candidate)) || null;
			for (let index = currentIndex + 1; index < sequence.length; index++) {
				if (pendingSet.has(sequence[index])) return sequence[index];
			}
			return null;
		}

		function getPreviousPendingUid(uid) {
			const primaryKey = triageColumns[0]?.key || "pending";
			const pendingSet = new Set(boardState?.filteredBuckets?.[primaryKey] || []);
			const sequence = boardState?.filteredSequence || [];
			if (!pendingSet.size) return null;
			const currentIndex = sequence.indexOf(uid);
			if (currentIndex === -1) {
				for (let index = sequence.length - 1; index >= 0; index--) {
					if (pendingSet.has(sequence[index])) return sequence[index];
				}
				return null;
			}
			for (let index = currentIndex - 1; index >= 0; index--) {
				if (pendingSet.has(sequence[index])) return sequence[index];
			}
			return null;
		}

		function updatePendingNavigation() {
			const prevBtn = document.getElementById("prev-pending-btn");
			const nextBtn = document.getElementById("next-pending-btn");
			const prevUid = getPreviousPendingUid(currentUid);
			const nextUid = getNextPendingUid(currentUid);
			prevBtn.disabled = !prevUid;
			nextBtn.disabled = !nextUid;
			prevBtn.dataset.uid = prevUid || "";
			nextBtn.dataset.uid = nextUid || "";
		}

		async function refreshFilteredUids(options = {}) {
			const resetVisibleCounts = options.resetVisibleCounts !== false;
			const token = ++filterRunToken;
			const selectedStates = getSelectedFilterStates();
			const mode = document.getElementById("filter-mode").value;
			const searchTerm = document.getElementById("search-box").value.trim().toLowerCase();
			const usePrecomputed = !!precomputedStates;
			if (selectedStates.length && !usePrecomputed) {
				document.getElementById("filter-status").textContent = "筛选：计算中...（无缓存，较慢）";
				renderFilterPanelChrome();
			}

			const nextFiltered = [];
			if (!selectedStates.length) {
				uidList.forEach(uid => {
					if (matchesGlobalSearch(uid, searchTerm)) nextFiltered.push(uid);
				});
			} else {
				const BATCH = 6;
				for (let index = 0; index < uidList.length; index += BATCH) {
					const batch = uidList.slice(index, index + BATCH);
					const statesList = await Promise.all(batch.map(uid => getUidStates(uid)));
					if (token !== filterRunToken) return;
					batch.forEach((uid, batchIndex) => {
						const states = statesList[batchIndex];
						const hit = mode === "all"
							? selectedStates.every(state => states.has(state))
							: selectedStates.some(state => states.has(state));
						if (hit && matchesGlobalSearch(uid, searchTerm)) nextFiltered.push(uid);
					});
				}
			}
			if (token !== filterRunToken) return;
			filteredUidList = nextFiltered;
			renderTriageBoard({ resetVisibleCounts });
			const filterDesc = !selectedStates.length
				? "未启用状态筛选"
				: `${mode === "all" ? "全部命中" : "任一命中"} ${selectedStates.join("/")}`;
			document.getElementById("filter-status").textContent = `筛选：${filterDesc} | 搜索命中 ${filteredUidList.length} / ${uidList.length} | backend: ${getBackendLabel()}`;
			renderFilterPanelChrome();
		}

		function clearActiveGroup() {
			if (activeGroup && map.hasLayer(activeGroup)) map.removeLayer(activeGroup);
			activeGroup = null;
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

		function debounce(fn, ms) {
			let t;
			return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
		}

		function syncMapToolsDock() {
			const dock = document.getElementById("map-tools-dock");
			const toggle = document.getElementById("map-tools-toggle");
			const label = document.getElementById("map-tools-toggle-label");
			dock.classList.toggle("open", mapToolsOpen);
			toggle.classList.toggle("active", mapToolsOpen);
			toggle.setAttribute("aria-expanded", mapToolsOpen ? "true" : "false");
			if (label) label.textContent = "图层";
			toggle.title = mapToolsOpen ? "收起图层与状态样式面板" : "打开图层与状态样式面板";
		}

		function setMapToolsOpen(nextOpen) {
			mapToolsOpen = !!nextOpen;
			syncMapToolsDock();
		}

		async function switchBatch(nextBatchName, options = {}) {
			const targetName = String(nextBatchName || "").trim();
			if (!targetName) return;
			if (targetName !== currentBatchName && !options.skipDirtyCheck && !confirmDiscardReviewChanges()) {
				document.getElementById("batch-select").value = currentBatchName || targetName;
				return;
			}
			const targetMeta = batchList.find(batch => batch.name === targetName) || {
				name: targetName,
				label: targetName,
				data_base: STATIC_DATA_BASE || `/batch-data/${targetName}`,
			};
			const keepUid = options.preserveUid !== false ? currentUid : null;
			currentBatchName = targetName;
			currentBatchMeta = targetMeta;
			currentDataBase = targetMeta.data_base || STATIC_DATA_BASE || `/batch-data/${targetName}`;
			renderBatchOptions();
			updateBatchStatusText();
			setBatchStatus(`批次切换中：${targetMeta.label || targetMeta.name}`);
			resetBatchCaches();
			resetBatchViewState();
			const nextUids = await discoverUids();
			uidList = [...nextUids];
			await loadReviewIndex();
			applyUiChrome();
			await refreshFilteredUids({ resetVisibleCounts: true });
			const initialUid = keepUid && uidList.includes(keepUid) ? keepUid : (filteredUidList[0] || uidList[0] || null);
			if (initialUid) {
				await selectUid(initialUid, { skipDirtyCheck: true });
			}
			updateBatchStatusText();
		}
