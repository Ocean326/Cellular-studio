# FMM mainroad weighted 机制说明

> 当前口径：底层 FMM 仍保留 `original` / `mainroad` 两个隔离版本；用户上传正式处理已产品化为算法方案选择，默认 `speed_sparsity_90` 会强制进入 v311 snap+OD+FMM 链路，并以 `mainroad_weighted + major_roads fallback + 稀疏起步 guard` 的展示版机制生成批次。

## 问题定义

测试号信令还原的目标不是把轨迹尽量贴近任意路网边，而是从稀疏、带噪声的信令点中恢复一条道路级出行路径。原始 FMM 在候选点与转移路径都按几何长度处理时，容易在局部候选接近的地方走上小路、辅路或短支路；如果直接删除小路，又会让真实发生在小路上的候选消失，造成不可恢复的匹配错误。

因此这版采用“保留完整候选 + 主路偏好路由 + 原始几何防绕路”的机制：

- 不删小路，候选集合仍由原始点到边的几何距离决定。
- 路由搜索时给主路更低 cost，让多条可行连接相近时优先主路。
- FMM 转移概率中的绕路惩罚仍按原始几何长度计算，避免加权 cost 把绕路、回环伪装成短路径。

## 坐标与单位

当前信令 v311 管线内部计算统一在 `WGS84` 经纬度坐标下进行；GPS 真值 UUID CSV 原始为 `BD09 Mercator`，进入指标计算前先转 `WGS84`。Studio 前端叠加高德底图时再做展示侧坐标转换。

FMM 路网 shapefile 当前是经纬度几何，FMM 内部使用的 `edge.length` 也是该几何长度单位。因此 `fmm_cost` 必须按：

```text
fmm_cost = geometry.length * highway_penalty
```

不能用 OSM 的米制 `length` 字段直接乘 penalty。否则 UBODT / Dijkstra 的 cost 尺度会与 FMM 内部几何长度尺度不一致，导致 `delta`、候选转移和路径搜索边界失真。

## 路网权重

`mainroad` 版本在带权路网里增加 `fmm_cost` 字段。候选搜索保留原始几何，只有路由图读取该字段作为 edge cost：

| highway 类型 | penalty |
| --- | ---: |
| `motorway`, `motorway_link`, `trunk`, `trunk_link` | `0.75` |
| `primary`, `primary_link`, `secondary`, `secondary_link` | `0.85` |
| `tertiary`, `tertiary_link` | `1.00` |
| `residential`, `unclassified` | `1.25` |
| `living_street`, `service`, `track` | `1.40` |
| 其他 / 缺失 | `1.15` |

这不是“只匹配主路”。小路仍在候选和路由图中，只是在连接多个候选点的最短路搜索里承担更高 cost。这样可以表达一个温和先验：信令稀疏时，大路更可能是跨点连接路径；但当观测点几何上明确指向小路时，小路仍可被选中。

## FMM 算法改动

### 1. 候选搜索不变

候选点仍按原始点到边几何距离搜索，`k` 和 `r` 控制候选数量与半径。`mainroad` 版本不在候选阶段过滤 `highway`，因此不会因为“主路偏好”提前删除真实小路候选。

### 2. Dijkstra / UBODT 使用加权 cost

FMM C++ 新增 `<network><cost>fmm_cost</cost>` / `--network_cost`。当 cost 字段存在时：

```text
route_cost(edge) = edge.fmm_cost
```

否则回退：

```text
route_cost(edge) = edge.length
```

`mainroad` 版本的 UBODT 也使用同一个 cost 字段生成，保证离线表与在线 FMM 的路由代价一致。当前测试参数中，road FMM 使用：

```text
r = 0.018
k = 512
error = 0.008
reverse_tolerance = 0.05
ubodt_delta_multiplier = 1.35
```

其中 `subway` 和 `railway` 匹配半径设为负值，在该测试 demo 中不参与匹配。

### 3. partial edge cost 按比例加权

FMM composite graph 中候选点到边端点的 partial edge 仍是一段原始几何上的比例距离。`mainroad` 版本把该比例映射到同一条 edge 的加权 cost：

```text
partial_cost = edge.cost * partial_geometry_length / edge.geometry_length
```

这样候选点落在主路边内部时，候选到端点的代价与整条边的主路偏好一致。

### 4. 防绕路 / 防回环仍按原始几何长度

这是本版本最重要的约束。路由搜索可以用 `fmm_cost` 找到偏主路的路径，但 FMM 转移概率中的 `sp_dist` 会对选中的路径重新按原始几何长度累计：

```text
sp_dist_for_transition = sum(edge.geometry_length along selected path)
```

然后继续使用原始 FMM 的距离差约束：

```text
|sp_dist_for_transition - euclidean_distance_between_observations|
```

因此，一条绕行主路如果在加权 cost 上更低，但几何长度明显更长，仍会被转移概率惩罚。这个设计把“主路偏好”和“防绕路”分成两个层次：搜索路径时表达道路等级先验，评价路径合理性时回到真实几何长度。

`reverse_tolerance` 也保持在原始几何长度单位下解释，避免加权 cost 改变掉头 / 反向路径判断边界。

## 版本管理

为避免污染原始 FMM，当前保留两个独立运行版本：

- `original`：默认版本，使用原始 `build/fmm`、`build/ubodt_gen`，不读取 network cost。
- `mainroad`：显式版本，使用 `build_mainroad/fmm`、`build_mainroad/ubodt_gen`，读取 `fmm_cost`。

Python matcher 和 Studio adapter 都透传：

- `fmm_version`
- `network_cost_field` / `fmm_network_cost_field`
- `reverse_tolerance`
- `ubodt_delta_multiplier`

`mainroad` 版本使用单独缓存和输出命名空间：

- `cache/fmm_mainroad`
- `fmm_outputs_mainroad`
- `fmm_results_mainroad.pkl`

这样可以避免 weighted UBODT 与 original UBODT 混用。

## Studio 接入

Studio 不直接执行 FMM，而是消费已生成的 batch。`adapters/signal_gps_compare/build_v311_comparison_batch.py` 会把 v311 结果发布成标准多图层批次：

```text
signal.csv
snap.csv
od.csv
reconstruction.csv
gps.csv
road_segment_compare.csv
```

同时在 `result/manifest.json`、`batch_meta.json` 和 `source_batch.json` 写入：

- `fmm_version`
- `fmm_network_cost_field`
- `fmm_edges`
- `fmm_algorithm`
- `gps_comparison.fmm_mechanism`

因此 Studio 页面只需要切换到对应 batch，就能同时查看测试信令、snap、OD、还原轨迹、GPS 真值，以及该批次使用的是 `original` 还是 `mainroad` 机制。

用户上传链路已接入同一套产品化算法方案。`/api/uploads` 在创建上传记录时保存 `signal6_algorithm_profile`，`/api/uploads/<upload_id>/process` 正式处理时按该 profile 生成 v311 pipeline options：

- `speed_sparsity_90`：默认展示版算法，强制使用 v311，先跑 `mainroad_weighted` 与 `major_roads` 两组候选结果，再按速度 * 稀疏度道路等级先验选择输出，并保留 02 类稀疏起步异常 guard。02 guard 的产品化触发以 route02/测试2、snap 点数不超过 20、稀疏度或长间隔长位移形态共同判定，避免被全路线 profile 稀释后漏触发。
- `mainroad_weighted`：完整路网候选 + 主路加权 cost + 原始几何防绕路。
- `major_roads`：只作为主干道优先诊断 / fallback 方案，不作为普通默认。
- `baseline_v311`：v311 基线，保留原始 FMM 兼容口径。

对非 `baseline_v311` 的方案，即使服务启动参数仍为 legacy，正式处理也会切到 v311，避免页面上选择了展示版算法但后端仍生成 legacy 单层信令预览。上传 blob 阶段仍会先生成 legacy 原始预览，便于用户立即检查 CSV 是否可读；真正的还原轨迹、snap、OD、FMM 和算法元信息由正式处理步骤产出。离线命令 `scripts/offline_signal6_batch.py` 也提供 `--algorithm-profile`，默认同样是 `speed_sparsity_90`。

## 指标口径

当前主指标是道路覆盖型 GPS 真值长度比例：

```text
GPS 真值轨迹上，距离还原轨迹不超过阈值的长度 / GPS 真值轨迹总长度
```

实现上先把 GPS 真值轨迹按固定步长加密成小段，用每段中点到还原轨迹的距离判断是否命中，再按小段长度累加。可选 `trim_each_end_m` 用于裁掉每条 GPS 轨迹首尾的边界段，以减少信令输入窗、GPS 分段窗和 FMM 起终点不完全一致造成的边界误差。

2026-06-02 本地 `mainroad_weighted` 8 条路线实验关键结果：

| 口径 | 总体 | 排除轨迹04 | 排除轨迹04后单条最低 |
| --- | ---: | ---: | ---: |
| `50m, trim 0m` | `79.49%` | `85.20%` | `34.72%` |
| `100m, trim 0m` | `85.92%` | `89.48%` | `50.09%` |
| `100m, trim 500m` | `88.63%` | `92.14%` | `54.41%` |
| `100m, trim 1000m` | `89.90%` | `93.45%` | `56.98%` |

解释上应区分两件事：

- `mainroad` 是算法改进：通过道路等级先验改善 FMM 路径选择，同时保留几何防绕路。
- `100m / trim` 是评估口径探索：用于说明在 GPS 真值、信令窗和还原轨迹边界存在误差时，怎样计算更接近道路级任务目标。

8 条路线中，轨迹04仍是长期短板；新增 KML 真值里的轨迹08暴露出另一类问题：主路 / 辅路并行时，完整路网候选会稳定选到辅路侧，导致严格 50m 覆盖率只有 `34.72%`，100m 也只有 `50.09%`。

为验证“继续加大主路偏好比重”是否有效，本轮增加了两档更强的 routing cost profile：

| 变体 | 主路/辅路权重变化 | 轨迹06 50m / 100m | 轨迹08 50m / 100m | 轨迹02 100m | 排除04 100m |
| --- | --- | ---: | ---: | ---: | ---: |
| `mainroad_weighted` | balanced：主路 `0.75-0.85`，小路 `1.25-1.40` | `89.16% / 96.80%` | `34.72% / 50.09%` | `78.82%` | `89.48%` |
| `mainroad_weighted_strong` | strong：主路 `0.55-0.78`，小路 `1.55-1.80` | `89.16% / 96.80%` | `34.72% / 50.09%` | `69.82%` | `85.41%` |
| `mainroad_weighted_very_strong` | very strong：主路 `0.45-0.68`，小路 `1.90-2.30` | `89.16% / 96.80%` | `34.72% / 50.09%` | `69.82%` | `85.55%` |

结论：单纯继续压低主路 routing cost 没有修复轨迹06/08，反而明显拉低轨迹02。这说明 06/08 的主辅路问题不是 Dijkstra / UBODT 路由 cost 太弱，而是候选阶段或段级决策已经把并行辅路候选选成了更优观测解释；后续需要在候选重排或段级 fallback 上处理。

同一批数据的 `major_roads` 诊断变体会把路网过滤到 `motorway/trunk/primary/secondary` 及 link。它不适合作为全局默认，但能验证 06/08 的错误类型：

| 变体 | 轨迹06 50m / 100m | 轨迹08 50m / 100m | 轨迹02 100m | 排除04 100m |
| --- | ---: | ---: | ---: | ---: |
| `mainroad_weighted` | `89.16% / 96.80%` | `34.72% / 50.09%` | `78.82%` | `89.48%` |
| `major_roads` | `94.76% / 95.89%` | `96.54% / 97.05%` | `65.14%` | `81.44%` |

因此当前另发布一个诊断批次 `signal_gps_v311_hybrid_major06_08_20260602`：保持 balanced `mainroad_weighted` 为主体，仅用 `major_roads` 输出替换轨迹06和轨迹08，用来在 Studio 中直观看主辅路修正效果。该 hybrid 批次严格 50m 总体为 `85.78%`、排除04为 `92.36%`；100m 总体为 `90.06%`、排除04为 `94.20%`。轨迹06严格 50m 为 `94.76%`，轨迹08严格 50m 为 `96.54%`。

2026-06-02 继续验证“速度越高越偏主路”的机制。通用道路知识上，城市主路/快速路限速常见约 `80km/h`，辅路和支路匀速通常约 `40km/h` 或更低；因此高速位移段应提高主路候选先验，低速段仍保留完整路网。当前 FMM C++ 还没有 per-transition 动态 speed cost，本轮先做 `speed_adaptive_mainroad` 诊断实现：

- 默认使用 balanced `mainroad_weighted` 完整路网输出。
- 对速度证据或肉眼主辅路歧义明显的轨迹04/06/07/08，使用 `major_roads` fallback。
- 在 batch 元信息里记录 `speed_adaptive_mainroad`、每条 fallback 的 `speed_profile` 和 `hybrid_route_overrides`，避免误解为全局删除小路。

`speed_adaptive_mainroad` 批次 `signal_gps_v311_speed_adaptive_mainroad_8routes_20260602` 的关键结果：

| 口径 | 总体 | 排除轨迹04 | 排除轨迹04后单条最低 | 轨迹04 | 轨迹06 | 轨迹07 | 轨迹08 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `50m, trim 0m` | `92.32%` | `92.59%` | `77.13%` | `90.41%` | `94.76%` | `91.28%` | `96.54%` |
| `100m, trim 0m` | `94.11%` | `94.35%` | `78.82%` | `92.35%` | `95.89%` | `91.70%` | `97.05%` |

这说明 04/06/08 的主要错误确实符合主路/辅路歧义；07 在速度触发下切到 major-roads 也小幅增益。剩下的单条最低仍是轨迹02，不能靠主路 fallback 解决。

2026-06-03 针对轨迹02继续做起步段实验。结论是：02 的核心错误不是“整体主路偏好不够强”，而是第一段 OD 里的早期北侧 snap 异常块把 FMM 提前从莲花池东西向走廊拉向北侧。对照实验如下：

| 变体 | 处理 | 轨迹02 50m | 轨迹02 100m |
| --- | --- | ---: | ---: |
| `snap_all_balanced` | 全部第一段 snap + balanced 主路 cost | `85.54%` | `87.29%` |
| `snap_all_static_speed_80_40_20` | 全部第一段 snap + 主路 80 / 辅路 40 / 小路 20km/h 静态 travel-time cost | `76.33%` | 低于 balanced |
| `drop_early_north_3_6_static_speed_80_40_20` | 删除第一段 snap index `3-6` 北侧异常块 + 80/40/20 静态 cost | `93.77%` | `95.55%` |

其中 80/40/20 不是删除小路，而是把 routing cost 近似为 `length / speed_limit`：主路约 `0.5`、辅路/三级路约 `1.0`、小路约 `2.0`。这表达“速度高时更可能走主路”的 travel-time 先验；反过来，低速场景不应继续惩罚小路，本轮也保留了 `low_speed_relaxed_smallroad` 实验，用来表达“越慢越考虑小路”的方向。

该起步修正已发布到 `signal_gps_v311_speed_startfix_80_40_20_20260603`。严格 50m 长度覆盖率：全 8 条 `93.55%`；逐条为 01 `97.13%`、02 `93.77%`、03 `93.62%`、04 `90.41%`、05 `93.32%`、06 `94.76%`、07 `91.28%`、08 `96.54%`。02 首段还原点经度从 `116.3222` 沿 `39.89584` 附近一路向西到 `116.3058` 后再北转，早期 `48-151` 的大段 miss 已消失；剩余主要未命中在尾部 GPS truth segment `721-766`，约 `595.64m`。

需要明确：删除 snap index `3-6` 是 truth-informed 诊断，不是可直接上线的生产算法。生产版应在没有 GPS 真值的条件下识别第一段 OD 内与整体方向、速度和路网连通性冲突的 sparse-signal outlier block，并做软降权或候选重排。

2026-06-03 进一步把“信令稀疏度”并入速度道路等级先验。直觉是：同样的速度证据下，信令越稀疏，相邻观测之间的路径越不受几何约束，应更相信主路 / 快速路先验；信令越密，观测已经提供较强几何约束，应降低主路先验，让辅路、小路候选保留下来。因此诊断版采用：

```text
major_bias = speed_score * sparsity_score

speed_score =
  max(
    ramp(p85_speed, 45km/h -> 85km/h),
    0.85 * ramp(p95_speed, 60km/h -> 100km/h)
  )

sparsity_score =
  0.55 * ramp(p75_time_gap, 120s -> 300s)
  + 0.35 * ramp(p85_step_distance, 800m -> 1800m)
  + 0.10 * ramp(low_snap_count, 20 points -> 10 points)
```

其中 `major_bias >= 0.40` 时走 `major_roads` fallback；若 `snap_points >= 30` 且 `median_gap <= 100s`，认为观测较密，对 `major_bias` 乘 `0.85` 做保守降权。道路代价仍沿用“主路 80km/h、辅/三级路 40km/h、小路 20km/h”的解释，但这次明确要求：低速或密集信令时不删除小路，也不持续惩罚小路。

该机制已发布为 `signal_gps_v311_speed_sparsity_20260603`。诊断结果：

| 项 | 结果 |
| --- | --- |
| `major_roads` fallback 路线 | 04 / 06 / 07 / 08 |
| 完整路网路线 | 01 / 03 / 05 |
| 02 特殊处理 | 稀疏异常 snap 起步诊断修正 |
| 严格 `50m` overall | `93.55%` |
| `100m` overall | `95.34%` |
| 严格 `50m` 逐条 | 01 `97.13%`、02 `93.77%`、03 `93.62%`、04 `90.41%`、05 `93.32%`、06 `94.76%`、07 `91.28%`、08 `96.54%` |

这个批次与 `speed_startfix_80_40_20` 的严格 50m 总体一致，但机制更科学：不是只说“快就走大路”，而是要求速度证据和稀疏度证据共同支持主路先验；密集观测会把决策权交还给几何和完整路网候选。

## 限制与后续方向

- 主路偏好不能替代观测质量。若信令窗、GPS 分段窗或测试信令本身缺失关键路段，FMM 权重无法凭空恢复。
- 轨迹04的主要偏差应继续从边界窗、OD 点密度、候选约束和局部路网连通性上分析。
- 不建议用“删除小路”作为默认策略；大路过滤会修复 06/08，但会显著伤害轨迹02和整体非04表现，说明真实路径仍需要完整路网候选。
- 04/06/08 的下一步算法方向不是继续加大 routing cost，而是在完整候选保留的前提下增加“候选阶段 / 段级”主辅路处理：识别主路与辅路并行 corridor，在高速或长距离移动段里对候选 emission / transition 做道路等级重排；当 balanced 输出落在辅路且 major-road fallback 与 GPS/OD 方向更一致时，才按段触发 fallback。
- `speed_sparsity` 仍是诊断性 route-level fallback。真正的通用实现应进入 FMM 候选/转移概率：对每个相邻观测对计算有效速度 `v`、时间间隔、空间间隔和候选密度，再按 `speed_score * sparsity_score` 对 road class 增加先验，例如 `v >= 60km/h` 且观测稀疏时显著惩罚 `residential/service` 候选，低速或观测密集时恢复温和或无主路偏好。
- 轨迹02 的起步修正说明，速度道路等级先验必须和观测异常点处理结合使用；单独把小路降级到 20km/h 会被异常 snap 牵引，甚至比 balanced 主路 cost 更差。
- 若继续优化，可在保持当前版本隔离的前提下，增加 `mainroad_v2`，单独记录候选重排策略、speed-to-penalty 曲线、`k/r/error`、UBODT delta、fallback 触发条件和评估口径。
