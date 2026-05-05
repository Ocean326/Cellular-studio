# trajectory_annotation_studio reviewer 命名空间开发与验证计划

这份文档是对：

- [08-reviewer-命名空间与多人标注汇总设计.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/08-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E4%B8%8E%E5%A4%9A%E4%BA%BA%E6%A0%87%E6%B3%A8%E6%B1%87%E6%80%BB%E8%AE%BE%E8%AE%A1.md)

的实施展开。目标不是“继续想”，而是把后面真正编码时的阶段、验收和风险闭环写清楚。

## 1. 实施目标

完成后，系统需要达到以下工作态：

1. 第一次打开页面会先选择 reviewer 身份。
2. 当前 reviewer 的审核与时间轴标记保存到自己的命名空间目录。
3. 左侧 triage 和右侧编辑都默认以当前 reviewer 为准。
4. 同一条轨迹可以查看多个 reviewer 的最新摘要。
5. organizer 可以按 reviewer 导出结果，也可以导出聚合冲突清单。

## 2. 实施切分

## Phase 0：合同冻结与现状保护

目标：

- 冻结 reviewer 命名空间目录合同
- 冻结 reviewer session 语义
- 冻结 per-reviewer export 和 aggregate export 语义
- 不修改现有线上批次数据

产物：

- 新设计文档
- 实施与测试计划
- 明确 legacy 迁移策略

通过条件：

- 团队对命名空间目录、导出语义、兼容路径无歧义

## Phase 1：后端存储地基

目标：

- 在 `review_lib.py` 中引入 reviewer 命名空间路径模型
- 支持 reviewer registry
- 支持 reviewer 维度的整轨审核读写
- 支持 reviewer 维度的时间轴标记读写

建议改动点：

- [review_lib.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_lib.py)
- 如有必要新增 `web/reviewer_registry.py` 或内部 helper

关键实现项：

- reviewer id 规范化与校验
- reviewer profile 写回
- per-reviewer ledger append
- per-reviewer latest index rebuild
- per-reviewer timeline snapshot / ledger
- aggregate by uid 索引更新

通过条件：

- 不同 reviewer 写同一 uid，不再互相覆盖
- 同一 reviewer 的 latest view 正常更新
- aggregate `by_uid/<uid>.json` 正常反映多人结果

## Phase 2：前端 reviewer session 与增量入口

目标：

- 首次进入必须选择 reviewer
- 保持登录态
- 支持修改/切换当前 reviewer
- 审核保存与时间轴保存都带 reviewer_id

建议改动点：

- [index.html](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/index.html)

关键实现项：

- reviewer session modal
- localStorage session 持久化
- reviewer badge / 切换入口
- reviewer-input 改为只读身份展示
- 切换 reviewer 时复用脏表单保护
- triage 改为使用当前 reviewer 的 review index

通过条件：

- 不登录不能保存
- 切换 reviewer 后左侧 triage 会切换到对应 reviewer 的状态
- 当前 reviewer 不再能通过自由文本误写成别人

## Phase 3：多人汇总与导出

目标：

- 增加当前 uid 的多人审核摘要
- 增加 aggregate 导出
- accepted_assets 改为按 reviewer 分目录

建议改动点：

- [review_server.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_server.py)
- [export_accepted_assets.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/export_accepted_assets.py)
- [export_reviewed_subset.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/export_reviewed_subset.py)

关键实现项：

- `GET /api/reviews/aggregate?uid=...`
- `GET /api/timeline-annotations/aggregate?uid=...`
- `POST /api/export/accepted` 增加 `reviewer_id`
- 新增 aggregate export
- 前端多人摘要折叠区

通过条件：

- 同一 uid 至少可展示 2 个 reviewer 的不同 latest 决策
- per-reviewer accepted 导出互不污染
- conflicts 导出能识别 `accept / reject` 不一致的 uid

## Phase 4：legacy 迁移与回归

目标：

- 允许已有批次从旧结构平滑迁移
- 保证旧数据不丢
- 给出回滚路径

关键实现项：

- 迁移脚本
- 只读兼容逻辑
- 迁移完成后的验证脚本

通过条件：

- 一个 legacy 批次可迁移到新结构
- 迁移前后 latest 结果数量一致
- 迁移失败时旧目录未损坏

## 3. 前端详细任务拆分

### 3.1 reviewer session

- 新增 `REVIEWER_SESSION_STORAGE_KEY`
- 存储对象至少包含：
  - `reviewer_id`
  - `reviewer_name`
  - `last_selected_at`
- 页面初始化时先检查 session，再决定是否弹 modal

### 3.2 reviewer 顶部入口

- 在现有顶部工具区加：
  - 当前 reviewer badge
  - 切换按钮
  - 可选的“查看多人汇总”入口

### 3.3 审核表单改造

- `reviewer-input` 由可编辑文本框改成当前身份展示
- 保存 payload 由前端自动注入 `reviewer_id`
- `review-meta` 支持展示当前 reviewer 信息和多人汇总统计

### 3.4 triage 改造

- `loadReviewIndex()` 改为必须带当前 reviewer
- `getReviewForUid(uid)` 读取当前 reviewer index
- 卡片上补一个多人 reviewer 计数徽标

### 3.5 多人汇总折叠区

- 当前 UID 下方新增只读列表
- 每条展示：
  - reviewer 名
  - decision
  - timestamp
  - notes 摘要
  - pin/segment 数

## 4. 后端详细任务拆分

### 4.1 reviewer registry

建议新增以下能力：

- `normalize_reviewer_id(display_name) -> reviewer_id`
- `ensure_reviewer_profile(review_root, display_name, reviewer_id?)`
- `list_reviewers(review_root)`

注册表至少包含：

- `reviewer_id`
- `reviewer_name`
- `created_at`
- `last_seen_at`
- `status`

### 4.2 路径模型

建议从当前 `ReviewPaths` 再拆一层：

- `ReviewPaths`
  批次级根路径
- `ReviewerPaths`
  某 reviewer 级路径集合

避免在每个函数里手拼 `reviewers/<reviewer_id>/...`。

### 4.3 写入鲁棒性

必须补的工程保护：

- reviewer_id 白名单校验
- 原子 JSON 写入
- 每 reviewer 锁
- aggregate 锁或串行刷新
- 错误时不写坏 latest 索引

### 4.4 聚合索引刷新策略

V1 推荐同步增量刷新，不做后台异步任务：

- reviewer 写入成功后
- 立即刷新该 reviewer 的 latest index
- 再刷新当前 uid 的 aggregate by_uid 文件

原因：

- 实现简单
- 一致性足够直观
- 对当前批次规模可接受

## 5. 测试计划

## 5.1 单元测试

### reviewer identity

- 合法昵称可生成稳定 reviewer_id
- 非法 reviewer_id 被拒绝
- slug 冲突时返回明确错误

### per-reviewer review storage

- reviewer A 写 `uid1=accept`
- reviewer B 写 `uid1=reject`
- 两边 latest 都应保留
- aggregate by uid 应出现两条记录

### per-reviewer timeline storage

- reviewer A 与 reviewer B 给同一 uid 各写一份 segment
- 各自 `<uid>.json` 不应互相覆盖

### export

- `export accepted --reviewer-id A`
  只导出 A 的 accept
- `export accepted --reviewer-id B`
  只导出 B 的 accept
- aggregate export 能正确输出冲突 uid

## 5.2 集成测试

### API 流程

1. `POST /api/reviewers/session`
2. `POST /api/reviews`
3. `GET /api/reviews?reviewer_id=...`
4. `GET /api/reviews/aggregate?uid=...`
5. `POST /api/timeline-annotations`
6. `GET /api/timeline-annotations/aggregate?uid=...`

要求：

- 两个 reviewer 交叉写入后结果稳定
- 不出现覆盖和串写

## 5.3 前端手测场景

### 场景 A：首次进入

- 无 session 时弹登录框
- 输入昵称后进入页面
- 刷新后保持当前 reviewer

### 场景 B：切换 reviewer

- reviewer A 打开 `uid1`
- 修改 notes 但不保存
- 切换 reviewer B
- 应弹未保存确认

### 场景 C：多人审同一轨迹

- reviewer A 对 `uid1` 保存 `accept`
- reviewer B 对 `uid1` 保存 `reject`
- 右侧多人汇总能同时看到两者

### 场景 D：时间轴多人标记

- reviewer A 打一个 pin 和一个 segment
- reviewer B 再打不同 segment
- 返回当前 uid 后，当前 reviewer 只编辑自己的标记
- 多人摘要能看到双方计数

### 场景 E：导出

- 按 reviewer 导出 accepted
- 生成目录落到 reviewer 子目录
- aggregate 导出能列出冲突 uid

## 5.4 回归测试

必须验证以下老能力没有被打断：

- 批次发现与切换
- 轨迹选择
- 地图渲染
- 三列审阅箱分页
- 状态筛选
- 时间轴交互
- accepted reference 校验

## 6. 风险与应对

### 风险 1：reviewer session 被误解成真正登录

应对：

- 文档和 UI 上统一使用“标注者身份 / reviewer session”
- 明确说明它不是权限鉴权

### 风险 2：用户误用同一个昵称共享 namespace

应对：

- slug 冲突时显式提示
- reviewer 切换器里显示已有 reviewer 列表
- 组内约定使用稳定昵称

### 风险 3：写入并发导致 latest 与 aggregate 不一致

应对：

- per-reviewer 写入锁
- aggregate 刷新锁
- JSON 原子替换

### 风险 4：旧脚本仍假设全局 `latest_reviews.json`

应对：

- 迁移期间保留 legacy 读兼容
- 文档明确旧脚本废弃时间点
- 优先先改 export 脚本

## 7. 回滚策略

如果新结构出现问题，回滚策略固定为：

1. 停止新版本服务
2. 保留 `review/reviewers/` 和 `review/aggregate/` 目录，不删除
3. 使用 legacy 只读模式重新启动
4. 基于保留的 legacy 文件继续工作

前提：

- 迁移不覆盖旧 `ledger.jsonl`
- 新写入只进入新目录

## 8. 完成定义

以下条件全部满足，才算 reviewer 命名空间功能真正落地：

1. 首次进入必须确认 reviewer 身份。
2. reviewer 切换可用且有脏表单保护。
3. review 与 timeline annotations 都按 reviewer 分目录保存。
4. triage 默认按当前 reviewer 工作。
5. 同一 uid 可查看多个 reviewer 的最新结果摘要。
6. accepted 导出支持按 reviewer。
7. aggregate 导出能输出 by_uid / by_reviewer / conflicts。
8. 至少完成一次 legacy 批次迁移演练。
