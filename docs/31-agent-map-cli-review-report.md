# Agent CLI 与地图辅助标注试验汇报

更新时间：2026-05-03

## 结论

当前 `trajectory_annotation_studio` 的 Agent-Native CLI（面向 agent 的命令行入口）已经是第一版可用状态：它能让 agent 稳定读取批次和样本上下文、materialize（落盘）CSV、提交 review、读写 timeline annotation（时间线分段标注）、导出 aggregate/bundle，并能跑开发期 roundtrip smoke。

但这轮试验也说明：CLI-only（纯命令行）最多适合初筛和结构化初标；真正要做高可信的“挑选还原较好的轨迹，然后分段打标签”，必须把 map snapshot（地图截图/地图上下文导出）纳入 agent 输入。没有地图时，agent 会对 road/stay 过度保守，或者只能基于 CSV gap 做推断，无法判断道路贴合、折返、自相交、河流/铁路/园区边界等空间语义。

本轮主案例选择 `UID 15448`，batch 为 `arena-s02-task01-20260423T063517Z-raw-competitor-layers`。它有完整 `signal.csv`、`truth.csv`、`truth_line.csv`、`truth_fmm.csv`，还暴露了一个长 gap，适合比较无可视化和带地图可视化的效果。

## 当前 CLI 已落实内容

CLI 化不是 GUI DOM 自动化，而是在现有 `review_server` 事实源外包了一层 agent-friendly 的 HTTP/JSON client 和命令树。

已落实的主要文件：

- `scripts/studio_agent_client.py`：标准库 HTTP client，封装 server API。
- `scripts/studio_agent_cli.py`：命令树入口。
- `scripts/tests/test_studio_agent_cli.py`：CLI 到 server 的真实链路测试。
- `docs/29-agent-native-cli.md`：目标、命令面、用法、边界。
- `docs/30-agent-native-cli-progress-report.md`：当前进展和风险。

已落实的命令面：

- `health`
- `batch list/show`
- `sample list/inspect/materialize`
- `reviewer start/list`
- `review get/submit`
- `timeline get/put`
- `aggregate uid/export`
- `bundle export`
- `dev roundtrip`

当前边界判断：

- GUI 继续负责人审、地图、时间轴和精细几何判断。
- CLI 负责 agent-native 读写、批处理、弱监督闭环和开发期 smoke。
- `track_edits` 服务端已有，但 CLI 还没有单独封装。
- 大规模 reviewer-aware queue（按 reviewer/review_status 的高效队列快照）还没做完。

## 本轮 agent 试验

### 1. Codex preview-only agent

`Confucius` 选择 `UID 1023384`。它只基于 preview 证据，发现前段 signal 和 nearest GPS 基本固定，因此保守切成多个 `stay`。

这个结果适合作为反例：纯 preview 能识别显然停留，但看不到完整移动段，也无法判断 road 的道路合理性。它不是坏结果，而是证明了“文本预览不足以完整分段”。

### 2. Codex CLI/CSV agent

`Kuhn` 选择 `UID 15448`。它基于完整 CLI 和 materialized CSV，给出以下分段：

- `1678306706-1678318041`：`stay`
- `1678318041-1678324778`：`road`
- `1678324778-1678327385`：`road`
- `1678327385-1678331476`：`stay_inferred_gap`
- `1678331476-1678332101`：`road`
- `1678332101-1678332669`：`stay`
- `1678332669-1678336981`：`road`

这个结果已经明显好于 preview-only：它能利用 `truth_line.csv` / `truth_fmm.csv` 的 segment 边界，也能发现 `1678327385-1678331476` 是一个 coverage gap（覆盖缺口）。

但它仍然不能确认 road 是否贴路，不能确认 gap 是否真的是停留，只能标成 `stay_inferred_gap`。

### 3. Cursor CLI-only subagent

按 `$subagent-cursor` 以只读方式调用 Cursor，使用 `composer-2-fast`、`safe` permission、`plan` mode。Cursor 也选择 `UID 15448`，结论为 `needs-review`。

它的主要判断是：CLI/CSV 足够发现候选和 gap，但没有地图时无法验证道路贴合、折返、自相交和长 gap 语义。这和 Codex CLI/CSV agent 的盲点一致。

### 4. 带地图可视化

本轮已经生成真实地图截图，底图为高德在线瓦片。

总览图：

![UID 15448 map overview](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gaode.png)

gap zoom 图：

![UID 15448 gap zoom](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gap_zoom_gaode.png)

地图确认了两个关键点：

- `road` 段能和北京城区道路形态对齐，agent 不再只是看经纬度数字猜。
- `1678327385-1678331476` 的 gap 集中在北京工人体育场附近，`truth.csv` 在该窗口 136 点且唯一坐标为 1，所以更像 `stay_inferred_gap`，但仍应保留 inferred/待复核标记。

## UID 15448 证据

materialize 输出：

- `/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/15448_context`
- `signal.csv`：1857 行
- `truth.csv`：1012 行
- `truth_line.csv`：1265 行
- `truth_fmm.csv`：263 行

地图产物：

- `/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gaode.png`
- `/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gap_zoom_gaode.png`
- `/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_summary.json`

关键 gap：

- 时间：`1678327385-1678331476`
- 长度：4091 秒
- `truth.csv`：136 点
- 唯一坐标数：1
- 坐标：`116.448305,39.931135`
- `signal.csv`：6 行
- 地图位置：北京工人体育场附近

## 多模态地图标注方案

建议把 agent 标注链路分成四层，而不是让一个 agent 直接“看 CSV 猜标签”。

第一层：候选样本推荐。

CLI 输出每个 UID 的基础质量摘要，包括文件完整性、时间跨度、点数、bbox、`truth_line/fmm` coverage、gap 数量、segment 数量、异常大跳点、review 状态。agent 先选“还原较好且值得标注”的样本，而不是随机挑。

第二层：结构化文本包。

`sample inspect/materialize` 继续提供 CSV 和 JSON，但新增 `segment summary`。每段至少包括 start/end、duration、source layer、点数、唯一坐标数、首尾坐标、平均/最大速度、gap 前后连接关系、候选 label、confidence。

第三层：地图视觉包。

新增 `sample map-snapshot` 或 `sample visual-context export`，为 agent 输出包含底图的 PNG/HTML：总览图、每个 segment 的 zoom 图、gap zoom 图、异常点 zoom 图。底图需要支持 online basemap（在线底图）和 offline tiles（离线瓦片）两种模式。

第四层：agent review payload。

timeline annotation payload 应把 `label`、`evidence`、`confidence`、`sourceLayers`、`visualEvidenceRefs`、`needsHumanReview` 做成一等字段。这样 agent 不只是写一个分段，而是写“为什么这么分、看了哪些证据、哪些地方仍需人审”。

## CLI 还缺什么

P0：补地图上下文导出。

- `sample map-snapshot --uid ... --layers truth,truth_line,truth_fmm,signal`
- `sample map-snapshot --uid ... --focus gap|segment:<id>|bbox`
- 输出 PNG、HTML、metadata JSON。
- health 检查要说明在线瓦片是否可用，离线瓦片是否可用。

P0：补 segment summary 和 coverage gap。

- `sample segment-summary --uid ...`
- 直接输出每段点数、时长、唯一坐标、首尾坐标、覆盖层和 gap。
- 对 `truth_line/fmm` 断档但 `truth.csv` 连续的窗口给出 warning。

P1：补多源对齐摘要。

- 对每个 segment 汇总 `signal/truth/truth_line/truth_fmm` 的覆盖情况。
- 输出 `source_alignment`，让 agent 不必自己写 CSV 聚合脚本。

P1：补样本推荐队列。

- `sample recommend --goal segment-labeling --min-quality ...`
- 结合还原质量、coverage、review_status、是否有足够地图证据排序。

P1：补 timeline payload schema helper。

- `timeline draft --uid ... --from-segment-summary`
- `timeline validate --payload-file ...`
- label enum、confidence、evidence、visual refs 都要有 schema。

P2：封装 `track_edits`。

- 服务端已有 `GET/POST /api/track-edits`，CLI 应补 `track-edits get/put/export`。

P2：降噪 inspect。

- 当前 inspect 里一些 expected 404 或缺图层噪声会干扰 agent，需要区分 fatal/missing optional layer/expected absent。

## 下一步最小落地

建议下一步先做一个小闭环，不要一下做完整平台：

1. 做 `sample segment-summary --uid`。
2. 做 `sample map-snapshot --uid`，至少支持在线地图总览和 gap zoom。
3. 做 `timeline validate`，固定 agent payload schema。
4. 用 `UID 15448` 做回归样例，验证 agent 能从文本包 + 地图包输出相同或更稳的分段。

这个切片最直接回应本轮试验暴露的问题：CLI 已经能读写，但 agent 真正需要的是“结构化证据 + 带地图的视觉证据 + 可验证 payload”。
