# Test Cases: Studio 管理上传模块

## Overview
- **Feature**: 主页面 `Studio 管理` 上传与处理模块
- **Requirements Source**: 当前对话中的需求迭代
- **Test Coverage**: 右侧上传入口、说明 `i` 浮层、字段大小写兼容、上传进度展示、上传/处理/删除链路、异常反馈
- **Last Updated**: 2026-04-18

## Test Case Categories

### 1. Functional Tests

#### TC-F-001: 右侧上传入口可见且可打开浮窗
- **Requirement**: 上传入口改到右侧贴边，垂直居中；点击后打开独立磨砂浮窗
- **Priority**: High
- **Preconditions**:
  - Studio 首页可正常访问
- **Test Steps**:
  1. 打开主页面
  2. 观察页面右侧贴边区域
  3. 点击圆形上传按钮
- **Expected Results**:
  - 右侧贴边能看到圆形磨砂上传按钮
  - 按钮大致处于垂直居中位置
  - 点击后打开 `Studio 管理` 浮窗
  - 浮窗背景与现有设置面板风格一致

#### TC-F-002: trajectory4 说明浮层展示正确字段与规则
- **Requirement**: 在文件标题右侧增加“说明 i”，hover/点击可查看字段说明
- **Priority**: High
- **Preconditions**:
  - `Studio 管理` 浮窗已打开
  - 上传类型选择为 `trajectory4`
- **Test Steps**:
  1. 将鼠标悬停到“说明 i”
  2. 再点击“说明 i”
  3. 观察字段列表和规则说明
- **Expected Results**:
  - hover 和 click 都能展示说明内容
  - 说明中包含 `uid`、`latitude/lat`、`longitude/lon`、`timestamp_ms/timestamp`
  - 说明中明确哪些字段必填、哪些可选
  - 说明中写明大小写兼容和“同一文件可包含多个 uid”

#### TC-F-003: signal6 说明浮层随上传类型切换
- **Requirement**: 说明内容需跟随格式变化，并展示多信令组织要求
- **Priority**: High
- **Preconditions**:
  - `Studio 管理` 浮窗已打开
- **Test Steps**:
  1. 将上传类型切换为 `signal6`
  2. 打开“说明 i”
  3. 观察字段和规则内容
- **Expected Results**:
  - 说明内容切换为 signal6 规则
  - 字段中包含 `cid`、`t_in/start_time`、`t_out/end_time`
  - 规则中明确“仅接受北京范围”
  - 规则中明确“同一文件可包含多个 uid，每行一条信令事件”

#### TC-F-004: 上传文件时展示阶段性进度
- **Requirement**: 上传并处理需要有进度前端显示
- **Priority**: High
- **Preconditions**:
  - 已选择合法 CSV 文件
- **Test Steps**:
  1. 点击“上传文件”
  2. 观察进度区域
- **Expected Results**:
  - 出现独立进度卡片
  - 至少能看到“创建上传记录”“上传文件中”“上传完成”等阶段文案
  - 百分比和进度条有变化
  - 上传完成后列表自动刷新

#### TC-F-005: 上传并处理时展示处理阶段进度
- **Requirement**: 上传并处理要在前端展示完整进度
- **Priority**: High
- **Preconditions**:
  - 已选择合法 CSV 文件
- **Test Steps**:
  1. 点击“上传并处理”
  2. 观察上传、处理中、同步结果、处理完成四个阶段
- **Expected Results**:
  - 上传阶段进度条递增
  - 进入处理阶段后，标题切为“后端处理中”
  - 处理返回后，显示“正在同步结果”
  - 最终显示“处理完成”且进度到 100%

#### TC-F-006: 处理完成后可直接打开生成批次
- **Requirement**: 处理完成的记录可继续打开对应 batch
- **Priority**: High
- **Preconditions**:
  - 至少有一条 `published` 上传记录
- **Test Steps**:
  1. 在“我的上传”中点击“打开批次”
- **Expected Results**:
  - 当前页面切换到对应 batch
  - 管理浮窗关闭
  - 页面批次状态文字同步刷新

### 2. Edge Case Tests

#### TC-E-001: 大小写不敏感头可正常处理 trajectory4
- **Requirement**: uid 及其他字段大小写兼容
- **Priority**: High
- **Preconditions**:
  - 准备头为 `UID,Latitude,Longitude,TimestampMS,State` 的 trajectory4 CSV
- **Test Steps**:
  1. 上传并处理该文件
- **Expected Results**:
  - 上传处理成功
  - 生成批次可正常打开
  - 轨迹点和状态可正确显示

#### TC-E-002: 大小写不敏感头可正常处理 signal6
- **Requirement**: uid 及其他字段大小写兼容
- **Priority**: High
- **Preconditions**:
  - 准备头为 `UID,CID,Lat,Lon,TIn,TOut,Status` 的 signal6 CSV
- **Test Steps**:
  1. 上传并处理该文件
- **Expected Results**:
  - 上传处理成功
  - 生成 `signal.csv`
  - 信令层可在 batch 中打开

#### TC-E-003: 同一文件中包含多个 uid 的 signal6
- **Requirement**: 展示多信令在一个文件内的组织要求，并支持真实处理
- **Priority**: High
- **Preconditions**:
  - 准备同一 CSV 内含多个 uid 的 signal6 文件
- **Test Steps**:
  1. 上传并处理该文件
  2. 打开结果批次
- **Expected Results**:
  - 后端按 uid 分组生成多条样本
  - 左侧队列能看到多个 uid
  - 每个 uid 的信令按时间正确排序

#### TC-E-004: 进度状态在上一次完成后可重新开始
- **Requirement**: 多次上传时进度条状态不能残留
- **Priority**: Medium
- **Preconditions**:
  - 已完成一次“上传并处理”
- **Test Steps**:
  1. 再次选择新文件
  2. 点击“上传并处理”
- **Expected Results**:
  - 进度从低位重新开始，而不是停在 100%
  - 阶段文案切换正确

### 3. Error Handling Tests

#### TC-ERR-001: signal6 文件超出北京范围时报错
- **Requirement**: signal6 限制北京地区
- **Priority**: High
- **Preconditions**:
  - 准备含上海坐标等超范围点的 signal6 文件
- **Test Steps**:
  1. 上传并处理该文件
- **Expected Results**:
  - 处理失败
  - 前端 flash 与进度卡片都显示失败信息
  - 错误文案指向北京范围限制

#### TC-ERR-002: 缺少必填字段时报错
- **Requirement**: 说明中定义的必填字段需要真正受约束
- **Priority**: High
- **Preconditions**:
  - 准备缺少 `uid` 或缺少时间字段的 CSV
- **Test Steps**:
  1. 上传并处理该文件
- **Expected Results**:
  - 处理失败
  - 错误文案说明缺失的字段名
  - 不会生成可打开的 batch

#### TC-ERR-003: 处理中的旧记录点击“触发处理”失败时应有错误反馈
- **Requirement**: 处理失败时前端需要有明确反馈
- **Priority**: Medium
- **Preconditions**:
  - 人为构造失败记录或上传非法数据
- **Test Steps**:
  1. 对失败记录点击“触发处理”
- **Expected Results**:
  - 进度卡片变为失败态
  - flash 显示错误原因
  - 页面不会卡死或失去交互

### 4. State Transition Tests

#### TC-ST-001: 说明浮层可通过外部点击收起
- **Requirement**: 说明 `i` 既支持 hover，也支持点击复现
- **Priority**: Medium
- **Preconditions**:
  - 说明浮层已通过点击展开
- **Test Steps**:
  1. 点击浮层外部任意空白区域
- **Expected Results**:
  - 说明浮层关闭
  - 不影响管理浮窗本体

#### TC-ST-002: 上传完成但未处理时，记录留在列表中可继续处理
- **Requirement**: 上传和处理是连续但可分离的动作
- **Priority**: Medium
- **Preconditions**:
  - 通过“上传文件”完成一次纯上传
- **Test Steps**:
  1. 在“我的上传”中找到该记录
  2. 点击“触发处理”
- **Expected Results**:
  - 记录先保持 uploaded / created 状态
  - 点击处理后进入 processing / published 流转

#### TC-ST-003: 删除上传后列表和批次同步移除
- **Requirement**: 上传记录可删除
- **Priority**: High
- **Preconditions**:
  - 至少存在一条已生成 batch 的上传记录
- **Test Steps**:
  1. 点击“删除”
  2. 确认删除
  3. 刷新批次列表
- **Expected Results**:
  - 上传记录状态变为 deleted 或不再可操作
  - 对应 batch 从当前 actor 可见批次中消失
  - 旧 batch-data 入口不再可访问

## Test Coverage Matrix

| Requirement ID | Test Cases | Coverage Status |
|---------------|------------|-----------------|
| REQ-001 右侧贴边上传入口 | TC-F-001 | ✓ Complete |
| REQ-002 说明 i 浮层 | TC-F-002, TC-F-003, TC-ST-001 | ✓ Complete |
| REQ-003 字段大小写兼容 | TC-E-001, TC-E-002 | ✓ Complete |
| REQ-004 多 UID / 多信令同文件要求 | TC-F-003, TC-E-003 | ✓ Complete |
| REQ-005 上传并处理进度展示 | TC-F-004, TC-F-005, TC-E-004 | ✓ Complete |
| REQ-006 上传/处理/打开批次 | TC-F-004, TC-F-005, TC-F-006, TC-ST-002 | ✓ Complete |
| REQ-007 北京范围约束与错误反馈 | TC-ERR-001, TC-ERR-002, TC-ERR-003 | ✓ Complete |
| REQ-008 删除与状态流转 | TC-ST-003 | ✓ Complete |

## Notes
- 浏览器视觉与 hover 交互建议在桌面端和窄屏各执行一次。
- 真实大文件上传建议额外做一次大于 5MB 的体验测试，观察上传阶段进度是否仍然顺滑。
- 若后续把后端处理改为异步队列，需新增“处理中刷新 / 断线重连 / 长时间轮询”的状态测试。
