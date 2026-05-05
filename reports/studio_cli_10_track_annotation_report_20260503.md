# Studio CLI 10 条轨迹测试标注报告

报告日期：2026-05-04（Asia/Shanghai）
证据窗口：2026-05-03
批次：`20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local`
Reviewer：`studio-cli-codex-20260503`

## 直接结论

本轮使用已开发的 `studio-cli` 与 Cursor/Codex agent 流程，完成了 10 条轨迹的测试标注读写闭环：分段多 tag timeline、轨迹还原准确/不准确/不确定标注、以及不准确段对应的轨迹编辑草案均已写回并读回。

10 条轨迹合计 456 个分段。其中 430 段标为 `accurate`，20 段标为 `uncertain`，6 段标为 `inaccurate`。6 个不准确段全部挂上 `trackEditRefs`，对应 6 个 point-level draft patches。

这批结果可作为 studio-cli 功能验证和 agent 标注方案样例；还不能直接视为人工金标。尤其是 6 个轨迹编辑 patch 仍需人类在地图上确认坐标后，才能成为正式 corrected trajectory。

## 总览

| 指标 | 结果 |
|---|---:|
| UID 数 | 10 |
| 总分段数 | 456 |
| `semanticTags` 覆盖 | 456/456 |
| `visualEvidenceRefs` 覆盖 | 456/456 |
| `trackEditRefs` 覆盖 | 6 个不准确段 |
| Timeline validate | 10/10 ok |
| Review 决策 | 8 accept / 2 skip |
| 有地图上下文 | 10/10 |
| `bundle_after_decisions` sample_count | 10 |

## 每 UID 标注结果

| UID | Review 决策 | 分段数 | 准确 | 不确定 | 不准确 | semantic/visual 覆盖 | 地图点/markers | track edits | 结论 |
|---|---|---:|---:|---:|---:|---|---|---:|---|
| `100453` | accept | 107 | 107 | 0 | 0 | 107/107 | 600 / 48 | 0 | 还原段整体接受 |
| `100617` | accept | 19 | 19 | 0 | 0 | 19/19 | 373 / 48 | 0 | 还原段整体接受 |
| `101051` | skip | 10 | 0 | 10 | 0 | 10/10 | 10 / 10 | 0 | 全部不确定，需要人工 QC |
| `101599` | accept | 69 | 69 | 0 | 0 | 69/69 | 600 / 48 | 0 | 还原段整体接受 |
| `106303` | skip | 10 | 0 | 10 | 0 | 10/10 | 10 / 10 | 0 | 全部不确定，需要人工 QC |
| `106863` | accept | 31 | 29 | 0 | 2 | 31/31 | 600 / 48 | 2 | 有 2 段不准确，已挂 edit 草案 |
| `110992` | accept | 20 | 18 | 0 | 2 | 20/20 | 600 / 48 | 2 | 有 2 段不准确，已挂 edit 草案 |
| `111601` | accept | 82 | 82 | 0 | 0 | 82/82 | 600 / 48 | 0 | 还原段整体接受 |
| `112483` | accept | 84 | 82 | 0 | 2 | 84/84 | 600 / 48 | 2 | 有 2 段不准确，已挂 edit 草案 |
| `114545` | accept | 24 | 24 | 0 | 0 | 24/24 | 380 / 48 | 0 | 还原段整体接受 |

## 不准确段与轨迹编辑草案

| UID | Segment | chain tag | Track edit ref | Confidence | 状态 |
|---|---|---|---|---:|---|
| `106863` | `draft:106863:segment:12` | `chain:segment_idx_12` | `te-106863-p2` | 0.62 | draft micro-adjust |
| `106863` | `draft:106863:segment:18` | `chain:segment_idx_18` | `te-106863-p1` | 0.62 | draft micro-adjust |
| `110992` | `draft:110992:segment:6` | `chain:segment_idx_6` | `te-110992-p2` | 0.62 | draft micro-adjust |
| `110992` | `draft:110992:segment:8` | `chain:segment_idx_8` | `te-110992-p1` | 0.62 | draft micro-adjust |
| `112483` | `draft:112483:segment:27` | `chain:segment_idx_27` | `te-112483-p2` | 0.62 | draft micro-adjust |
| `112483` | `draft:112483:segment:46` | `chain:segment_idx_46` | `te-112483-p1` | 0.62 | draft micro-adjust |

3 条有 edit 的轨迹读回情况：

| UID | patches | pointPatches | draft refs | reason |
|---|---:|---:|---|---|
| `106863` | 2 | 2 | `te-106863-p1`, `te-106863-p2` | `draft_micro_adjust_after_map_review` |
| `110992` | 2 | 2 | `te-110992-p1`, `te-110992-p2` | `draft_micro_adjust_after_map_review` |
| `112483` | 2 | 2 | `te-112483-p1`, `te-112483-p2` | `draft_micro_adjust_after_map_review` |

所有 patch metadata 都包含提示：`Inspect materials/<uid>/index.html before accepting coordinates.` 这意味着它们是地图审查后的编辑建议，不是已经人工确认的最终坐标。

## 地图证据

10 个 UID 都有地图上下文，证据形式为：

| 项 | 状态 |
|---|---|
| `visual_context.json` | 存在 |
| `index.html` | 存在，使用 Leaflet |
| basemap | `offline_tiles` |
| tile URL | `http://127.0.0.1:8016/offline_tiles/beijing/{z}/{x}/{y}.png` |
| geometry | `LineString` |
| layer count | 每个 UID 1 个 line layer |

逐 UID 地图材料路径：

| UID | 路径 |
|---|---|
| `100453` | `.codex_run/studio_cli_leader_20260503/visual_contexts/100453/` |
| `100617` | `.codex_run/studio_cli_leader_20260503/visual_contexts/100617/` |
| `101051` | `.codex_run/studio_cli_leader_20260503/visual_contexts/101051/` |
| `101599` | `.codex_run/studio_cli_leader_20260503/visual_contexts/101599/` |
| `106303` | `.codex_run/studio_cli_leader_20260503/visual_contexts/106303/` |
| `106863` | `.codex_run/studio_cli_leader_20260503/visual_contexts/106863/` |
| `110992` | `.codex_run/studio_cli_leader_20260503/visual_contexts/110992/` |
| `111601` | `.codex_run/studio_cli_leader_20260503/visual_contexts/111601/` |
| `112483` | `.codex_run/studio_cli_leader_20260503/visual_contexts/112483/` |
| `114545` | `.codex_run/studio_cli_leader_20260503/visual_contexts/114545/` |

注意：这批地图证据不是 PNG 截图，而是可打开的 Leaflet 地图上下文。瓦片依赖 `127.0.0.1:8016` review server 的 `offline_tiles` 服务。

## Export 与验证状态

Timeline validate：

| UID | validate |
|---|---|
| `100453` | ok |
| `100617` | ok |
| `101051` | ok |
| `101599` | ok |
| `106303` | ok |
| `106863` | ok |
| `110992` | ok |
| `111601` | ok |
| `112483` | ok |
| `114545` | ok |

Bundle 状态要分开看：

| 文件 | sample_count | 解释 |
|---|---:|---|
| `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/export/bundle_after_decisions/segment_label_dataset.json` | 10 | 本轮可引用的 10 样本导出索引 |
| `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/export/bundle/segment_label_dataset.json` | 0 | 早期/同轮空导出，不应当作为 10 条成果引用 |
| `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback_quality_summary.json` 中的 `bundle_export` | 0 | 汇总里该子块复述空导出，不能替代 `bundle_after_decisions` |

`bundle_after_decisions` 的 `samples` 记录主要包含 `uid`、`signal_csv`、`gps_csv`、`signal_count`、`gps_count`、`annotation_source`、`interval_semantics`。它是 10 样本导出索引，不是完整内嵌的标签数据；完整标签证据应以 timeline readback 为准。

## Caveats

1. `semanticTags` 是本轮多 tag 的主承载字段；`categoryId`、`categoryName`、`color` 在 final timeline payload 中仍为空。
2. `legacy:ocean0416:*` tag 来自 0416 准确还原段标注/启发式历史证据，不等同于最终出行链 ontology。
3. `101051`、`106303` 虽然有分段和地图证据，但全部为 `uncertain`，所以 review decision 是 `skip`。
4. `106863`、`110992`、`112483` 的不准确段已挂 track edits，但 edits 是草案，需要人工地图 QC。
5. 目前没有 `sample map-snapshot`，所以报告不能声称已经生成了 10 张可归档地图截图。

## 后续人工 QC 清单

1. 打开 3 条有 edit 的 UID 地图：`106863`、`110992`、`112483`。
2. 对照每个不准确 segment 的 `trackEditRefs` 与 `track_edits/<uid>.json` 中的 patch 坐标。
3. 人工确认 patch 后，补一个正式 correction decision 字段，区分 `draft`、`accepted`、`rejected`。
4. 对 `101051`、`106303` 做人工复核，决定是继续 `skip`，还是重分段/重修正后进入 accept。
5. 开发 `corrected trajectory export` 后，重新导出本批 10 UID 的完整出行链数据包。

## 证据索引

| 证据 | 路径 |
|---|---|
| 汇总 | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback_quality_summary.json` |
| Timeline readback | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback/timelines/` |
| Track edits readback | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/readback/track_edits/` |
| Review readback | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/review_readback/` |
| Timeline validate | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/validate/` |
| 地图上下文 | `.codex_run/studio_cli_leader_20260503/visual_contexts/` |
| 10 样本导出索引 | `.codex_run/studio_cli_leader_20260503/final_apply_after_reload/export/bundle_after_decisions/segment_label_dataset.json` |
