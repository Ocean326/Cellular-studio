# Studio CLI 系统进展与开发计划报告

报告日期：2026-05-04（Asia/Shanghai）
证据窗口：2026-05-03 本轮 `studio-cli` leader/subagent 实验
工作区：`/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio`

## 直接结论

本轮已经把当前标注平台从“主要面向人工 UI 的 review server”推进到一条可由 agent 操作的 `studio-cli` 闭环：能发现样本、物化样本材料、生成地图上下文、写回分段多 tag timeline、写回轨迹编辑草案、验证 timeline，并导出 reviewer bundle。

最关键的落地不是“做了一个命令壳”，而是已经拿同一批 0416 local1000 样本跑通了 10 条轨迹的测试闭环：10 个 UID 都有 timeline 读回，合计 456 个分段，所有分段都有 `semanticTags` 和 `visualEvidenceRefs`；其中 6 个不准确段挂上了 6 个 `trackEditRefs`，对应 3 条轨迹的 point-level draft correction。10 个 UID 都通过 `timeline validate`。

边界也要说清楚：这批结果是 map-backed CLI/agent 测试标注，不是人工 gold label；地图证据是 `visual_context.json + Leaflet index.html + offline tile URL`，不是 10 张已渲染截图；轨迹编辑是 `draft_micro_adjust_after_map_review` 草案，需要人工在地图上 QC 后才能作为修正真值。

## 本轮 Leader/Subagent 编排

`delivery-router` 路由判断：这是端到端交付任务，主线程保持 leader/owner，Cursor 作为快速执行与 QA worker，Codex subagent 作为只读复核 lane。

`subagent-cursor` 使用方式：采用 `composer-2-fast` operator lane，把任务拆成有边界的 worker 包，要求输出证据路径、风险和剩余缺口。已留下的 Cursor 日志包括：

| 轮次 | Worker 目标 | 证据 |
|---|---|---|
| Round 1 | 数据选择、CLI gap 盘点 | `.codex_run/studio_cli_leader_20260503/round1/logs/` |
| Round 2 | CLI review、UID visual annotation 试验 | `.codex_run/studio_cli_leader_20260503/round2/logs/` |
| Round 3 | 材料、历史标注、CLI 缺口、draft payload 四路并行 | `.codex_run/studio_cli_leader_20260503/round3/` |
| Round 4 | export flags 实现/QA、最终证据地图 | `.codex_run/studio_cli_leader_20260503/round4/` |
| Final QA | bundle/map/readback 风险核对 | `.codex_run/studio_cli_leader_20260503/final_cursor_qa3/logs/export-map-qa.log` |

Cursor QA 明确指出的关键事实已纳入本报告：`bundle_after_decisions` 是 10 样本导出索引；同级 `bundle` 和 `readback_quality_summary.bundle_export` 的 `sample_count=0` 不能被误引用为 10 条成果。

## 已落实的 CLI 能力

当前 `scripts/studio_agent_cli.py` 的顶层命令面包括：

`health`、`batch`、`sample`、`reviewer`、`review`、`timeline`、`track-edits`、`aggregate`、`bundle`、`dev`。

与本轮目标直接相关的能力：

| 能力域 | 已有命令 | 本轮用途 |
|---|---|---|
| 样本发现/材料化 | `sample list`、`sample inspect`、`sample materialize` | 拉取 UID、生成 agent 可读上下文 |
| 分段规划 | `sample segment-summary` | 把轨迹切成 agent 可处理的分段摘要 |
| 地图上下文 | `sample visual-context` | 生成 `visual_context.json` 和 Leaflet `index.html` |
| Timeline 标注 | `timeline get`、`timeline put`、`timeline validate` | 写回分段多 tag、准确/不准确/不确定标签 |
| 轨迹编辑 | `track-edits get`、`track-edits put`、`track-edits export` | 写回 point-level correction 草案 |
| Review 决策 | `review`、`reviewer` | 写回 accept/skip 和 trajectory tags |
| 导出 | `bundle export --interval-seconds --timestamp-unit --labeled-span-only` | 生成 reviewer bundle / segment dataset index |

测试状态：本轮已在包父目录 `/Users/ocean/Documents/Playground/Cellular-projects` 跑通过 `python3 -m unittest trajectory_annotation_studio.scripts.tests.test_studio_agent_cli trajectory_annotation_studio.scripts.tests.test_studio_agent_segment_context trajectory_annotation_studio.scripts.tests.test_studio_agent_timeline_validation`，结果为 `Ran 37 tests ... OK`。日志已归档到 `.codex_run/studio_cli_leader_20260503/verification/studio_agent_cli_unittest_20260504.log`。

运行入口 caveat：当前源码态从项目目录内直接执行 `python3 -m trajectory_annotation_studio.scripts.studio_agent_cli` 会因为包父目录不在 `sys.path` 而失败；可选用 `python3 scripts/studio_agent_cli.py ...`，或切到 `/Users/ocean/Documents/Playground/Cellular-projects` 后执行模块入口，或安装 editable package 后使用 `studio-agent` console script。

## 10 条轨迹闭环事实

目标批次：`20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local`
Reviewer：`studio-cli-codex-20260503`
UID：`100453`、`100617`、`101051`、`101599`、`106303`、`106863`、`110992`、`111601`、`112483`、`114545`

读回事实：

| 指标 | 数值 |
|---|---:|
| UID 数 | 10 |
| Timeline 分段总数 | 456 |
| `semanticTags` 覆盖 | 456/456 |
| `visualEvidenceRefs` 覆盖 | 456/456 |
| 准确段 | 430 |
| 不确定段 | 20 |
| 不准确段 | 6 |
| 有 track edit 的 UID | 3 |
| point-level draft patches | 6 |
| review 决策 | 8 accept / 2 skip |
| timeline validate | 10/10 ok |

两条 `skip` 是 `101051` 与 `106303`，原因是 10 个分段全部标为 `uncertain`，需要人类 QC 后再进入 clean acceptance。

三条带修正草案的轨迹是 `106863`、`110992`、`112483`。每条各有 2 个不准确段、2 个 `trackEditRefs`、2 个 point patches。

## 地图证据现状

10 个 UID 都有 map-backed visual context：

| 地图字段 | 当前状态 |
|---|---|
| `basemap.mode` | `offline_tiles` |
| `tile_url_template` | `http://127.0.0.1:8016/offline_tiles/beijing/{z}/{x}/{y}.png` |
| 前端渲染 | 每个 UID 目录都有 Leaflet `index.html`，使用 `L.map` 与 `L.tileLayer(vc.tile_url_template, ...)` |
| 几何 | `layers[0].geojson.geometry.type = LineString` |
| 点位 | 8 条长轨迹为 373-600 个坐标点，2 条短轨迹为 10 个坐标点 |
| 标记 | 长轨迹 48 个 markers，短轨迹 10 个 markers |

地图证据路径：`.codex_run/studio_cli_leader_20260503/visual_contexts/<UID>/visual_context.json` 与同目录 `index.html`。

运行时 caveat：`index.html` 依赖本机 review server 的 `8016` 端口服务离线瓦片和 Leaflet 静态资源。没有 server 时，HTML 仍能作为地图上下文契约存在，但瓦片可能空白。

## 当前主要缺口

1. 缺 `sample map-snapshot`：现在有地图 HTML/JSON，但没有一键生成可归档 PNG/SVG 截图的 CLI。
2. 缺 `timeline draft`：分段多 tag payload 仍主要靠外部脚本/agent 草拟，CLI 未内建草案生成器。
3. 缺 `sample recommend --goal segment-labeling`：样本挑选策略还没有产品化，不能自动挑“还原较好、适合标注”的队列。
4. 缺 `queue snapshot`：缺 agent/human 混合标注队列的状态快照、锁定和恢复。
5. 缺 full trip-chain export view：现在 bundle_after_decisions 更像 10 样本数据索引，timeline readback 才是标签证据；还需要把分段标签、准确性、track edit refs 打成完整出行链导出。
6. 缺 corrected trajectory export：track edits 能写回草案，但还没有导出“原轨迹 + 修正点 + corrected trajectory”的完整产物。
7. validator 还不够严格：应检查 `visualEvidenceRefs` 指向的文件真实存在、`trackEditRefs` 与 `track_edits` patch id 双向一致、地图 context 中 tile/vendor 是否可服务。
8. ontology/tag 体系还粗：`semanticTags` 已能承载多 tag，但目前混有 `matcher:*`、`workflow:*`、`legacy:ocean0416:*`。真正全过程出行链需要明确 travel mode、stay/move、transfer、reconstruction quality、edit status 等 tag namespace。
9. UI/CLI 的编辑闭环还没完全合流：CLI 能写 point patches，但 UI 侧的人类 QC、diff preview、accept correction 还需要更强的交互和状态同步。

## 下一轮 Studio CLI 开发计划

建议按 5 轮推进，主 agent 负责架构与验收，Cursor Composer 2 Fast 负责边界清晰的 worker 包。

### Round A：证据与 QA 基建

目标：把“可视化一定有地图”和“10 条导出不能误读”固化为机器检查。

Worker 包：

| Worker | 写入范围 | 交付 |
|---|---|---|
| Map snapshot worker | `scripts/studio_agent_cli.py`、`web/offline_tile_lib.py`、相关 tests | 新增 `sample map-snapshot`，能从 visual context 渲染 PNG，并验证非空瓦片 |
| Visual ref validator worker | `scripts/studio_agent_timeline_validation.py`、tests | `timeline validate --strict-refs` 检查 visual refs、track edit refs、文件存在性 |
| Bundle manifest worker | `scripts/studio_agent_cli.py`、bundle tests | 明确 `bundle_after_decisions`/empty bundle 的命名和 QA 断言，避免 sample_count=0 误用 |

### Round B：分段多 tag authoring

目标：把本轮手工/agent 草拟 payload 的流程变成 CLI 原生命令。

Worker 包：

| Worker | 写入范围 | 交付 |
|---|---|---|
| Timeline draft worker | `scripts/studio_agent_segment_context.py`、`scripts/studio_agent_cli.py` | 新增 `timeline draft --uid --goal trip-chain`，输出可 validate 的草案 |
| Tag ontology worker | `docs/`、validation schema、tests | 定义 namespace：`chain:*`、`mode:*`、`quality:*`、`edit:*`、`legacy:*` |
| Sample recommend worker | CLI sample 子命令、tests | 新增 `sample recommend --goal segment-labeling --limit N`，优先挑还原好且地图证据充分的轨迹 |

### Round C：轨迹编辑闭环

目标：把“不准确段 -> 轨迹编辑 -> 修正结果”做成可复核链路。

Worker 包：

| Worker | 写入范围 | 交付 |
|---|---|---|
| Track edit draft worker | `track-edits` CLI、tests | 从不准确段生成 edit draft，并与 segment refs 双向绑定 |
| Corrected trajectory export worker | export 模块、tests | 导出 `raw_track.csv`、`track_edits.json`、`corrected_track.csv`、diff summary |
| Human QC bridge worker | `web/` track edit UI、review API tests | UI 中能看到 patch、接受/拒绝修正、回写 correction decision |

### Round D：出行链导出与报告化

目标：让一次标注能直接产出训练/评测/审计都可用的数据包。

Worker 包：

| Worker | 写入范围 | 交付 |
|---|---|---|
| Trip-chain export worker | bundle/export 模块 | 导出完整分段出行链 JSONL/CSV，含 semanticTags、quality、visual refs、track edit refs |
| Report generator worker | `scripts/studio_agent_cli.py`、`reports/` templates | 新增 `aggregate report` 或 `bundle report`，自动生成本轮这样的系统报告和样本报告 |
| Regression suite worker | `scripts/tests/` | 建立 10 UID fixture，覆盖 timeline/readback/map/export/track-edits |

### Round E：Agent 队列与并行开发常态化

目标：把“主 agent + Cursor subagent”的开发/标注方式固化。

Worker 包：

| Worker | 写入范围 | 交付 |
|---|---|---|
| Queue snapshot worker | CLI queue 模块、tests | `queue snapshot/claim/release/status`，支持 agent 并行标注不互相覆盖 |
| Cursor work-order templates worker | `docs/` 或 `.codex_run/templates/` | 标准化 worker prompt：scope、allowed actions、acceptance criteria、output schema |
| End-to-end smoke worker | tests + docs | 一条命令跑完 sample recommend -> map snapshot -> timeline draft -> validate -> put -> export |

## 下一步建议

最先做 Round A。原因很简单：用户已经明确“可视化一定要有地图”，而当前地图证据仍依赖 HTML/本地 server；同时 bundle 的 `sample_count=0`/`10` 分歧容易在后续报告里造成误判。先把地图截图、严格引用校验和 bundle manifest contract 做稳，再扩展 timeline draft 和 corrected trajectory export。

## 证据索引

| 证据 | 路径 |
|---|---|
| 最终 readback 汇总 | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback_quality_summary.json` |
| 10 UID timeline readback | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback/timelines/` |
| 10 UID validation | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/validate/` |
| 3 UID track edits | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback/track_edits/` |
| 地图上下文 | `.codex_run/studio_cli_leader_20260503/visual_contexts/` |
| 10 样本 bundle 索引 | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/export/bundle_after_decisions/segment_label_dataset.json` |
| Cursor map/export QA | `.codex_run/studio_cli_leader_20260503/final_cursor_qa3/logs/export-map-qa.log` |
| CLI 单元测试日志 | `.codex_run/studio_cli_leader_20260503/verification/studio_agent_cli_unittest_20260504.log` |
