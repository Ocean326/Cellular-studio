# adapters/arena_task03_occupation

Research Arena **S02-03 职业身份识别** -> trajectory_annotation_studio batch.

## 这个 adapter 干什么

职业识别是 **UID 级排序**（hidden positive ranking），不是逐点序列标注。
这个 adapter 把它映射到 studio 的「正轨标签」通道：

- 每个 UID 的预测职业写进 `profile.csv` 的 `state` 列
- `states_index.json` 对应 UID 带上职业 tag（供筛选、搜索）
- studio 自带的 **review 面板**（accept / reject / skip）就是 reviewer 确认/否决预测的主入口
- 不预种 timeline segments — 职业是整段 UID 的属性，不是某一段的属性

## 批次结构

```text
<output-batch-root>/
  batch_meta.json
  source_batch.json
  result/
    manifest.json
    states_index.json       # uid -> [profession tags]
    <uid>/
      signal.csv            # raw6 信令（kind=signal，可选）
      profile.csv           # 单行画像：state + 三职业 score + rank（review_reference）
  review/                   # 空壳，等 reviewer 填
```

## 正轨标签接入方式

studio 原生的 `state` / `states_index` / review 机制就是这条「正轨标签」：

- `manifest.states[uid]` → 在样本列表里显示为标签 Pill
- `manifest.review_reference_files = ["profile.csv"]` → accept/reject review 基于 profile.csv
- 每个 reviewer 通过 `review/reviewers/<reviewer_id>/` 独立保留决策
- 多人结果通过 `review/aggregate/` 汇总

reviewer 在 UI 里看到：

1. `signal.csv` 图层 → 观察该 UID 的出行模式（路线、时间分布）
2. `profile.csv` → 预测职业、三职业分数、排名
3. 左右键切 UID，对每个 UID 做一次决策

## 输入合同

### `--signal-csv`（可选，推荐）

raw6 信令，覆盖所有候选 UID：

```text
uid, cid, lat/latitude, lon/longitude, t_in, t_out
```

如果不提供 `--signal-csv`，会生成 profile-only batch（仅 `profile` 图层），
仍可进行 UID 级 accept/reject/skip 审核。

### `--bus-rank-csv` / `--cab-rank-csv` / `--delivery-rank-csv`（各自必填）

提交格式（赛题规定）：

```text
uid,score
100023,0.923456
200441,0.891234
...
```

按 score 降序。允许带 header 或不带。

## 运行

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio

python3 adapters/arena_task03_occupation/build_batch.py \
  --signal-csv        adapters/arena_task03_occupation/examples/signal.example.csv \
  --bus-rank-csv      adapters/arena_task03_occupation/examples/bus_driver.example.csv \
  --cab-rank-csv      adapters/arena_task03_occupation/examples/cab_driver.example.csv \
  --delivery-rank-csv adapters/arena_task03_occupation/examples/delivery.example.csv \
  --top-k 100 \
  --multi-label-threshold-rank 50 \
  --output-batch-root /tmp/arena_task03_batch \
  --batch-name arena_task03_v1 \
  --label "S02-03 职业身份识别 · Top-100 Review" \
  --force
```

## 参数调优

- `--top-k`：每个职业取 top-K 纳入 batch。建议 100（初轮）/ 200（深审）
- `--multi-label-threshold-rank`：UID 若同时进入 2 个以上职业的前 N 名，state 标为 `multi` → reviewer 重点排查噪声 / 候选跨职业

## 启动 studio

```bash
python3 web/review_server.py \
  --result-root /tmp/arena_task03_batch/result \
  --review-root /tmp/arena_task03_batch/review \
  --export-root /tmp/arena_task03_batch/accepted_assets \
  --port 8018
```

浏览器：`http://127.0.0.1:8018/web/index.html`

## Accept/Reject -> 提交回路

人工审核后：

- `reviewer bundle export` 拿回每个 reviewer 的决策
- accept 的 UID 可作为「正标签 seed」回流到 Task03 pipeline 的 PU rerank 阶段
- reject 的 UID 作为强负样本剔除
- 多 reviewer 结果 aggregate 后可以提高最终 top-K 榜单质量

这就是「用正轨的标签接」：studio 的 review 就是标注机制本身，结果通过 `accepted_assets/` 和 `review_exports/` 往下游流。
