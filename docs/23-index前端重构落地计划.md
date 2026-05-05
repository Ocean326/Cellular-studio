# index 前端重构落地计划

## 1. 本计划目标

这份计划不是“最终理想态蓝图”，而是面向当前仓库现实的完整落地版本，用来把 [`web/index.html`](../web/index.html) 从超大单文件演进成可持续维护的前端壳体。

当前阶段目标只有 4 个：

1. 保持现有主入口、现有行为和现有批次工作流稳定
2. 把前端主边界从“一个页面大脚本”收敛成清晰能力域
3. 把高复用、低风险、可验证的逻辑逐步迁出 `index.html`
4. 在迁移过程中补齐运行时合同和回归护栏，避免“CI 绿但页面半坏”

## 2. 当前基线

截至 `2026-04-18`：

- 稳定 bootstrap 常量已在 [`../web/app/studio_bootstrap.js`](../web/app/studio_bootstrap.js)
- `studio_admin` 的第一批纯逻辑 / adapter 已在 [`../web/app/features/studio_admin/studio_management_core.js`](../web/app/features/studio_admin/studio_management_core.js)
- 架构方案已落在 [`22-index前端模块化重构方案.md`](./22-index前端模块化重构方案.md)
- 已补前端模块合同测试：
  - [`../web/test_studio_management_ui_contract.py`](../web/test_studio_management_ui_contract.py)
  - [`../web/test_frontend_module_contract.py`](../web/test_frontend_module_contract.py)

## 3. 最终阶段边界

### 3.1 页面壳

`index.html` 最终保留：

- DOM skeleton
- 测试敏感文案 / DOM id / 入口按钮
- 必须保留在壳层的兼容桥
- 启动入口

### 3.2 三个能力域

#### `studio_admin`

职责：

- actor 读取
- 上传
- 处理
- 打开批次
- 上传格式说明

#### `review_flow`

职责：

- reviewer session
- triage / queue
- review form
- aggregate

#### `track_inspection`

职责：

- 地图
- 图层样式
- time scrubber
- timeline annotation
- annotation settings

### 3.3 shell 与 shared

#### `shell`

只负责：

- 页面生命周期
- feature 装配
- 路由参数
- 页面级 orchestration

禁止：

- 继续吸收业务状态

#### `shared`

只允许：

1. 无业务语义纯函数
2. 平台适配
3. 明确合同类型与 normalizer

禁止：

- review / map / timeline / studio management 业务逻辑进入 `shared`

## 4. 完整落地分阶段

### Phase 0：合同与护栏固化

目标：

- 把迁移边界写清楚
- 先补验证，再继续拆

工作项：

1. 固化页面壳合同
2. 固化 bridge 合同
3. 固化状态所有权
4. 补运行时合同测试

主要产物：

- [`22-index前端模块化重构方案.md`](./22-index前端模块化重构方案.md)
- 本文档
- [`../web/test_frontend_module_contract.py`](../web/test_frontend_module_contract.py)

验收标准：

- 能明确说出第一阶段哪些内容不能迁出 `index.html`
- 新模块必须有运行时合同测试

### Phase 1：完成 `studio_admin`

目标：

- 把 `studio management` 从“大段内联业务逻辑”收敛成“页面壳 orchestrator + 外置 core”

当前已完成：

- 格式 spec
- normalize
- payload parse
- API record 创建
- actor / uploads 获取
- blob 上传 adapter

剩余工作：

1. 将 `studio management` 的渲染 helper 继续从壳层剥离成 feature 内部模块
2. 将状态更新与按钮启停收成 feature 内部状态辅助
3. 将 overlay orchestration 与 batch 切换桥保留在壳层，但边界显式化
4. 增加 `studio management` 运行时 smoke

优先文件：

- [`../web/app/features/studio_admin/studio_management_core.js`](../web/app/features/studio_admin/studio_management_core.js)
- [`../web/index.html`](../web/index.html)

验收标准：

- 打开、刷新、上传、处理、打开批次、删除都不回退
- 说明默认收起不回退
- 删除后列表立即刷新不回退

### Phase 2：收拢 `review_flow`

目标：

- 不再把 reviewer / queue / review form 拆成松散全局函数簇

工作项：

1. reviewer session 收到单独 feature 子目录
2. triage / queue 收到单独子模块
3. review workbench 收到单独子模块
4. review_flow 内部统一事件与状态 contract

建议目录：

```text
web/app/features/review_flow/
  reviewer_session.js
  triage_queue.js
  review_workbench.js
  review_flow_contract.js
```

验收标准：

- reviewer session 打开 / 切换 / 已知 reviewer 选择稳定
- queue 筛选、切列、切 UID 不回退
- review 保存与 aggregate 刷新不回退

### Phase 3：收拢 `track_inspection`

目标：

- 将地图、时间轴、annotation settings 作为一个高耦合交互域统一治理

工作项：

1. 抽地图渲染基础能力
2. 抽 time scrubber 状态与交互控制
3. 抽 timeline annotation 与 pin / segment 逻辑
4. 抽 annotation settings
5. 明确共享快照 contract

建议目录：

```text
web/app/features/track_inspection/
  map_runtime.js
  layer_controls.js
  time_scrubber.js
  timeline_annotations.js
  annotation_settings.js
  track_snapshot_contract.js
```

验收标准：

- 地图初始化与图层切换稳定
- 左右键与时间轴快捷键稳定
- 段落标注与 pin 标注稳定
- annotation settings 修改后即刻生效

### Phase 4：压缩页面壳

目标：

- 把 `index.html` 的内联 JS 明显收缩

工作项：

1. 清理已迁出的旧逻辑
2. 保留最薄兼容桥
3. 重新整理初始化顺序
4. 清点仍必须留在壳层的 CSS 与 DOM 合同

验收标准：

- `index.html` 主要承担 DOM 与初始化
- 壳层不再持有大量业务 helper

### Phase 5：样式治理

目标：

- 在 JS 边界稳定后，再收 CSS

工作项：

1. 先分出 tokens / base / overlays / feature CSS
2. 只迁非测试敏感、非高风险部分
3. 保留页面壳必须存在的关键规则，直到合同测试升级

验收标准：

- 样式迁移不影响 UI 合同
- 浮窗、时间轴、侧栏等关键区域视觉不回退

## 5. 状态所有权计划

### 页面级上下文

只允许保留：

- `currentBatchName`
- `currentUid`
- `currentUiMode`
- `currentUiConfig`

### feature 内状态

- `studio_admin`
  - `studioManagementState`
- `review_flow`
  - reviewer / queue / review form 相关状态
- `track_inspection`
  - map / scrubber / timeline / annotation settings 相关状态

控制原则：

- 能留在 feature 内的，不上收
- 只有跨域导航上下文才上收

## 6. 验证矩阵

### 静态护栏

- `python3 scripts/check_index_html_inline_js.py`

### Python 回归

- `python3 -m unittest web/test_studio_management_ui_contract.py web/test_frontend_module_contract.py web/test_review_server.py`

### live smoke

至少覆盖：

1. 打开 `Studio 管理`
2. 默认说明收起
3. 上传
4. 处理
5. 打开批次
6. 删除后刷新
7. reviewer session 可用
8. time scrubber 左右键与按钮可用

### 每阶段退出条件

每一阶段结束前，至少满足：

1. 主入口仍可打开
2. 本阶段涉及功能全部 smoke 一遍
3. 现有单测通过
4. 新增模块合同测试通过

## 7. 现阶段建议执行顺序

当前最合理的继续推进顺序：

1. 补 `studio_admin` 剩余渲染/状态拆分
2. 进入 `review_flow`
3. 再进入 `track_inspection`
4. 最后压缩壳层与 CSS

原因：

- `studio_admin` 已经有第一刀落地，继续做性价比最高
- `review_flow` 次高耦合，但比地图/时间轴更容易建立合同
- `track_inspection` 风险最高，应该放在边界和护栏成熟后

## 8. 本轮之后的最佳下一步

最佳下一步不是继续写新文档，而是直接推进 `Phase 1` 的剩余项：

- 把 `studio management` 的渲染 helper 和状态辅助继续迁出
- 同时补一个更贴近真实使用的 runtime smoke

这样可以在不冒高风险的前提下，继续把“方案”变成“仓库里真实存在的边界”。
