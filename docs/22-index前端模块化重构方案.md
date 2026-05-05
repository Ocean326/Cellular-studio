# index 前端模块化重构方案

## 1. 背景

截至 `2026-04-18`，[`web/index.html`](../web/index.html) 仍承担了页面结构、样式、运行时状态、事件绑定和大部分前端业务流程：

- 总行数约 `7590`
- 内联样式约 `1526` 行
- 内联脚本约 `5619` 行
- 约 `298` 个函数

当前仓库已经有一部分前端治理基础：

- 稳定 preset 已抽到 [`../web/app/studio_bootstrap.js`](../web/app/studio_bootstrap.js)
- [`../scripts/check_index_html_inline_js.py`](../scripts/check_index_html_inline_js.py) 已能校验 `index.html` 内联脚本和本地脚本
- `studio management` 已有最小 UI contract 测试

因此这轮不建议重写，也不建议引入新的前端框架或打包链路。更合适的路径是：先固定边界与合同，再做渐进式拆分。

## 2. 架构结论

本轮采用：

- `architect`
  - 主 lane：`codebase-architecture`
  - 副 lane：`architecture-governance`
- `proposal-synthesis`
  - 生成 3 个候选方案：低风险渐进式、feature-slice、page shell + runtime
- `proposal-critique-refine`
  - 从迁移风险、边界健康、测试/合同安全三条线收敛

最终收敛方向不是“按实现形态切文件”，而是：

1. `index.html` 先收敛为稳定页面壳
2. 前端主边界优先按能力域切，而不是按 UI 小部件切
3. `shell` 只负责页面级 orchestration，不再承接业务大状态
4. `shared` 拆成有准入规则的公共层，不允许继续做杂物间
5. 第一阶段只迁移 `studio_admin` 域中的非合同、非编排部分

## 3. 稳定能力域

前端第一轮不按 `map_stage / time_navigation / review_queue` 这类 UI 名词切主边界，而是先按稳定能力域切：

### 3.1 `studio_admin`

职责：

- 上传
- 处理
- 批次打开
- actor 读取
- 上传说明/格式合同

当前对应热点：

- `studioManagementState`
- `/api/me`
- `/api/uploads`
- `/blob`
- `/process`

### 3.2 `review_flow`

职责：

- reviewer session
- triage / queue
- review form
- aggregate / latest review

### 3.3 `track_inspection`

职责：

- 地图渲染
- 图层样式
- time scrubber
- timeline annotation
- annotation settings

## 4. 目标分层

### 4.1 `index.html`

只保留：

- DOM 结构
- 测试敏感的文案与 `id`
- 阶段一必须留在页面里的 CSS 合同
- 启动入口
- 兼容桥接函数

### 4.2 `web/app/shell`

只允许做：

- 启动顺序
- 页面级生命周期
- feature 装配
- 路由参数解析
- 事件分发

禁止：

- 持有 review / timeline / map 的业务状态
- 承接 feature 语义 helper

### 4.3 `web/app/shared`

只允许三类东西：

1. 无业务语义的纯函数
2. 平台适配：DOM / fetch / storage / transport
3. 明确的合同对象与 normalizer

禁止：

- review / map / timeline / studio management 的业务逻辑直接进入 `shared`

建议后续细分为：

- `shared/kernel`
- `shared/platform`
- `shared/contracts`

### 4.4 `web/app/features`

能力域是主边界；`controller / state / view / api` 只是 feature 内部组织方式。

## 5. 阶段一合同清单

在文本合同测试升级前，以下内容默认继续留在 [`../web/index.html`](../web/index.html)：

- `studio management` 相关 DOM 结构
- `studio-management-entry` 相关关键 CSS 规则
- 入口文案：`展开说明`
- overlay 开关与关闭行为
- 全局桥接函数签名

第一阶段允许外移的内容：

- `studio_admin` 的格式合同
- 纯 normalize 逻辑
- 纯 payload 解析
- API adapter
- 上传 `XMLHttpRequest` 逻辑

第一阶段暂不外移：

- overlay 编排
- 与 annotation overlay 的互斥
- batch 切换编排
- 事件装配主流程

## 6. 状态所有权

### 6.1 页面级上下文

页面级只保留最少导航上下文：

- `currentBatchName`
- `currentUid`
- `currentUiMode`
- `currentUiConfig`

### 6.2 feature 本地状态

以下状态优先留在 feature 内：

- `studioManagementState`
- `annotationSettings`
- `timeScrubberState`
- `currentTimeWindow`
- `reviewFormDirty`
- queue 过滤与 board 局部态

后续如果某状态跨域共享，再通过显式 contract 上收，而不是默认丢给 shell。

## 7. 迁移阶段

### Phase 0：补验证护栏

先补三类合同：

1. 页面壳合同
2. bridge 合同
3. shell / feature 状态所有权

同时把“只扫字符串”的测试降级成静态护栏，并补至少一个模块运行时合同测试。

### Phase 1：抽 `studio_admin` 的纯逻辑与 adapter

目标：

- 新建 `web/app/features/studio_admin/`
- 抽出格式 spec、normalize、payload parse、API adapter、upload adapter
- `index.html` 保留 orchestration 和兼容桥

### Phase 2：收 `review_flow`

先把 reviewer session、queue、review workbench 作为一个能力域治理，避免切得过碎。

### Phase 3：收 `track_inspection`

将地图、时间轴、annotation settings 作为一个交互域处理，避免 `map_stage / time_navigation / annotation_settings` 形成频繁双向 reach-through。

### Phase 4：压缩 `index.html`

当合同测试和运行时护栏成熟后，再逐步把 JS 主逻辑从页面壳移出，并评估 CSS 外置节奏。

## 8. 第一阶段验收标准

第一阶段不以“文件搬走了多少”为完成标准，而以这些标准为准：

1. `index.html` 主入口仍能启动
2. `studio management` 的打开、刷新、上传、处理、打开批次、删除链路不回退
3. 现有 Python 单测通过
4. 新增前端模块合同测试通过
5. `shell` 不新增业务大状态
6. `shared` 不吸收 feature 语义

## 9. 本轮落地切片

本轮代码落地只做一件事：

- 在 `studio_admin` 能力域内，先把 `studio management` 的格式 spec、normalize、payload parse 和 API/upload adapter 抽到外部脚本

这样既建立了模块化的实际入口，又不会在第一刀就动到最脆弱的页面壳编排。
