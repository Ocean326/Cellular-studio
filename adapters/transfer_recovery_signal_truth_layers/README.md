# transfer_recovery_signal_truth_layers

这个 adapter 把 `Transfer_Recovery` 里的跨城市信令恢复数据投影成
`trajectory_annotation` 可直接浏览的 `trajectory_layers` batch。

当前面向两套数据：

- `dalian_fingerprint`
- `mysignals_chania`

## 可视化内容

每个 UID 会导出三层：

- `signal_raw.csv`
  - 原始信令层
  - 来自 `processed/sim_signal/*.csv`
- `gps_native.csv`
  - 原始 GPS 轨迹层
  - 来自 `processed/gps_native/*_trajectory.csv`
- `gps_truth.csv`
  - truth json 展开的真值 GPS 层
  - 来自 `processed/internal_truth/sim_signal/*.json`

说明：

- Dalian 当前原始信令是 `uid/cid/lon/lat/t_in/t_out`
- Chania 当前原始信令带有 `rssi` 与 Kalman 相关列
- adapter 会统一成 studio 能直接识别的 `signal` / `gps` 图层合同

## 用法

```bash
cd /home/ocean/apps/City-Agent-Scientist/deploy/products/trajectory_annotation
python3 adapters/transfer_recovery_signal_truth_layers/build_batch.py \
  --output-batch-root /home/ocean/apps/Agent_Scientist_runtime/trajectory_annotation/batches/transferrec_dalian_chania_signal_truth_v1 \
  --batch-name transferrec_dalian_chania_signal_truth_v1 \
  --force
```

只导出单个数据集：

```bash
python3 adapters/transfer_recovery_signal_truth_layers/build_batch.py \
  --datasets dalian \
  --output-batch-root /tmp/transferrec_dalian_only \
  --force
```

限制每个数据集的样本数：

```bash
python3 adapters/transfer_recovery_signal_truth_layers/build_batch.py \
  --limit-per-dataset 5 \
  --output-batch-root /tmp/transferrec_preview \
  --force
```

## 输出结构

标准 batch 根目录下会生成：

- `batch_meta.json`
- `source_batch.json`
- `track_manifest.json`
- `result/manifest.json`
- `result/states_index.json`
- `result/<uid>/signal_raw.csv`
- `result/<uid>/gps_native.csv`
- `result/<uid>/gps_truth.csv`

## 默认输入

默认直接读取：

- `/home/ocean/Transfer_Recovery/applications/signal_reconstruction/manifests/dalian_fingerprint_inventory.json`
- `/home/ocean/Transfer_Recovery/applications/signal_reconstruction/manifests/mysignals_chania_inventory.json`

如果 inventory 路径变化，可通过 `--dalian-inventory` / `--chania-inventory`
覆盖。
