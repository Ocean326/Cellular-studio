# adapters

这个目录是 `Cellular-studio` 的适配层入口。

## 原则

- 某个人或某类数据格式不同，优先在这里适配
- 不把个性化数据判断直接写进 `web/`
- adapter 的目标是把外部数据投影成统一 batch 合同

## 现在的最小工作流

如果你要接一类新数据，推荐直接复制模板：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
cp -R adapters/template adapters/my_dataset
```

然后修改：

- `adapters/my_dataset/build_batch.py`
- `adapters/my_dataset/README.md`
- `adapters/my_dataset/examples/`

## 推荐子目录结构

```text
adapters/
  template/
    README.md
    build_batch.py
    examples/
  <owner_or_dataset>/
    README.md
    build_batch.py
    examples/
```

## 每个 adapter 至少应包含

- `README.md`
  说明输入、输出、字段依赖和运行方式
- `build_batch.py`
  负责生成标准 batch
- `examples/`
  给出一份最小可复现输入

## 模板入口

- [template/README.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters/template/README.md)
- [template/build_batch.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters/template/build_batch.py)
- [template/examples/source_records.example.json](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters/template/examples/source_records.example.json)

## 当前专用适配器

- [signal_gps_compare/README.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters/signal_gps_compare/README.md)
  多天信令 + GPS/KML 真值 + 信令还原结果接入；v311 入口按 `WGS84` 计算，支持 UUID GPS CSV 的 `BD09 Mercator -> WGS84` 转换、KML 真值读入、`signal/gate/lbs/snap/od/reconstruction/gps` 七层展示，并产出 `gps_comparison` 正确率供前端展示。用户上传的 `signal_triplet` zip 会复用同一展示合同：`signal.csv` 入算法，`gate.csv/lbs.csv` 作为输入辅助层，`gps.csv` 存在时作为真值比对层。
