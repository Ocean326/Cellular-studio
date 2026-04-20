		const debouncedRefreshFilteredUids = debounce(() => {
			void refreshFilteredUids({ resetVisibleCounts: true });
		}, 200);

		document.getElementById("search-box").addEventListener("input", debouncedRefreshFilteredUids);
		document.getElementById("batch-select").addEventListener("change", async (event) => {
			await switchBatch(event.target.value);
		});
		document.querySelectorAll(".review-decision-btn").forEach(btn => {
			btn.addEventListener("click", () => setDecisionButtons(btn.dataset.decision));
		});
		document.getElementById("save-review-btn").addEventListener("click", saveReview);
		document.getElementById("refresh-review-btn").addEventListener("click", async () => {
			if (!currentUid) {
				setReviewStatus("请先选择 UID", true);
				return;
			}
			const hadDirty = reviewFormDirty;
			if (hadDirty && !confirmDiscardReviewChanges()) return;
			const meta = await ensureUidMeta(currentUid);
			await loadReviewForUid(currentUid, meta.exists);
			setReviewStatus(hadDirty ? "已丢弃未保存修改并刷新当前 UID 的最新审核记录" : "已刷新当前 UID 的最新审核记录", false);
		});
		document.getElementById("reviewer-open-session-btn").addEventListener("click", () => {
			openReviewerSessionModal({ required: false });
		});
		document.getElementById("reviewer-switch-btn").addEventListener("click", () => {
			if (reviewFormDirty && !confirmDiscardReviewChanges()) return;
			openReviewerSessionModal({ required: false });
		});
		document.getElementById("reviewer-session-cancel").addEventListener("click", () => {
			closeReviewerSessionModal();
		});
		document.getElementById("reviewer-session-submit").addEventListener("click", async () => {
			const displayName = document.getElementById("reviewer-session-input").value.trim();
			if (!displayName) {
				setReviewerSessionStatus("请输入姓名或昵称。", true);
				return;
			}
			try {
				setReviewerSessionStatus("正在进入标注...", false);
				await submitReviewerSession({ display_name: displayName });
				reviewerSessionModalRequired = false;
				closeReviewerSessionModal(true);
				await onReviewerSessionChanged();
			} catch (error) {
				setReviewerSessionStatus(`设置失败：${error.message || error}`, true);
			}
		});
		document.getElementById("reviewer-session-input").addEventListener("keydown", async (event) => {
			if (event.key !== "Enter") return;
			event.preventDefault();
			document.getElementById("reviewer-session-submit").click();
		});
		document.getElementById("reviewer-session-known").addEventListener("click", async (event) => {
			const btn = event.target.closest(".reviewer-known-btn[data-reviewer-id]");
			if (!btn) return;
			try {
				setReviewerSessionStatus("正在切换标注者...", false);
				await submitReviewerSession({
					reviewer_id: btn.dataset.reviewerId,
					display_name: btn.dataset.reviewerName,
				});
				reviewerSessionModalRequired = false;
				closeReviewerSessionModal(true);
				await onReviewerSessionChanged();
			} catch (error) {
				setReviewerSessionStatus(`切换失败：${error.message || error}`, true);
			}
		});
		document.getElementById("reviewer-session-overlay").addEventListener("click", (event) => {
			if (event.target !== document.getElementById("reviewer-session-overlay")) return;
			closeReviewerSessionModal();
		});
		document.getElementById("reference-source-input").addEventListener("input", syncReviewDirtyState);
		document.getElementById("reference-source-input").addEventListener("change", syncReviewDirtyState);
		document.getElementById("review-tag-select").addEventListener("input", syncReviewDirtyState);
		document.getElementById("review-tag-select").addEventListener("change", syncReviewDirtyState);
		document.getElementById("review-notes").addEventListener("input", syncReviewDirtyState);
		document.getElementById("review-notes").addEventListener("change", syncReviewDirtyState);
		document.getElementById("status-filter-row").addEventListener("change", () => {
			void refreshFilteredUids({ resetVisibleCounts: true });
		});
		document.getElementById("filter-mode").addEventListener("change", () => {
			void refreshFilteredUids({ resetVisibleCounts: true });
		});
		document.getElementById("filter-toggle-btn").addEventListener("click", () => {
			setFilterPanelCollapsed(!filterPanelCollapsed);
		});
		document.getElementById("review-aggregate-toggle").addEventListener("click", () => {
			setReviewAggregateCollapsed(!reviewAggregateCollapsed, { userInitiated: true });
		});
		document.getElementById("review-panel-toggle").addEventListener("click", () => {
			setReviewPanelCollapsed(!reviewPanelCollapsed);
		});
		document.getElementById("prev-pending-btn").addEventListener("click", async (event) => {
			const uid = event.currentTarget.dataset.uid;
			if (uid) await selectUid(uid);
		});
		document.getElementById("next-pending-btn").addEventListener("click", async (event) => {
			const uid = event.currentTarget.dataset.uid;
			if (uid) await selectUid(uid);
		});
		document.getElementById("triage-board").addEventListener("click", async (event) => {
			const loadMoreButton = event.target.closest(".load-more-btn[data-column]");
			if (loadMoreButton) {
				const column = loadMoreButton.dataset.column;
				if (!column) return;
				columnVisibleCounts[column] = (columnVisibleCounts[column] || BOARD_PAGE_SIZE) + BOARD_PAGE_SIZE;
				renderTriageBoard({ resetVisibleCounts: false });
				return;
			}
			const card = event.target.closest(".triage-card[data-uid]");
			if (!card) return;
			await selectUid(card.dataset.uid);
		});
		document.getElementById("triage-board").addEventListener("change", (event) => {
			if (event.target.id !== "other-review-filter") return;
			otherReviewFilterValue = event.target.value;
			renderTriageBoard({ resetVisibleCounts: true });
		});
		document.getElementById("triage-column-tabs").addEventListener("click", (event) => {
			const tab = event.target.closest(".triage-tab[data-column]");
			if (!tab) return;
			activeTriageColumnKey = tab.dataset.column || activeTriageColumnKey;
			renderTriageBoard({ resetVisibleCounts: false });
		});
		document.getElementById("map-tools-toggle").addEventListener("click", () => {
			setMapToolsOpen(!mapToolsOpen);
		});
		document.getElementById("time-plus8-cb").addEventListener("change", (e) => {
			timePlus8 = e.target.checked;
			if (currentUid) {
				clearRenderedCache();
				void renderUid(currentUid);
			}
			renderTimeScrubberControl();
		});
		document.getElementById("map-view-follow-cb").addEventListener("change", (e) => {
			mapViewFollowScrubber = e.target.checked;
		});
		const timeScrubberControl = document.getElementById("time-scrubber-control");
		const timeScrubberCanvas = document.getElementById("time-scrubber-canvas");
		const timeScrubberOverviewCanvas = document.getElementById("time-scrubber-overview-canvas");
		const timeScrubberLayerSelect = document.getElementById("time-scrubber-layer-select");
		const timeScrubberStepPrev = document.getElementById("time-scrubber-step-prev");
		const timeScrubberStepNext = document.getElementById("time-scrubber-step-next");
		const timeScrubberLeft = document.getElementById("time-scrubber-left");
		const timeScrubberRight = document.getElementById("time-scrubber-right");
		const timeScrubberZoomOut = document.getElementById("time-scrubber-zoom-out");
		const timeScrubberZoomIn = document.getElementById("time-scrubber-zoom-in");
		const timeScrubberContextMenu = document.getElementById("time-scrubber-context-menu");
		const annotationSettingsEntry = document.getElementById("annotation-settings-entry");
		const annotationSettingsOverlay = document.getElementById("annotation-settings-overlay");
		const annotationSettingsClose = document.getElementById("annotation-settings-close");
		const annotationCategoryAdd = document.getElementById("annotation-category-add");
		const annotationTagAdd = document.getElementById("annotation-tag-add");
		const annotationFocusOpacityInput = document.getElementById("annotation-focus-opacity");
		const annotationIdleOpacityInput = document.getElementById("annotation-idle-opacity");
		const studioManagementEntry = document.getElementById("studio-management-entry");
		const studioManagementOverlay = document.getElementById("studio-management-overlay");
		const studioManagementClose = document.getElementById("studio-management-close");
		const studioManagementRefreshBtn = document.getElementById("studio-management-refresh-btn");
		const studioManagementUploadBtn = document.getElementById("studio-management-upload-btn");
		const studioManagementUploadProcessBtn = document.getElementById("studio-management-upload-process-btn");
		const studioManagementResetBtn = document.getElementById("studio-management-reset-btn");
		const studioManagementUploadsList = document.getElementById("studio-management-uploads-list");
		const studioManagementUploadTypeSelect = document.getElementById("studio-management-upload-type");
		const studioManagementCustomFieldsToggle = document.getElementById("studio-management-custom-fields-toggle");
		const studioManagementCustomFields = document.getElementById("studio-management-custom-fields");
		const studioManagementHelpAnchor = document.getElementById("studio-management-help-anchor");
		const studioManagementHelpTrigger = document.getElementById("studio-management-help-trigger");
		const themeModeToggle = document.getElementById("theme-mode-toggle");
		const themeModeLabel = document.getElementById("theme-mode-label");
		const THEME_MODE_STORAGE_KEY = "studioThemeMode";
		const THEME_MODE_DAY = "day";
		const THEME_MODE_NIGHT = "night";
		let themeMode = normalizeThemeMode(localStorage.getItem(THEME_MODE_STORAGE_KEY));

		function normalizeThemeMode(mode) {
			return mode === THEME_MODE_NIGHT ? THEME_MODE_NIGHT : THEME_MODE_DAY;
		}

		function syncThemeModeToggle() {
			const nextMode = themeMode === THEME_MODE_NIGHT ? THEME_MODE_DAY : THEME_MODE_NIGHT;
			const nextLabel = nextMode === THEME_MODE_NIGHT ? "夜景" : "日景";
			const nextTitle = nextMode === THEME_MODE_NIGHT ? "切换到夜间模式" : "切换到日间模式";
			themeModeToggle.dataset.label = nextLabel;
			themeModeToggle.setAttribute("aria-label", nextTitle);
			themeModeToggle.setAttribute("aria-pressed", themeMode === THEME_MODE_NIGHT ? "true" : "false");
			themeModeToggle.setAttribute("title", nextTitle);
			themeModeToggle.classList.toggle("active", themeMode === THEME_MODE_NIGHT);
			if (themeModeLabel) themeModeLabel.textContent = nextLabel;
		}

		function applyThemeMode(mode, { persist = true } = {}) {
			themeMode = normalizeThemeMode(mode);
			document.body.dataset.theme = themeMode;
			syncThemeModeToggle();
			if (persist) localStorage.setItem(THEME_MODE_STORAGE_KEY, themeMode);
		}

		themeModeToggle.addEventListener("click", () => {
			applyThemeMode(themeMode === THEME_MODE_NIGHT ? THEME_MODE_DAY : THEME_MODE_NIGHT);
		});

		let timeScrubberScrollWheelSuppressed = false;
		function suppressMapScrollWheelForTimeScrubber() {
			if (timeScrubberScrollWheelSuppressed || typeof map === "undefined" || !map?.scrollWheelZoom) return;
			try {
				map.scrollWheelZoom.disable();
				timeScrubberScrollWheelSuppressed = true;
			} catch (_) {}
		}
		function restoreMapScrollWheelAfterTimeScrubber() {
			if (!timeScrubberScrollWheelSuppressed || typeof map === "undefined" || !map?.scrollWheelZoom) return;
			try {
				map.scrollWheelZoom.enable();
			} catch (_) {}
			timeScrubberScrollWheelSuppressed = false;
		}
		timeScrubberControl.addEventListener("mouseenter", () => {
			setTimeScrubberActive(true);
			suppressMapScrollWheelForTimeScrubber();
		});
		timeScrubberControl.addEventListener("mouseleave", () => {
			restoreMapScrollWheelAfterTimeScrubber();
			if (!timeScrubberState.isDragging && !timeScrubberState.isOverviewDragging) setTimeScrubberActive(false);
		});
		timeScrubberLayerSelect.addEventListener("change", (event) => {
			setTimeScrubberLayer(event.target.value);
		});
		timeScrubberStepPrev.addEventListener("click", () => {
			setTimeScrubberActive(true);
			stepTimeScrubberSelection(-1);
		});
		timeScrubberStepNext.addEventListener("click", () => {
			setTimeScrubberActive(true);
			stepTimeScrubberSelection(1);
		});
		timeScrubberLeft.addEventListener("click", () => panTimeScrubberWindow(-1));
		timeScrubberRight.addEventListener("click", () => panTimeScrubberWindow(1));
		timeScrubberZoomOut.addEventListener("click", () => zoomTimeScrubberWindow(1 + TIME_SCRUBBER_ZOOM_STEP));
		timeScrubberZoomIn.addEventListener("click", () => zoomTimeScrubberWindow(1 - TIME_SCRUBBER_ZOOM_STEP));
		timeScrubberContextMenu.addEventListener("click", (event) => {
			const actionButton = event.target.closest(".time-scrubber-menu-item[data-action]");
			if (!actionButton || timeScrubberContextMenuState.pointIndex == null) return;
			const action = actionButton.dataset.action;
			if (action === "pin") {
				addTimelinePinAtIndex(timeScrubberContextMenuState.pointIndex);
				return;
			}
			if (action === "delete-segment") {
				removeTimelineSegmentById(actionButton.dataset.segmentId || "");
				hideTimeScrubberContextMenu();
				return;
			}
			if (action === "segment") {
				startTimelineSegmentDraft(actionButton.dataset.categoryId || "", timeScrubberContextMenuState.pointIndex);
			}
		});
		timeScrubberCanvas.addEventListener("pointerdown", (event) => {
			if (!timeScrubberState.enabled) return;
			event.preventDefault();
			hideTimeScrubberContextMenu();
			timeScrubberState.isDragging = true;
			timeScrubberCanvas.classList.add("dragging");
			setTimeScrubberActive(true);
			timeScrubberCanvas.setPointerCapture?.(event.pointerId);
			updateTimeFocusMarker();
			updateTimeScrubberSelectionFromClientX(event.clientX);
		});
		timeScrubberCanvas.addEventListener("contextmenu", (event) => {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length || currentUiConfig.annotationEnabled === false) return;
			if (!ensureAnnotationSessionReady({ prompt: true })) return;
			event.preventDefault();
			updateTimeScrubberSelectionFromClientX(event.clientX);
			showTimeScrubberContextMenu(event.clientX, event.clientY, timeScrubberState.selectedIndex);
			setTimeScrubberActive(true);
		});
		timeScrubberControl.addEventListener("wheel", (event) => {
			if (event.target.closest("#date-window-control")) return;
			handleTimeScrubberWheel(event);
		}, { passive: false });
		timeScrubberCanvas.addEventListener("pointermove", (event) => {
			if (timeScrubberState.isDragging) {
				event.preventDefault();
				updateTimeScrubberSelectionFromClientX(event.clientX);
				if (segmentDraftState.active) {
					updateTimelineSegmentDraftFromIndex(timeScrubberState.selectedIndex);
					renderTimeScrubberControl();
				}
				return;
			}
			if (segmentDraftState.active) {
				updateTimeScrubberSelectionFromClientX(event.clientX);
				updateTimelineSegmentDraftFromIndex(timeScrubberState.selectedIndex);
				renderTimeScrubberControl();
			}
		});
		timeScrubberCanvas.addEventListener("click", (event) => {
			if (!segmentDraftState.active || timeScrubberState.isDragging) return;
			updateTimeScrubberSelectionFromClientX(event.clientX);
			commitTimelineSegmentDraft(timeScrubberState.selectedIndex);
		});
		const stopTimeScrubberDragging = (event) => {
			if (!timeScrubberState.isDragging) return;
			timeScrubberState.isDragging = false;
			timeScrubberCanvas.classList.remove("dragging");
			if (event?.pointerId != null) {
				try { timeScrubberCanvas.releasePointerCapture?.(event.pointerId); } catch (_) {}
			}
			setTimeScrubberActive(false);
			updateTimeFocusMarker();
		};
		timeScrubberCanvas.addEventListener("pointerup", stopTimeScrubberDragging);
		timeScrubberCanvas.addEventListener("pointercancel", stopTimeScrubberDragging);
		timeScrubberCanvas.addEventListener("pointerleave", () => {
			if (!timeScrubberState.isDragging) setTimeScrubberActive(false);
		});
		timeScrubberOverviewCanvas.addEventListener("pointerdown", (event) => {
			if (!timeScrubberState.enabled || !timeScrubberState.allPoints.length) return;
			event.preventDefault();
			hideTimeScrubberContextMenu();
			const rect = timeScrubberOverviewCanvas.getBoundingClientRect();
			const scale = createTimeScrubberScale(timeScrubberState.allPoints, rect.width, rect.height);
			const visibleBounds = getCurrentVisibleTimeBounds();
			if (!visibleBounds) return;
			const pointerX = event.clientX - rect.left;
			const pointerTime = scale.getTimeForX(pointerX);
			const hitMode = getTimeScrubberOverviewHitMode(pointerX, scale, visibleBounds);
			if (hitMode === "resize-start") {
				timeScrubberState.isOverviewDragging = true;
				timeScrubberState.overviewDragMode = "resize-start";
				updateTimeScrubberOverviewCursor();
				timeScrubberOverviewCanvas.setPointerCapture?.(event.pointerId);
				setTimeScrubberActive(true);
				updateTimeFocusMarker();
				return;
			}
			if (hitMode === "resize-end") {
				timeScrubberState.isOverviewDragging = true;
				timeScrubberState.overviewDragMode = "resize-end";
				updateTimeScrubberOverviewCursor();
				timeScrubberOverviewCanvas.setPointerCapture?.(event.pointerId);
				setTimeScrubberActive(true);
				updateTimeFocusMarker();
				return;
			}
			if (hitMode === "move") {
				timeScrubberState.isOverviewDragging = true;
				timeScrubberState.overviewDragMode = "move";
				timeScrubberState.overviewDragOffsetSeconds = pointerTime - visibleBounds.start;
				updateTimeScrubberOverviewCursor();
				timeScrubberOverviewCanvas.setPointerCapture?.(event.pointerId);
				setTimeScrubberActive(true);
				updateTimeFocusMarker();
				return;
			}
			const visibleSpan = Math.max(0, visibleBounds.end - visibleBounds.start);
			setTimeScrubberWindowFromStartTime(pointerTime - visibleSpan / 2);
			setTimeScrubberActive(true);
		});
		timeScrubberOverviewCanvas.addEventListener("pointermove", (event) => {
			const rect = timeScrubberOverviewCanvas.getBoundingClientRect();
			const scale = createTimeScrubberScale(timeScrubberState.allPoints, rect.width, rect.height);
			const visibleBounds = getCurrentVisibleTimeBounds();
			if (!timeScrubberState.isOverviewDragging) {
				if (!visibleBounds) {
					updateTimeScrubberOverviewCursor();
					return;
				}
				updateTimeScrubberOverviewCursor(getTimeScrubberOverviewHitMode(event.clientX - rect.left, scale, visibleBounds));
				return;
			}
			event.preventDefault();
			const pointerTime = scale.getTimeForX(event.clientX - rect.left);
			const total = timeScrubberState.allPoints.length;
			const startIndex = timeScrubberState.visibleStartIndex;
			const endIndex = Math.min(total - 1, startIndex + getTimeScrubberVisibleCount(total) - 1);
			if (timeScrubberState.overviewDragMode === "move") {
				setTimeScrubberWindowFromStartTime(pointerTime - timeScrubberState.overviewDragOffsetSeconds);
				return;
			}
			if (timeScrubberState.overviewDragMode === "resize-start") {
				const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, total);
				const minVisible = Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxVisible);
				const candidateStart = Math.max(0, Math.min(findNearestTimeScrubberPointIndex(timeScrubberState.allPoints, pointerTime), endIndex - minVisible + 1));
				const boundedStart = Math.max(candidateStart, endIndex - maxVisible + 1);
				timeScrubberState.visibleCount = endIndex - boundedStart + 1;
				setTimeScrubberVisibleStart(boundedStart);
				return;
			}
			if (timeScrubberState.overviewDragMode === "resize-end") {
				const maxVisible = Math.min(TIME_SCRUBBER_MAX_POINTS, total);
				const minVisible = Math.min(TIME_SCRUBBER_MIN_VISIBLE_POINTS, maxVisible);
				const candidateEnd = Math.min(total - 1, Math.max(findNearestTimeScrubberPointIndex(timeScrubberState.allPoints, pointerTime), startIndex + minVisible - 1));
				const boundedEnd = Math.min(candidateEnd, startIndex + maxVisible - 1);
				setTimeScrubberVisibleCount(boundedEnd - startIndex + 1);
			}
		});
		const stopTimeScrubberOverviewDragging = (event) => {
			if (!timeScrubberState.isOverviewDragging) return;
			timeScrubberState.isOverviewDragging = false;
			timeScrubberState.overviewDragMode = "";
			if (event?.pointerId != null) {
				try { timeScrubberOverviewCanvas.releasePointerCapture?.(event.pointerId); } catch (_) {}
			}
			setTimeScrubberActive(false);
			updateTimeScrubberOverviewCursor();
			updateTimeFocusMarker();
		};
		timeScrubberOverviewCanvas.addEventListener("pointerup", stopTimeScrubberOverviewDragging);
		timeScrubberOverviewCanvas.addEventListener("pointercancel", stopTimeScrubberOverviewDragging);
		timeScrubberOverviewCanvas.addEventListener("pointerleave", () => {
			updateTimeScrubberOverviewCursor();
			if (!timeScrubberState.isOverviewDragging && !timeScrubberState.isDragging) setTimeScrubberActive(false);
		});
		document.addEventListener("click", (event) => {
			if (!timeScrubberContextMenuState.open) return;
			if (timeScrubberContextMenu.contains(event.target)) return;
			hideTimeScrubberContextMenu();
		});
		document.addEventListener("keydown", (event) => {
			if (event.key === "Escape") {
				if (segmentDraftState.active) {
					cancelTimelineSegmentDraft();
					return;
				}
				if (document.getElementById("reviewer-session-overlay").classList.contains("open")) {
					closeReviewerSessionModal();
					return;
				}
				if (studioManagementOverlay.classList.contains("open")) {
					closeStudioManagement();
					return;
				}
				if (annotationSettingsOverlay.classList.contains("open")) {
					closeAnnotationSettings();
					return;
				}
				hideTimeScrubberContextMenu();
				return;
			}
			if (event.defaultPrevented) return;
			if (document.getElementById("reviewer-session-overlay").classList.contains("open")) return;
			if (studioManagementOverlay.classList.contains("open")) return;
			if (annotationSettingsOverlay.classList.contains("open")) return;
			if (!isKeyboardTargetBlockingReviewShortcuts(event.target) && handleReviewShortcutKeyboardEvent(event)) return;
			if (event.metaKey || event.ctrlKey || event.altKey) return;
			if (isEditableKeyboardTarget(event.target)) return;
			if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
			const moved = stepTimeScrubberSelection(event.key === "ArrowLeft" ? -1 : 1);
			if (!moved) return;
			event.preventDefault();
			event.stopPropagation();
			setTimeScrubberActive(true);
		});
		annotationSettingsEntry.addEventListener("click", () => {
			if (currentUiConfig.annotationEnabled === false) return;
			openAnnotationSettings();
		});
		annotationSettingsClose.addEventListener("click", () => closeAnnotationSettings());
		annotationSettingsOverlay.addEventListener("click", (event) => {
			if (event.target === annotationSettingsOverlay) closeAnnotationSettings();
		});
		studioManagementEntry.addEventListener("click", () => {
			if (studioManagementOverlay.classList.contains("open")) {
				closeStudioManagement();
				return;
			}
			openStudioManagement();
		});
		studioManagementClose.addEventListener("click", () => closeStudioManagement());
		studioManagementOverlay.addEventListener("click", (event) => {
			if (studioManagementState.helpPinned && !event.target.closest("#studio-management-help-anchor")) {
				setStudioManagementHelpVisibility(false, { pinned: false });
			}
			if (event.target === studioManagementOverlay) closeStudioManagement();
		});
		studioManagementRefreshBtn.addEventListener("click", () => {
			if (studioManagementState.busy) return;
			void loadStudioManagementUploads().catch((error) => {
				setStudioManagementFlash("error", String(error?.message || error));
			});
		});
		studioManagementUploadTypeSelect.addEventListener("change", () => {
			renderStudioManagementHelp();
			renderStudioManagementCustomFields();
		});
		studioManagementCustomFieldsToggle.addEventListener("click", (event) => {
			event.stopPropagation();
			setStudioManagementCustomFieldsExpanded(!studioManagementState.customFieldsExpanded);
		});
		studioManagementCustomFields.addEventListener("input", (event) => {
			const fieldInput = event.target.closest("input[data-studio-field-key]");
			if (!fieldInput) return;
			const uploadType = String(studioManagementUploadTypeSelect.value || "trajectory4").trim().toLowerCase();
			const fieldStore = getStudioManagementCustomFieldStore(uploadType);
			fieldStore[fieldInput.dataset.studioFieldKey || ""] = fieldInput.value;
		});
		studioManagementHelpAnchor.addEventListener("mouseenter", () => {
			renderStudioManagementHelp();
			if (!studioManagementState.helpPinned) {
				setStudioManagementHelpVisibility(true, { pinned: false });
			}
		});
		studioManagementHelpAnchor.addEventListener("mouseleave", () => {
			if (!studioManagementState.helpPinned) {
				setStudioManagementHelpVisibility(false, { pinned: false });
			}
		});
		studioManagementHelpTrigger.addEventListener("click", (event) => {
			event.stopPropagation();
			renderStudioManagementHelp();
			if (studioManagementState.helpPinned) {
				setStudioManagementHelpVisibility(false, { pinned: false });
				return;
			}
			setStudioManagementHelpVisibility(true, { pinned: true });
		});
		studioManagementUploadBtn.addEventListener("click", () => {
			void submitStudioManagementUpload({ processAfterUpload: false });
		});
		studioManagementUploadProcessBtn.addEventListener("click", () => {
			void submitStudioManagementUpload({ processAfterUpload: true });
		});
		studioManagementResetBtn.addEventListener("click", () => resetStudioManagementForm());
		studioManagementUploadsList.addEventListener("click", (event) => {
			const actionButton = event.target.closest("button[data-studio-action]");
			if (!actionButton || studioManagementState.busy) return;
			const action = actionButton.dataset.studioAction || "";
			if (action === "process") {
				void (async () => {
					setStudioManagementBusy(true);
					try {
						await processStudioManagementUpload(actionButton.dataset.uploadId || "");
					} catch (error) {
						setStudioManagementFlash("error", String(error?.message || error));
					} finally {
						setStudioManagementBusy(false);
					}
				})();
				return;
			}
			if (action === "delete") {
				void (async () => {
					setStudioManagementBusy(true);
					try {
						await deleteStudioManagementUpload(actionButton.dataset.uploadId || "");
					} catch (error) {
						setStudioManagementFlash("error", String(error?.message || error));
					} finally {
						setStudioManagementBusy(false);
					}
				})();
				return;
			}
			if (action === "open-batch") {
				void openStudioManagementBatch(actionButton.dataset.batchName || "").catch((error) => {
					setStudioManagementFlash("error", String(error?.message || error));
				});
			}
		});
		annotationCategoryAdd.addEventListener("click", () => {
			const nextIndex = annotationSettings.categories.length + 1;
			annotationSettings.categories.push({
				id: `annotation-category-${Date.now()}-${nextIndex}`,
				name: `类别 ${nextIndex}`,
				color: DEFAULT_ANNOTATION_CATEGORIES[(nextIndex - 1) % DEFAULT_ANNOTATION_CATEGORIES.length].color,
			});
			persistAnnotationSettings();
			renderAnnotationCategoryList();
			applyAnnotationUiSettings();
		});
		annotationTagAdd.addEventListener("click", () => {
			const nextIndex = annotationSettings.reviewTags.length + 1;
			annotationSettings.reviewTags.push(`Tag ${nextIndex}`);
			annotationSettings = normalizeAnnotationSettings(annotationSettings);
			persistAnnotationSettings();
			renderAnnotationTagList();
			renderReviewTagOptions(getSelectedReviewTag());
			syncReviewDirtyState();
			window.setTimeout(() => {
				const inputs = [...document.querySelectorAll("#annotation-tag-list .annotation-tag-name")];
				const target = inputs[inputs.length - 1];
				target?.focus();
				target?.select?.();
			}, 0);
		});
		annotationFocusOpacityInput.addEventListener("input", (event) => {
			annotationSettings.focusOpacity = Math.max(0.5, Math.min(1, parseNumericValue(event.target.value) ?? annotationSettings.focusOpacity));
			annotationSettings.idleOpacity = Math.min(annotationSettings.focusOpacity, annotationSettings.idleOpacity);
			persistAnnotationSettings();
			applyAnnotationUiSettings();
		});
		annotationIdleOpacityInput.addEventListener("input", (event) => {
			annotationSettings.idleOpacity = Math.max(0.5, Math.min(annotationSettings.focusOpacity, parseNumericValue(event.target.value) ?? annotationSettings.idleOpacity));
			persistAnnotationSettings();
			applyAnnotationUiSettings();
		});
		const dateWindowControl = document.getElementById("date-window-control");
		const dateWindowStart = document.getElementById("date-window-start");
		const dateWindowEnd = document.getElementById("date-window-end");
		const dateWindowStartDecrease = document.getElementById("date-window-start-decrease");
		const dateWindowStartIncrease = document.getElementById("date-window-start-increase");
		const dateWindowEndDecrease = document.getElementById("date-window-end-decrease");
		const dateWindowEndIncrease = document.getElementById("date-window-end-increase");
		const dateWindowFixedSpanInput = document.getElementById("date-window-fixed-span");
		const dateWindowQuickCategory = document.getElementById("date-window-quick-category");
		const dateWindowQuickToggle = document.getElementById("date-window-quick-toggle");
		dateWindowControl.addEventListener("mouseenter", () => setDateWindowControlActive(true));
		dateWindowControl.addEventListener("mouseleave", () => {
			currentTimeWindow.hoverEdge = "";
			updateDateWindowEdgeStyles();
			setDateWindowControlActive(false);
		});
		document.querySelectorAll(".date-window-group").forEach(group => {
			group.addEventListener("mouseenter", () => {
				currentTimeWindow.hoverEdge = group.dataset.edge || "";
				updateDateWindowEdgeStyles();
			});
		});
		dateWindowStart.addEventListener("click", () => {
			currentTimeWindow.activeEdge = "start";
			updateDateWindowControl();
		});
		dateWindowEnd.addEventListener("click", () => {
			currentTimeWindow.activeEdge = "end";
			updateDateWindowControl();
		});
		dateWindowStartDecrease.addEventListener("click", (event) => {
			event.stopPropagation();
			currentTimeWindow.activeEdge = "start";
			updateDateWindowControl();
			void nudgeTimeWindow("start", -1);
		});
		dateWindowStartIncrease.addEventListener("click", (event) => {
			event.stopPropagation();
			currentTimeWindow.activeEdge = "start";
			updateDateWindowControl();
			void nudgeTimeWindow("start", 1);
		});
		dateWindowEndDecrease.addEventListener("click", (event) => {
			event.stopPropagation();
			currentTimeWindow.activeEdge = "end";
			updateDateWindowControl();
			void nudgeTimeWindow("end", -1);
		});
		dateWindowEndIncrease.addEventListener("click", (event) => {
			event.stopPropagation();
			currentTimeWindow.activeEdge = "end";
			updateDateWindowControl();
			void nudgeTimeWindow("end", 1);
		});
		dateWindowFixedSpanInput.addEventListener("input", (event) => {
			event.stopPropagation();
			void setCurrentTimeWindowFixedSpanDays(event.target.value, {
				anchorEdge: currentTimeWindow.activeEdge || "start",
			});
		});
		dateWindowQuickCategory.addEventListener("change", (event) => {
			currentTimeWindow.quickSegmentCategoryId = String(event.target.value || "").trim();
			updateDateWindowControl();
		});
		dateWindowQuickToggle.addEventListener("click", (event) => {
			event.stopPropagation();
			toggleCurrentWindowQuickSegment();
		});
		dateWindowControl.addEventListener("wheel", (event) => {
			if (!currentTimeWindow.enabled) return;
			event.preventDefault();
			event.stopPropagation();
			const edge = currentTimeWindow.hoverEdge || currentTimeWindow.activeEdge || "start";
			const delta = event.deltaY > 0 ? 1 : -1;
			void nudgeTimeWindow(edge, delta);
		}, { passive: false });
		dateWindowControl.addEventListener("click", (event) => {
			if (event.target.closest(".date-window-nudge, .date-window-inline-control")) return;
			const group = event.target.closest(".date-window-group");
			if (group) {
				currentTimeWindow.activeEdge = group.dataset.edge || currentTimeWindow.activeEdge || "start";
				updateDateWindowControl();
				return;
			}
			const rect = dateWindowControl.getBoundingClientRect();
			const edge = event.clientX < rect.left + rect.width / 2 ? "start" : "end";
			currentTimeWindow.activeEdge = edge;
			updateDateWindowControl();
		});
		(function initHelpPanel() {
			const panel = document.getElementById("help-panel");
			const btn = document.getElementById("help-toggle-btn");
			const header = document.getElementById("help-header");
			const toggle = () => {
				panel.classList.toggle("collapsed");
				btn.textContent = panel.classList.contains("collapsed") ? "+" : "−";
			};
			btn.addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
			header.addEventListener("click", toggle);
		})();
		window.addEventListener("beforeunload", (event) => {
			if (!reviewFormDirty) return;
			event.preventDefault();
			event.returnValue = "";
		});
		window.addEventListener("resize", debounce(() => {
			renderTimeScrubberControl();
			maybeSyncTriageLayoutMode();
		}, 80));

		const SIDEBAR_MIN = 260, SIDEBAR_MAX = 600, SIDEBAR_DEFAULT = 360;
		let sidebarWidth = parseInt(localStorage.getItem("sidebarWidth") || SIDEBAR_DEFAULT, 10) || SIDEBAR_DEFAULT;
		sidebarWidth = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, sidebarWidth));

		document.getElementById("sidebar-toggle").addEventListener("click", () => {
			const sidebar = document.getElementById("sidebar");
			const willCollapse = !sidebar.classList.contains("collapsed");
			sidebar.classList.toggle("collapsed");
			if (willCollapse) {
				sidebar.style.width = sidebar.style.minWidth = sidebar.style.maxWidth = "";
			} else {
				sidebar.style.width = sidebarWidth + "px";
				sidebar.style.minWidth = sidebarWidth + "px";
				sidebar.style.maxWidth = sidebarWidth + "px";
			}
			if (map) {
				setTimeout(() => {
					map.invalidateSize();
					renderTimeScrubberControl();
					maybeSyncTriageLayoutMode();
				}, 250);
			}
		});

		const sidebarEl = document.getElementById("sidebar");
		const resizeEl = document.getElementById("sidebar-resize");
		resizeEl.addEventListener("mousedown", (e) => {
			if (sidebarEl.classList.contains("collapsed")) return;
			e.preventDefault();
			resizeEl.classList.add("resizing");
			const startX = e.clientX;
			const startW = sidebarEl.offsetWidth;
			const onMove = (ev) => {
				const dx = ev.clientX - startX;
				let w = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, startW + dx));
				sidebarEl.style.width = w + "px";
				sidebarEl.style.minWidth = w + "px";
				sidebarEl.style.maxWidth = w + "px";
				sidebarWidth = w;
				maybeSyncTriageLayoutMode();
			};
			const onUp = () => {
				resizeEl.classList.remove("resizing");
				document.removeEventListener("mousemove", onMove);
				document.removeEventListener("mouseup", onUp);
				localStorage.setItem("sidebarWidth", String(sidebarWidth));
				if (map) {
					map.invalidateSize();
					renderTimeScrubberControl();
					maybeSyncTriageLayoutMode();
				}
			};
			document.addEventListener("mousemove", onMove);
			document.addEventListener("mouseup", onUp);
		});
		sidebarEl.style.width = sidebarWidth + "px";
		sidebarEl.style.minWidth = sidebarWidth + "px";
		sidebarEl.style.maxWidth = sidebarWidth + "px";
		applyThemeMode(themeMode, { persist: false });
		renderReviewerIdentity();
		renderReviewAggregatePanel(null);
		resetStudioManagementForm();
		renderStudioManagementActor();
		renderStudioManagementUploads();
		syncStudioManagementChrome();

		(async function init() {
			initMap();
			applyManifestUiConfig(null);
			applyAnnotationUiSettings();
			renderLayerControls({});
			renderStatusStyleControls();
			syncMapToolsDock();
			await loadBatchList();
			await switchBatch(currentBatchName || batchList[0]?.name || "current", { skipDirtyCheck: true, preserveUid: false });
			if (SHOULD_OPEN_STUDIO_MANAGEMENT_ON_LOAD) openStudioManagement();
		})();
