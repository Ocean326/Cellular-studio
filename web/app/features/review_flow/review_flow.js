		function renderReviewerIdentity() {
			const name = getCurrentReviewerName() || "未设置";
			document.getElementById("current-reviewer-chip").textContent = name;
			document.getElementById("reviewer-identity-value").textContent = name;
			document.getElementById("save-review-btn").disabled = !getCurrentReviewerId() || currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel;
			document.getElementById("refresh-review-btn").disabled = !currentUid || currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel;
		}

		function ensureAnnotationSessionReady(options = {}) {
			if (currentUiConfig.annotationEnabled === false) return false;
			if (getCurrentReviewerId()) return true;
			if (options.prompt !== false) openReviewerSessionModal({ required: true });
			setReviewStatus("请先设置标注者身份", true);
			return false;
		}

		function renderKnownReviewerButtons() {
			const container = document.getElementById("reviewer-session-known");
			if (!container) return;
			const buttons = reviewerRegistry.map(reviewer => `
				<button
					type="button"
					class="reviewer-known-btn"
					data-reviewer-id="${escapeHtml(reviewer.reviewer_id || "")}"
					data-reviewer-name="${escapeHtml(reviewer.reviewer_name || reviewer.display_name || "")}"
				>${escapeHtml(reviewer.reviewer_name || reviewer.display_name || reviewer.reviewer_id || "")}</button>
			`).join("");
			container.innerHTML = buttons;
		}

		function openReviewerSessionModal(options = {}) {
			const overlay = document.getElementById("reviewer-session-overlay");
			const input = document.getElementById("reviewer-session-input");
			reviewerSessionModalRequired = options.required !== false;
			overlay.classList.add("open");
			overlay.setAttribute("aria-hidden", "false");
			document.getElementById("reviewer-session-cancel").style.display =
				reviewerSessionModalRequired ? "none" : "";
			input.value = options.prefillName || getCurrentReviewerName() || "";
			setReviewerSessionStatus(reviewerSessionModalRequired ? "请先设置当前标注者身份。" : "可以切换到其他标注者。", false);
			renderKnownReviewerButtons();
			window.setTimeout(() => input.focus(), 0);
		}

		function closeReviewerSessionModal(force = false) {
			if (reviewerSessionModalRequired && !force) return;
			const overlay = document.getElementById("reviewer-session-overlay");
			overlay.classList.remove("open");
			overlay.setAttribute("aria-hidden", "true");
			setReviewerSessionStatus("", false);
		}

		async function loadReviewerRegistry() {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) {
				reviewerRegistry = [];
				renderKnownReviewerButtons();
				return [];
			}
			try {
				const response = await fetch(buildReviewApiUrl("/reviewers"));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				reviewerRegistry = Array.isArray(payload.reviewers) ? payload.reviewers : [];
			} catch (_) {
				reviewerRegistry = [];
			}
			renderKnownReviewerButtons();
			return reviewerRegistry;
		}

		async function submitReviewerSession(payload = {}) {
			const displayName = String(payload.display_name || "").trim();
			const reviewerId = String(payload.reviewer_id || "").trim();
			const body = {};
			if (displayName) body.display_name = displayName;
			if (reviewerId) body.reviewer_id = reviewerId;
			const response = await fetch(buildReviewApiUrl("/reviewers/session"), {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			});
			if (!response.ok) {
				const text = await response.text();
				throw new Error(text || `HTTP ${response.status}`);
			}
			const sessionPayload = await response.json();
			const reviewer = sessionPayload.reviewer || null;
			if (!reviewer?.reviewer_id || !reviewer?.reviewer_name) {
				throw new Error("reviewer session response is incomplete");
			}
			persistReviewerSession(reviewer);
			await loadReviewerRegistry();
			return reviewer;
		}

		async function ensureReviewerSessionReady(options = {}) {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) return true;
			await loadReviewerRegistry();
			if (!currentReviewerSession) {
				if (options.prompt !== false) openReviewerSessionModal({ required: true });
				return false;
			}
			try {
				await submitReviewerSession({
					reviewer_id: currentReviewerSession.reviewer_id,
					display_name: currentReviewerSession.reviewer_name,
				});
				return true;
			} catch (error) {
				setReviewStatus(`标注者身份校验失败：${error.message || error}`, true);
				if (options.prompt !== false) openReviewerSessionModal({ required: true });
				return false;
			}
		}

		async function onReviewerSessionChanged() {
			renderReviewerIdentity();
			await loadReviewIndex();
			if (currentUid) {
				await renderUid(currentUid, {
					forceFit: false,
					preserveScrubberTime: true,
					resetScrubberVisibleRange: false,
					resetTimeWindow: false,
					resetTrackEditState: true,
				});
			} else {
				renderTriageBoard({ resetVisibleCounts: false });
			}
			renderTrackEditPanel();
		}

		function getUiPresetForMode(mode) {
			if (mode === "sim_signal") return SIM_SIGNAL_UI_PRESET;
			if (mode === "trajectory_layers") return TRAJECTORY_LAYERS_UI_PRESET;
			return CHAIN2_UI_PRESET;
		}

		function isSimMode() {
			return currentUiMode === "sim_signal";
		}

		function getLayerLabel(layer) {
			return layerLabels[layer] || layer;
		}

		function renderStatusFilterOptions() {
			document.getElementById("status-filter-row").innerHTML = filterStateOptions.map(state => `
				<label><input type="checkbox" value="${escapeHtml(state)}">${escapeHtml(state)}</label>
			`).join("");
		}

		function renderHelpContent() {
			document.getElementById("help-content").innerHTML = currentUiConfig.helpContentHtml || "";
		}

		function getBatchUiConfig(batchMeta = currentBatchMeta) {
			if (!batchMeta?.ui_config || typeof batchMeta.ui_config !== "object") return {};
			return batchMeta.ui_config;
		}

		function setReviewPanelCollapsed(nextCollapsed) {
			reviewPanelCollapsed = !!nextCollapsed;
			const panel = document.getElementById("review-panel");
			const toggle = document.getElementById("review-panel-toggle");
			if (panel) panel.classList.toggle("collapsed", reviewPanelCollapsed);
			if (toggle) toggle.textContent = reviewPanelCollapsed ? "展开" : "收起";
		}

		function applyUiChrome() {
			const annotationEnabled = currentUiConfig.annotationEnabled !== false;
			const showReviewPanel = annotationEnabled && !currentUiConfig.hideReviewPanel;
			document.title = currentUiConfig.title || "轨迹预览";
			document.getElementById("sidebar-title").textContent = currentUiConfig.title || "轨迹预览";
			document.getElementById("filter-panel-title").textContent = currentUiConfig.filterTitle || "按状态筛选 UID";
			document.getElementById("status-style-title").textContent = currentUiConfig.statusStyleTitle || "状态样式";
			document.getElementById("search-box").placeholder = currentUiConfig.searchPlaceholder || "搜索 UID...";
			document.getElementById("review-panel").style.display = showReviewPanel ? "" : "none";
			document.getElementById("review-aggregate-panel").style.display = SHOW_REVIEW_AGGREGATE && showReviewPanel ? "" : "none";
			document.getElementById("annotation-settings-entry").style.display = annotationEnabled ? "" : "none";
			document.getElementById("reviewer-badge-row").style.display = annotationEnabled ? "" : "none";
			if (!annotationEnabled) {
				hideTimeScrubberContextMenu();
				closeAnnotationSettings();
			}
			setReviewPanelCollapsed(reviewPanelCollapsed);
			renderReviewerIdentity();
			renderHelpContent();
			renderFilterPanelChrome();
			syncReviewAggregateChrome(currentUidAggregate);
		}

		function getSelectedFilterStates() {
			return [...document.querySelectorAll("#status-filter-row input:checked")].map(el => el.value);
		}

		function buildFilterSummaryText() {
			const selectedStates = getSelectedFilterStates();
			const mode = document.getElementById("filter-mode")?.value || "any";
			const searchTerm = document.getElementById("search-box")?.value.trim();
			const parts = [];
			parts.push(
				selectedStates.length
					? `状态: ${mode === "all" ? "全部" : "任一"} ${selectedStates.join("/")}`
					: "状态: 全部"
			);
			if (searchTerm) parts.push(`搜索: ${searchTerm}`);
			if (uidList.length) parts.push(`${filteredUidList.length} / ${uidList.length}`);
			return parts.join(" | ");
		}

		function renderFilterPanelChrome() {
			const panel = document.getElementById("filter-panel");
			const toggle = document.getElementById("filter-toggle-btn");
			const summary = document.getElementById("filter-summary");
			if (!panel || !toggle || !summary) return;
			panel.classList.toggle("collapsed", filterPanelCollapsed);
			toggle.textContent = filterPanelCollapsed ? "展开" : "收起";
			summary.textContent = buildFilterSummaryText();
		}

		function setFilterPanelCollapsed(nextCollapsed) {
			filterPanelCollapsed = !!nextCollapsed;
			renderFilterPanelChrome();
		}

		function setReviewAggregateCollapsed(nextCollapsed, options = {}) {
			reviewAggregateCollapsed = !!nextCollapsed;
			if (options.userInitiated) reviewAggregateCollapseTouched = true;
			const panel = document.getElementById("review-aggregate-panel");
			const toggleText = document.getElementById("review-aggregate-toggle-text");
			if (panel) panel.classList.toggle("collapsed", reviewAggregateCollapsed);
			if (toggleText) toggleText.textContent = reviewAggregateCollapsed ? "展开" : "收起";
		}

		function syncReviewAggregateChrome(aggregate = null) {
			if (!SHOW_REVIEW_AGGREGATE) return;
			const reviewerCount = Number(aggregate?.reviewer_count || 0);
			if (!reviewAggregateCollapseTouched) {
				setReviewAggregateCollapsed(reviewerCount <= 1, { userInitiated: false });
				return;
			}
			if (!aggregate || reviewerCount <= 0) {
				setReviewAggregateCollapsed(true, { userInitiated: false });
				return;
			}
			setReviewAggregateCollapsed(reviewAggregateCollapsed, { userInitiated: false });
		}

		function setReviewStatus(message, isError) {
			const el = document.getElementById("review-status");
			el.textContent = message;
			el.style.color = isError ? "#c62828" : "#666";
		}

		function setReviewDirtyStatus(message, isDirty) {
			const el = document.getElementById("review-dirty-status");
			el.textContent = message;
			el.classList.toggle("is-dirty", !!isDirty);
		}

		function getCurrentFormState() {
			const selectedTag = getSelectedReviewTag();
			return {
				decision: selectedDecision || "",
				reviewer_id: getCurrentReviewerId(),
				reference_source: document.getElementById("reference-source-input").value.trim(),
				notes: document.getElementById("review-notes").value.trim(),
				trajectory_tags: selectedTag ? [selectedTag] : [],
			};
		}

		function markReviewPristine() {
			reviewFormSnapshot = JSON.stringify(getCurrentFormState());
			reviewFormDirty = false;
			setReviewDirtyStatus("当前内容已保存", false);
		}

		function syncReviewDirtyState() {
			const nextSnapshot = JSON.stringify(getCurrentFormState());
			reviewFormDirty = nextSnapshot !== reviewFormSnapshot;
			setReviewDirtyStatus(reviewFormDirty ? "当前修改未保存" : "当前内容已保存", reviewFormDirty);
		}

		function confirmDiscardReviewChanges() {
			if (!reviewFormDirty) return true;
			return window.confirm("当前审核有未保存修改，确定要放弃并切换吗？");
		}

		function setDecisionButtons(decision, options = {}) {
			selectedDecision = decision || "";
			document.querySelectorAll(".review-decision-btn").forEach(btn => {
				btn.classList.toggle("active", btn.dataset.decision === selectedDecision);
			});
			if (!options.silent) syncReviewDirtyState();
		}

		function getReviewForUid(uid) {
			return reviewIndex.reviews?.[uid] || null;
		}

		function getReviewBucketKey(uid) {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) return triageColumns[0]?.key || "pending";
			const review = getReviewForUid(uid);
			if (!review || !review.decision) return "pending";
			if (review.decision === "accept") return "accept";
			return "other";
		}

		function formatReviewTimestamp(value) {
			const text = String(value || "").trim();
			if (!text) return "";
			if (text.includes("T")) return text.replace("T", " ").replace("Z", "").slice(0, 16);
			return text.slice(0, 16);
		}

		function getPreferredReferenceSource(exists) {
			for (const [layer, filename] of Object.entries(currentLayerFileMap || {})) {
				if (!currentReviewReferenceFiles.includes(filename)) continue;
				if (exists?.[layer]) return filename;
			}
			if (Array.isArray(currentReviewReferenceFiles) && currentReviewReferenceFiles.length === 0) return "";
			if (exists?.line) return "line.csv";
			if (exists?.fmm) return "fmm.csv";
			return "";
		}

		function getReviewBadgeHtml(review) {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) return "";
			if (!review || !review.decision) return "";
			return `<span class="review-badge ${escapeHtml(review.decision)}">${escapeHtml(getReviewDecisionLabel(review.decision))}</span>`;
		}

		function buildReviewCardMetaHtml(uid) {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) {
				const states = [...(getUidStatesFromPrecomputed(uid) || new Set())];
				const summary = states.length ? states.join(" / ") : "无预计算状态";
				return `<div class="triage-card-meta">${escapeHtml(summary)}</div>`;
			}
			const review = getReviewForUid(uid);
			if (!review) return `<div class="triage-card-meta">未审核</div>`;
			const timestamp = formatReviewTimestamp(review.timestamp) || "-";
			const reviewerName = review.reviewer_name || review.reviewer || review.reviewer_id || "";
			const reviewerCount = Number(reviewIndex?.aggregate_counts_by_uid?.[uid] || 0);
			const summary = [timestamp, reviewerName].filter(Boolean).join(" | ");
			const tags = getReviewTags(review);
			const tagLine = tags.length ? `<div class="triage-card-meta">Tag：${escapeHtml(tags.join(" / "))}</div>` : "";
			const notes = review.notes ? `<div class="triage-card-note">${escapeHtml(review.notes)}</div>` : "";
			return `
				<div class="triage-card-meta">${escapeHtml(summary || timestamp)}${reviewerCount > 1 ? ` | 多人 ${reviewerCount}` : ""}</div>
				${tagLine}
				${notes}
			`;
		}

		async function toggleReplayTimelineForReviewer(reviewerId, reviewerName = "") {
			const normalizedReviewerId = String(reviewerId || "").trim();
			if (!currentUid || !normalizedReviewerId) return false;
			if (isReplayTimelineActiveForReviewer(normalizedReviewerId)) {
				clearReplayTimelineState({ render: true });
				renderReviewAggregatePanel(currentUidAggregate);
				setReviewStatus("已退出 reviewer 分段回放", false);
				return true;
			}
			const loaded = await loadReplayTimelineAnnotationsForUid(currentUid, {
				reviewerId: normalizedReviewerId,
				reviewerName: String(reviewerName || "").trim() || normalizedReviewerId,
				batchName: currentBatchName,
			});
			renderReviewAggregatePanel(currentUidAggregate);
			if (loaded) {
				setReviewStatus(`正在回放 ${getReplayTimelineSourceLabel()} 的分段`, false);
			}
			return loaded;
		}

		function renderReviewAggregatePanel(aggregate = null) {
			if (!SHOW_REVIEW_AGGREGATE) {
				currentUidAggregate = null;
				return;
			}
			const summaryEl = document.getElementById("review-aggregate-summary");
			const listEl = document.getElementById("review-aggregate-list");
			const replayLabel = getReplayTimelineSourceLabel();
			currentUidAggregate = aggregate || null;
			if (!aggregate || !Array.isArray(aggregate.latest_reviews)) {
				summaryEl.textContent = currentUid
					? (replayLabel ? `当前 UID 暂无多人摘要 | 回放 ${replayLabel}` : "当前 UID 暂无多人摘要")
					: "选择 UID 后显示多人摘要";
				listEl.innerHTML = `<div class="review-aggregate-empty">暂无数据</div>`;
				syncReviewAggregateChrome(null);
				return;
			}
			const latestReviews = aggregate.latest_reviews || [];
			const decisionCounts = aggregate.decision_counts || {};
			const reviewerCount = Number(aggregate.reviewer_count || latestReviews.length || 0);
			summaryEl.textContent = reviewerCount
				? `已参与 ${reviewerCount} 人 | 保留 ${decisionCounts.accept || 0} / 排除 ${decisionCounts.reject || 0} / 跳过 ${decisionCounts.skip || 0}${replayLabel ? ` | 回放 ${replayLabel}` : ""}`
				: "当前 UID 暂无多人摘要";
			if (!latestReviews.length) {
				listEl.innerHTML = `<div class="review-aggregate-empty">暂无 reviewer 审核记录</div>`;
				syncReviewAggregateChrome(aggregate);
				return;
			}
			const timelineByReviewer = Object.fromEntries(
				(aggregate.timeline_annotation_summary || []).map(item => [item.reviewer_id, item])
			);
			listEl.innerHTML = latestReviews.map(item => {
				const timeline = timelineByReviewer[item.reviewer_id] || {};
				const replayActive = isReplayTimelineActiveForReviewer(item.reviewer_id);
				const timelineText = (timeline.pin_count || timeline.segment_count || timeline.window_quick_segment_count)
					? ` | pin ${timeline.pin_count || 0} / segment ${timeline.segment_count || 0}${timeline.window_quick_segment_count ? ` / quick ${timeline.window_quick_segment_count}` : ""}`
					: "";
				const referenceText = item.reference_source ? ` | ${item.reference_source}` : "";
				const tagText = getReviewTags(item).join(" / ");
				const tagHtml = tagText ? `<div class="review-aggregate-note">Tag：${escapeHtml(tagText)}</div>` : "";
				const notes = item.notes ? `<div class="review-aggregate-note">${escapeHtml(item.notes)}</div>` : "";
				const replayButtonHtml = item.reviewer_id ? `
					<div class="review-aggregate-actions">
						<button
							type="button"
							class="review-aggregate-replay-btn${replayActive ? " active" : ""}"
							data-replay-reviewer-id="${escapeHtml(item.reviewer_id || "")}"
							data-replay-reviewer-name="${escapeHtml(item.reviewer_name || item.reviewer || item.reviewer_id || "")}"
						>${replayActive ? "关闭回放" : "回放分段"}</button>
					</div>
				` : "";
				return `
					<div class="review-aggregate-item">
						<div class="review-aggregate-item-top">
							<div class="review-aggregate-name">${escapeHtml(item.reviewer_name || item.reviewer || item.reviewer_id || "-")}</div>
							<div>${getReviewBadgeHtml(item)}</div>
						</div>
						<div class="review-aggregate-meta">${escapeHtml(formatReviewTimestamp(item.timestamp) || "-")}${escapeHtml(referenceText)}${escapeHtml(timelineText)}</div>
						${replayButtonHtml}
						${tagHtml}
						${notes}
					</div>
				`;
			}).join("");
			syncReviewAggregateChrome(aggregate);
		}

		async function loadReviewAggregateForUid(uid) {
			if (!SHOW_REVIEW_AGGREGATE || !uid || currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel || !reviewApiAvailable) {
				renderReviewAggregatePanel(null);
				return;
			}
			try {
				const response = await fetch(buildReviewApiUrl("/reviews/aggregate", { uid }));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				if (!reviewIndex.aggregate_counts_by_uid) reviewIndex.aggregate_counts_by_uid = {};
				reviewIndex.aggregate_counts_by_uid[uid] = Number(payload.aggregate?.reviewer_count || 0);
				renderReviewAggregatePanel(payload.aggregate || null);
			} catch (_) {
				renderReviewAggregatePanel(null);
			}
		}

		function updateReviewMeta(review, fallbackReferenceSource) {
			const meta = document.getElementById("review-meta");
			const uidText = currentUid ? `UID：${currentUid}` : "UID：未选择";
			const reviewerName = getCurrentReviewerName() || "-";
			const aggregateText = SHOW_REVIEW_AGGREGATE && currentUidAggregate?.reviewer_count
				? ` | 多人 ${currentUidAggregate.reviewer_count}`
				: "";
			const replayText = getReplayTimelineSourceLabel() ? ` | 回放 ${getReplayTimelineSourceLabel()}` : "";
			if (!review) {
				meta.textContent = `${uidText} | 当前标注者：${reviewerName} | 当前状态：未设置 | 时间：- | Tag：无 | 参考图层：${fallbackReferenceSource || "未设置"}${aggregateText}${replayText}`;
				return;
			}
			const timestamp = formatReviewTimestamp(review.timestamp) || "-";
			const ref = review.reference_source || fallbackReferenceSource || "未设置";
			const tagText = getReviewTags(review).join(" / ") || "无";
			meta.textContent = `${uidText} | 当前标注者：${reviewerName} | 当前状态：${getReviewDecisionLabel(review.decision)} | 时间：${timestamp} | Tag：${tagText} | 参考图层：${ref}${aggregateText}${replayText}`;
		}

		function populateReviewForm(uid, exists, review) {
			const preferredReferenceSource = review?.reference_source || getPreferredReferenceSource(exists);
			const selectedTag = getReviewTags(review)[0] || "";
			document.getElementById("review-current").textContent = uid ? `当前 UID：${uid}` : "请选择 UID 后保存 `accept / reject / skip`。";
			document.getElementById("reviewer-identity-value").textContent = getCurrentReviewerName() || "未设置";
			document.getElementById("reference-source-input").value = preferredReferenceSource || "";
			document.getElementById("review-notes").value = review?.notes || "";
			renderReviewTagOptions(selectedTag);
			setDecisionButtons(review?.decision || "", { silent: true });
			updateReviewMeta(review, preferredReferenceSource);
			markReviewPristine();
		}

		async function loadReviewIndex() {
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) {
				reviewApiAvailable = false;
				reviewIndex = { reviews: {}, counts: {}, aggregate_counts_by_uid: {} };
				return;
			}
			const reviewerReady = await ensureReviewerSessionReady({ prompt: true });
			if (!reviewerReady) {
				reviewApiAvailable = false;
				reviewIndex = { reviews: {}, counts: {}, aggregate_counts_by_uid: {} };
				setReviewStatus("请先设置标注者身份", true);
				if (uidList.length) await refreshFilteredUids({ resetVisibleCounts: false });
				return;
			}
			try {
				const response = await fetch(buildReviewApiUrl("/reviews", buildReviewerScopedParams()));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				reviewIndex = await response.json();
				reviewApiAvailable = true;
				setReviewStatus(`审核接口：已连接 | 当前 reviewer ${getCurrentReviewerName()}`, false);
			} catch (_) {
				reviewApiAvailable = false;
				reviewIndex = { reviews: {}, counts: {}, aggregate_counts_by_uid: {} };
				setReviewStatus("审核接口：未连接（请使用 review_server.py）", true);
			}
			if (uidList.length) await refreshFilteredUids({ resetVisibleCounts: false });
		}

		async function loadReviewForUid(uid, exists) {
			if (!uid) return;
			if (currentUiConfig.annotationEnabled === false || currentUiConfig.hideReviewPanel) {
				populateReviewForm(uid, exists, null);
				return;
			}
			if (!reviewApiAvailable) {
				populateReviewForm(uid, exists, getReviewForUid(uid));
				await loadReviewAggregateForUid(uid);
				return;
			}
			try {
				const response = await fetch(buildReviewApiUrl("/reviews", buildReviewerScopedParams({ uid })));
				if (!response.ok) throw new Error(`HTTP ${response.status}`);
				const payload = await response.json();
				const review = payload.review || null;
				if (review) reviewIndex.reviews[uid] = review;
				else delete reviewIndex.reviews[uid];
				await loadReviewAggregateForUid(uid);
				populateReviewForm(uid, exists, review);
				renderTriageBoard({ resetVisibleCounts: false });
			} catch (_) {
				populateReviewForm(uid, exists, getReviewForUid(uid));
				await loadReviewAggregateForUid(uid);
				setReviewStatus("审核接口：读取失败", true);
			}
		}

		let reviewSaveToastTimerId = 0;

		function showReviewSaveToast(decision) {
			const el = document.getElementById("review-save-toast");
			if (!el) return;
			const key = String(decision || "").trim().toLowerCase();
			const labels = window.TrajectoryStudioBootstrap?.REVIEW_DECISION_LABELS;
			const label = labels?.[key];
			if (!label) return;
			el.textContent = `已保存——${label}`;
			el.classList.add("review-save-toast--visible");
			if (reviewSaveToastTimerId) window.clearTimeout(reviewSaveToastTimerId);
			reviewSaveToastTimerId = window.setTimeout(() => {
				el.classList.remove("review-save-toast--visible");
				reviewSaveToastTimerId = 0;
			}, 2000);
		}

		async function saveReview() {
			if (!currentUid) {
				setReviewStatus("请先选择 UID", true);
				return;
			}
			if (!selectedDecision) {
				setReviewStatus("请先选择 accept / reject / skip", true);
				return;
			}
			if (!getCurrentReviewerId()) {
				openReviewerSessionModal({ required: true });
				setReviewStatus("请先设置标注者身份", true);
				return;
			}
			const decisionForToast = selectedDecision;
			const notes = document.getElementById("review-notes").value.trim();
			const referenceSource = document.getElementById("reference-source-input").value.trim();
			const trajectoryTags = getSelectedReviewTag() ? [getSelectedReviewTag()] : [];
			if (!reviewApiAvailable) {
				setReviewStatus("审核接口：未连接，无法保存", true);
				return;
			}
			try {
				const savedUid = currentUid;
				const response = await fetch(buildReviewApiUrl("/reviews"), {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						uid: savedUid,
						sample_id: savedUid,
						decision: selectedDecision,
						reviewer_id: getCurrentReviewerId(),
						reviewer_name: getCurrentReviewerName(),
						notes,
						reference_source: referenceSource,
						trajectory_tags: trajectoryTags,
					})
				});
				if (!response.ok) {
					const text = await response.text();
					throw new Error(text || `HTTP ${response.status}`);
				}
				const payload = await response.json();
				const review = payload.review || null;
				if (review) reviewIndex.reviews[savedUid] = review;
				showReviewSaveToast(decisionForToast);
				await loadReviewAggregateForUid(savedUid);
				const meta = await ensureUidMeta(savedUid);
				populateReviewForm(savedUid, meta.exists, review);
				await refreshFilteredUids({ resetVisibleCounts: false });
				const nextPendingUid = getNextPendingUid(savedUid);
				if (nextPendingUid) {
					await selectUid(nextPendingUid, { skipDirtyCheck: true });
					setReviewStatus("审核结果已保存并跳转到下一条待审", false);
				} else {
					renderTriageBoard({ resetVisibleCounts: false });
					updatePendingNavigation();
					setReviewStatus("审核结果已保存，当前筛选结果中已无待审", false);
				}
			} catch (error) {
				setReviewStatus(`审核保存失败：${error.message || error}`, true);
			}
		}
