# adapter template

这个目录是一个最小可复制的 adapter 样板。

适用场景：

- 你有自己的原始轨迹点数据
- 想先把它投影成 studio 可读的标准 batch
- 希望先跑通最小闭环，再逐步补更多图层或规则

## 这个模板现在能做什么

- 读取一个简单的 JSON 输入文件
- 生成一个可直接被 studio 打开的 batch 目录
- 输出：
  - `batch_meta.json`
  - `source_batch.json`
  - `result/manifest.json`
  - `result/states_index.json`
  - `result/<uid>/raw.csv`

这个模板故意只做一件事：

- 把“原始点序列 -> 标准 batch”这条最小路径跑通

## 输入合同

参考 [examples/source_records.example.json](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters/template/examples/source_records.example.json)：

```json
{
  "dataset_name": "demo_points",
  "label": "Demo Points Batch",
  "samples": [
    {
      "uid": "1001",
      "points": [
        {
          "latitude": 39.9,
          "longitude": 116.3,
          "timestamp_ms": 1711929600000,
          "state": "road"
        }
      ]
    }
  ]
}
```

要求：

- 顶层使用 `samples`
- 每个 sample 至少有一个 `uid`
- 每个 sample 至少有一个 `points` 条目
- 点支持字段：
  - `latitude` 或 `lat`
  - `longitude` 或 `lon`
  - `timestamp_ms`
  - `state` 可选

## 用法

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 adapters/template/build_batch.py \
  --input-json adapters/template/examples/source_records.example.json \
  --output-batch-root /tmp/template_batch \
  --batch-name template_demo \
  --force
```

跑完后可直接启动 studio 指向这个 batch：

```bash
python3 web/review_server.py \
  --result-root /tmp/template_batch/result \
  --review-root /tmp/template_batch/review \
  --export-root /tmp/template_batch/accepted_assets
```

## 你通常只需要改哪几处

1. 改 `load / normalize` 输入数据的方式
2. 改 `point_to_row`，把你的字段投影到统一列
3. 如果你有多图层，补 `layers` 和 `layer_specs`
4. 如果你有更强的 review reference，改 `review_reference_files`

## 建议复制方式

```bash
cp -R adapters/template adapters/my_dataset
```

然后重点改：

- `adapters/my_dataset/build_batch.py`
- `adapters/my_dataset/README.md`
- `adapters/my_dataset/examples/`
