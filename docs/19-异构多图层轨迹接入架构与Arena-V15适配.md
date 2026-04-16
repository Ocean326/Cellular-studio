# trajectory_annotation_studio 异构多图层轨迹接入架构与 Arena V1.5 适配

- 状态：implemented slice
- 日期：2026-04-16
- 角色：architecture + delivery bridge doc
- 适用范围：`trajectory_annotation_studio` 批次合同、前端图层加载、review reference 语义、`research_arena` V1.5 分层轨迹接入

## 1. 问题定义

当前 studio 的前端已经基本具备 manifest 驱动图层加载能力，但整个系统仍存在两个不一致：

1. 前端可按 `manifest.layers` 动态展示多层
2. intake / validate / reviewer export / docs 仍默认世界只有 `raw/snap/od/fmm/line`

这会导致两个直接问题：

- 当我们把 `GPS -> tier1 -> tier2 -> tier3 -> tier4` 这类“同一条轨迹的多来源异构图层”接入 studio 时，前端能勉强显示，后端合同却不认识
- 当未来接入别的异构来源时，系统会继续被迫新增一轮文件名特判

因此本次目标不是单独把 `tier1-4` 硬塞进 studio，而是把“多图层轨迹批次”升级为正式合同。

## 2. 设计目标

### 2.1 目标

- 允许同一 UID 下挂载任意数量、任意来源的轨迹图层
- 允许图层 key 与实际 CSV 文件名解耦
- 允许 organizer 明确声明哪些图层可作为 `accept` 的 review reference
- 保持旧批次 `raw/snap/od/fmm/line` 和 `gps/signal/stations` 完全兼容
- 为 `research_arena` V1.5 提供一条从 split/batch/truth 资产到 studio batch 的稳定适配路径

### 2.2 非目标

- 不在本次把 review 流程彻底改写成图层可配置工作流
- 不在本次引入新的后端数据库或中心配置服务
- 不要求所有图层都必须可过滤、可状态着色、可作为 time scrubber 主层

## 3. 新的批次合同

### 3.1 核心原则

批次的唯一规范入口仍然是：

- `batch_meta.json`
- `result/manifest.json`
- `result/<uid>/...`

但从本次起，studio 不再默认“图层 key 等于文件名等于旧版五件套”，而是采用：

- `manifest.layers`
  决定图层顺序和图层 key
- `manifest.layer_specs`
  决定每个图层对应的文件名和结构语义
- `manifest.review_reference_files`
  决定 review `accept` 时允许引用哪些文件

### 3.2 `result/manifest.json` 新字段

新增 canonical 字段：

```json
{
  "ui_mode": "trajectory_layers",
  "uids": ["1011509"],
  "layers": ["gps", "tier1", "tier2", "tier3", "tier4"],
  "hide_review_panel": true,
  "time_scrubber_preferred_layers": ["gps", "tier4", "tier3", "tier2", "tier1"],
  "review_reference_files": ["tier4.csv"],
  "layer_labels": {
    "gps": "GPS 真值",
    "tier1": "Tier-1 Clean Physical",
    "tier2": "Tier-2 Overlap Ambiguity",
    "tier3": "Tier-3 Raw-like Local Noise",
    "tier4": "Tier-4 Closest To Raw"
  },
  "layer_specs": {
    "gps": {
      "filename": "gps.csv",
      "kind": "gps",
      "hasLine": true
    },
    "tier4": {
      "filename": "tier4.csv",
      "kind": "signal",
      "hasLine": true,
      "review_reference": true
    }
  }
}
```

字段语义：

- `layer_specs.<layer>.filename`
  当前图层实际读取哪个 CSV，默认值是 `<layer>.csv`
- `layer_specs.<layer>.kind`
  当前图层采用哪种前端渲染语义。当前已支持：
  - `default`
  - `gps`
  - `signal`
  - `stations`
  - `od`
  - `line`
- `layer_specs.<layer>.review_reference`
  可选。若为 `true`，表示该图层可作为 review `accept` 的参考文件
- `review_reference_files`
  显式覆盖 review reference 文件列表。若显式写成空数组，表示该 batch 不提供 review reference；若未提供，则从 `layer_specs.*.review_reference=true` 推导；若仍为空，则回退到旧版 `line.csv / fmm.csv`

### 3.3 兼容规则

旧批次无需改动即可继续工作：

- 若没有 `layer_specs`，仍从 `manifest.layers` 推导 `<layer>.csv`
- 若没有 `review_reference_files`，仍回退到 `line.csv / fmm.csv`
- 若 `ui_mode` 是旧值，仍沿用旧 preset

因此本次是增量升级，不是 breaking change。

## 4. 前端行为约定

### 4.1 图层读取

前端现在按以下顺序决定如何读取图层：

1. 取 `manifest.layers`
2. 读取 `manifest.layer_specs[layer].filename`
3. 以 `<uid>/<filename>` 发起 `HEAD` 和 `GET`

这意味着图层 key 已经不再和文件名硬绑定。

### 4.2 图层渲染

前端继续根据 `kind` 决定渲染方式，而不是根据固定文件名：

- `gps`
  适合真值轨迹，读取 `latitude/longitude/timestamp_ms`
- `signal`
  适合 raw6 类事件流，支持 `uid/cid/lat/lon/t_in/t_out`
- `default`
  适合一般点线类轨迹

对 raw6 类图层，本次补齐了：

- `lat/lon` 坐标列支持
- `t_in/t_out` 时间窗支持
- `cid` 信息在 tooltip 和 inline label 中展示

### 4.3 UI 模式

新增 `trajectory_layers` preset，默认特征是：

- 单列样本列表
- 隐藏 review panel
- time scrubber 默认优先 GPS，再依次回退到更高 tier

它的目标不是替代旧模式，而是为“同一条轨迹的多层对照浏览”提供更合适的默认 chrome。

## 5. Review 与导出语义

### 5.1 Review reference

`accept` 不再强制要求 `line.csv` 或 `fmm.csv`。

现在的规则是：

1. 若 manifest 显式声明 `review_reference_files`
   则只认这些文件
2. 否则若 `layer_specs` 中有 `review_reference=true`
   则使用这些图层对应的 `filename`
3. 否则回退到旧版 `line.csv / fmm.csv`

### 5.2 Reviewer bundle

reviewer bundle 导出不再只复制旧版五件套，而是：

- 保留旧版文件复制逻辑
- 同时复制 manifest 中声明的异构图层文件

这样 organizer 在复盘一条轨迹时，拿到的 bundle 会保留这条轨迹的多图层上下文。

## 6. Adapter 边界

### 6.1 统一思路

studio 不直接理解 `research_arena` 的 split/batch/sample/truth 目录树。

本次明确 adapter 边界：

- 上游资产继续按 arena 自己的 release 结构组织
- adapter 负责把它们投影成 studio batch
- studio 只消费自己稳定的 `result/manifest.json + result/<uid>/...`

### 6.2 Arena V1.5 到 studio 的映射

对 `trajectory_reconstruction` V1.5，当前采用以下 user-facing 对照：

- `gps`
  organizer 真值轨迹
- `tier1`
  对应 organizer 内部 `tier1-clean-physical`
- `tier2`
  对应 organizer 内部 `tier2-overlap-ambiguity`
- `tier3`
  对应 organizer 内部 `tier3-raw-like-local-noise`
- `tier4`
  对应 organizer 内部 `tier4-closest-to-raw`

这里 user-facing 层与 organizer split_dir 已经基本对齐，只保留了 `tier1-4` 作为前端 layer key 的轻量别名，避免把批次里的展示 key 直接绑定到磁盘目录名。

### 6.3 当前落地脚本

本次新增：

- `scripts/adapt_research_arena_v15_layers_batch.py`

它负责：

1. 从 `tier0-starter / tier1-structural / tier2-bursty / tier3-realistic` 的同 phase split 中取交集 UID
2. 生成 studio `result/<uid>/gps.csv`
3. 生成 studio `result/<uid>/tier1.csv` 到 `tier4.csv`
4. 写出 `manifest.json / states_index.json / track_manifest.json / source_batch.json / batch_meta.json`

## 7. 为什么这条路线更稳

相比“直接给前端新增 tier1-4 文件名判断”，当前方案有四个明显优点：

- 新来源接入只需要补 adapter 和 manifest，不需要再改前端文件名判断
- 后端 validate / publish / reviewer export 的合同和前端一致
- 旧批次兼容成本低
- `GPS + tier1-4` 只是第一个实例，后续还能接 `raw -> snap -> fmm`、`gps -> signal -> stations` 之外的第三类来源

## 8. 本次落地范围

本次已经落地：

- manifest 驱动的 layer filename / review reference 语义
- 前端 raw6 `lat/lon/t_in/t_out` 图层支持
- `trajectory_layers` UI 模式
- `research_arena` V1.5 layered batch adapter

仍未在本次落地：

- 完全图层可配置的 review policy
- 按图层自定义过滤器计算
- 对所有新图层 kinds 的独立 legend / specialized stats

## 9. 推荐后续动作

如果下一步继续扩这条能力，优先级建议如下：

1. 把 `track_manifest.json` 中的 `sample_ids_by_layer` 暴露到前端详情面板
2. 为 `trajectory_layers` 增加图层差异统计，比如 row count / 时间跨度 / 平均驻留时长
3. 若后续需要在异构图层上做审核，再把 review reference 规则提升为 batch policy 文档
