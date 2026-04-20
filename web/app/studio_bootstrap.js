(function bootstrapTrajectoryStudio() {
	const CHAIN2_TRIAGE_COLUMNS = [
		{ key: "pending", title: "待审", subtitle: "还没有 latest review" },
		{ key: "accept", title: "已通过", subtitle: "latest decision = accept" },
		{ key: "other", title: "未通过/跳过", subtitle: "latest decision = reject / skip" }
	];

	const CHAIN2_UI_PRESET = {
		mode: "chain2",
		title: "信令轨迹演示与调试预览",
		searchPlaceholder: "搜索 UID / tag / 当前 notes / 状态...",
		filterTitle: "按状态筛选 UID（来源: fmm/line/od）",
		filterStateOptions: ["road", "subway", "railway", "unmatch", "stay"],
		pointStatusTypes: ["road", "subway", "railway", "unmatch", "stay"],
		layerOrder: ["raw", "snap", "od", "fmm", "line"],
		layerConfig: {
			raw:  { defaultColor: "#808080", defaultOpacity: 0.7, hasLine: true, dashArray: "5,5", kind: "default" },
			snap: { defaultColor: "#2196f3", defaultOpacity: 0.6, hasLine: true, dashArray: null, kind: "default" },
			od:   { defaultColor: "#f44336", defaultOpacity: 0.5, hasLine: false, isOD: true, kind: "od" },
			fmm:  { defaultColor: "#4caf50", defaultOpacity: 0.55, hasLine: true, dashArray: null, kind: "default" },
			line: { defaultColor: "#b8860b", defaultOpacity: 0.7, hasLine: true, dashArray: null, lineOnly: true, kind: "line" }
		},
		layerVisibility: { raw: false, snap: true, od: false, fmm: true, line: true },
		pointStatusStyles: {
			road: { color: "#4caf50", size: 5 },
			subway: { color: "#9c27b0", size: 5 },
			railway: { color: "#795548", size: 5 },
			unmatch: { color: "#ffd700", size: 5 },
			stay: { color: "#000000", size: 5 }
		},
		layerLabels: { raw: "raw", snap: "snap", od: "od", fmm: "fmm", line: "line" },
		triageColumns: CHAIN2_TRIAGE_COLUMNS,
		hideReviewPanel: false,
		annotationEnabled: true,
		statusStyleTitle: "状态样式（fmm/line 点）",
		helpContentHtml: `
			<h5>交互</h5>
			<ul>
				<li>点击地图上的点可查看该点的<strong>状态</strong>和<strong>时间</strong></li>
				<li><strong>时间标签常显</strong>：右下角图层面板现在支持按图层开启“标签常显”，勾选后无需点击，直接在地图上展示该图层的时间/停留信息</li>
				<li><strong>标签标注</strong>：时间轴右键支持“打单点标签”和“开始段落标记”；段落标记会以当前点为起点，跟随鼠标预览，到下一次点击时落成一个带颜色的时间段</li>
				<li><strong>三列审阅箱</strong>：左侧按当前标注者的“待审 / 已通过 / 未通过或跳过”分栏展示 UID，点击任意卡片即可切换轨迹并加载当前标注者的 latest review</li>
				<li><strong>筛选</strong>：搜索框同时匹配 UID、当前标注者 notes 和状态词；状态筛选支持 road/subway/railway/unmatch/stay 的任一命中或全部命中</li>
				<li><strong>编辑与流转</strong>：已审 UID 再次打开后可直接修改并保存；保存后默认跳到当前筛选结果中的下一条待审 UID</li>
				<li><strong>时间轴</strong>：日期区间条上方新增拖动式时间轴；拖动后会在地图上用气泡高亮当前时间点，左右按钮可平移当前时间轴窗口，滚轮和右上角缩放键可低敏调整时间范围</li>
				<li><strong>日期窗口快标</strong>：日期条右侧支持输入“跨度 x 天”；0 表示不限，大于 0 时起止日期会按固定天数联动。选好整段标签后，可将当前日期窗口一键保存成整段标记，再次点击可取消或更新标签</li>
				<li><strong>Studio 管理</strong>：页面右侧贴边新增圆形上传按钮，点击后会弹出磨砂管理浮窗，可直接创建上传、触发处理和打开生成后的批次</li>
				<li><strong>标注设置</strong>：右上角“标注设置”可自定义段落类别、颜色和顺序，并调节时间轴的聚焦/未聚焦透明度</li>
				<li><strong>图层/样式</strong>：地图右下角提供折叠式浮动面板</li>
			</ul>
			<h5>图层含义（raw / snap / od / fmm / line）</h5>
			<div class="layer-desc">
				<strong>raw</strong>：原始信令轨迹点（未处理）<br>
				<strong>snap</strong>：卡尔曼平滑后的轨迹点<br>
				<strong>od</strong>：OD 分割结果（驻留 stay / 移动 move 的起止点）<br>
				<strong>fmm</strong>：FMM 匹配后的点（投影到道路/地铁/铁路）<br>
				<strong>line</strong>：FMM 匹配后的路径线（按 segment 分段）
			</div>
			<h5>状态含义（fmm/line 点）</h5>
			<div class="state-desc">
				<strong>road</strong>：匹配到道路网<br>
				<strong>subway</strong>：匹配到地铁网<br>
				<strong>railway</strong>：匹配到铁路网<br>
				<strong>unmatch</strong>：未匹配到任何网络<br>
				<strong>stay</strong>：驻留点（OD 判定为停留）
			</div>
		`
	};

	const SIM_SIGNAL_UI_PRESET = {
		mode: "sim_signal",
		title: "模拟信令轨迹演示与调试预览",
		searchPlaceholder: "搜索 UID / tag / 当前 notes / 状态...",
		filterTitle: "按状态筛选 UID（来源: GPS 状态 + 模拟切换特征）",
		filterStateOptions: ["stay", "walking", "bicycling", "driving", "ping_pong", "long_jump"],
		pointStatusTypes: ["stay", "walking", "bicycling", "driving"],
		layerOrder: ["gps", "signal", "stations"],
		layerConfig: {
			gps: { defaultColor: "#1565c0", defaultOpacity: 0.7, hasLine: true, dashArray: null, kind: "gps", review_reference: true },
			signal: { defaultColor: "#e65100", defaultOpacity: 0.72, hasLine: true, dashArray: null, kind: "signal", review_reference: true },
			stations: { defaultColor: "#5d4037", defaultOpacity: 0.85, hasLine: false, kind: "stations", pointRadius: 4 }
		},
		layerVisibility: { gps: true, signal: true, stations: false },
		pointStatusStyles: {
			stay: { color: "#111827", size: 5 },
			walking: { color: "#2e7d32", size: 4 },
			bicycling: { color: "#1565c0", size: 4 },
			driving: { color: "#c62828", size: 4 }
		},
		layerLabels: { gps: "GPS", signal: "模拟信令", stations: "基站" },
		triageColumns: CHAIN2_TRIAGE_COLUMNS,
		hideReviewPanel: false,
		annotationEnabled: true,
		statusStyleTitle: "状态样式（GPS 点）",
		helpContentHtml: `
			<h5>交互</h5>
			<ul>
				<li>点击左侧样本卡片即可切换 UID，并在地图上叠加查看 GPS、模拟信令和基站位置</li>
				<li><strong>整轨标注</strong>：顶部标注栏支持保留 / 排除 / 跳过、Tag 与备注，保存后会按待审队列自动流转</li>
				<li><strong>筛选</strong>：搜索框匹配 UID；状态筛选支持 stay/walking/bicycling/driving，以及模拟切换特征 ping_pong / long_jump</li>
				<li><strong>时间轴</strong>：日期区间条上方新增拖动式时间轴；默认聚焦一层，拖动后会在地图上浮起当前时间点的信息气泡，滚轮/缩放键可调整时间窗</li>
				<li><strong>日期窗口快标</strong>：日期条右侧支持固定“跨度 x 天”；0 表示不限，在多日窗口里可直接选择整段标签，把当前窗口一键保存成整段标记</li>
				<li><strong>Studio 管理</strong>：页面右侧贴边新增圆形上传按钮，点击后会弹出磨砂管理浮窗，可直接创建上传、触发处理和打开生成后的批次</li>
				<li><strong>标签标注</strong>：时间轴右键可打单点标签，也可以按“标注设置”里定义的类别启动段落标记</li>
				<li><strong>图层/样式</strong>：地图右下角提供图层显隐、颜色、透明度和顺序调整；状态样式只作用于 GPS 点</li>
			</ul>
			<h5>图层含义（GPS / 模拟信令 / 基站）</h5>
			<div class="layer-desc">
				<strong>GPS</strong>：输入的原始 GPS 轨迹点，按 stay/walking/bicycling/driving 着色<br>
				<strong>模拟信令</strong>：重生成后的基站连接序列，按时间串联显示，并可查看 CID 与时间区间<br>
				<strong>基站</strong>：当前 UID 涉及到的唯一基站点位，用于对照信令切换位置
			</div>
			<h5>筛选状态含义</h5>
			<div class="state-desc">
				<strong>stay / walking / bicycling / driving</strong>：来自输入 GPS 的状态标签<br>
				<strong>ping_pong</strong>：检测到 A→B→A 形式的来回切换<br>
				<strong>long_jump</strong>：相邻信令点位之间出现较大的空间跃迁
			</div>
		`
	};

	const TRAJECTORY_LAYERS_UI_PRESET = {
		mode: "trajectory_layers",
		title: "轨迹多图层对照预览",
		searchPlaceholder: "搜索 UID / tag / sample_id / 备注...",
		filterTitle: "按多图层轨迹样本筛选",
		filterStateOptions: [],
		pointStatusTypes: [],
		layerOrder: ["gps", "tier1", "tier2", "tier3", "tier4"],
		layerConfig: {
			gps: { defaultColor: "#0f766e", defaultOpacity: 0.85, hasLine: true, dashArray: null, kind: "gps", review_reference: true },
			tier1: { defaultColor: "#475569", defaultOpacity: 0.72, hasLine: true, dashArray: "2,4", kind: "signal" },
			tier2: { defaultColor: "#2563eb", defaultOpacity: 0.72, hasLine: true, dashArray: "3,3", kind: "signal" },
			tier3: { defaultColor: "#ea580c", defaultOpacity: 0.78, hasLine: true, dashArray: null, kind: "signal" },
			tier4: { defaultColor: "#7c3aed", defaultOpacity: 0.82, hasLine: true, dashArray: null, kind: "signal", review_reference: true }
		},
		layerVisibility: { gps: true, tier1: true, tier2: true, tier3: true, tier4: true },
		pointStatusStyles: {},
		layerLabels: {
			gps: "GPS 真值",
			tier1: "Tier-1",
			tier2: "Tier-2",
			tier3: "Tier-3",
			tier4: "Tier-4"
		},
		triageColumns: CHAIN2_TRIAGE_COLUMNS,
		hideReviewPanel: false,
		annotationEnabled: true,
		statusStyleTitle: "状态样式",
		helpContentHtml: `
			<h5>交互</h5>
			<ul>
				<li>左侧点击任意样本后，地图会叠加展示同一条轨迹的 GPS 与 4 个 tier 图层</li>
				<li><strong>整轨标注</strong>：顶部标注栏支持保留 / 排除 / 跳过、Tag 与备注，适合在多层对照时直接给整条轨迹下结论</li>
				<li><strong>标签标注</strong>：时间轴右键可打单点标签，也可以按“标注设置”里定义的类别启动段落标记</li>
				<li><strong>Studio 管理</strong>：页面右侧贴边新增圆形上传按钮，点击后会弹出磨砂管理浮窗，可直接创建上传、触发处理和打开生成后的批次</li>
				<li><strong>图层顺序</strong>：右下角面板可调整显隐、颜色、透明度和顺序，适合观察从 starter 到 realistic 的递进差异</li>
				<li><strong>时间轴</strong>：默认优先跟随 GPS 或当前可定位图层，可拖动查看同一时刻不同图层的落点差异</li>
				<li><strong>日期窗口快标</strong>：日期条右侧支持设置固定跨度并一键生成整段标记；0 表示不限，适合快速圈定某几天的窗口进行审阅</li>
				<li><strong>原始 6 元组</strong>：tier 图层可直接承载 <code>uid/cid/lat/lon/t_in/t_out</code> 这类原始事件流，不要求先转成旧版 raw/snap/fmm 文件族</li>
			</ul>
			<h5>图层含义</h5>
			<div class="layer-desc">
				<strong>GPS</strong>：组织者保留的真值轨迹<br>
				<strong>Tier-1 ~ Tier-4</strong>：同一条真值轨迹在不同仿真真实度下生成的 raw 6 元组信令层
			</div>
		`
	};

	const GAODE_TILE = "https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}";
	const QUERY = new URLSearchParams(window.location.search);
	const STATIC_DATA_BASE = QUERY.get("resultRoot") || "";
	const REVIEW_API_BASE = QUERY.get("reviewApi") || "/api";
	const INITIAL_BATCH_NAME = QUERY.get("batch") || "";
	const CACHE_MAX = 24;
	const BOARD_PAGE_SIZE = 60;
	const TRIAGE_STACK_WIDTH_THRESHOLD = 430;
	const MAX_BUCKET_DETAIL_ROWS = 12;
	const TIME_SCRUBBER_MAX_POINTS = Number.POSITIVE_INFINITY;
	const TIME_SCRUBBER_MIN_VISIBLE_POINTS = 8;
	const TIME_SCRUBBER_SHIFT_RATIO = 0.72;
	const TIME_SCRUBBER_ZOOM_STEP = 0.14;
	const TIME_SCRUBBER_OVERVIEW_EDGE_PAD = 10;
	const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
	const REVIEWER_SESSION_STORAGE_KEY = "trajectoryReviewerSessionV1";
	const ANNOTATION_SETTINGS_STORAGE_KEY = "trajectoryAnnotationSettingsV2";
	const TIMELINE_PINS_STORAGE_KEY = "trajectoryTimelinePinsV2";
	const TIMELINE_SEGMENTS_STORAGE_KEY = "trajectoryTimelineSegmentsV2";
	const DEFAULT_ANNOTATION_CATEGORIES = [
		{ id: "focus-segment", name: "重点段", color: "#60a5fa" },
		{ id: "review-segment", name: "待复核", color: "#f59e0b" },
		{ id: "abnormal-segment", name: "异常段", color: "#f97316" },
	];
	const DEFAULT_LAYER_COLOR_PALETTE = [
		"#0f766e",
		"#2563eb",
		"#ea580c",
		"#0891b2",
		"#7c3aed",
		"#16a34a",
		"#dc2626",
		"#b45309",
		"#475569",
		"#be185d",
		"#4f46e5",
		"#0d9488",
	];
	const DEFAULT_REVIEW_TAG_OPTIONS = [];
	const REVIEW_DECISION_LABELS = {
		accept: "保留",
		reject: "排除",
		skip: "跳过",
	};
	const SHOW_REVIEW_AGGREGATE = false;

	window.TrajectoryStudioBootstrap = Object.freeze({
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
	});
})();
