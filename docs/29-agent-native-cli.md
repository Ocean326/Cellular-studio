# Agent-Native CLI（与 GUI 并行）

> 更新时间：2026-05-06

## 目标

给 `trajectory_annotation_studio` 增加一条面向 agent / 自动化 / 开发 smoke 的 CLI 入口，同时保持：

- `web/` 里的 GUI 和 review server 继续做事实源
- CLI 不改写 GUI 状态模型，不做“第二套 review truth”
- 复杂可视化仍留在 GUI
- 结构化读写、批量脚本化、弱监督闭环优先走 CLI

这条入口的定位是：

- `GUI`：人审、地图/时间轴可视化、精细理解
- `CLI`：agent-native 读样本上下文、写 review/timeline、导 aggregate/bundle、做开发期 roundtrip

## 实现形态

- 客户端库：
  [scripts/studio_agent_client.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/studio_agent_client.py)
- CLI 入口：
  [scripts/studio_agent_cli.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/studio_agent_cli.py)
- 安装后 console script：
  `studio-agent`

核心原则借鉴 `CLI-Anything`：

- 命令树先行，而不是把逻辑糊进一个大脚本
- `stdout` 可结构化，支持 `--json`
- 纯 client/lib 与命令解析分离
- 同一套逻辑既可给人，也可给 agent / 自动化
- 先做 flag-friendly CLI，不急着做 TUI

## 当前命令面

```bash
studio-agent health
studio-agent batch list
studio-agent batch show

studio-agent sample list --tag ambiguous_case
studio-agent sample list --review-status unreviewed --reviewer-id codex-agent-cli
studio-agent sample inspect --uid 62161
studio-agent sample materialize --uid 62161 --output-dir ./tmp/62161

studio-agent reviewer start --name "Codex Agent CLI"
studio-agent reviewer list

studio-agent review get --uid 62161
studio-agent review submit --uid 62161 --decision skip ...

studio-agent timeline get --uid 62161
studio-agent timeline put --uid 62161 --payload-file ./timeline.json
studio-agent timeline validate --payload-file ./timeline.json

studio-agent track-edits get --uid 62161 --reviewer-id codex-agent-cli
studio-agent track-edits put --uid 62161 --reviewer-id codex-agent-cli --payload-file ./track_edits.json

studio-agent mode-label candidates --per-label 6 --output-file ./mode_candidates.json
studio-agent mode-label apply --plan-file ./mode_candidates.json --reviewer-id studio-cli-multimode-20260506 --reviewer-name "Studio CLI Multimode 2026-05-06"

studio-agent aggregate uid --uid 62161
studio-agent aggregate export

studio-agent bundle export --reviewer-id codex-agent-cli --create-zip

studio-agent dev roundtrip --uid 62161 --reviewer-name "Codex Agent CLI"
```

## Agent 快速上手

给后续 agent 的最短路径：

1. 启动 studio server，保持 GUI 仍是事实源：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 scripts/start_review_studio.py --port 8016
```

2. 确认 CLI 能连上同一个 server：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  health
```

3. 选择批次并拉取 agent 最小上下文：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  batch list

python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  --batch <batch_name> \
  sample inspect --uid <uid>
```

4. 写 review / timeline 时固定 reviewer namespace，不要冒充人工 reviewer：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  --batch <batch_name> \
  review submit \
  --uid <uid> \
  --decision accept \
  --reviewer-id <agent_reviewer_id> \
  --reviewer-name "<Agent Reviewer Name>" \
  --reference-source studio_agent_cli \
  --tag agent-reviewed
```

5. 对多类出行状态批量标注，先生成候选计划，再 apply；`flight` 和 `low_speed` 默认当作需人审候选：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  --batch <batch_name> \
  --json mode-label candidates \
  --per-label 6 \
  --output-file /tmp/mode_candidates.json

python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8016 \
  --batch <batch_name> \
  --json mode-label apply \
  --plan-file /tmp/mode_candidates.json \
  --reviewer-id <agent_reviewer_id> \
  --reviewer-name "<Agent Reviewer Name>"
```

验证写入是否能被人看见：打开 GUI，搜索目标 UID，切到对应审阅列，在「多人标注汇总」中点击该 reviewer 的「回放分段」。CLI 写入的 timeline 应显示在时间轴「分段层」canvas 和详情文本中；地图上的黑色细条不是这个数据层。

## 适合 agent 的地方

### 1. `sample inspect`

一次返回：

- `case_manifest.json`
- `signal/line/fmm/state_candidates/anchor_candidates` 预览
- `review_reference_files`
- 当前 `review_aggregate`
- 当前 `timeline_aggregate`

这让 agent 不必先理解 GUI DOM，就能拿到 judge 所需的最小上下文。

### 1.5 `sample list --review-status`

现在 `sample list` 已支持 reviewer-aware 队列过滤：

- `--review-status any`
- `--review-status reviewed`
- `--review-status unreviewed`
- 可配合 `--reviewer-id <rid>`

例子：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8031 \
  --batch ten_day_mobility_s0_20_reviewable_v0 \
  --json sample list \
  --review-status unreviewed \
  --reviewer-id codex-agent-cli
```

这条命令更适合作为 agent review worker 的队列入口，而不是每轮都靠外部脚本自己 diff reviewer namespace。

### 1.6 `mode-label candidates/apply`

`mode-label` 是给 agent 批量补多类出行状态用的小闭环：

- `mode-label candidates`：从本地 batch `result_root` 扫描候选段，当前覆盖 `subway / low_speed / road / stay / flight / railway`。
- `mode-label apply`：把候选计划按 reviewer 写入 `review` 和 `timeline_annotations`，供 GUI 的「多人标注汇总」直接回放。
- `subway / road / stay / railway` 优先使用 `fmm.csv` / `line.csv` 的 `match_type` 证据。
- `low_speed` 使用 `od.csv` 中非静止、低速、有限时长移动段作为启发式候选。
- `flight` 当前没有显式 `match_type`，使用 `od.csv` 的高速、长距离、机场近邻启发式，默认 `needsHumanReview=true`。

示例：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8020 \
  --batch 20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local \
  --json mode-label candidates \
  --per-label 6 \
  --output-file .codex_run/multimode_labeling/mode_candidates.json

python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8020 \
  --batch 20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local \
  --json mode-label apply \
  --plan-file .codex_run/multimode_labeling/mode_candidates.json \
  --reviewer-id studio-cli-multimode-20260506 \
  --reviewer-name "Studio CLI Multimode 2026-05-06"
```

GUI 回放入口和人工逻辑共用同一套 reviewer aggregate 面板：在左侧搜索候选 UID（例如 `295435`），切到「已通过」列，点开卡片后在「多人标注汇总」里点对应 reviewer 的「回放分段」。回放只读，不覆盖当前人工 reviewer；真实分段看时间轴的「分段层」canvas 和详情文本，不是地图轨迹上的黑色细条。

### 2. `sample materialize`

把某个 `uid` 的上下文直接落盘，方便：

- 外部 agent
- 批量 judge worker
- notebook / diff / 归档

### 3. `dev roundtrip`

这是开发期 smoke lane：

- 开 reviewer session
- 取 sample context
- 写一条 review
- 可选写 segment annotation
- 回读 aggregate

适合 disposable batch（一次性验证批次）或 demo 环境，不建议直接对 production-like 批次无脑扫写。

## 推荐用法

### 本地 ten-day batch

```bash
python3 web/review_server.py \
  --host 127.0.0.1 \
  --port 8031 \
  --project-root /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio \
  --batches-root /Users/ocean/Documents/Playground/Agent_Scientist/receipts/runs/ten_day_mobility_demo_v0/s0_20/bootstrap_local_visible6_v0/studio_published
```

读上下文：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8031 \
  --batch ten_day_mobility_s0_20_reviewable_v0 \
  sample inspect --uid 62161
```

写 reviewer 结果：

```bash
python3 scripts/studio_agent_cli.py \
  --base-url http://127.0.0.1:8031 \
  --batch ten_day_mobility_s0_20_reviewable_v0 \
  review submit \
  --uid 62161 \
  --decision skip \
  --reviewer-id codex-agent-cli \
  --reviewer-name "Codex Agent CLI" \
  --reference-source fmm.csv \
  --tag ambiguous_case
```

## 边界

- CLI 目前是 `review/timeline/export/track-edits/mode-label` 强；大规模队列 API 和更强地图截图自动化仍需继续补
- 大规模 `sample list` 还没有 review-status-aware 队列编排
- 对高精度几何 patch，仍推荐从 GUI 进入
- 对真正的远端多人协作，权限仍以 server 当前 actor / reviewer namespace 为准，CLI 不额外发明权限层

## 验证

新增测试：

- [scripts/tests/test_studio_agent_cli.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/tests/test_studio_agent_cli.py)

建议一起跑：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m unittest trajectory_annotation_studio.scripts.tests.test_studio_agent_cli
python3 -m unittest trajectory_annotation_studio.web.test_review_server trajectory_annotation_studio.web.test_review_lib trajectory_annotation_studio.scripts.tests.test_server_batch_tools trajectory_annotation_studio.scripts.tests.test_adapter_template
```
