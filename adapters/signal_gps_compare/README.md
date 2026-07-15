# signal_gps_compare adapter

把“信令还原结果 + GPS 对照文件”投影成 `trajectory_annotation_studio` 批次。

## 输入

- `--signal-dir`：还原结果 CSV 目录。当前演示数据为无表头 CSV，前两列是百度墨卡托 `x,y`。
- `--raw-signal-csv`：可选，原始测试信令/基站点 CSV。若不传，会默认读取 `--gps-dir` 下 `测试*.csv` 文件。
- `--gps-dir`：GPS 分段 CSV 目录。每个文件代表一个真值分段，adapter 优先用文件名里的分段时间窗裁剪和排序 GPS 点，再切原始多天信令。当前 GPS / 信令经纬度按 `WGS84` 处理，并转换到高德底图使用的 `GCJ-02`。
- `--signal-layer-label`、`--reconstruction-layer-label`、`--reference-layer-label`：可覆盖前端图层名。当前测试号重配批次中，`测试号.rar` 作为信令来源，5 个 UUID 轨迹作为 `GPS真值结果`，`测试号` 内分段文件显示为 `测试号信令分段`。
- `--reconstruct-from-signal`：把 `--gps-dir` 内的测试号分段文件作为信令输入，按时间去重和距离步长插值生成 `信令还原轨迹`；`--signal-dir` 内的 UUID 轨迹作为 `GPS真值轨迹`。
- `build_v311_comparison_batch.py`：v311 专用比对入口。其计算合同是：v311 `raw.csv / line.csv` 和测试号分段经纬度按 `WGS84` 计算；UUID GPS 真值 CSV 是百度墨卡托，先转 `WGS84` 参与配对、距离和路段指标；KML 真值按 `WGS84` 读入。CSV/KML 混合真值时，KML 会按文件名时间排序分配给最新信令段，剩余旧路线继续在 CSV 真值内做几何匹配，避免新 KML 被旧路线抢走。写入 Studio 展示层前再统一转为高德底图使用的 `GCJ-02`。当前测试号 demo 的 v311 runner 在 FMM 阶段显式跳过 `subway` 候选，只匹配道路候选；默认 FMM 版本仍是 `original`。
- `scripts/run_signal6_v311_demo.py --fmm-version mainroad`：切到独立 `build_mainroad/` FMM 二进制和带 `fmm_cost` 字段的主路偏好路网。该版本保留完整路网候选，只在 routing cost 上给主路低成本，转移防绕路仍按原始几何长度计算；机制说明见 [`../../docs/34-fmm-mainroad-weighted-mechanism.md`](../../docs/34-fmm-mainroad-weighted-mechanism.md)。

## 处理

1. 常规入口将无表头百度墨卡托还原结果转为高德底图使用的 `GCJ-02`。
2. 常规入口将 GPS 分段和原始信令经纬度按 `WGS84 -> GCJ-02` 写入展示层。
3. v311 专用入口先统一到 `WGS84` 计算：v311 还原结果保持 `WGS84`，UUID GPS 真值从 `BD09 Mercator` 转 `WGS84`。
4. 对每条还原轨迹，按几何距离自动匹配最近的 GPS polyline。
5. GPS 分段按文件名时间窗裁剪，并按时间升序重排后生成 `gps.csv` 链道。
6. 对每个还原点计算到 GPS polyline 的最近距离。
7. 常规入口将原始多天信令按每个 GPS 分段的时间窗切片，作为该段的 `signal.csv` 展示，且连线显示；v311 专用入口优先把 v311 结果目录中的 `raw.csv` 写成展示用 `signal.csv`，让 Studio 看到的信令点与算法实际输入一致。
8. 统计 GPS 分段坐标与原始信令坐标的重合率；若高度重合，前端图层会标记为 `GPS分段文件（与信令坐标重合）`，避免误认为独立 GPS 真值。
9. 按 `--threshold-meters` 标记 `gps_match / gps_mismatch`，并生成整体和每条轨迹的正确率。

`--reconstruct-from-signal` / v311 demo 模式下，adapter 会先用 GPS 真值轨迹重采样生成 `road_segment_compare.csv` 覆盖明细，再按“GPS 真值小段中点在还原轨迹 50m 范围内的长度 / GPS 真值总长度”计算主百分比。当前本机缺少 v311 FMM 可执行文件时，`--reconstruct-from-signal` 模式使用可复现的信令插值基线；装好 FMM 后可替换为正式 `snap + OD + FMM` 输出。

v311 demo 的 `gps_comparison_summary.json` 还会输出 `gps_coverage_scenarios`，按多个距离阈值扫描同一个 GPS 真值长度覆盖口径，用来判断整体、排除轨迹04、或排除轨迹04后逐条轨迹是否能达到 `90%`。

2026-06-02 本地 5 条 `mainroad_weighted` 实验结果：排除轨迹04时，50m 为 `91.76%`，100m 为 `94.37%`；含轨迹04整体在 `100m + 首尾各裁 1000m` 口径下为 `90.92%`。实验输出在 `data/work/testing_signal6_v311_experiments/mainroad_weighted_summary.json`。

2026-06-02 已接入 8 条 `mainroad_weighted` 批次：旧 5 条使用 UUID GPS CSV 真值，新 6-8 使用 KML 真值。严格 50m 长度覆盖率：全 8 条 `79.49%`，排除轨迹04 `85.20%`；探索口径中，全 8 条在 `100m + 首尾各裁 1500m` 达到 `90.61%`，排除轨迹04在 `100m + 首尾各裁 500m` 为 `92.14%`、`100m + 首尾各裁 1000m` 为 `93.45%`。逐条全都达到 90% 目前未满足，主要受轨迹08真值/信令边界差异影响。实验输出在 `data/work/testing_signal8_v311_experiments/mainroad_weighted_summary.json`。

同日继续测试更强主路 routing cost：`mainroad_weighted_strong` / `mainroad_weighted_very_strong` 均未改善轨迹06/08，且把轨迹02的 100m 覆盖率从 `78.82%` 拉低到 `69.82%`。`major_roads` 过滤路网诊断能把轨迹06提升到 `94.76% / 95.89%`（50m / 100m）、轨迹08提升到 `96.54% / 97.05%`，但会伤害轨迹02和总体，不能作为全局默认。当前另发布 `signal_gps_v311_hybrid_major06_08_20260602`，仅用 `major_roads` 输出替换 06/08，用于 Studio 中观察主辅路修正效果；该批次 50m 总体 `85.78%`、排除04 `92.36%`，100m 总体 `90.06%`、排除04 `94.20%`。

随后按“速度越高越偏主路”的机制做 `speed_adaptive_mainroad` 诊断批次：默认保留 balanced `mainroad_weighted` 完整路网输出，对 04/06/07/08 使用 `major_roads` fallback，并在 `fmm_algorithm.speed_adaptive_mainroad` 与 `hybrid_route_overrides` 里记录速度画像和替换原因。`signal_gps_v311_speed_adaptive_mainroad_8routes_20260602` 的严格 50m 结果为：全 8 条 `92.32%`、排除04 `92.59%`；04 `90.41%`、06 `94.76%`、07 `91.28%`、08 `96.54%`。100m 结果为：全 8 条 `94.11%`、排除04 `94.35%`。该版本仍是 route-level fallback 实验，不是最终 per-transition FMM speed cost。

2026-06-03 针对轨迹02起步段继续实验：单独加大主路偏好或把小路降级到 `20km/h` 不能解决问题；02 的主要失败来自第一段 OD 内 snap index `3-6` 的北侧异常块提前牵引 FMM 北转。诊断性删除该异常块后，再使用主路 `80km/h`、辅路/三级路 `40km/h`、小路 `20km/h` 的静态 travel-time cost，发布 `signal_gps_v311_speed_startfix_80_40_20_20260603`，严格 50m 全 8 条为 `93.55%`，02 为 `93.77%`。该批次在 `fmm_algorithm.speed_cost_rule` 和 `fmm_algorithm.route02_startfix` 中明确记录：小路没有被删除，低速实验可放松小路惩罚；02 的删点是 truth-informed 诊断，生产版应改成无 GPS 真值的异常 snap 软降权 / 候选重排。

同日继续把“信令稀疏度”并入速度先验，发布 `signal_gps_v311_speed_sparsity_20260603`。该批次在 `fmm_algorithm.speed_sparsity_road_class_prior` 中记录：

```text
major_bias = speed_score * sparsity_score
```

其中速度越高越偏主路；信令时间间隔 / 空间间隔越大、snap 点越少，稀疏度越高，也越偏主路；信令越密则降低主路偏好，保留辅路和小路候选。当前诊断版按 route-level 选择：04/06/07/08 使用 `major_roads` fallback，01/03/05 保持完整路网，02 使用稀疏异常 snap 起步修正。严格 50m 全 8 条为 `93.55%`，100m 全 8 条为 `95.34%`；逐条 50m 为 01 `97.13%`、02 `93.77%`、03 `93.62%`、04 `90.41%`、05 `93.32%`、06 `94.76%`、07 `91.28%`、08 `96.54%`。这仍是诊断版，生产版应进入 per-transition FMM candidate / transition scoring。

默认阈值是 `1200m`，用于当前 GPS 稀疏且无可靠时间对齐的道路级比对演示。

## 输出

常规入口生成三层标准 batch；v311 专用入口生成七层 batch，并把 FMM 版本写进 `manifest.json / batch_meta.json / source_batch.json`：

```text
<batch>/
  batch_meta.json
  source_batch.json
  result/
    manifest.json
    states_index.json
    gps_comparison_summary.json
    <uid>/
      signal.csv
      gate.csv              # GPS 真值非均匀稀疏抽样，展示为卡口定位输入
      lbs.csv               # GPS 真值中命中还原轨迹的稀疏短片段，展示为 LBS 辅助输入
      snap.csv              # v311 only
      od.csv                # v311 only
      reconstruction.csv
      gps.csv
      road_segment_compare.csv
      gps_compare_segments.csv
```

常规前端展示三层：`测试信令 -> 信令还原结果 -> GPS 分段文件`。v311 前端展示七层：`测试号信令 -> 卡口定位 -> LBS辅助定位 -> Snap中间结果 -> OD中间结果 -> 信令还原轨迹 -> GPS真值轨迹`。其中 `测试号信令` 在 v311 批次中来自算法实际 `raw.csv` 输入；`gate.csv` 和 `lbs.csv` 仅作为演示输入层，分别由 GPS 真值稀疏抽样和已命中还原轨迹的短 GPS 片段生成；`lbs.csv` 使用 UID 稳定伪随机抽样，短轨 1 段、长轨 2 段，单段几百米，总覆盖不超过整条 GPS 轨迹长度的 10%；`road_segment_compare.csv` 支撑 GPS 真值长度覆盖率统计。OD 层区分移动 OD 和停留 OD，并会基于 GPS 核心窗前后外延信令识别起点驻留/终点停留；`is_stationary=true` 时显示带米级半径的停留圆，半径由周边信令数量、基站数量和空间离散度反推。

2026-06-02 已发布 Studio 批次：

```text
data/batches/signal_gps_v311_mainroad_weighted_20260602
data/batches/signal_gps_v311_mainroad_weighted_8routes_20260602
data/batches/signal_gps_v311_hybrid_major06_08_20260602
data/batches/signal_gps_v311_speed_adaptive_mainroad_8routes_20260602
data/batches/signal_gps_v311_speed_startfix_80_40_20_20260603
data/batches/signal_gps_v311_speed_sparsity_20260603
```

这些批次的 `fmm_version=mainroad`，`fmm_network_cost_field=fmm_cost`，并在 `fmm_algorithm.mechanism` 中记录主路偏好与原始几何防绕路机制。`hybrid_major06_08`、`speed_adaptive_mainroad`、`speed_startfix_80_40_20` 和 `speed_sparsity` 是诊断 / 展示批次，不是全局默认算法。

## 运行

```bash
python3 adapters/signal_gps_compare/build_batch.py \
  --signal-dir data/source_uploads/current_two_sources/signal_zip \
  --gps-dir data/source_uploads/current_two_sources/gps_rar/测试号 \
  --output-batch-root data/batches/signal_gps_compare_demo \
  --batch-name signal_gps_compare_demo \
  --force
```
