# Test Cases: 日期窗口固定间隔与整段快标

## Overview
- **Feature**: 日期窗口固定间隔联动 + 整段标记快速入口
- **Requirements Source**: 当前对话中的产品与实现需求
- **Test Coverage**: 自由区间 / 固定间隔切换、窗口联动、整段标签选择、创建 / 更新 / 取消整段快标、只读态与空窗口保护
- **Last Updated**: 2026-04-18

## Functional Tests

### TC-F-001: 默认自由区间模式可独立调整起止日期
- **Priority**: High
- **Preconditions**:
  - 打开任意含多天数据的 UID
  - `间隔` 输入框值为 `0`
- **Test Steps**:
  1. 点击起始日期 `+`
  2. 观察结束日期
  3. 点击结束日期 `-`
- **Expected Results**:
  - 起始日期和结束日期可独立变化
  - 当前窗口内地图和时间轴同步刷新

### TC-F-002: 固定间隔模式下，起止日期按 x 天联动
- **Priority**: High
- **Preconditions**:
  - 打开任意含 4 天以上数据的 UID
- **Test Steps**:
  1. 将 `间隔` 输入为 `2`
  2. 调整起始日期 `+`
  3. 再调整结束日期 `-`
- **Expected Results**:
  - `startDay` 和 `endDay` 始终相差 `2` 天
  - 调整任意一端时，另一端自动联动
  - 到达轨迹日期边界后会自动钳制，不会越界

### TC-F-003: 选择整段标签后可创建整段快标
- **Priority**: High
- **Preconditions**:
  - 当前批次为可标注模式
  - 已设置 reviewer
  - 段落类别中至少存在一个标签
- **Test Steps**:
  1. 选定一个日期窗口
  2. 在 `整段标签` 下拉框中选择一个标签
  3. 点击 `整段标记`
- **Expected Results**:
  - 当前窗口生成一条整段标记
  - 时间轴中出现对应颜色段
  - 状态文案变为 `已标记：<标签名>`

### TC-F-004: 同一窗口可更新整段标签
- **Priority**: High
- **Preconditions**:
  - 当前窗口已经存在整段快标
- **Test Steps**:
  1. 将 `整段标签` 切换为另一个标签
  2. 点击 `更新整段标签`
- **Expected Results**:
  - 不会新增第二条窗口快标
  - 原快标标签和颜色更新为新值

### TC-F-005: 同一窗口可取消整段快标
- **Priority**: High
- **Preconditions**:
  - 当前窗口已经存在整段快标
  - 下拉框标签与当前快标标签一致
- **Test Steps**:
  1. 点击 `取消整段标记`
- **Expected Results**:
  - 当前窗口快标被删除
  - 状态文案恢复为 `未标记`
  - 不影响用户手动画出的其它段落

## Edge Case Tests

### TC-E-001: 固定间隔超过可用日期范围时自动钳制
- **Priority**: Medium
- **Preconditions**:
  - 当前 UID 只有 3 天数据
- **Test Steps**:
  1. 将 `间隔` 输入为 `7`
- **Expected Results**:
  - 输入值被自动收敛到当前轨迹允许的最大间隔
  - 页面不报错

### TC-E-002: 当前窗口内无可定位时间时禁止整段快标
- **Priority**: Medium
- **Preconditions**:
  - 当前日期窗口筛到空范围或空图层
- **Test Steps**:
  1. 观察整段标记按钮
- **Expected Results**:
  - 按钮禁用
  - 状态文案提示 `当前窗口内无可标记时间`

### TC-E-003: 无 reviewer 时点击整段快标会提示进入标注
- **Priority**: Medium
- **Preconditions**:
  - 当前批次为可标注模式
  - 未设置 reviewer
- **Test Steps**:
  1. 点击 `整段标记`
- **Expected Results**:
  - 弹出 reviewer 会话面板
  - 不会写入匿名标注

## State Transition Tests

### TC-ST-001: 切换 UID 后，已存在的窗口快标可自动回填状态
- **Priority**: High
- **Preconditions**:
  - 某 UID 已保存过窗口快标
- **Test Steps**:
  1. 切到其他 UID
  2. 再切回原 UID
  3. 将日期窗口调整回已标记范围
- **Expected Results**:
  - 标签下拉框回填为原标签
  - 主按钮显示 `取消整段标记` 或 `更新整段标签`
  - 状态文案显示已标记标签

### TC-ST-002: 只读批次中整段快标控件不可执行写入
- **Priority**: High
- **Preconditions**:
  - 当前批次 `annotation_mode=view_only`
- **Test Steps**:
  1. 打开任意 UID
  2. 观察整段标签和整段标记按钮
- **Expected Results**:
  - 控件处于禁用或只读态
  - 状态文案提示 `当前批次为只读模式`

## Coverage Matrix

| Requirement | Test Cases | Coverage Status |
| --- | --- | --- |
| 自由区间与固定间隔切换 | TC-F-001, TC-F-002, TC-E-001 | ✓ Complete |
| 整段快标创建 / 更新 / 取消 | TC-F-003, TC-F-004, TC-F-005 | ✓ Complete |
| 空窗口与 reviewer 保护 | TC-E-002, TC-E-003 | ✓ Complete |
| UID / 批次切换状态回填 | TC-ST-001, TC-ST-002 | ✓ Complete |
