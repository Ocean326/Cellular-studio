		let currentUiMode = QUERY.get("uiMode") || "chain2";
		const SHOULD_OPEN_STUDIO_MANAGEMENT_ON_LOAD = QUERY.get("openStudioManagement") === "1";
		let currentUiConfig = deepClone(
			currentUiMode === "sim_signal"
				? SIM_SIGNAL_UI_PRESET
				: currentUiMode === "trajectory_layers"
					? TRAJECTORY_LAYERS_UI_PRESET
					: CHAIN2_UI_PRESET
		);
		let filterStateOptions = [...currentUiConfig.filterStateOptions];
		let pointStatusTypes = [...currentUiConfig.pointStatusTypes];
		let layerConfig = deepClone(currentUiConfig.layerConfig);
		let layerLabels = deepClone(currentUiConfig.layerLabels);
		let layerOrder = [...currentUiConfig.layerOrder];
		let triageColumns = deepClone(currentUiConfig.triageColumns);
		let currentLayerFileMap = Object.fromEntries(layerOrder.map(layer => [layer, `${layer}.csv`]));
		let currentReviewReferenceFiles = ["line.csv", "fmm.csv"];
		let currentTimeScrubberPreferredLayers = [];

		let map = null;
		let tileLayer = null;
		let currentUid = null;
		let activeGroup = null;
		let uidList = [];
		let filteredUidList = [];
		let layerStyles = {};
		let statusPointStyles = deepClone(currentUiConfig.pointStatusStyles);
		let csvCache = {};
		let uidMetaCache = {};
		let uidStatesCache = {};
		let precomputedStates = null;
		let reviewIndex = { reviews: {}, counts: {} };
		let reviewApiAvailable = false;
		let reviewerRegistry = [];
		let currentReviewerSession = loadReviewerSession();
		let reviewerSessionModalRequired = false;
		let currentUidAggregate = null;
		let batchList = [];
		let currentBatchName = "";
		let currentBatchMeta = null;
		let currentManifest = null;
		let currentBaseRawDataByLayer = {};
		let currentRawDataByLayer = {};
		let currentFilteredDataByLayer = {};
		let timeScrubberStyleContextCache = {
			batchName: "",
			uid: "",
			gpsRowsRef: null,
			gpsSamples: [],
		};
		let currentExistsByLayer = {};
		let currentDataBase = STATIC_DATA_BASE || "";
		let selectedDecision = "";
		let reviewFormSnapshot = null;
		let reviewFormDirty = false;
		let otherReviewFilterValue = "all";
		let filterRunToken = 0;
		let boardState = null;
		let columnVisibleCounts = { pending: BOARD_PAGE_SIZE, accept: BOARD_PAGE_SIZE, other: BOARD_PAGE_SIZE };
		let filterPanelCollapsed = true;
		let triageLayoutMode = "grid";
		let activeTriageColumnKey = triageColumns[0]?.key || "";
		let reviewAggregateCollapsed = true;
		let reviewAggregateCollapseTouched = false;
		let reviewPanelCollapsed = false;
		let mapToolsOpen = false;
		let renderedCache = new Map();
		let renderedCacheKeys = [];
		let lastRenderZoomBucket = null;
		let timeFocusMarker = null;
		let timelinePinsByTrack = loadTimelineAnnotationStore(TIMELINE_PINS_STORAGE_KEY);
		let timelineSegmentsByTrack = loadTimelineAnnotationStore(TIMELINE_SEGMENTS_STORAGE_KEY);
		let trackEditsByTrack = loadTimelineAnnotationStore(TRACK_EDITS_STORAGE_KEY);
		let replayTimelineState = {
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
		};
		let timeScrubberContextMenuState = {
			open: false,
			pointIndex: null,
			clientX: 0,
			clientY: 0,
		};
		let annotationSettings = loadAnnotationSettings();
		let segmentDraftState = {
			active: false,
			categoryId: "",
			startTime: null,
			previewTime: null,
			startIndex: null,
			previewIndex: null,
		};
		let timeScrubberState = {
			enabled: false,
			selectedLayer: "",
			focusLayers: [],
			allPoints: [],
			hoveredSegmentId: "",
			selectedSegmentId: "",
			visibleStartIndex: 0,
			visibleCount: 0,
			selectedIndex: 0,
			followSelectionOnUpdate: false,
			isDragging: false,
			isOverviewDragging: false,
			overviewDragMode: "",
			overviewDragOffsetSeconds: 0,
		};
		let currentTimeWindow = {
			availableDays: [],
			startDay: "",
			endDay: "",
			activeEdge: "start",
			hoverEdge: "",
			fixedSpanDays: 0,
			quickSegmentCategoryId: "",
			enabled: false,
		};
		let trackEditState = {
			enabled: false,
			selectedPointIds: [],
			anchorPointId: "",
			lastTouchedPointId: "",
			pointRefsById: {},
			pointIdsByLayer: {},
			renderedMarkersByPointId: {},
			selectionLayerKey: "",
			dragging: false,
			dragPointId: "",
			dragOriginDisplayLat: null,
			dragOriginDisplayLon: null,
			dragSnapshot: [],
			dragSuppressClickUntil: 0,
			contextMenuOpen: false,
			contextPointId: "",
			contextField: "",
			contextValue: "",
			statusMessage: "编辑关闭",
			statusTone: "idle",
			lastSavedAt: "",
			undoStack: [],
			redoStack: [],
			dirty: false,
			showCoordinates: false,
			spaceModifierActive: false,
			scrollWheelSuppressed: false,
			saveMenuOpen: false,
			savedBaselineSignature: "",
		};
		let studioManagementState = {
			actor: null,
			uploads: [],
			exportBatches: [],
			exportReviewsByBatch: {},
			exportActiveWorkspace: "upload",
			exportSelectedBatch: "",
			exportSelectedUid: "",
			exportSelectedTag: "",
			exportSelectedDecisions: ["accept", "reject", "skip"],
			exportBusy: false,
			exportDatasetProgressActive: false,
			exportDatasetProgressPercent: 0,
			exportDatasetProgressTimerId: 0,
			exportDatasetProgressResetTimerId: 0,
			exportResult: null,
			busy: false,
			lastRefreshAt: "",
			progressVisible: false,
			progressPercent: 0,
			progressTitle: "等待上传",
			progressDetail: "选择文件后可以看到上传与处理进度。",
			progressTone: "info",
			progressTimerId: 0,
			helpVisible: false,
			helpPinned: false,
			customFieldsExpanded: false,
			customFieldMappings: {
				trajectory4: {},
				signal6: {},
			},
		};
