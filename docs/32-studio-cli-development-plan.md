# Studio-CLI 开发计划：全过程出行链、多 tag 分段、准确段标注与轨迹编辑闭环

更新时间：2026-05-03

## 1. 本轮目标

这版 `studio-cli` 的目标不是再做一个 GUI 替身，而是把标注平台中最适合 agent / 批处理 / 回归验证的部分 CLI 化，形成一条稳定链路：

1. 从批次里推荐“还原得还可以、值得标注”的轨迹。
2. 对轨迹按全过程出行链做分段。
3. 每段允许多个 tag，而不是只能写一个 `categoryName`。
4. 标出轨迹还原准确段、不准确段和不确定段。
5. 对不准确段通过轨迹编辑功能修正，并把修正和原始分段绑定。
6. 导出可训练、可复查、可回放的数据包。

核心原则：

- `review_server` 和现有 reviewer namespace 继续做事实源。
- CLI 做 agent-native 的证据整理、payload 生成、校验、批量读写和回归测试。
- 地图可视化必须进入 agent 输入；没有地图的 CLI-only 结果只能当初筛或低置信初标。
- 0416 的已有准确还原段标注要保留为历史事实，不破坏、不误读、不直接当成最终 ontology。

## 2. 路由结论

按本轮使用的三个入口：

- `delivery-router`：这是端到端交付计划，应该由主 agent 做单一 owner，分阶段推进。
- `architect-router`：这是跨 CLI、server schema、地图证据、track edit、agent orchestration 的架构问题，主线应走 broad architect lane。
- `proposal-critique-refine`：已有方案基础是“CLI + agent + 地图 + track edit”，本轮重点是批判、修补和固化执行计划，而不是重新发散多个方案。

因此开发方式建议为：

- 主 agent 负责 schema/API 边界、地图证据 contract、迁移策略、worker 包拆分、最终集成和验收。
- Cursor subagent 做边界清晰的实现包：CLI 命令、client wrapper、单元测试、文档样例。
- Codex subagent 更适合做只读 review、样本试标、回归证据审计，不建议让它和 Cursor 同时改同一组文件。

## 3. 当前已落实内容

当前已有 `Agent-Native CLI` 第一版，主要文件是：

- `scripts/studio_agent_client.py`
- `scripts/studio_agent_cli.py`
- `scripts/tests/test_studio_agent_cli.py`
- `docs/29-agent-native-cli.md`
- `docs/30-agent-native-cli-progress-report.md`
- `docs/31-agent-map-cli-review-report.md`

已落实命令面：

```bash
studio-agent health
studio-agent batch list
studio-agent batch show
studio-agent sample list
studio-agent sample inspect
studio-agent sample materialize
studio-agent reviewer start
studio-agent reviewer list
studio-agent review get
studio-agent review submit
studio-agent timeline get
studio-agent timeline put
studio-agent aggregate uid
studio-agent aggregate export
studio-agent bundle export
studio-agent dev roundtrip
```

已经证明可行的能力：

- agent 可以不操作 GUI，直接读取 batch/sample/review/timeline/aggregate。
- agent 可以 materialize CSV 到本地，供外部模型或脚本分析。
- CLI 可以写 review 和 timeline annotation，并通过 aggregate 回读。
- `dev roundtrip` 已经能作为开发期 smoke。

但现在 CLI 仍停在“能读写基础标注”的层次，还没有形成“高可信分段标注 + 地图证据 + 编辑修正”的闭环。

## 4. 0416 1000uid 标注事实

目标批次：

```text
data/batches/20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local_studio
```

注意：仓库里还有另一个名字接近的 0416 1000uid-like 批次，但当前已经有 `ocean` timeline segment 保存事实的是上面这个目录。正式做 migration 或批量补标前，CLI 应要求显式传入 batch id，并在输出里回显 resolved batch，避免 agent 误扫到另一个批次。

当前 reviewer namespace：

```text
review/reviewers/ocean/
```

当前统计：

- 已 review UID：7 个。
- 决策分布：3 个 `accept`，4 个 `reject`。
- 有 timeline 分段文件：4 个 UID。
- timeline truth 当前在 `review/reviewers/ocean/timeline_annotations/<uid>.json`。
- `segments/` 目录不是当前主事实源。

已有 timeline 文件：

- `100453.json`
- `100617.json`
- `101599.json`
- `111601.json`

现有分段形态：

- `100453` 是旧手工风格：`categoryId=focus-segment`，`categoryName=骑行`。
- `100617`、`101599`、`111601` 多数是 `window_quick`：`categoryName=保留段`，`segmentScope=date_window`，`sourceLayerKey=snap`。
- 多数 `segmentPolicy` 为 `null` 或默认，不能假设现在已经有严格非重叠策略。

关键判断：

- 这些是“准确还原段/保留段”的历史标注证据，不是完整出行链 ontology。
- 不应把 `categoryName` 继续塞成复杂多 tag 字符串。
- 需要通过 migration/read-compat 把旧字段映射成 `legacyLabel` / `sourceAnnotation`，保留可追溯性。
- 三类 tag 要分开处理：`trajectory_tags` 是整轨 review 级；`timeline_annotations.segments[]` 是时间段级；`states_index.json` 一类索引 tag 只适合筛选，不是人工修正真值。

## 5. 上一轮 agent 与地图实验结论

实验批次：

```text
arena-s02-task01-20260423T063517Z-raw-competitor-layers
```

主案例：

```text
UID 15448
```

无地图结果：

- preview-only agent 只能保守识别明显停留，无法完整分段。
- CLI/CSV agent 能利用 `truth_line.csv` / `truth_fmm.csv` 做结构化分段，并发现 coverage gap。
- Cursor CLI-only subagent 也判断为 `needs-review`，原因是无法验证道路贴合、折返、自相交、地物语义和长 gap 位置。

带地图结果：

- 已生成高德底图截图：
  - `.codex_run/agent_map_trial/uid15448_map_gaode.png`
  - `.codex_run/agent_map_trial/uid15448_map_gap_zoom_gaode.png`
  - `.codex_run/agent_map_trial/uid15448_map_summary.json`
- 地图确认 road 段与北京城区道路形态基本一致。
- 关键 gap `1678327385-1678331476` 位于北京工人体育场附近，`truth.csv` 在该窗口 136 点且唯一坐标为 1，更适合标为 `stay_inferred_gap` / review-needed，而不是硬判移动或准确停留。

结论：

- 地图不是锦上添花，而是 agent 标注链路的 P0 输入。
- CLI 必须能导出含真实底图的 map snapshot 或 visual context package。
- 没有地图时，agent 输出要自动降级为 `confidence<=medium` 或 `needsHumanReview=true`。

## 6. 目标数据模型 vNext

### 6.1 Segment 一等字段

建议新增 timeline vNext segment 字段，先以兼容方式扩展，不直接破坏当前 `categoryId/categoryName/color/startTime/endTime`：

```json
{
  "id": "seg-15448-1678318041-1678324778",
  "startTime": 1678318041,
  "endTime": 1678324778,
  "categoryId": "travel-chain",
  "categoryName": "move",
  "legacyLabel": "",
  "chainType": "move",
  "chainSubType": "road",
  "modeTags": ["vehicle_like", "road_matched"],
  "placeTags": [],
  "qualityTags": ["map_aligned", "continuous"],
  "reconstructionQuality": "accurate",
  "errorTypes": [],
  "correctionStatus": "none",
  "trackEditRefs": [],
  "sourceLayers": ["truth", "truth_line", "truth_fmm", "signal"],
  "visualEvidenceRefs": ["map-overview", "map-seg-31"],
  "evidence": [
    {
      "type": "map",
      "ref": "map-seg-31",
      "summary": "segment follows urban road shape"
    }
  ],
  "confidence": 0.82,
  "needsHumanReview": false
}
```

### 6.2 Tag 维度

全过程出行链不要设计成一个巨大的单选 enum。建议拆成多维 tag：

- `chainType`：`stay`、`move`、`transfer`、`gap`、`uncertain`。
- `chainSubType`：`road`、`stay_point`、`stay_inferred_gap`、`walk_like`、`bike_like`、`vehicle_like`、`transit_like`、`unknown`。
- `modeTags`：交通方式或运动形态，多选。
- `placeTags`：住宅、工作地、商圈、体育场、站点、园区等空间语义，多选，可为空。
- `qualityTags`：`map_aligned`、`continuous`、`sparse_signal`、`large_gap`、`single_coord_truth`、`fmm_break` 等证据性标签。
- `reconstructionQuality`：`accurate`、`inaccurate`、`uncertain`。
- `errorTypes`：`offroad`、`teleport`、`wrong_match`、`missing_segment`、`over_smoothing`、`loop_artifact`、`timestamp_gap` 等。
- `correctionStatus`：`none`、`planned`、`edited`、`verified`。

### 6.3 Track edit 绑定

轨迹编辑不应只是另存一份点 patch；它需要能回指到“不准确段”：

```json
{
  "editSetId": "edit-15448-seg-32-v1",
  "uid": "15448",
  "reviewer_id": "ocean",
  "targetSegmentId": "seg-15448-1678324778-1678327385",
  "targetTimeRange": [1678324778, 1678327385],
  "reason": "wrong_match",
  "patches": [],
  "status": "verified"
}
```

服务端已有 `GET/POST /api/track-edits`，CLI 需要补齐 `track-edits get/put/export`，并在 export 中把 `timeline segment -> track edits -> corrected trajectory` 串起来。

## 7. CLI 缺口清单

P0：

- `sample segment-summary`：输出每段点数、时长、唯一坐标、首尾坐标、速度异常、source coverage、gap 和 warning。
- `sample map-snapshot` 或 `sample visual-context export`：必须含真实地图底图，输出 overview PNG/HTML、segment zoom、gap zoom、metadata JSON。
- `timeline validate`：校验 vNext 多 tag schema、时间覆盖、segmentPolicy、证据引用、trackEditRefs。
- `timeline draft`：从 segment-summary 和 map evidence 生成可编辑初稿 payload。

P1：

- `sample recommend --goal segment-labeling`：按还原质量、coverage、gap、review 状态和地图证据可用性推荐样本。
- reviewer-aware queue snapshot：避免 `sample list --review-status` 对大量 UID 做 N+1 aggregate 调用。
- `aggregate export` 扩展：导出 full trip chain、accurate/inaccurate/corrected 三类视图。
- inspect 降噪：区分 fatal、optional layer missing、expected absent，减少 agent 误判。

P2：

- `track-edits get/put/export`：封装已有 server API。
- `sample visual-context compare`：固定无地图/有地图对照，用于 agent 评估。
- batch-level regression pack：自动跑 0416 legacy、UID15448 map/gap、track-edit export 的 smoke。

## 8. 开发轮次

### Round 0：冻结 schema 与迁移目标

主 agent owner。

要做：

- 写清 timeline vNext 字段白名单。
- 修改 server normalizer 前先定兼容策略。
- 明确旧 `categoryName=保留段/骑行` 的迁移映射。
- 明确 `segmentPolicy` 默认值和严格导出的处理方式。
- 明确 track edit 与 segment 的绑定方式。

验收：

- 0416 四个 timeline 文件原样可读。
- vNext payload 不会被 normalizer 静默吞掉关键字段。
- 旧字段和新字段在导出时可同时保留。

### Round 1：结构化分段摘要

Cursor Worker A 可做。

要做：

- client 增加 segment-summary 请求方法，或先在 CLI 侧基于 materialized CSV 实现。
- CLI 增加：

```bash
studio-agent sample segment-summary --uid 15448 --json
```

输出至少包括：

- segment list
- coverage gaps
- per-layer row counts
- duration
- unique coordinate count
- start/end coordinate
- speed/jump warnings
- source alignment

验收：

- UID15448 能复现 6 个 source segment 和 1 个 4091s gap。
- 0416 已标注 UID 能输出已有 timeline segment + source coverage。

### Round 2：地图视觉证据包

主 agent owner，Cursor Worker 可做外围命令，不建议独立改核心地图 contract。

要做：

- CLI 增加：

```bash
studio-agent sample map-snapshot --uid 15448 --layers truth,truth_line,truth_fmm,signal --json
studio-agent sample visual-context export --uid 15448 --include-map --focus gaps,segments
```

输出：

- `overview.png`
- `overview.html`
- `segment-<id>.png`
- `gap-<idx>.png`
- `visual_context.json`

metadata 必须写：

- basemap provider
- online/offline tile mode
- bbox
- layer colors
- segment/gap refs
- screenshot paths
- tile availability / fallback status

验收：

- visual package 必须能在无 GUI 人工操作下生成。
- PNG 中必须有真实地图底图，不允许只有白底折线。
- UID15448 的 gap zoom 能稳定生成。

### Round 3：timeline vNext draft/validate

Cursor Worker B 可做，主 agent 审 schema。

要做：

```bash
studio-agent timeline draft --uid 15448 --from-segment-summary summary.json --from-visual-context visual_context.json --output draft.json
studio-agent timeline validate --payload-file draft.json
```

校验规则：

- segment 时间合法。
- segment overlap/gap 是否符合 `segmentPolicy`。
- `chainType/reconstructionQuality/confidence` 必填。
- `visualEvidenceRefs` 必须能在 visual context 中找到。
- `trackEditRefs` 指向的 edit set 必须存在或标记为 planned。
- legacy 字段只能作为兼容字段，不能承载多 tag。

验收：

- UID15448 能生成 vNext draft。
- 0416 legacy timeline 能通过兼容校验，并提示“legacy-only，不是完整 trip-chain”。

### Round 4：track-edits CLI 闭环

Cursor Worker C 可做。

要做：

```bash
studio-agent track-edits get --uid 15448 --reviewer-id ocean
studio-agent track-edits put --uid 15448 --reviewer-id ocean --payload-file edits.json
studio-agent track-edits export --uid 15448 --reviewer-id ocean --include-corrected
```

验收：

- 不准确 segment 可以绑定 `targetSegmentId`。
- edit payload 可 roundtrip。
- export 能同时看到 original segment、error type、patch、corrected trajectory ref。

### Round 5：样本推荐与 agent review queue

Cursor Worker D 可做队列 API/CLI，主 agent 做排序策略。

要做：

```bash
studio-agent sample recommend --goal segment-labeling --reviewer-id ocean --limit 20 --json
studio-agent queue snapshot --reviewer-id ocean --json
```

排序建议：

- layer 完整性高。
- map snapshot 可生成。
- fmm/line coverage 较高。
- gap 数量可解释，不是完全破碎。
- 未被当前 reviewer 完整标注。
- 0416 legacy 准确段优先作为迁移/补全候选。

验收：

- 大 batch 不再靠 N+1 aggregate 扫描。
- recommend 输出能解释排序理由。

### Round 6：导出与训练/质检数据包

主 agent owner，Cursor Worker 可补测试。

要做：

导出三类数据：

- `full_trip_chain_labels.jsonl`
- `reconstruction_accuracy_segments.jsonl`
- `trajectory_corrections.jsonl`

每条记录包含：

- uid
- reviewer
- source batch
- segment id
- time range
- multi tags
- reconstruction quality
- evidence refs
- correction refs
- legacy source annotation

验收：

- 0416 legacy 标注能进入 `legacy_source` 字段。
- vNext 标注能进入完整 trip-chain 字段。
- inaccurate + edited 的样本能导出 corrected 视图。

### Round 7：回归包与开发守门

Cursor Worker E 可做测试矩阵。

固定回归样例：

- 0416 batch：legacy timeline migration/read compatibility。
- UID15448：segment-summary + map/gap visual evidence。
- track-edit synthetic sample：inaccurate segment + correction roundtrip。

建议测试：

```bash
python3 -m unittest trajectory_annotation_studio.scripts.tests.test_studio_agent_cli
python3 -m unittest trajectory_annotation_studio.web.test_review_lib
python3 -m unittest trajectory_annotation_studio.web.test_review_server
```

新增测试方向：

- `test_segment_summary_cli`
- `test_visual_context_manifest`
- `test_timeline_vnext_validate`
- `test_track_edits_cli`
- `test_segment_export_with_corrections`

## 9. Cursor worker 包拆分

### Worker A：segment-summary

允许改：

- `scripts/studio_agent_cli.py`
- `scripts/studio_agent_client.py`
- `scripts/tests/test_studio_agent_cli.py`
- 必要时新增 `scripts/studio_segment_summary.py`

禁止改：

- timeline vNext schema
- track edit normalizer
- map snapshot 核心实现

交付：

- `sample segment-summary`
- JSON 输出 fixture
- UID15448 回归断言

### Worker B：timeline draft/validate

允许改：

- `scripts/studio_agent_cli.py`
- `scripts/studio_agent_client.py`
- `scripts/tests/test_studio_agent_cli.py`
- `web/review_lib.py` 中 timeline normalizer 的白名单扩展
- `web/test_review_lib.py`

禁止改：

- track edit API 行为
- map rendering

交付：

- `timeline validate`
- `timeline draft`
- legacy-only warning
- vNext 字段不被静默丢弃

### Worker C：track-edits CLI

允许改：

- `scripts/studio_agent_cli.py`
- `scripts/studio_agent_client.py`
- `scripts/tests/test_studio_agent_cli.py`
- 必要时补 `web/test_review_server.py`

禁止改：

- timeline schema 主设计
- segment-summary 排序策略

交付：

- `track-edits get`
- `track-edits put`
- `track-edits export`
- segment/edit binding smoke

### Worker D：queue/recommend

允许改：

- `scripts/studio_agent_cli.py`
- `scripts/studio_agent_client.py`
- `web/review_lib.py`
- `web/review_server.py`
- `web/test_review_server.py`

禁止改：

- track edit payload schema
- map rendering

交付：

- `queue snapshot`
- `sample recommend`
- 不走 N+1 aggregate 的 reviewer-aware summary
- 输出排序解释

### Worker E：docs/examples/regression

允许改：

- `docs/`
- `scripts/tests/`
- `web/test_*`
- `docs/examples/`

禁止改：

- production code，除非主 agent 明确转交

交付：

- README / docs 命令样例更新
- UID15448 visual-context example
- 0416 legacy migration note
- regression checklist

## 10. 主 agent 集成规则

主 agent 每轮都要做：

1. 先读 worker 输出，不直接覆盖。
2. 跑相关测试。
3. 检查 schema 是否兼容 0416 legacy truth。
4. 检查地图 evidence 是否真的含底图。
5. 检查 CLI 输出是否适合 agent 消费：结构化 JSON、错误可解释、路径可追溯。
6. 把新增行为写回 docs。

Cursor subagent prompt 必须包含：

- 你不是独占代码库，不能 revert 他人改动。
- 只改允许文件。
- 输出 changed files / tests run / residual risks。
- 如果需要越界改文件，先停止并说明。

## 11. 方案批判与修补

### Value lens

原方案价值成立：CLI 化能把标注从“单次 GUI 人审”升级成“agent 可批量试标、人可复核、证据可追溯、导出可训练”的链路。

需要修补的点：

- 目标不能只写“轨迹打标签”，必须明确三类数据产物：全过程出行链、准确/不准确段、编辑修正。
- 0416 legacy 标注不能被误升级成完整 ontology，只能作为准确段/保留段历史证据。

### Feasibility lens

最大可行性风险是当前 `_normalize_timeline_segment` 会丢掉未知字段。若直接让 agent 写多 tag payload，会出现“CLI 看起来提交成功，关键字段落盘消失”的失败。

修补：

- Round 0/3 先扩 normalizer 白名单和 validate，再允许 worker 批量写 vNext。
- map snapshot 先做最小可用：overview + gap zoom，不一开始做复杂交互。

### Failure-mode lens

主要失败模式：

- 无地图时 agent 过度自信，把 gap / off-road / wrong-match 误标成准确 road。
- 多 tag 被塞进 `categoryName`，后续无法训练。
- track edit 和 segment 脱节，导出时不知道修的是哪段。
- worker 并行改同一文件导致 schema/API 不一致。

修补：

- `visualEvidenceRefs` 成为 high-confidence 标注的必要证据。
- `timeline validate` 阻止 schema 漂移。
- track edit 加 `targetSegmentId` / `targetTimeRange`。
- Worker 包按文件和责任拆分，主 agent 保持 schema owner。

## 12. 推荐执行顺序

最小闭环不应一口气做完整平台，建议按以下顺序推进：

1. Round 0：主 agent 定 schema 和迁移边界。
2. Round 1：Worker A 做 `sample segment-summary`。
3. Round 2：主 agent 做地图 visual-context contract 和最小 map snapshot。
4. Round 3：Worker B 做 `timeline draft/validate`。
5. Round 4：Worker C 做 `track-edits` CLI。
6. Round 6：主 agent 整合导出。
7. Round 5/7：队列推荐和回归包可并行穿插。

最小可交付版本定义：

- 对 UID15448：CLI 能导出 segment summary + 带地图 visual context + timeline vNext draft。
- 对 0416：CLI 能读取 legacy 标注，输出 migration warning，并能补全过程多 tag 分段。
- 对一个 synthetic inaccurate segment：CLI 能写 track edit，导出 correction bundle。

达到这三个条件后，`studio-cli` 才算从“agent 可读写”升级到“agent 可参与标注生产”。
