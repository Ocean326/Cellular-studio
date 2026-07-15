# adapters/arena_task02_travel_mode

Research Arena **S02-02 出行语义识别** -> trajectory_annotation_studio batch.

## 这个 adapter 干什么

把两份 CSV 投影为一个标准 studio batch：

- `signal.csv`（raw6 信令：`uid,cid,lon,lat,t_in,t_out`）
- `pred.csv`（逐点预测：`uid,(cid,lon,lat,)time,prediction`；`prediction ∈ {0,1,2,3}`）

产出：

```text
<output-batch-root>/
  batch_meta.json
  source_batch.json
  result/
    manifest.json
    states_index.json
    <uid>/
      signal.csv           # 原始信令图层（kind=signal）
      pred.csv             # 逐点预测图层（kind=default, review_reference=true）
  review/
    timeline_annotations/
      <uid>.json           # 预先种入的多段标签（模型段化结果）
```

## 多段 + 多段标签怎么实现

studio 原生支持每个 UID 挂一份 `timeline_annotations`，里面的 `segments` 就是「多段任意标签」。

- 模型预测的连续同标签点 → 压成 segment → 写进 `review/timeline_annotations/<uid>.json`
- 类别集合：`subway / bus / highway / other`（每段可独立改）
- reviewer 打开 UID → UI 里已经有模型段化结果 → 可以：
  - 拖边界调整起止点（分段粒度）
  - 点改类别（换标签）
  - 新增段 / 合并段
  - 每段独立一条记录 → 多段 + 多段标签自然支持

同时 `pred.csv` 的 `state` 列进 `states_index.json`，作为 UID 级可过滤的出行方式 tag。
`review_reference_files = ["pred.csv"]` → accept/reject review 走 `pred.csv` 作为凭据。

## 输入合同

### `--signal-csv`（必填）

raw6 格式，表头按任意顺序，包含：

```text
uid, cid, lat/latitude, lon/longitude, t_in(/time_in/time), t_out(/time_out)
```

### `--pred-csv`（必填）

逐点预测，表头至少包含：

```text
uid, time(/timestamp/t_in), prediction(/pred)
```

可选：`lat/latitude, lon/longitude, cid`

`prediction` 语义（与科研竞技场第二期赛题一致）：

| 值 | 状态码 | 中文 |
|----|--------|------|
| 0  | other  | 其他 |
| 1  | subway | 地铁 |
| 2  | bus    | 公交 |
| 3  | highway| 高速 |

## 用法

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio

python3 adapters/arena_task02_travel_mode/build_batch.py \
  --signal-csv adapters/arena_task02_travel_mode/examples/signal.example.csv \
  --pred-csv   adapters/arena_task02_travel_mode/examples/pred.example.csv \
  --output-batch-root /tmp/arena_task02_batch \
  --batch-name arena_task02_v3 \
  --label "S02-02 出行语义识别 · v3 · 多段 Review" \
  --force
```

## 启动 studio 指向这个 batch

```bash
python3 web/review_server.py \
  --result-root  /tmp/arena_task02_batch/result \
  --review-root  /tmp/arena_task02_batch/review \
  --export-root  /tmp/arena_task02_batch/accepted_assets \
  --port 8017
```

浏览器打开 `http://127.0.0.1:8017/web/index.html`。

或者走共享批次根：把 `/tmp/arena_task02_batch/` 拷进 `data/batches/<name>/` 后：

```bash
python3 scripts/start_review_studio.py --port 8016
```

## 版本对比

batch 层面可以并行发布多个版本 batch：

- `arena_task02_v1`（保守，无公交段）
- `arena_task02_v2`（激进，切换过多）
- `arena_task02_v3`（短公交段剪枝，推荐）

每版分别跑一次 `build_batch.py` → 独立 batch → studio 批次列表里对比挑最优。

## 建议工作流

1. 本地 Mac 运行 `build_batch.py` 生成 batch
2. `zip -qr arena_task02_batch.zip result` 打包
3. 按 `docs/16-快速接入指南.md` 上传到 179 operator incoming
4. operator publish 后，组内 reviewer 进 studio → 多段标签 review
5. `reviewer bundle export` 拿回标注结果
