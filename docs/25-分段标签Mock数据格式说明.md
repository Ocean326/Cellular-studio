# 分段标签 Mock 数据格式说明

## 任务契约

- deliverable: `systematic-learning-note`
- target_reader: 标注平台前端、后端、算法接入方
- central_question: 如何定义一套简单、稳定、可直接用于 mock 和真实接入的分段标签数据格式？
- time_window: 2026-04-24 当前仓库能力
- stop_condition: 形成可直接落地的字段规范、枚举、命名规则和最小示例
- evidence_bar: 本地代码与现有文档一致，避免脱离仓库现状另起一套格式

## 来源映射

| id | 来源 | 类型 | 本地/外部 | 可信度 | 作用 | 支撑内容 |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | `scripts/user_upload_adapter_lib.py` | source code | local | 高：实现约束 | 主锚点 | `signal6` / `trajectory4` 字段别名、北京范围、`status` 读法 |
| S2 | `docs/05-组内共享部署与数据接入规范.md` | doc | local | 高：接入规范 | 结构约束 | `raw.csv` / `gps.csv` 的最小字段与推荐字段 |
| S3 | `web/review_lib.py` | source code | local | 高：导出结构 | 标注落点 | `trajectory_tags`、`timeline_annotations.segments` 的真实落盘方式 |
| S4 | 当前任务对话约束 | user requirement | local | 高：需求事实 | 目标格式 | 两个 CSV、分段标签、状态枚举与命名 |

## 事实 / 判断 / 推断 / 延展

### Facts

- 当前仓库已支持 `signal6` 上传，核心字段是 `uid / cid / latitude / longitude / t_in / t_out`。
- 当前仓库已支持 `trajectory4` 风格上传，核心字段是 `uid / latitude / longitude / timestamp / status`。
- 当前前端和导出链路已经能消费 `status` 字段。
- 当前时间轴分段标注的真实后端结构是 `timeline_annotations.json -> segments[]`。

### Judgments

- 为了降低对接复杂度，mock 阶段不应再单独发第三份标签文件。
- 最稳的方案是把分段标签直接放进 `{uid}_gps.csv` 和 `{uid}_signal.csv` 的 `status` 列。

### Inferences

- 对算法和标注联调来说，`gps` 与 `signal` 共用同一套 `status` 枚举，最便于核对时序一致性。
- `signal` 保留前 6 列原始语义，再补 1 列 `status`，比重新定义一份“七元组”更容易沟通。

### Extensions

- 后续如果要细化“road”内部识别，可以在不破坏主格式的前提下新增 `sub_status` 或 `confidence`。

## 决策与行动寄存器

| type | 内容 | owner | due | status | confidence | source |
| --- | --- | --- | --- | --- | --- | --- |
| decision | mock 只交付两个文件：`{uid}_signal.csv`、`{uid}_gps.csv` | current thread | 2026-04-24 | agreed | high | S4 |
| decision | 两个文件都带 `status`，其中 `signal` 前 6 列保持原始信令六元组 | current thread | 2026-04-24 | agreed | high | S1,S4 |
| decision | `status` 作为分段标签主字段，统一使用英文 snake_case 枚举 | current thread | 2026-04-24 | agreed | high | S1,S4 |
| action | 后续若进入真实生产接入，再决定是否补 `segment_id` / `confidence` | next iteration | pending | open | medium | S3 |

## 说明范围

这份说明只定义 **mock 与联调用的数据交换格式**，不替代 Studio 内部真实落盘结构。

对外统一交付：

- `{uid}_signal.csv`
- `{uid}_gps.csv`

其中：

- `signal` 表示原始信令六元组数据，并附带该条记录所属的分段标签 `status`
- `gps` 表示轨迹点数据，并附带该点所属的分段标签 `status`

## 一句话结论

推荐统一成下面这套：

1. `signal` 用 `6 个原始字段 + 1 个标注字段 status`
2. `gps` 用 `4 个轨迹字段 + 1 个标注字段 status`
3. `status` 枚举统一为 9 类，作为分段标签的唯一主字段
4. 时间统一使用 **Unix 毫秒时间戳**
5. 坐标统一使用 **WGS84 十进制度**

## 文件命名规则

每个 UID 一对文件：

- `{uid}_signal.csv`
- `{uid}_gps.csv`

示例：

- `1001_signal.csv`
- `1001_gps.csv`

约束：

- 一个文件只包含一个 `uid`
- 行内仍保留 `uid` 字段，便于合并和校验
- 文件内容按时间升序排列

## 标签枚举

`status` 统一使用以下 9 类：

| status | 中文 | 含义 |
| --- | --- | --- |
| `subway` | 地铁 | 明确属于地铁出行 |
| `road_car` | 驾车 | 明确为私家车/网约车中的驾车态 |
| `road_bus` | 公交 | 明确为公交 |
| `road_taxi` | 出租车 | 明确为出租车 |
| `road` | 泛道路乘车 | 能确定在道路机动车上，但无法细分 |
| `low_speed` | 低速 | 缓行、短距移动、难归类的低速状态 |
| `train` | 火车 | 明确属于铁路列车 |
| `stay` | 驻留 | 基本停留不动 |
| `flight` | 飞机 | 明确属于航班飞行 |

使用规则：

- 能细分时，优先使用 `road_car / road_bus / road_taxi`
- 不能细分但明确是道路乘车时，使用 `road`
- 不要同时出现多个状态值

## `{uid}_signal.csv` 定义

### 字段列表

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `uid` | string | 是 | 用户或轨迹 ID |
| `cid` | string | 是 | 基站或信令点标识 |
| `longitude` | float | 是 | 经度，WGS84 |
| `latitude` | float | 是 | 纬度，WGS84 |
| `t_in` | int64 | 是 | 信令开始时间，Unix 毫秒时间戳 |
| `t_out` | int64 | 是 | 信令结束时间，Unix 毫秒时间戳 |
| `status` | enum string | 是 | 该条信令记录对应的分段标签 |

### 解释

- 前 6 列是原始信令六元组。
- `status` 是为 mock / 标注联调补充的标签列，不改变前 6 列的原始语义。
- 必须满足 `t_out >= t_in`。

### 类型约束

- `uid`、`cid` 不做数值型强制，统一按字符串处理
- `longitude` 范围建议在 `[115.7, 117.4]`
- `latitude` 范围建议在 `[39.4, 41.1]`
- `t_in`、`t_out` 必须是 13 位毫秒时间戳

## `{uid}_gps.csv` 定义

### 字段列表

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `uid` | string | 是 | 用户或轨迹 ID |
| `longitude` | float | 是 | 经度，WGS84 |
| `latitude` | float | 是 | 纬度，WGS84 |
| `timestamp` | int64 | 是 | 轨迹点时间，Unix 毫秒时间戳 |
| `status` | enum string | 是 | 该点所属的分段标签 |

### 解释

- 这是“4 元组 + `status`”格式。
- `status` 表示当前轨迹点落在哪一类分段中。
- 同一连续时间段内的点，`status` 应保持一致。

## 对齐规则

为避免 `signal` 和 `gps` 两份文件标签不一致，推荐采用下面的同步规则：

1. 先以分段标签为真值定义时间区间。
2. `gps` 中凡是时间落入该区间的点，写入同一个 `status`。
3. `signal` 中凡是 `[t_in, t_out]` 与该区间有重叠的记录，写入同一个 `status`。

简单说：

- `gps` 按点打标签
- `signal` 按时间窗重叠打标签

## 最小可用示例

### `1001_signal.csv`

```csv
uid,cid,longitude,latitude,t_in,t_out,status
1001,cell_a,116.39731,39.90812,1710000000000,1710000180000,stay
1001,cell_b,116.40152,39.90746,1710000180000,1710000480000,subway
1001,cell_c,116.41783,39.90511,1710000480000,1710000780000,subway
1001,cell_d,116.43622,39.90345,1710000780000,1710001080000,road_taxi
```

### `1001_gps.csv`

```csv
uid,longitude,latitude,timestamp,status
1001,116.39710,39.90805,1710000000000,stay
1001,116.39712,39.90804,1710000060000,stay
1001,116.40130,39.90750,1710000240000,subway
1001,116.41755,39.90520,1710000540000,subway
1001,116.43590,39.90360,1710000900000,road_taxi
```

## 推荐校验规则

交付前建议至少检查：

1. 文件名与内容中的 `uid` 一致
2. 每个文件只有一个 `uid`
3. 时间严格升序或非降序
4. `status` 只能取 9 个枚举之一
5. `signal` 中每行满足 `t_out >= t_in`
6. 经纬度在北京范围内

## 边界与取舍

- 这版格式优先服务 mock、标注联调和人工核对，先不引入 `segment_id`
- 这版格式优先简单可读，先不引入 `confidence`
- 若后续要做严格评测，可在不破坏本格式的前提下追加字段：
  - `segment_id`
  - `source`
  - `confidence`
  - `annotator`

## 实践清单

- 如果你要给前端 mock：
  - 直接提供 `{uid}_signal.csv` 和 `{uid}_gps.csv`
- 如果你要给算法训练：
  - 优先读取 `gps.status`
  - `signal.status` 作为辅助对齐与核对
- 如果你要给人工标注：
  - 保证同一时间段内 `gps` 与 `signal` 的 `status` 一致

## 参考来源

- [user_upload_adapter_lib.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/user_upload_adapter_lib.py)
- [05-组内共享部署与数据接入规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/05-%E7%BB%84%E5%86%85%E5%85%B1%E4%BA%AB%E9%83%A8%E7%BD%B2%E4%B8%8E%E6%95%B0%E6%8D%AE%E6%8E%A5%E5%85%A5%E8%A7%84%E8%8C%83.md)
- [review_lib.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_lib.py)
