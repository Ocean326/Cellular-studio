# Agent Review 渐进式加载记忆

> 更新时间：2026-05-05
> 来源会话：`019decf8-9312-78a0-bb68-f48a4ddba304`
> 作用：后续会话的首读记忆页。先读 [CURRENT.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/CURRENT.md) 的指针，再按需回看本页和 `docs/29-32`。

## Source Map

- [CURRENT.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/CURRENT.md)
- [docs/29-agent-native-cli.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/29-agent-native-cli.md)
- [docs/30-agent-native-cli-progress-report.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/30-agent-native-cli-progress-report.md)
- [docs/31-agent-map-cli-review-report.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/31-agent-map-cli-review-report.md)
- [docs/32-studio-cli-development-plan.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/32-studio-cli-development-plan.md)
- [scripts/studio_agent_client.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/studio_agent_client.py)
- [scripts/studio_agent_cli.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/studio_agent_cli.py)
- [scripts/tests/test_studio_agent_cli.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts/tests/test_studio_agent_cli.py)
- [web/review_server.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_server.py)
- [web/review_lib.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/review_lib.py)
- [web/index.html](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/index.html)
- [web/styles/index.css](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/styles/index.css)
- [web/test_review_aggregate_ui_contract.py](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web/test_review_aggregate_ui_contract.py)
- [.codex_run/agent_map_trial/15448_context](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/15448_context)
- [.codex_run/agent_map_trial/uid15448_map_gaode.png](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gaode.png)
- [.codex_run/agent_map_trial/uid15448_map_gap_zoom_gaode.png](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_gap_zoom_gaode.png)
- [.codex_run/agent_map_trial/uid15448_map_summary.json](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.codex_run/agent_map_trial/uid15448_map_summary.json)

## Facts

- `web/review_server.py` 和 GUI 继续做事实源，CLI 只是 agent-friendly 的读写层，不是第二套 review truth。
- `sample inspect` 是当前最 agent-native 的读路径，适合先拿样本上下文、reference files、aggregate 和 timeline 证据。
- `dev roundtrip` 是开发期 smoke lane，适合做最小闭环验证，不是正式批量审阅入口。
- `sample list --review-status` 已能用，但还没有真正可扩展的 reviewer-aware queue snapshot API；大批量扫描仍会碰到 N+1 aggregate 问题。
- 当前真正该记住的命令名是 `sample segment-summary`、`sample visual-context export`、`timeline validate` 和 `track-edits get/put/export`。
- `sample map-snapshot` 目前应按提案名理解，不要误当成已实现的正式命令；实际已落地的视觉桥是 `sample visual-context export`。
- GUI 已支持从「多人标注汇总」按 reviewer 回放 timeline annotations。回放时当前人工 reviewer 不变，回放来源单独显示，轨迹编辑与整段标记会锁定为只读。
- 回放分段显示在 `#time-scrubber-segment-row` / `#time-scrubber-segment-canvas` / `#time-scrubber-segment-detail`，不要把地图轨迹上的黑色细条当成 segment annotation。
- 旧 agent timeline payload 可能用毫秒级时间戳；server 读出 `/api/timeline-annotations` 时会把明显的毫秒 epoch 归一为秒，避免分段落到当前时间窗口外。
- 对只写了 `semanticTags` 的 agent segment，server 会补齐可显示的 `categoryId/categoryName/color`，例如 `matcher:road` -> `road / #4caf50`。
- 0416 batch 回放验证样例：`20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local / UID 100453`，`studio-cli-codex-20260503` 回放 108 段，`ocean` 人工分段 5 段，地图仍为 Leaflet + Gaode。
- `UID 15448` 是当前最重要的 map / gap 回归样本，关键 gap 是 `1678327385-1678331476`。
- `UID 1023384` 是 preview-only 反例，说明纯预览可以抓显眼停留，但不能完成可信分段。

## Judgments

- 纯 CLI 可以支撑初筛、结构化初标和回归 smoke，但不足以独立完成高可信的几何审阅。
- 地图上下文必须留在 agent 输入里，否则 road / stay / gap 的判断会过保守，或者只能靠 CSV 硬猜。
- `docs/30-agent-native-cli-progress-report.md` 和 `docs/32-studio-cli-development-plan.md` 里关于 `track-edits` 的口径已经落后于当前代码与新计划。
- `sample map-snapshot` 更像概念名称；后续如果沿用，也应明确它只是 `sample visual-context export` 的历史别名或上层概念。

## Inferences

- 更稳的 agent review flow 应该是 `sample inspect -> sample segment-summary -> sample visual-context export -> timeline validate -> track-edits ...`。
- 当前最有价值的缺口不是再写一个 CLI wrapper，而是补一个批量 / 队列快照能力，让 `sample list --review-status` 不再依赖逐 UID 聚合。
- 一旦 `track-edits` 被 CLI 包起来，agent review 就能从“读写基础标注”推进到“读写 + 校验 + 编辑闭环”。

## Open Loops

- 批量样本状态快照 / reviewer-aware queue API。
- `track-edits` CLI 收口。
- `sample visual-context compare` 之类的有图 / 无图对照能力。
- vNext timeline payload 的 schema 硬化和兼容迁移。

## Next-Resume Checklist

- 先读 [CURRENT.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/CURRENT.md)，再读本页。
- 需要样本上下文时先跑 `sample inspect --uid <uid>`。
- 需要结构化分段摘要时跑 `sample segment-summary --uid <uid> --json`。
- 需要地图证据包时跑 `sample visual-context export --uid <uid> --include-map --focus gaps,segments`。
- 需要校验 payload 时跑 `timeline validate --payload-file <draft.json>`。
- 需要轨迹编辑闭环时跑 `track-edits get/put/export --uid <uid> --reviewer-id <rid>`。
- 最终几何判断仍要回到 GUI / 地图证据，不要只看文本摘要下结论。

## Guardrails

- 不要把 GUI truth boundary 改写成 CLI truth boundary。
- 不要把 `docs/30` 或 `docs/32` 里关于 `track-edits` 的旧表述当成现状。
- 不要把 `sample map-snapshot` 倒读成已经落地的稳定命令。
- 不要让 replay reviewer 冒充当前人工 reviewer；回放只能读别人的 timeline，不能用来保存人工标注或轨迹编辑。
- 本页只记录当前会话里最需要跨轮保持的事实、判断、推断和恢复动作，不替代长报告。
