# trajectory_annotation_studio reviewer 命名空间与多人标注汇总设计

## 1. 背景与目标

当前 `trajectory_annotation_studio` 已经能完成：

- 批次切换
- 三列审阅箱
- 整轨审核 `accept / reject / skip`
- 时间轴 `pins / segments` 标记
- `accepted_assets` 导出

但当前实现仍然是“单 reviewer 最新值”模型：

- 整轨审核最终只保留“每个 `uid` 的一条最新结果”
- 时间轴标记最终只保留“每个 `uid` 的一份最新快照”
- 前端里的 `reviewer` 只是普通文本框，不是真正的身份上下文

这会直接导致 3 个问题：

1. 多个 reviewer 审同一条轨迹时，后保存的人会覆盖前一个人的“最新视图”。
2. 时间轴标记无法按 reviewer 分离，也无法可靠比较不同 reviewer 的标注差异。
3. 导出和汇总阶段没有稳定的“按 reviewer 看结果”和“按轨迹看多人差异”能力。

本设计的目标是把这部分升级为一个稳定、增量、可迁移的多人标注基础设施。

## 2. 本轮设计范围

本轮做的是：

- reviewer 身份进入、保持、切换
- 按 reviewer 命名空间保存整轨审核与时间轴标记
- 同一轨迹聚合同步多个 reviewer 的最新结果
- 支持按 reviewer 导出，以及按轨迹聚合汇总
- 前端保持当前风格，仅做增量入口和增量面板

本轮不做的是：

- 账号密码体系
- 权限审批流
- 数据库化重构
- 强一致实时协同
- 复杂的多人冲突编辑界面

这里的“登录态”定义为：

- 一个轻量的 `reviewer session`
- 用于确定“我现在是谁、我的保存写到哪个命名空间”
- 它不是安全鉴权，不替代反向代理或内网权限控制

## 3. 当前真实约束

当前实现依据以下代码与文档：

- [review_lib.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_lib.py)
- [review_server.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_server.py)
- [index.html](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/index.html)
- [06-后台逻辑与存储说明.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/06-%E5%90%8E%E5%8F%B0%E9%80%BB%E8%BE%91%E4%B8%8E%E5%AD%98%E5%82%A8%E8%AF%B4%E6%98%8E.md)

当前真实行为：

- 整轨审核写到 `review/ledger.jsonl`，再重建 `review/latest_reviews.json`
- `latest_reviews.json` 只按 `uid` 聚合，不区分 reviewer
- 时间轴标记写到 `review/timeline_annotations/<uid>.json`
- 同一个 `uid` 的时间轴快照没有 reviewer 维度
- 前端 triage、搜索、卡片摘要、导出脚本都默认“每条轨迹只有一份最新审核结果”

因此，这次设计不能只是在现有记录里补一个 `reviewer` 字段，否则多人之间仍会在“最新视图”层互相覆盖。

## 4. 设计原则

### 4.1 产品原则

- 默认工作视图必须是“当前 reviewer 视角”，否则 triage 会失真
- 聚合视图必须作为辅助能力，而不是反过来替代个人工作台
- reviewer 身份不能再靠手填文本框决定
- 导出语义必须清晰区分“个人导出”和“多人汇总导出”

### 4.2 工程原则

- 继续使用文件系统存储，不引入数据库
- append-only ledger 继续保留
- 所有“最新视图”都由流水重建或增量刷新
- 写操作必须带命名空间并经过后端校验
- 聚合索引只做缓存和加速，不做唯一事实源

### 4.3 体验原则

- 前端风格保持当前黑白灰磨砂体系
- 不重做整页结构
- reviewer 入口放在已有工具条/说明区域附近
- 右侧详情区增量加入“当前身份”和“多人汇总摘要”

## 5. 批判性改进结论

这部分按照 `proposal-critique-refine` 的思路，对 3 条最直觉但不够稳的方案做了收敛。

### 5.1 方案 A：继续沿用全局 `ledger.jsonl`，只在记录里写 reviewer

保留点：

- 改动最小
- 旧脚本看起来容易兼容

致命问题：

- `latest_reviews.json` 仍然只能按 `uid` 收敛成一条
- triage 仍然会被最后一个保存的人“夺走状态”
- 时间轴标记仍无法区分 reviewer

结论：

- 否决

### 5.2 方案 B：上完整账号系统和数据库

保留点：

- 长期上限最高
- 权限与审计更完整

问题：

- 明显超出当前组内共享工具的复杂度预算
- 会把本轮需求从“标注协作升级”拖成“平台重构”
- 交付速度、维护成本、部署复杂度都会显著上升

结论：

- 否决，保留为远期演进方向

### 5.3 方案 C：轻量 reviewer session + reviewer 命名空间文件存储 + 聚合索引

保留点：

- 与现有文件系统方案连续
- 能真正解决多人互相覆盖
- 能支持按 reviewer 工作、按轨迹汇总
- 可以渐进迁移，不必一口气推翻当前工具

风险：

- 需要补一层 reviewer registry 和聚合索引
- 需要清楚划分“当前 reviewer 视图”和“聚合视图”

结论：

- 采用本方案

## 6. 核心产品决策

### 6.1 reviewer 身份模型

前端首次进入页面时，必须先获得一个 reviewer 身份：

- 输入 `姓名 / 昵称`
- 后端规范化出稳定 `reviewer_id`
- 返回 `display_name`
- 浏览器保存当前 session

约定：

- `display_name`
  用于页面展示与最终导出
- `reviewer_id`
  用于目录名、接口参数、落盘和聚合

推荐规范：

- `reviewer_id` 只允许小写字母、数字、短横线、下划线
- 由后端根据昵称做 slug 化
- 若 slug 已存在但显示名不一致，返回冲突并提示用户改名或复用

### 6.2 reviewer session 语义

这里的 session 是：

- 浏览器本地持久化的当前 reviewer 上下文
- 所有审核保存与时间轴保存都绑定这个 reviewer
- 切换 reviewer 等于切换命名空间

这里的 session 不是：

- 账号密码登录
- 权限认证
- 服务器全局单点身份

### 6.3 triage 默认视图

三列审阅箱默认按“当前 reviewer 的最新审核结果”分列：

- `待审`
  当前 reviewer 还没审过
- `已通过`
  当前 reviewer 最新 `decision = accept`
- `未通过/跳过`
  当前 reviewer 最新 `decision in {reject, skip}`

这样每个人都能有自己的工作面。

多人结果查看走单独的聚合摘要，而不是直接把 triage 改成公共桶。

### 6.4 时间轴标记默认视图

当前 reviewer 只编辑自己的时间轴标记：

- 自己的 `pins`
- 自己的 `segments`

多人聚合只作为只读比较层：

- 显示还有哪些 reviewer 对当前轨迹打过点或段
- 支持后续按 reviewer 展开查看
- 不允许直接编辑别人的标记

### 6.5 导出语义

导出分成两类：

1. `per-reviewer export`
   面向个人工作结果，例如某个 reviewer 的 `accepted_assets`
2. `aggregate export`
   面向 organizer 汇总，例如同一 `uid` 被哪些 reviewer 标了什么

不能再沿用“整个批次只有一个 accepted 导出根”的隐含前提。

## 7. 后端目录与存储合同

## 7.1 目标目录结构

建议把批次下的 `review/` 升级为：

```text
<batch_root>/review/
  system/
    schema_version.json
    reviewer_registry.json
  reviewers/
    <reviewer_id>/
      profile.json
      reviews/
        ledger.jsonl
        latest_reviews.json
      timeline_annotations/
        ledger.jsonl
        <uid>.json
  aggregate/
    stats.json
    by_uid/
      <uid>.json
```

说明：

- `system/reviewer_registry.json`
  存 reviewer 注册表和最近活跃信息
- `reviewers/<reviewer_id>/reviews/ledger.jsonl`
  该 reviewer 的整轨审核流水
- `reviewers/<reviewer_id>/reviews/latest_reviews.json`
  该 reviewer 的“按 uid 最新审核结果”
- `reviewers/<reviewer_id>/timeline_annotations/<uid>.json`
  该 reviewer 对该 uid 的最新时间轴标记
- `aggregate/by_uid/<uid>.json`
  按轨迹聚合多个 reviewer 的最新摘要，供最终查看与导出使用

## 7.2 整轨审核记录 schema

审核记录建议升级为：

```json
{
  "schema_version": 2,
  "uid": "12345",
  "sample_id": "12345",
  "decision": "accept",
  "reviewer_id": "ocean",
  "reviewer_name": "Ocean",
  "timestamp": "2026-04-14T08:00:00Z",
  "notes": "line 合理，轨迹连续",
  "reference_source": "line.csv"
}
```

兼容策略：

- 对外 API 在过渡期仍可回传 `reviewer`
- 但服务端内部以 `reviewer_id + reviewer_name` 为准

## 7.3 时间轴标记 schema

时间轴标记建议升级为：

```json
{
  "schema_version": 2,
  "uid": "12345",
  "sample_id": "12345",
  "reviewer_id": "ocean",
  "reviewer_name": "Ocean",
  "updated_at": "2026-04-14T08:00:00Z",
  "pins": [],
  "segments": []
}
```

其中：

- `pins`
  继续保存单点图钉
- `segments`
  继续保存段落标签

但它们的归属从“uid 最新快照”改为“reviewer + uid 最新快照”。

## 7.4 聚合摘要 schema

`aggregate/by_uid/<uid>.json` 推荐结构：

```json
{
  "uid": "12345",
  "sample_id": "12345",
  "generated_at": "2026-04-14T08:10:00Z",
  "latest_reviews": [
    {
      "reviewer_id": "ocean",
      "reviewer_name": "Ocean",
      "decision": "accept",
      "timestamp": "2026-04-14T08:00:00Z",
      "notes": "line 合理",
      "reference_source": "line.csv"
    },
    {
      "reviewer_id": "teammate-a",
      "reviewer_name": "Teammate A",
      "decision": "reject",
      "timestamp": "2026-04-14T08:03:00Z",
      "notes": "地铁段不合理",
      "reference_source": "fmm.csv"
    }
  ],
  "timeline_annotation_summary": [
    {
      "reviewer_id": "ocean",
      "reviewer_name": "Ocean",
      "updated_at": "2026-04-14T08:02:00Z",
      "pin_count": 1,
      "segment_count": 3,
      "categories": ["通勤", "驻留"]
    }
  ]
}
```

注意：

- 聚合文件是缓存和展示加速层
- 真正事实源仍然是 reviewer 命名空间下的 ledger 与快照

## 8. 前端交互设计

## 8.1 首次进入

首次打开页面，如果本地没有有效 reviewer session：

- 弹出一个轻量磨砂登录框
- 输入 `姓名 / 昵称`
- 点击“进入标注”
- 后端返回规范化 reviewer profile
- 浏览器持久化当前 reviewer session

登录框只做身份选择，不做密码输入。

## 8.2 顶部新增入口

在当前页面右上角说明区域附近，增量加入：

- `当前标注者：<display_name>`
- `切换标注者`
- `查看多人汇总`

风格要求：

- 不大改当前页面结构
- 继续沿用半透明、磨砂、弱对比的工具条风格
- 切换 reviewer 时，如有未保存修改，复用现有脏表单确认逻辑

## 8.3 审核面板调整

当前右侧审核面板中的 `reviewer-input` 不再作为自由文本输入框。

替换方案：

- 面板显示当前身份：`当前标注者：Ocean`
- 保留 `切换` 按钮
- 保存时后端直接使用 session 中的 reviewer

原因：

- 如果 reviewer 仍然可随手改，会让“当前命名空间”和“实际落盘 reviewer”脱节
- 对多人协作来说，这属于高风险误操作

### 8.3.1 当前元信息摘要

`review-meta` 改为两层信息：

1. 当前 reviewer 视角
   - 当前 reviewer 对该 uid 的最新 decision、timestamp、reference_source
2. 多人汇总摘要
   - 该 uid 已有多少 reviewer 参与
   - 决策分布，例如 `accept=2 / reject=1 / skip=0`

## 8.4 三列审阅箱

三列仍保持当前布局和风格，但默认只显示当前 reviewer 的状态。

每张卡片建议显示：

- `UID`
- 当前 reviewer 的 latest decision badge
- 当前 reviewer 的 notes 摘要
- 一个多人小徽标，例如 `3 reviewers`

点击卡片后，在右侧详情区加载：

- 当前 reviewer 可编辑视图
- 同轨迹多人只读摘要

## 8.5 多人汇总面板

右侧在审核面板下方新增一个折叠区：

- 标题：`多人标注汇总`
- 默认折叠
- 点开后展示当前 `uid` 的所有 reviewer 最新记录

每个 reviewer 摘要项显示：

- `reviewer_name`
- `decision`
- `timestamp`
- `notes` 摘要
- `reference_source`
- `pin_count / segment_count`

V1 只要求只读摘要，不要求在主界面直接叠加所有人的时间轴段落。

## 8.6 搜索与筛选逻辑

默认搜索逻辑拆成两层：

1. 当前 reviewer 工作层
   - 搜索 `uid`
   - 搜索当前 reviewer 的 `notes`
   - 搜索轨迹状态标签
2. 聚合层
   - 当前 `uid` 详情页再展示其他 reviewer 的结果

这样可以避免左侧 triage 因为多人 notes 混在一起而变乱。

## 9. 后端接口设计

## 9.1 reviewer identity 相关接口

新增：

- `POST /api/reviewers/session`
  - 入参：`display_name`
  - 出参：规范化后的 `reviewer_id`、`reviewer_name`、`created_at`、`last_seen_at`
- `GET /api/reviewers`
  - 返回已知 reviewer 列表，供切换器和 organizer 查看

接口语义：

- `session` 只是“申请/确认一个 reviewer 命名空间”
- 不做密码校验
- 但会做非法字符校验、slug 冲突处理、目录安全校验

## 9.2 整轨审核接口

保留：

- `GET /api/reviews`
- `POST /api/reviews`

升级语义：

- `GET /api/reviews?reviewer_id=<id>`
  返回该 reviewer 的 `latest_reviews`
- `GET /api/reviews?uid=<uid>&reviewer_id=<id>`
  返回该 reviewer 对该 uid 的最新审核
- `POST /api/reviews`
  必须带 `reviewer_id`

新增：

- `GET /api/reviews/aggregate?uid=<uid>`
  返回该 uid 的所有 reviewer 最新审核摘要

## 9.3 时间轴标记接口

保留：

- `GET /api/timeline-annotations`
- `POST /api/timeline-annotations`

升级语义：

- `GET /api/timeline-annotations?uid=<uid>&reviewer_id=<id>`
  返回当前 reviewer 的最新标记
- `POST /api/timeline-annotations`
  必须带 `reviewer_id`

新增：

- `GET /api/timeline-annotations/aggregate?uid=<uid>`
  返回该 uid 的各 reviewer 标记摘要

## 9.4 导出接口

当前：

- `POST /api/export/accepted`

升级为两类：

1. `POST /api/export/accepted`
   - 必须指明 `reviewer_id`
   - 导出该 reviewer 的 `accepted_assets`
2. `POST /api/export/review-aggregate`
   - 生成聚合汇总结果
   - 用于 organizer 后处理

## 10. 导出与汇总设计

## 10.1 per-reviewer 导出

建议输出：

```text
<batch_root>/accepted_assets/
  reviewers/
    <reviewer_id>/
      samples/
      accepted_reviews.jsonl
      export_manifest.json
```

这样不会把多个 reviewer 的 `accept` 混进同一目录。

## 10.2 aggregate 导出

建议新增：

```text
<batch_root>/review_exports/
  aggregate/
    by_uid.jsonl
    by_reviewer.jsonl
    conflicts.jsonl
    export_manifest.json
```

文件语义：

- `by_uid.jsonl`
  每条轨迹一行，聚合所有 reviewer 最新结果
- `by_reviewer.jsonl`
  每个 reviewer 的统计摘要
- `conflicts.jsonl`
  只列出存在决策冲突或标记差异的 uid

## 10.3 汇总页面或汇总脚本目标

最终 organizer 需要能回答这些问题：

- 某条轨迹被哪些 reviewer 看过
- 不同 reviewer 的 decision 是否一致
- 哪些轨迹存在明显冲突，值得复审
- 某个 reviewer 当前审了多少、通过多少、拒绝多少

因此聚合导出必须先服务这些问题，而不是先做花哨报表。

## 11. 迁移与兼容策略

## 11.1 旧数据现状

当前已有批次里常见结构仍是：

```text
<batch_root>/review/
  ledger.jsonl
  latest_reviews.json
  timeline_annotations/
    <uid>.json
    ledger.jsonl
```

## 11.2 迁移原则

- 不直接覆盖旧文件
- 迁移过程必须可回滚
- 旧文件默认视作“legacy 单 reviewer 数据”

## 11.3 推荐迁移路径

新增一个迁移脚本，把旧结构导入到：

```text
review/reviewers/<legacy_reviewer_id>/
```

推荐默认 reviewer：

- `legacy-import`
  或
- `organizer-legacy`

迁移完成后：

- 旧文件保留
- 新服务优先读 reviewer 命名空间
- 若某批次还没迁移，可只读兼容 legacy 结构

## 11.4 兼容窗口

兼容窗口建议分两步：

1. `read compatibility`
   新代码能读老结构，也能读新结构
2. `write freeze on legacy`
   一旦完成迁移，新的写入只进入 reviewer 命名空间

## 12. 功能需求与验收口径

### 12.1 Functional Requirements

`FR-001: MUST`
首次进入页面时，若本地无 reviewer session，系统必须要求输入姓名/昵称后才能进入标注页面。

`FR-002: MUST`
系统必须为每个 reviewer 建立稳定命名空间，并将整轨审核与时间轴标记写入该命名空间。

`FR-003: MUST`
三列审阅箱必须按当前 reviewer 的最新审核结果工作，而不是全局共享状态。

`FR-004: MUST`
系统必须支持在同一条轨迹上查看多个 reviewer 的最新审核摘要。

`FR-005: MUST`
系统必须支持切换当前 reviewer，并在切换时保持未保存修改保护。

`FR-006: MUST`
系统必须支持按 reviewer 导出 accepted 结果。

`FR-007: MUST`
系统必须支持按轨迹聚合导出多个 reviewer 的审核结果。

`FR-008: SHOULD`
系统应支持 organizer 在界面上查看 reviewer 列表与简单统计。

### 12.2 Non-Functional Requirements

`NFR-001: MUST`
所有写回操作必须避免路径穿越和非法 reviewer_id。

`NFR-002: MUST`
多线程请求下，同一 reviewer 命名空间的写回必须串行化，避免 ledger 与 latest file 不一致。

`NFR-003: MUST`
JSON 索引文件写入必须采用临时文件 + 原子替换，避免部分写入损坏。

`NFR-004: SHOULD`
聚合读取不应阻塞主审核流程；优先读取缓存索引，而不是每次全量扫目录。

`NFR-005: SHOULD`
前端新增 reviewer 入口不应破坏现有审阅节奏，页面主要交互路径保持连续。

## 13. 推荐实施顺序

推荐按 4 步做，而不是一次性混改：

1. 后端 reviewer registry 与 reviewer 命名空间落盘
2. 前端 reviewer session 与当前 reviewer triage
3. 聚合摘要与聚合导出
4. legacy 迁移与回归验证

详细阶段与测试计划见：

- [09-reviewer-命名空间开发与验证计划.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/09-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E5%BC%80%E5%8F%91%E4%B8%8E%E9%AA%8C%E8%AF%81%E8%AE%A1%E5%88%92.md)
