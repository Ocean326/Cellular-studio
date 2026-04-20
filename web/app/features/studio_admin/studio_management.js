		function setStudioManagementBusy(busy) {
			studioManagementState.busy = !!busy;
			const uploadButton = document.getElementById("studio-management-upload-btn");
			const uploadProcessButton = document.getElementById("studio-management-upload-process-btn");
			const refreshButton = document.getElementById("studio-management-refresh-btn");
			const resetButton = document.getElementById("studio-management-reset-btn");
			if (uploadButton) uploadButton.disabled = studioManagementState.busy;
			if (uploadProcessButton) uploadProcessButton.disabled = studioManagementState.busy;
			if (refreshButton) refreshButton.disabled = studioManagementState.busy;
			if (resetButton) resetButton.disabled = studioManagementState.busy;
			renderStudioManagementProgress();
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
			title.textContent = studioManagementState.progressTitle || "等待上传";
			percent.textContent = `${Math.max(0, Math.min(100, Math.round(studioManagementState.progressPercent || 0)))}%`;
			bar.style.width = `${Math.max(0, Math.min(100, studioManagementState.progressPercent || 0))}%`;
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
			panel.innerHTML = buildStudioManagementCustomFieldHtml(spec, getStudioManagementCustomFieldStore(uploadType));
			panel.classList.toggle("collapsed", !studioManagementState.customFieldsExpanded);
			toggle.setAttribute("aria-expanded", studioManagementState.customFieldsExpanded ? "true" : "false");
			toggle.textContent = studioManagementState.customFieldsExpanded ? "收起自定义" : "自定义字段";
		}

		function setStudioManagementCustomFieldsExpanded(expanded) {
			studioManagementState.customFieldsExpanded = !!expanded;
			renderStudioManagementCustomFields();
		}

		function getStudioManagementFieldMappingForSubmit(uploadType = getStudioManagementUploadType()) {
			if (!studioManagementState.customFieldsExpanded) return undefined;
			const mapping = getStudioManagementCustomFieldStore(uploadType);
			const normalizedEntries = Object.entries(mapping).filter(([, value]) => String(value || "").trim());
			if (!normalizedEntries.length) return undefined;
			return Object.fromEntries(normalizedEntries.map(([key, value]) => [key, String(value || "").trim()]));
		}

		function resetStudioManagementForm(options = {}) {
			const uploadTypeInput = document.getElementById("studio-management-upload-type");
			const visibilityScopeInput = document.getElementById("studio-management-visibility-scope");
			const annotationModeInput = document.getElementById("studio-management-annotation-mode");
			const displayNameInput = document.getElementById("studio-management-display-name");
			const uploadFileInput = document.getElementById("studio-management-upload-file");
			if (uploadTypeInput) uploadTypeInput.value = "trajectory4";
			if (visibilityScopeInput) visibilityScopeInput.value = "private";
			if (annotationModeInput) annotationModeInput.value = "annotatable";
			if (displayNameInput) displayNameInput.value = "";
			if (uploadFileInput) uploadFileInput.value = "";
			studioManagementState.customFieldsExpanded = false;
			studioManagementState.customFieldMappings = { trajectory4: {}, signal6: {} };
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
			const uploadType = getStudioManagementUploadType();
			const file = uploadFileInput?.files?.[0] || null;
			return {
				file,
				body: {
					upload_type: uploadType,
					visibility_scope: visibilityScopeInput?.value || "private",
					annotation_mode: annotationModeInput?.value || "annotatable",
					display_name: displayNameInput?.value?.trim() || undefined,
					original_name: file ? file.name : undefined,
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
			return Boolean(upload?.batchName);
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

		function syncStudioManagementChrome() {
			const overlay = document.getElementById("studio-management-overlay");
			const entry = document.getElementById("studio-management-entry");
			const isOpen = overlay?.classList.contains("open");
			if (entry) entry.classList.toggle("active", !!isOpen);
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
			const { file, body } = getStudioManagementFormPayload();
			if (!file) {
				setStudioManagementFlash("error", "先选择一个要上传的 CSV 文件。");
				return;
			}
			setStudioManagementBusy(true);
			try {
				clearStudioManagementProgress();
				setStudioManagementProgress({
					visible: true,
					percent: 8,
					title: "创建上传记录",
					detail: `正在为 ${file.name} 创建上传记录…`,
					tone: "info",
				});
				setStudioManagementFlash("info", "正在创建上传记录…");
				const created = normalizeStudioManagementUpload(await createStudioManagementUploadRecord(body));
				if (!created.uploadId) throw new Error("后端未返回 upload_id，前端无法继续上传文件。");
				setStudioManagementProgress({
					visible: true,
					percent: 14,
					title: "上传文件中",
					detail: `上传记录已创建：${created.uploadId}，正在传输文件内容…`,
					tone: "info",
				});
				setStudioManagementFlash("info", `上传记录已创建，正在传输文件：${created.uploadId}`);
				await uploadStudioManagementBlob(created.uploadId, file, {
					onProgress: (event) => {
						if (!event.lengthComputable || event.total <= 0) {
							setStudioManagementProgress({
								visible: true,
								percent: Math.max(18, studioManagementState.progressPercent || 18),
								title: "上传文件中",
								detail: `正在上传 ${file.name}，已发送 ${formatBytes(event.loaded)}。`,
								tone: "info",
							});
							return;
						}
						const ratio = Math.max(0, Math.min(1, event.loaded / event.total));
						const mappedPercent = 14 + ratio * 58;
						setStudioManagementProgress({
							visible: true,
							percent: mappedPercent,
							title: "上传文件中",
							detail: `正在上传 ${file.name}：${formatBytes(event.loaded)} / ${formatBytes(event.total)}`,
							tone: "info",
						});
					},
				});
				setStudioManagementProgress({
					visible: true,
					percent: options.processAfterUpload ? 74 : 100,
					title: options.processAfterUpload ? "文件上传完成" : "上传完成",
					detail: options.processAfterUpload
						? `文件 ${file.name} 已上传完成，准备进入后端处理。`
						: `文件 ${file.name} 已上传完成，后续可在“我的上传”里单独触发处理。`,
					tone: options.processAfterUpload ? "info" : "success",
				});
				if (options.processAfterUpload) {
					await processStudioManagementUpload(created.uploadId, {
						successDetail: `上传 ${created.uploadId} 已处理完成，可以直接打开生成后的 batch。`,
					});
				} else {
					await loadStudioManagementUploads({ silent: true });
					setStudioManagementFlash("success", `文件已上传：${created.uploadId}`);
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

		async function syncStudioManagementData() {
			renderStudioManagementActor();
			renderStudioManagementUploads();
			const results = await Promise.allSettled([
				loadStudioManagementActor(),
				loadStudioManagementUploads({ silent: true }),
			]);
			const firstRejected = results.find(result => result.status === "rejected");
			if (firstRejected) {
				throw firstRejected.reason;
			}
			setStudioManagementFlash("info", `已同步 ${studioManagementState.uploads.length} 条上传记录。`);
		}

		function openStudioManagement() {
			const overlay = document.getElementById("studio-management-overlay");
			if (!overlay) return;
			hideTimeScrubberContextMenu();
			if (annotationSettingsOverlay?.classList.contains("open")) closeAnnotationSettings();
			setStudioManagementHelpVisibility(false, { pinned: false });
			renderStudioManagementHelp();
			renderStudioManagementCustomFields();
			overlay.classList.add("open");
			overlay.setAttribute("aria-hidden", "false");
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
			overlay.classList.remove("open");
			overlay.setAttribute("aria-hidden", "true");
			syncStudioManagementChrome();
		}

		function resolveStudioManagementActor(payload) {
			return STUDIO_ADMIN_CORE.resolveActor(payload);
		}

		function normalizeStudioManagementUpload(item) {
			return STUDIO_ADMIN_CORE.normalizeUpload(item, {
				formatVisibilityScope: formatStudioVisibilityScope,
				formatAnnotationMode: formatStudioAnnotationMode,
			});
		}

		function getStudioManagementStatusClass(status) {
			return STUDIO_ADMIN_CORE.getStatusClass(status);
		}
