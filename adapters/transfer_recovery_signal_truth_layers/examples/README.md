# examples

最小示例命令：

```bash
python3 adapters/transfer_recovery_signal_truth_layers/build_batch.py \
  --datasets dalian,chania \
  --limit-per-dataset 2 \
  --output-batch-root /tmp/transferrec_signal_truth_demo \
  --batch-name transferrec_signal_truth_demo \
  --force
```

生成后可直接用 studio 打开对应 batch 根目录。
