		function setStudioManagementBusy(busy) {
			studioManagementState.busy = !!busy;
			const uploadButton = document.getElementById("studio-management-upload-btn");
			const uploadProcessButton = document.getElementById("studio-management-upload-process-btn");
			const refreshButton = document.getElementById("studio-management-refresh-btn");
			const resetButton = document.getElementById("studio-management-reset-btn");
			const exportDownloadButton = document.getElementById("studio-export-download-btn");
			const exportDatasetButton = document.getElementById("studio-export-dataset-btn");
			if (uploadButton) uploadButton.disabled = studioManagementState.busy;
			if (uploadProcessButton) uploadProcessButton.disabled = studioManagementState.busy;
			if (refreshButton) refreshButton.disabled = studioManagementState.busy;
			if (resetButton) resetButton.disabled = studioManagementState.busy;
			if (exportDownloadButton) exportDownloadButton.disabled = studioManagementState.busy;
			if (exportDatasetButton) exportDatasetButton.disabled = studioManagementState.busy;
			renderStudioExportActionButtons();
			renderStudioManagementProgress();
		}

		function stopStudioExportDatasetButtonProgress() {
			if (!studioManagementState.exportDatasetProgressTimerId) return;
			window.clearInterval(studioManagementState.exportDatasetProgressTimerId);
			studioManagementState.exportDatasetProgressTimerId = 0;
		}

		function stopStudioExportDatasetButtonProgressReset() {
			if (!studioManagementState.exportDatasetProgressResetTimerId) return;
			window.clearTimeout(studioManagementState.exportDatasetProgressResetTimerId);
			studioManagementState.exportDatasetProgressResetTimerId = 0;
		}

		function renderStudioExportActionButtons() {
			const exportDatasetButton = document.getElementById("studio-export-dataset-btn");
			if (!exportDatasetButton) return;
			const active = !!studioManagementState.exportDatasetProgressActive;
			const percent = Math.max(0, Math.min(100, Math.round(studioManagementState.exportDatasetProgressPercent || 0)));
			exportDatasetButton.dataset.progressActive = active ? "true" : "false";
			exportDatasetButton.style.setProperty("--studio-btn-progress", `${percent}%`);
			exportDatasetButton.textContent = active ? `最小 GPS 导出 ${percent}%` : "最小 GPS 导出";
			exportDatasetButton.setAttribute("aria-busy", active ? "true" : "false");
		}

		function formatSignal6AlgorithmProfile(value) {
			const normalized = String(value || "").trim().toLowerCase().replace(/[-.]/g, "_");
			const labels = {
				baseline_v311: "v311 基线",
				mainroad_weighted: "主路加权",
				major_roads: "主干道优先",
				speed_sparsity_90: "90%展示算法",
			};
			return labels[normalized] || (normalized ? normalized : "-");
		}

		function resetStudioExportDatasetButtonProgress() {
			stopStudioExportDatasetButtonProgress();
			stopStudioExportDatasetButtonProgressReset();
			studioManagementState.exportDatasetProgressActive = false;
			studioManagementState.exportDatasetProgressPercent = 0;
			renderStudioExportActionButtons();
		}

		function scheduleStudioExportDatasetButtonProgressReset(delayMs = 0) {
			stopStudioExportDatasetButtonProgress();
			stopStudioExportDatasetButtonProgressReset();
			const normalizedDelay = Math.max(0, Number(delayMs) || 0);
			if (!normalizedDelay) {
				resetStudioExportDatasetButtonProgress();
				return;
			}
			studioManagementState.exportDatasetProgressResetTimerId = window.setTimeout(() => {
				studioManagementState.exportDatasetProgressResetTimerId = 0;
				studioManagementState.exportDatasetProgressActive = false;
				studioManagementState.exportDatasetProgressPercent = 0;
				renderStudioExportActionButtons();
			}, normalizedDelay);
		}

		function startStudioExportDatasetButtonProgress() {
			stopStudioExportDatasetButtonProgress();
			stopStudioExportDatasetButtonProgressReset();
			studioManagementState.exportDatasetProgressActive = true;
			studioManagementState.exportDatasetProgressPercent = 8;
			renderStudioExportActionButtons();
			studioManagementState.exportDatasetProgressTimerId = window.setInterval(() => {
				const currentPercent = Number(studioManagementState.exportDatasetProgressPercent) || 0;
				if (currentPercent >= 94) return;
				studioManagementState.exportDatasetProgressPercent = Math.min(
					94,
					currentPercent + Math.max(2, (94 - currentPercent) * 0.16),
				);
				renderStudioExportActionButtons();
			}, 180);
		}

		function setStudioManagementFlash(kind, message) {
			const flash = document.getElementById("studio-management-flash");
			if (!flash) return;
			flash.className = kind ? `${kind} visible` : "";
			flash.textContent = message || "";
		}

		function clearStudioManagementFlash() {
			setStudioManagementFlash("", "");
		}

		function stopStudioManagementProgressSimulation() {
			if (!studioManagementState.progressTimerId) return;
			window.clearInterval(studioManagementState.progressTimerId);
			studioManagementState.progressTimerId = 0;
		}

		function renderStudioManagementProgress() {
			const progress = document.getElementById("studio-management-progress");
			const title = document.getElementById("studio-management-progress-title");
			const percent = document.getElementById("studio-management-progress-percent");
			const bar = document.getElementById("studio-management-progress-bar");
			const detail = document.getElementById("studio-management-progress-detail");
			if (!progress || !title || !percent || !bar || !detail) return;
			progress.classList.toggle("visible", !!studioManagementState.progressVisible);
			progress.dataset.tone = studioManagementState.progressTone || "info";
			progress.dataset.busy = studioManagementState.busy ? "true" : "false";
			progress.setAttribute("aria-busy", studioManagementState.busy ? "true" : "false");
			title.textContent = studioManagementState.progressTitle || "等待上传";
			const clampedPercent = Math.max(0, Math.min(100, Math.round(studioManagementState.progressPercent || 0)));
			percent.textContent = `${clampedPercent}%`;
			bar.style.width = `${clampedPercent}%`;
			bar.setAttribute("aria-valuenow", String(clampedPercent));
			bar.setAttribute("aria-valuetext", `${studioManagementState.progressTitle || "等待上传"} ${clampedPercent}%`);
			detail.textContent = studioManagementState.progressDetail || "选择文件后可以看到上传与处理进度。";
		}

		function setStudioManagementProgress(next = {}) {
			if (Object.prototype.hasOwnProperty.call(next, "visible")) {
				studioManagementState.progressVisible = !!next.visible;
			}
			if (Object.prototype.hasOwnProperty.call(next, "percent")) {
				studioManagementState.progressPercent = Math.max(0, Math.min(100, Number(next.percent) || 0));
			}
			if (Object.prototype.hasOwnProperty.call(next, "title")) {
				studioManagementState.progressTitle = String(next.title || "").trim() || "等待上传";
			}
			if (Object.prototype.hasOwnProperty.call(next, "detail")) {
				studioManagementState.progressDetail = String(next.detail || "").trim() || "选择文件后可以看到上传与处理进度。";
			}
			if (Object.prototype.hasOwnProperty.call(next, "tone")) {
				studioManagementState.progressTone = String(next.tone || "").trim() || "info";
			}
			renderStudioManagementProgress();
		}

		function clearStudioManagementProgress(options = {}) {
			stopStudioManagementProgressSimulation();
			studioManagementState.progressVisible = options.visible === true;
			studioManagementState.progressPercent = 0;
			studioManagementState.progressTitle = "等待上传";
			studioManagementState.progressDetail = "选择文件后可以看到上传与处理进度。";
			studioManagementState.progressTone = "info";
			renderStudioManagementProgress();
		}

		function startStudioManagementProcessProgress(uploadId) {
			stopStudioManagementProgressSimulation();
			studioManagementState.progressVisible = true;
			studioManagementState.progressTone = "info";
			studioManagementState.progressTitle = "后端处理中";
			studioManagementState.progressDetail = `正在处理 ${uploadId}，完成后会自动刷新上传列表和批次列表。`;
			studioManagementState.progressPercent = 74;
			renderStudioManagementProgress();
			studioManagementState.progressTimerId = window.setInterval(() => {
				const currentPercent = Number(studioManagementState.progressPercent) || 0;
				if (currentPercent >= 96) return;
				studioManagementState.progressPercent = Math.min(96, currentPercent + Math.max(1.2, (96 - currentPercent) * 0.18));
				renderStudioManagementProgress();
			}, 260);
		}

		function getStudioManagementUploadType() {
			const uploadTypeInput = document.getElementById("studio-management-upload-type");
			return String(uploadTypeInput?.value || "trajectory4").trim().toLowerCase();
		}

		function getStudioManagementFormatSpec() {
			return STUDIO_ADMIN_CORE.getFormatSpec(getStudioManagementUploadType());
		}

		function buildStudioManagementHelpHtml(spec) {
			return STUDIO_ADMIN_CORE.buildHelpHtml(spec, { escapeHtml });
		}

		function renderStudioManagementHelp() {
			const popover = document.getElementById("studio-management-help-popover");
			if (!popover) return;
			popover.innerHTML = buildStudioManagementHelpHtml(getStudioManagementFormatSpec());
			syncStudioManagementHelpUi();
		}

		function syncStudioManagementHelpUi() {
			const helpPanel = document.getElementById("studio-management-help-popover");
			const trigger = document.getElementById("studio-management-help-trigger");
			const anchor = document.getElementById("studio-management-help-anchor");
			if (helpPanel) helpPanel.classList.toggle("collapsed", !studioManagementState.helpVisible);
			if (helpPanel) helpPanel.setAttribute("aria-hidden", studioManagementState.helpVisible ? "false" : "true");
			if (trigger) trigger.setAttribute("aria-expanded", studioManagementState.helpVisible ? "true" : "false");
			if (anchor) anchor.classList.toggle("pinned", !!studioManagementState.helpPinned);
		}

		function setStudioManagementHelpVisibility(visible, options = {}) {
			studioManagementState.helpVisible = !!visible;
			if (Object.prototype.hasOwnProperty.call(options, "pinned")) {
				studioManagementState.helpPinned = !!options.pinned;
			}
			if (!studioManagementState.helpVisible) {
				studioManagementState.helpPinned = false;
			}
			if (studioManagementState.helpPinned) {
				studioManagementState.helpVisible = true;
			}
			syncStudioManagementHelpUi();
		}

		function setStudioManagementHelpPinned(pinned) {
			setStudioManagementHelpVisibility(!!pinned, { pinned });
		}

		function getStudioManagementCustomFieldStore(uploadType = getStudioManagementUploadType()) {
			const normalizedType = String(uploadType || "trajectory4").trim().toLowerCase();
			if (!studioManagementState.customFieldMappings[normalizedType]) {
				studioManagementState.customFieldMappings[normalizedType] = {};
			}
			return studioManagementState.customFieldMappings[normalizedType];
		}

		function buildStudioManagementCustomFieldHtml(spec, mapping = {}) {
			const normalizedSpec = spec && typeof spec === "object" ? spec : getStudioManagementFormatSpec();
			const fieldCards = (normalizedSpec.fields || []).map(field => `
				<label class="studio-management-custom-field-card${field.required ? " required" : ""}">
					<div class="studio-management-custom-field-top">
						<span class="studio-management-custom-field-name">${escapeHtml(field.name || field.key || "-")}</span>
						<span class="studio-management-custom-field-badge">${field.required ? "必填" : "可选"}</span>
					</div>
					<input
						class="studio-management-input studio-management-custom-field-input"
						type="text"
						data-studio-field-key="${escapeHtml(field.key || "")}"
						value="${escapeHtml(mapping[field.key] || "")}"
						placeholder="${escapeHtml(field.placeholder || "填写你文件里的列名")}"
					/>
					<div class="studio-management-custom-field-meta">${escapeHtml(field.type || "-")}</div>
					${Array.isArray(field.accepted) && field.accepted.length
						? `<div class="studio-management-custom-field-hint">默认兼容：${escapeHtml(field.accepted.join(" / "))}</div>`
						: ""}
				</label>
			`).join("");
			return `
				<div class="studio-management-custom-fields-shell">
					<div class="studio-management-custom-fields-head">
						<div class="studio-management-custom-fields-title">自定义字段映射</div>
						<div class="studio-management-custom-fields-copy">只有当你的列名不在默认兼容范围内时才需要填写。留空会继续使用预置别名。</div>
					</div>
					<div class="studio-management-custom-fields-grid">${fieldCards}</div>
				</div>
			`;
		}

		function renderStudioManagementCustomFields() {
			const panel = document.getElementById("studio-management-custom-fields");
			const toggle = document.getElementById("studio-management-custom-fields-toggle");
			if (!panel || !toggle) return;
			const uploadType = getStudioManagementUploadType();
			const spec = getStudioManagementFormatSpec();
			if (spec && spec.customMappingDisabled) {
				panel.innerHTML = `
					<div class="studio-management-custom-fields-shell">
						<div class="studio-management-custom-fields-head">
							<div class="studio-management-custom-fields-title">固定文件名</div>
							<div class="studio-management-custom-fields-copy">多源轨迹包按 signal.csv / gate.csv / lbs.csv / gps.csv 读取，不需要字段映射配置。</div>
						</div>
					</div>
				`;
				studioManagementState.customFieldsExpanded = false;
				panel.classList.add("collapsed");
				panel.setAttribute("aria-hidden", "true");
				toggle.setAttribute("aria-expanded", "false");
				toggle.disabled = true;
				toggle.textContent = "无需映射";
				return;
			}
			toggle.disabled = false;
			panel.innerHTML = buildStudioManagementCustomFieldHtml(spec, getStudioManagementCustomFieldStore(uploadType));
			panel.classList.toggle("collapsed", !studioManagementState.customFieldsExpanded);
			panel.setAttribute("aria-hidden", studioManagementState.customFieldsExpanded ? "false" : "true");
			toggle.setAttribute("aria-expanded", studioManagementState.customFieldsExpanded ? "true" : "false");
			toggle.textContent = studioManagementState.customFieldsExpanded ? "收起自定义" : "自定义字段";
		}

		function setStudioManagementCustomFieldsExpanded(expanded) {
			studioManagementState.customFieldsExpanded = !!expanded;
			renderStudioManagementCustomFields();
		}

		function getStudioManagementFieldMappingForSubmit(uploadType = getStudioManagementUploadType()) {
			if (String(uploadType || "").trim().toLowerCase() === "signal_triplet") return undefined;
			if (!studioManagementState.customFieldsExpanded) return undefined;
			const mapping = getStudioManagementCustomFieldStore(uploadType);
			const normalizedEntries = Object.entries(mapping).filter(([, value]) => String(value || "").trim());
			if (!normalizedEntries.length) return undefined;
			return Object.fromEntries(normalizedEntries.map(([key, value]) => [key, String(value || "").trim()]));
		}

		function resetStudioManagementForm(options = {}) {
			const uploadTypeInput = document.getElementById("studio-management-upload-type");
			const signal6AlgorithmProfileInput = document.getElementById("studio-management-signal6-algorithm-profile");
			const visibilityScopeInput = document.getElementById("studio-management-visibility-scope");
			const annotationModeInput = document.getElementById("studio-management-annotation-mode");
			const displayNameInput = document.getElementById("studio-management-display-name");
			const uploadFileInput = document.getElementById("studio-management-upload-file");
			if (uploadTypeInput) uploadTypeInput.value = "auto";
			if (signal6AlgorithmProfileInput) signal6AlgorithmProfileInput.value = "speed_sparsity_90";
			if (visibilityScopeInput) visibilityScopeInput.value = "private";
			if (annotationModeInput) annotationModeInput.value = "annotatable";
			if (displayNameInput) displayNameInput.value = "";
			if (uploadFileInput) uploadFileInput.value = "";
			studioManagementState.customFieldsExpanded = false;
			studioManagementState.customFieldMappings = { trajectory4: {}, signal6: {}, signal_triplet: {} };
			if (options.clearFlash !== false) clearStudioManagementFlash();
			if (options.clearProgress !== false) clearStudioManagementProgress();
			setStudioManagementHelpVisibility(false, { pinned: false });
			renderStudioManagementHelp();
			renderStudioManagementCustomFields();
		}

		function getStudioManagementFormPayload() {
			const visibilityScopeInput = document.getElementById("studio-management-visibility-scope");
			const annotationModeInput = document.getElementById("studio-management-annotation-mode");
			const displayNameInput = document.getElementById("studio-management-display-name");
			const uploadFileInput = document.getElementById("studio-management-upload-file");
			const signal6AlgorithmProfileInput = document.getElementById("studio-management-signal6-algorithm-profile");
			const uploadType = getStudioManagementUploadType();
			const files = Array.from(uploadFileInput?.files || []).filter(Boolean);
			const displayName = displayNameInput?.value?.trim() || "";
			return {
				files,
				body: {
					upload_type: uploadType,
					visibility_scope: visibilityScopeInput?.value || "private",
					annotation_mode: annotationModeInput?.value || "annotatable",
					signal6_algorithm_profile: signal6AlgorithmProfileInput?.value || "speed_sparsity_90",
					display_name: files.length === 1 ? displayName || undefined : undefined,
					original_name: files.length === 1 ? files[0].name : undefined,
					field_mapping: getStudioManagementFieldMappingForSubmit(uploadType),
				},
			};
		}

		function renderStudioManagementActor() {
			const actorBadge = document.getElementById("studio-management-actor-badge");
			const actorName = document.getElementById("studio-management-actor-name");
			const actorDescription = document.getElementById("studio-management-actor-description");
			const actorId = document.getElementById("studio-management-actor-id");
			const actorRole = document.getElementById("studio-management-actor-role");
			if (!studioManagementState.actor) {
				if (actorBadge) actorBadge.textContent = "?";
				if (actorName) actorName.textContent = "未加载";
				if (actorDescription) actorDescription.textContent = "打开面板后自动读取当前请求身份。";
				if (actorId) actorId.textContent = "-";
				if (actorRole) actorRole.textContent = "-";
				return;
			}
			if (actorBadge) actorBadge.textContent = studioManagementState.actor.name.slice(0, 1).toUpperCase();
			if (actorName) actorName.textContent = studioManagementState.actor.name;
			if (actorDescription) {
				actorDescription.textContent = studioManagementState.actor.description || "上传、处理与批次操作都会使用这一身份。";
			}
			if (actorId) actorId.textContent = studioManagementState.actor.id;
			if (actorRole) actorRole.textContent = studioManagementState.actor.role;
		}

		function studioManagementUploadCanProcess(upload) {
			const status = String(upload?.status || "").toLowerCase();
			if (!upload?.uploadId) return false;
			return !status.includes("process")
				&& !status.includes("publish")
				&& !status.includes("complete")
				&& !status.includes("delete");
		}

		function studioManagementUploadCanOpen(upload) {
			const status = String(upload?.status || "").toLowerCase();
			return Boolean(upload?.batchName)
				&& (
					status.includes("publish")
					|| status.includes("complete")
					|| status.includes("asset_ready")
					|| status.includes("preview_ready")
				);
		}

		function isStudioManagementVisibleUpload(upload) {
			const status = String(upload?.status || "").trim().toLowerCase();
			return !status.includes("delete");
		}

		function renderStudioManagementUploads() {
			const uploadsList = document.getElementById("studio-management-uploads-list");
			const uploadCount = document.getElementById("studio-management-upload-count");
			const lastRefresh = document.getElementById("studio-management-last-refresh");
			if (!uploadsList || !uploadCount || !lastRefresh) return;
			const visibleUploads = studioManagementState.uploads.filter(isStudioManagementVisibleUpload);
			uploadCount.textContent = `${visibleUploads.length} 条上传`;
			lastRefresh.textContent = studioManagementState.lastRefreshAt
				? `上次刷新：${studioManagementState.lastRefreshAt}`
				: "尚未刷新";
			if (!visibleUploads.length) {
				uploadsList.innerHTML = `<div class="studio-management-empty">当前还没有上传记录。你可以通过右侧悬浮上传按钮进入这里，新建上传后再继续处理和打开批次。</div>`;
				return;
			}
			uploadsList.innerHTML = visibleUploads.map(upload => `
				<article class="studio-upload-item">
					<div class="studio-upload-top">
						<div class="studio-upload-title-wrap">
							<div class="studio-upload-name">${escapeHtml(upload.displayName)}</div>
							<div class="studio-upload-subline">
								<div class="studio-upload-id">Upload ID · ${escapeHtml(upload.uploadId || "-")}</div>
								${upload.batchName ? `<div class="studio-upload-batch">Batch · ${escapeHtml(upload.batchName)}</div>` : ""}
							</div>
						</div>
						<div class="studio-upload-chips">
							<span class="studio-upload-chip ${escapeHtml(upload.statusClass)}">${escapeHtml(upload.status || "created")}</span>
							<span class="studio-upload-chip">${escapeHtml(upload.uploadType)}</span>
							${upload.signal6AlgorithmProfile ? `<span class="studio-upload-chip">${escapeHtml(upload.signal6AlgorithmProfileLabel || upload.signal6AlgorithmProfile)}</span>` : ""}
							<span class="studio-upload-chip">${escapeHtml(upload.visibilityLabel)}</span>
							<span class="studio-upload-chip">${escapeHtml(upload.annotationModeLabel)}</span>
							${upload.hasCustomFieldMapping ? `<span class="studio-upload-chip">自定义字段 ${escapeHtml(String(upload.customFieldCount || 0))}</span>` : ""}
						</div>
					</div>
					<div class="studio-upload-meta-grid">
						<div class="studio-upload-meta-card">
							<div class="studio-upload-meta-label">原始文件</div>
							<div class="studio-upload-meta-value">${escapeHtml(upload.originalName)}</div>
						</div>
						<div class="studio-upload-meta-card">
							<div class="studio-upload-meta-label">文件大小</div>
							<div class="studio-upload-meta-value">${escapeHtml(formatBytes(upload.sizeBytes))}</div>
						</div>
						<div class="studio-upload-meta-card">
							<div class="studio-upload-meta-label">创建时间</div>
							<div class="studio-upload-meta-value">${escapeHtml(formatStudioDateTime(upload.createdAt))}</div>
						</div>
						<div class="studio-upload-meta-card">
							<div class="studio-upload-meta-label">最近状态时间</div>
							<div class="studio-upload-meta-value">${escapeHtml(formatStudioDateTime(upload.updatedAt))}</div>
						</div>
					</div>
					${upload.note ? `<div class="studio-upload-note">${escapeHtml(upload.note)}</div>` : ""}
					${upload.errorText ? `<div class="studio-upload-error">${escapeHtml(upload.errorText)}</div>` : ""}
					<div class="studio-upload-actions">
						<button class="studio-management-btn" type="button" data-studio-action="process" data-upload-id="${escapeHtml(upload.uploadId || "")}" ${studioManagementUploadCanProcess(upload) ? "" : "disabled"}>触发处理</button>
						<button class="studio-management-btn primary" type="button" data-studio-action="open-batch" data-batch-name="${escapeHtml(upload.batchName || "")}" ${studioManagementUploadCanOpen(upload) ? "" : "disabled"}>打开批次</button>
						<button class="studio-management-btn danger" type="button" data-studio-action="delete" data-upload-id="${escapeHtml(upload.uploadId || "")}" ${upload.uploadId ? "" : "disabled"}>删除</button>
					</div>
				</article>
			`).join("");
		}

		function getStudioManagementWorkspaceAnchor(workspace = "upload") {
			return document.getElementById(workspace === "export" ? "studio-export-section" : "studio-upload-section");
		}

		function getStudioManagementWorkspaceScrollOwner() {
			if (typeof window?.matchMedia === "function" && window.matchMedia("(max-width: 980px)").matches) {
				return document.getElementById("studio-management-body");
			}
			return document.getElementById("studio-management-sidebar") || document.getElementById("studio-management-body");
		}

		function syncStudioManagementChrome() {
			const overlay = document.getElementById("studio-management-overlay");
			const body = document.getElementById("studio-management-body");
			const entry = document.getElementById("studio-management-entry");
			const exportEntry = document.getElementById("studio-export-entry");
			const uploadSection = document.getElementById("studio-upload-section");
			const exportSection = document.getElementById("studio-export-section");
			const isOpen = overlay?.classList.contains("open");
			const activeWorkspace = studioManagementState.exportActiveWorkspace === "export" ? "export" : "upload";
			const isUploadActive = activeWorkspace === "upload";
			const isExportActive = activeWorkspace === "export";
			if (overlay) overlay.dataset.activeWorkspace = activeWorkspace;
			if (body) body.dataset.activeWorkspace = activeWorkspace;
			if (uploadSection) {
				uploadSection.dataset.workspaceActive = isUploadActive ? "true" : "false";
				uploadSection.hidden = !isUploadActive;
				uploadSection.setAttribute("aria-hidden", isUploadActive ? "false" : "true");
			}
			if (exportSection) {
				exportSection.dataset.workspaceActive = isExportActive ? "true" : "false";
				exportSection.hidden = !isExportActive;
				exportSection.setAttribute("aria-hidden", isExportActive ? "false" : "true");
			}
			if (entry) {
				const isActive = !!isOpen && isUploadActive;
				entry.classList.toggle("active", isActive);
				entry.setAttribute("aria-expanded", isOpen ? "true" : "false");
				entry.setAttribute("aria-pressed", isActive ? "true" : "false");
			}
			if (exportEntry) {
				const isActive = !!isOpen && isExportActive;
				exportEntry.classList.toggle("active", isActive);
				exportEntry.setAttribute("aria-expanded", isOpen ? "true" : "false");
				exportEntry.setAttribute("aria-pressed", isActive ? "true" : "false");
			}
		}

		async function loadStudioManagementActor() {
			studioManagementState.actor = await STUDIO_ADMIN_CORE.fetchActor(apiFetchJson);
			renderStudioManagementActor();
			return studioManagementState.actor;
		}

		async function loadStudioManagementUploads(options = {}) {
			studioManagementState.uploads = await STUDIO_ADMIN_CORE.fetchUploads(apiFetchJson, {
				formatVisibilityScope: formatStudioVisibilityScope,
				formatAnnotationMode: formatStudioAnnotationMode,
				formatSignal6AlgorithmProfile,
			});
			studioManagementState.lastRefreshAt = new Date().toLocaleString("zh-CN", { hour12: false });
			renderStudioManagementUploads();
			if (!options.silent) {
				setStudioManagementFlash("info", `已同步 ${studioManagementState.uploads.length} 条上传记录。`);
			}
			return studioManagementState.uploads;
		}

		async function createStudioManagementUploadRecord(body) {
			return STUDIO_ADMIN_CORE.createUploadRecord(apiFetchJson, body);
		}

		function parseStudioManagementRawPayload(rawText) {
			return STUDIO_ADMIN_CORE.parseRawPayload(rawText);
		}

		async function uploadStudioManagementBlob(uploadId, file, options = {}) {
			return STUDIO_ADMIN_CORE.uploadBlob({ pickFirstString, XMLHttpRequest }, uploadId, file, options);
		}

		async function processStudioManagementUpload(uploadId, options = {}) {
			if (!uploadId) throw new Error("缺少 upload id，无法触发处理。");
			startStudioManagementProcessProgress(uploadId);
			setStudioManagementFlash("info", `正在触发处理：${uploadId}`);
			try {
				await apiFetchJson(`/api/uploads/${encodeURIComponent(uploadId)}/process`, { method: "POST" });
				stopStudioManagementProgressSimulation();
				setStudioManagementProgress({
					visible: true,
					percent: 98,
					title: "正在同步结果",
					detail: `后端处理已返回，正在刷新上传记录和批次列表：${uploadId}`,
					tone: "info",
				});
				await loadStudioManagementUploads({ silent: true });
				await loadStudioExportBatches();
				await refreshBatchListPreservingCurrent({ preferredBatchName: currentBatchName || "" });
				setStudioManagementProgress({
					visible: true,
					percent: 100,
					title: "处理完成",
					detail: options.successDetail || `上传 ${uploadId} 已处理完成，可以直接打开对应 batch。`,
					tone: "success",
				});
				setStudioManagementFlash("success", `已触发处理：${uploadId}`);
			} catch (error) {
				stopStudioManagementProgressSimulation();
				try {
					await loadStudioManagementUploads({ silent: true });
					await loadStudioExportBatches();
					await refreshBatchListPreservingCurrent({ preferredBatchName: currentBatchName || "" });
				} catch (_) {
					// Keep the original processing error as the primary signal.
				}
				setStudioManagementProgress({
					visible: true,
					percent: Math.max(74, studioManagementState.progressPercent || 74),
					title: "处理失败",
					detail: String(error?.message || error),
					tone: "error",
				});
				throw error;
			}
		}

		async function deleteStudioManagementUpload(uploadId) {
			if (!uploadId) throw new Error("缺少 upload id，无法删除。");
			if (!window.confirm(`确认删除上传 ${uploadId} 吗？`)) return;
			setStudioManagementFlash("info", `正在删除：${uploadId}`);
			await apiFetchJson(`/api/uploads/${encodeURIComponent(uploadId)}`, { method: "DELETE" });
			studioManagementState.uploads = studioManagementState.uploads.filter(upload => upload.uploadId !== uploadId);
			renderStudioManagementUploads();
			await loadStudioManagementUploads({ silent: true });
			await loadStudioExportBatches();
			await refreshBatchListPreservingCurrent({ preferredBatchName: currentBatchName || "" });
			setStudioManagementFlash("success", `已删除上传：${uploadId}`);
		}

		async function openStudioManagementBatch(batchName) {
			const normalizedBatchName = String(batchName || "").trim();
			if (!normalizedBatchName) throw new Error("当前记录还没有可打开的 batch 名称。");
			await refreshBatchListPreservingCurrent({ preferredBatchName: currentBatchName || "" });
			if (!batchList.some(batch => batch.name === normalizedBatchName)) {
				throw new Error(`当前 actor 下未找到批次：${normalizedBatchName}`);
			}
			await switchBatch(normalizedBatchName);
			closeStudioManagement();
			setBatchStatus(`批次已切换：${normalizedBatchName}`);
		}

		async function submitStudioManagementUpload(options = {}) {
			const { files, body } = getStudioManagementFormPayload();
			if (!files.length) {
				setStudioManagementFlash("error", "先选择至少一个要上传的 CSV 或 ZIP 文件。");
				return;
			}
			setStudioManagementBusy(true);
			try {
				clearStudioManagementProgress();
				const completedUploadIds = [];
				for (let index = 0; index < files.length; index += 1) {
					const file = files[index];
					const fileLabel = `${file.name}（${index + 1}/${files.length}）`;
					const recordBody = {
						...body,
						display_name: files.length === 1 ? body.display_name : undefined,
						original_name: file.name,
					};
					setStudioManagementProgress({
						visible: true,
						percent: 4 + (index / files.length) * (options.processAfterUpload ? 48 : 84),
						title: "创建上传记录",
						detail: `正在为 ${fileLabel} 创建上传记录…`,
						tone: "info",
					});
					setStudioManagementFlash("info", `正在创建上传记录：${fileLabel}`);
					const created = normalizeStudioManagementUpload(await createStudioManagementUploadRecord(recordBody));
					if (!created.uploadId) throw new Error("后端未返回 upload_id，前端无法继续上传文件。");
					completedUploadIds.push(created.uploadId);
					const uploadBase = 10 + (index / files.length) * (options.processAfterUpload ? 46 : 82);
					const uploadSpan = (options.processAfterUpload ? 34 : 72) / files.length;
					setStudioManagementProgress({
						visible: true,
						percent: uploadBase,
						title: "上传文件中",
						detail: `上传记录已创建：${created.uploadId}，正在传输 ${fileLabel}…`,
						tone: "info",
					});
					await uploadStudioManagementBlob(created.uploadId, file, {
						onProgress: (event) => {
							if (!event.lengthComputable || event.total <= 0) {
								setStudioManagementProgress({
									visible: true,
									percent: Math.max(uploadBase, studioManagementState.progressPercent || uploadBase),
									title: "上传文件中",
									detail: `正在上传 ${fileLabel}，已发送 ${formatBytes(event.loaded)}。`,
									tone: "info",
								});
								return;
							}
							const ratio = Math.max(0, Math.min(1, event.loaded / event.total));
							setStudioManagementProgress({
								visible: true,
								percent: uploadBase + ratio * uploadSpan,
								title: "上传文件中",
								detail: `正在上传 ${fileLabel}：${formatBytes(event.loaded)} / ${formatBytes(event.total)}`,
								tone: "info",
							});
						},
					});
					if (options.processAfterUpload) {
						setStudioManagementProgress({
							visible: true,
							percent: Math.max(52, studioManagementState.progressPercent || 52),
							title: "文件上传完成",
							detail: `${fileLabel} 已上传完成，准备进入后端处理。`,
							tone: "info",
						});
						await processStudioManagementUpload(created.uploadId, {
							successDetail: `上传 ${created.uploadId} 已处理完成，可以直接打开生成后的 batch。`,
						});
					}
				}
				if (!options.processAfterUpload) {
					setStudioManagementProgress({
						visible: true,
						percent: 100,
						title: "上传完成",
						detail: `已完成 ${files.length} 个文件上传，后续可在“我的上传”里单独触发处理。`,
						tone: "success",
					});
					await loadStudioManagementUploads({ silent: true });
					await loadStudioExportBatches();
					setStudioManagementFlash("success", `已上传 ${files.length} 个文件：${completedUploadIds.join("、")}`);
				} else {
					setStudioManagementFlash("success", `已完成 ${files.length} 个文件的上传与处理。`);
				}
				resetStudioManagementForm({ clearFlash: false, clearProgress: false });
			} catch (error) {
				stopStudioManagementProgressSimulation();
				setStudioManagementProgress({
					visible: true,
					percent: Math.max(8, studioManagementState.progressPercent || 8),
					title: "上传失败",
					detail: String(error?.message || error),
					tone: "error",
				});
				setStudioManagementFlash("error", String(error?.message || error));
			} finally {
				setStudioManagementBusy(false);
			}
		}

		function setStudioExportSummary(message, tone = "") {
			const summary = document.getElementById("studio-export-summary");
			if (!summary) return;
			summary.className = tone ? `studio-management-hint ${tone}` : "studio-management-hint";
			summary.textContent = message || "默认使用当前 batch，可切换批次后再按 UID、Tag 和状态筛选。";
		}

		function getStudioExportSelectedDecisions() {
			return ["accept", "reject", "skip"].filter((decision) => {
				const input = document.getElementById(`studio-export-decision-${decision}`);
				return !!input?.checked;
			});
		}

		function getStudioExportReviewEntries(batchName = studioManagementState.exportSelectedBatch || currentBatchName || "") {
			return studioManagementState.exportReviewsByBatch[String(batchName || "").trim()]?.entries || [];
		}

		function renderStudioExportBatchOptions() {
			const select = document.getElementById("studio-export-batch-select");
			if (!select) return;
			const current = String(studioManagementState.exportSelectedBatch || currentBatchName || "").trim();
			const items = studioManagementState.exportBatches || [];
			select.innerHTML = items.map((batch) => `
				<option value="${escapeHtml(batch.name || "")}" ${current === batch.name ? "selected" : ""}>
					${escapeHtml(batch.label || batch.name || "-")}
				</option>
			`).join("");
		}

		function renderStudioExportReviewFilters() {
			const uidSelect = document.getElementById("studio-export-uid-select");
			const tagSelect = document.getElementById("studio-export-tag-select");
			const entries = getStudioExportReviewEntries();
			if (uidSelect) {
				const uidOptions = entries.map((review) => String(review.uid || "").trim()).filter(Boolean);
				uidSelect.innerHTML = [
					`<option value="">全部已标注 UID</option>`,
					...uidOptions.map((uid) => `<option value="${escapeHtml(uid)}"${studioManagementState.exportSelectedUid === uid ? " selected" : ""}>${escapeHtml(uid)}</option>`),
				].join("");
			}
			if (tagSelect) {
				const tags = [];
				entries.forEach((review) => {
					(review.trajectory_tags || []).forEach((tag) => {
						const value = String(tag || "").trim();
						if (value && !tags.includes(value)) tags.push(value);
					});
				});
				tagSelect.innerHTML = [
					`<option value="">全部 Tag</option>`,
					...tags.map((tag) => `<option value="${escapeHtml(tag)}"${studioManagementState.exportSelectedTag === tag ? " selected" : ""}>${escapeHtml(tag)}</option>`),
				].join("");
			}
			const counts = { accept: 0, reject: 0, skip: 0 };
			entries.forEach((review) => {
				const decision = String(review.decision || "").trim().toLowerCase();
				if (Object.prototype.hasOwnProperty.call(counts, decision)) counts[decision] += 1;
			});
			setStudioExportSummary(
				entries.length
					? `当前批次可导出 ${entries.length} 条已标注样本，其中通过 ${counts.accept}、未通过 ${counts.reject}、跳过 ${counts.skip}。`
					: "当前批次下还没有当前标注者的已标注样本。"
			);
		}

		function resetStudioExportFilters(options = {}) {
			if (options.preferCurrentBatch === true) {
				const preferredBatchName = String(currentBatchName || "").trim();
				if (preferredBatchName) {
					studioManagementState.exportSelectedBatch = preferredBatchName;
				}
			}
			if (options.clearBatch === true && options.preferCurrentBatch !== true) {
				studioManagementState.exportSelectedBatch = "";
			}
			studioManagementState.exportSelectedUid = "";
			studioManagementState.exportSelectedTag = "";
		}

		async function loadStudioExportBatches() {
			const payload = await STUDIO_ADMIN_CORE.fetchBatches(apiFetchJson);
			studioManagementState.exportBatches = payload.items || [];
			const fallbackBatchName = String(currentBatchName || payload.currentBatch || studioManagementState.exportBatches[0]?.name || "").trim();
			if (!studioManagementState.exportSelectedBatch || !studioManagementState.exportBatches.some((batch) => batch.name === studioManagementState.exportSelectedBatch)) {
				studioManagementState.exportSelectedBatch = fallbackBatchName;
			}
			renderStudioExportBatchOptions();
			return studioManagementState.exportBatches;
		}

		async function loadStudioExportReviews(batchName = studioManagementState.exportSelectedBatch || currentBatchName || "") {
			const normalizedBatchName = String(batchName || "").trim();
			const reviewerId = getCurrentReviewerId();
			if (!normalizedBatchName) {
				studioManagementState.exportReviewsByBatch = {};
				renderStudioExportReviewFilters();
				return [];
			}
			if (!reviewerId) {
				studioManagementState.exportReviewsByBatch[normalizedBatchName] = { entries: [], payload: {} };
				renderStudioExportReviewFilters();
				setStudioExportSummary("先选择当前标注者，再按当前标注者的结果导出压缩包。");
				return [];
			}
			const payload = await STUDIO_ADMIN_CORE.fetchReviewerReviews(apiFetchJson, {
				batch: normalizedBatchName,
				reviewer_id: reviewerId,
			});
			const entries = Object.values(payload?.reviews || {}).sort((left, right) => {
				return String(left?.uid || "").localeCompare(String(right?.uid || ""), "zh-CN", { numeric: true });
			});
			studioManagementState.exportReviewsByBatch[normalizedBatchName] = { entries, payload };
			if (studioManagementState.exportSelectedUid && !entries.some((review) => String(review.uid || "") === studioManagementState.exportSelectedUid)) {
				studioManagementState.exportSelectedUid = "";
			}
			if (studioManagementState.exportSelectedTag) {
				const hasTag = entries.some((review) => (review.trajectory_tags || []).includes(studioManagementState.exportSelectedTag));
				if (!hasTag) studioManagementState.exportSelectedTag = "";
			}
			renderStudioExportReviewFilters();
			return entries;
		}

		function focusStudioManagementWorkspace(workspace = "upload") {
			studioManagementState.exportActiveWorkspace = workspace === "export" ? "export" : "upload";
			syncStudioManagementChrome();
			const target = getStudioManagementWorkspaceAnchor(studioManagementState.exportActiveWorkspace);
			const scrollOwner = getStudioManagementWorkspaceScrollOwner();
			if (scrollOwner) {
				if (typeof scrollOwner.scrollTo === "function") {
					scrollOwner.scrollTo({ top: 0, left: 0, behavior: "smooth" });
				} else if (Object.prototype.hasOwnProperty.call(scrollOwner, "scrollTop") || typeof scrollOwner.scrollTop === "number") {
					scrollOwner.scrollTop = 0;
				}
			}
			try {
				target?.focus?.({ preventScroll: true });
			} catch (_) {
				target?.focus?.();
			}
		}

		async function submitStudioExportDownload() {
			return submitStudioExportAction({ exportMode: "reviewer_bundle" });
		}

		function getStudioExportIntervalSeconds() {
			const input = document.getElementById("studio-export-interval-seconds");
			const value = Number(input?.value || 5);
			const normalized = Math.max(5, Number.isFinite(value) ? Math.round(value) : 5);
			if (input) input.value = String(normalized);
			return normalized;
		}

		function getStudioExportTimestampUnit() {
			const active = document.querySelector("#studio-export-timestamp-unit-group .studio-export-unit-btn.active");
			const token = String(active?.dataset?.studioExportTimestampUnit || active?.getAttribute("data-studio-export-timestamp-unit") || "ms")
				.trim()
				.toLowerCase();
			return token === "s" || token === "sec" || token === "seconds" ? "seconds" : "ms";
		}

		function getStudioExportLabeledSpanOnly() {
			return !!document.getElementById("studio-export-labeled-span-only")?.checked;
		}

		async function submitStudioExportAction(options = {}) {
			const reviewerId = getCurrentReviewerId();
			if (!reviewerId) {
				setStudioExportSummary("先选择当前标注者，再导出对应标注结果。", "error");
				return;
			}
			const batchName = String(studioManagementState.exportSelectedBatch || currentBatchName || "").trim();
			if (!batchName) {
				setStudioExportSummary("当前没有可导出的 batch。", "error");
				return;
			}
			const decisions = getStudioExportSelectedDecisions();
			if (!decisions.length) {
				setStudioExportSummary("至少选择一种状态：通过、未通过或跳过。", "error");
				return;
			}
			const exportMode = String(options.exportMode || "reviewer_bundle").trim().toLowerCase();
			const isDatasetExport = exportMode === "segment_label_dataset";
			const datasetExportStartedAt = isDatasetExport ? Date.now() : 0;
			let datasetExportCompleted = false;
			if (isDatasetExport) startStudioExportDatasetButtonProgress();
			else resetStudioExportDatasetButtonProgress();
			setStudioManagementBusy(true);
			setStudioExportSummary(isDatasetExport ? "正在生成分段标签数据集，请稍候…" : "正在打包导出，请稍候…");
			try {
				const bundleName = [
					isDatasetExport ? "segment_label_dataset" : "review_bundle",
					batchName.replace(/[^a-zA-Z0-9_-]+/g, "_"),
					new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z"),
				].join("_");
				const payload = {
					batch: batchName,
					reviewer_id: reviewerId,
					decisions,
					create_zip: true,
					clean: true,
					bundle_name: bundleName,
				};
				if (isDatasetExport) {
					payload.export_mode = "segment_label_dataset";
					payload.interval_seconds = getStudioExportIntervalSeconds();
					payload.timestamp_unit = getStudioExportTimestampUnit();
					payload.labeled_span_only = getStudioExportLabeledSpanOnly();
				}
				if (studioManagementState.exportSelectedUid) payload.uids = [studioManagementState.exportSelectedUid];
				if (studioManagementState.exportSelectedTag) payload.trajectory_tags = [studioManagementState.exportSelectedTag];
				const manifest = await STUDIO_ADMIN_CORE.exportReviewerBundle(apiFetchJson, payload);
				studioManagementState.exportResult = manifest;
				if (isDatasetExport) {
					datasetExportCompleted = true;
					studioManagementState.exportDatasetProgressPercent = 100;
					renderStudioExportActionButtons();
				}
				if (manifest?.download_url) {
					STUDIO_ADMIN_CORE.triggerDownload(manifest.download_url, manifest.download_name || `${manifest.bundle_name || bundleName}.zip`);
				}
				setStudioExportSummary(
					isDatasetExport
						? `数据集导出完成：${manifest?.sample_count || 0} 个 UID，压缩包已开始下载。`
						: `导出完成：${manifest?.sample_count || 0} 条样本，压缩包已开始下载。`,
					"success"
				);
			} catch (error) {
				setStudioExportSummary(String(error?.message || error), "error");
			} finally {
				if (isDatasetExport && datasetExportStartedAt) {
					const minPendingMs = 48;
					const elapsedMs = Date.now() - datasetExportStartedAt;
					if (elapsedMs < minPendingMs) {
						await new Promise(resolve => window.setTimeout(resolve, minPendingMs - elapsedMs));
					}
				}
				setStudioManagementBusy(false);
				if (isDatasetExport) {
					if (datasetExportCompleted) {
						studioManagementState.exportDatasetProgressActive = true;
						studioManagementState.exportDatasetProgressPercent = 100;
						renderStudioExportActionButtons();
					}
					scheduleStudioExportDatasetButtonProgressReset(datasetExportCompleted ? 650 : 0);
				} else {
					resetStudioExportDatasetButtonProgress();
				}
			}
		}

		async function syncStudioManagementData() {
			renderStudioManagementActor();
			renderStudioManagementUploads();
			renderStudioExportBatchOptions();
			renderStudioExportReviewFilters();
			const results = await Promise.allSettled([
				loadStudioManagementActor(),
				loadStudioManagementUploads({ silent: true }),
				loadStudioExportBatches().then(() => loadStudioExportReviews()),
			]);
			const firstRejected = results.find(result => result.status === "rejected");
			if (firstRejected) {
				throw firstRejected.reason;
			}
			setStudioManagementFlash("info", `已同步 ${studioManagementState.uploads.length} 条上传记录。`);
		}

		function openStudioManagement(workspace = "upload") {
			const overlay = document.getElementById("studio-management-overlay");
			if (!overlay) return;
			const activeWorkspace = workspace === "export" ? "export" : "upload";
			hideTimeScrubberContextMenu();
			if (annotationSettingsOverlay?.classList.contains("open")) closeAnnotationSettings();
			setStudioManagementHelpVisibility(false, { pinned: false });
			if (activeWorkspace === "export") {
				resetStudioExportFilters({ preferCurrentBatch: true });
			}
			renderStudioManagementHelp();
			renderStudioManagementCustomFields();
			overlay.classList.add("open");
			overlay.setAttribute("aria-hidden", "false");
			focusStudioManagementWorkspace(activeWorkspace);
			syncStudioManagementChrome();
			setStudioManagementFlash("info", "正在同步 Studio 管理数据…");
			void syncStudioManagementData().catch((error) => {
				setStudioManagementFlash("error", String(error?.message || error));
			});
		}

		function closeStudioManagement() {
			const overlay = document.getElementById("studio-management-overlay");
			if (!overlay) return;
			setStudioManagementHelpVisibility(false, { pinned: false });
			resetStudioExportDatasetButtonProgress();
			overlay.classList.remove("open");
			overlay.setAttribute("aria-hidden", "true");
			resetStudioExportFilters({ preferCurrentBatch: true });
			studioManagementState.exportActiveWorkspace = "upload";
			syncStudioManagementChrome();
		}

		function resolveStudioManagementActor(payload) {
			return STUDIO_ADMIN_CORE.resolveActor(payload);
		}

		function normalizeStudioManagementUpload(item) {
			return STUDIO_ADMIN_CORE.normalizeUpload(item, {
				formatVisibilityScope: formatStudioVisibilityScope,
				formatAnnotationMode: formatStudioAnnotationMode,
				formatSignal6AlgorithmProfile,
			});
		}

		function getStudioManagementStatusClass(status) {
			return STUDIO_ADMIN_CORE.getStatusClass(status);
		}
