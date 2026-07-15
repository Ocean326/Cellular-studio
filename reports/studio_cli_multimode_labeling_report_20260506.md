# Studio CLI 六类出行状态标注报告

更新时间：2026-05-06

## 目标

在 `20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local` 批次上，补齐六类出行状态候选标注：

- `subway`
- `low_speed`
- `road`
- `stay`
- `flight`
- `railway`

要求是每类至少找到 6 条轨迹，并能通过前端按 reviewer 回放。

## CLI 落地

新增命令：

```bash
studio-agent mode-label candidates
studio-agent mode-label apply
```

关键文件：

- `scripts/studio_agent_mode_labeling.py`
- `scripts/studio_agent_cli.py`
- `scripts/studio_agent_client.py`
- `scripts/tests/test_studio_agent_cli.py`

候选证据规则：

- `subway / road / stay / railway`：优先取 `fmm.csv`，按 `match_type` 和 `segment_idx` 聚合。
- `low_speed`：从 `od.csv` 找非静止、速度 `0.2-1.5 m/s`、时长 `120-7200s` 的移动段。
- `flight`：当前没有显式 `match_type`，从 `od.csv` 取高速、长距离、机场近邻候选；全部写入 `needsHumanReview=true`。

## 写入结果

Reviewer：

```text
studio-cli-multimode-20260506
Studio CLI Multimode 2026-05-06
```

输出文件：

- `.codex_run/multimode_labeling/mode_candidates.json`
- `.codex_run/multimode_labeling/mode_apply_result.json`
- `.codex_run/multimode_labeling/cursor_audit/`

汇总：

| label | count | evidence |
| --- | ---: | --- |
| subway | 6 | `fmm.csv match_type=subway` |
| low_speed | 6 | `od.csv speed/duration moving heuristic` |
| road | 6 | `fmm.csv match_type=road` |
| stay | 6 | `fmm.csv match_type=stay` |
| flight | 6 | `od.csv high-speed/airport heuristic` |
| railway | 6 | `fmm.csv match_type=railway` |

总计写入：

- 35 个 UID
- 36 个 timeline segment

其中 UID `939819` 同时含 `stay` 与 `flight` 候选；按 reviewer 回放时会显示两个不同时间段。

## 六类候选 UID

`subway`：

- `295435`
- `658336`
- `226073`
- `617886`
- `299057`
- `788647`

`low_speed`：

- `816552`
- `133969`
- `47280`
- `296013`
- `677833`
- `70338`

`road`：

- `112483`
- `531736`
- `304052`
- `469342`
- `862728`
- `491987`

`stay`：

- `439524`
- `939819`
- `117824`
- `682955`
- `817510`
- `953319`

`flight`：

- `145769`
- `540057`
- `477503`
- `494750`
- `443650`
- `939819`

`railway`：

- `731972`
- `856018`
- `351840`
- `719555`
- `93176`
- `978497`

## 验证

Fresh verification（2026-05-06）已通过：

```bash
python3 -m unittest scripts.tests.test_studio_agent_cli
python3 -m unittest scripts.tests.test_studio_agent_cli web.test_review_lib web.test_review_server web.test_review_aggregate_ui_contract
python3 scripts/check_docs_entrypoints.py
git diff --check
```

API 回查：

```text
uid_count=35
segment_total=36
subway=6, low_speed=6, road=6, stay=6, flight=6, railway=6
needsHumanReview: flight=6, low_speed=6
missing=[]
```

示例回放 UID：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8020 \
  --batch 20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local \
  timeline get \
  --uid 295435 \
  --reviewer-id studio-cli-multimode-20260506
```

返回的 segment 为 `categoryId=subway`、`categoryName=地铁`，并带有 `workflow:multimode_labeling_v1`、`mode:subway`、`matcher:subway` 和 `confidence=0.88`。

前端回放实测：

- URL：`http://127.0.0.1:8020/web/index.html?batch=20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local&tileMode=online`
- 操作：在左侧搜索 `295435`，切到「已通过」列，点击 `295435` 卡片；展开「多人标注汇总」，点击 `Studio CLI Multimode 2026-05-06` 的「回放分段」。
- 结果：地图容器可见且加载高德瓦片；时间轴分段层显示 `当前窗口 1 段 | 回放 Studio CLI Multimode 2026-05-06`；`#time-scrubber-segment-canvas` 有非透明像素和地铁紫色段落色块。
- 截图：`.codex_run/multimode_labeling/frontend_replay_295435.png`

Cursor subagent 审计：

- `subway-railway`：通过，地铁/铁路各 6 条，均可用 `fmm.csv match_type + segment_idx` 对上。
- `road-stay-low`：通过，road/stay 各 6 条为直接 FMM 证据，low_speed 6 条满足 OD 低速启发式窗口。
- `flight-candidates`：首次并行 worker 退出非零，未产出有效判断；已单独重跑 `flight-candidates-rerun.log`，结论是 6 条满足候选数，但全部应保持 `needsHumanReview=true`。

## 风险

- `flight` 只是候选标注，不是强真值；当前批次没有显式飞机匹配层，必须在 GUI 地图里复核。
- `low_speed` 是 OD 低速启发式，不等价于完整步行/骑行识别。
- 本轮是 reviewer namespace 下的 agent 标注结果，不会覆盖 Ocean 人工标注。
