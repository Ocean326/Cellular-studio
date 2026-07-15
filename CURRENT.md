# trajectory_annotation_studio · 当前状态

> 更新时间：2026-07-15
> 维护：Codex/Cursor agent（**Composer 2** 本回合梳理）
> 文档原则：本文件是「少数活文档」，一直更新；其他报告（`docs/14-…`、`docs/17-…`、`docs/18-…`、`docs/24-…`）按日期冻结。

## Agent review 渐进式加载

- 首读：[`docs/33-agent-review-progressive-memory.md`](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/33-agent-review-progressive-memory.md)。后续会话先看这份，再按需回看 `docs/29-32`。
- 当前口径：`sample map-snapshot` 仍按提案名理解，真实已落地的视觉桥是 `sample visual-context export`；`track-edits` 的真实边界以最新代码和本页为准，`docs/30` / `docs/32` 有滞后表述。
- 2026-05-05 口径：前端已支持在「多人标注汇总」里按 reviewer 回放 timeline annotations。回放是只读视图，不切换当前人工 reviewer，不允许轨迹编辑保存；真实分段显示位置是 `#time-scrubber-segment-row` / `#time-scrubber-segment-canvas` / `#time-scrubber-segment-detail`，不是轨迹上的黑色细条。
- agent 旧结果里常见的毫秒级 `startTime/endTime` 会在 server 读出时归一到秒；仅有 `semanticTags` 的 segment 会尽量补齐 `categoryId/categoryName/color`，用于前端分段层着色和回放。

## 2026-04-25 目录与交付物梳理

### Patch（20260424）去重与归档
- **仓库根**未检出多个并列的 `trajectory_annotation_studio_delivery_patch_20260424` 风格目录；**有效归档仅此一处**：`Cellular-projects/delivery_out/studio/patches/20260424/`，内含：
  - 解压型增量：`web/`、`scripts/`（热区：review 服务/前端 admin/boot、`user_upload_adapter_lib` 与单测等）
  - 同内容压缩包：`trajectory_annotation_studio_delivery_patch_20260424.tar.gz`（约 70K）
- **与「曾有三副本、去重 2/3」的关系**：本工作区当前**仅保留一份**可交付物；若历史上曾在根目录放过多份同名目录/解压树，**现状已等价为单点归档**，无需再删重复目录。
- **小补丁与 `min_bundle` 的关系**（`README.offline` + 实际目录对照）：
  - `delivery_out/trajectory_annotation_studio_min_bundle_20260424/`（及 `.tar.gz`）= **全量离线基线**（`trajectory_annotation_studio` 完整源码 + `cellular_quality`、map_assets、离线瓦片等，体量约 823M 解压 / 约 71M 压缩可搬运），用于内网/无网「一把解压 + `docker load` 镜像后 `start_bundle`」。
  - 上述 **patch 目录** = 对基线/主干在 **4/24 当日** 的**增量热修复**（比全量小几个数量级），可覆盖在运环境中的少数文件，不必重拷整个 `min_bundle`。

### OCI 镜像 tar（约 2.5GB，**本次未移动**）
- 文件：`/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio_offline_image_linux_amd64.tar`（约 2.5G，供 `docker load`）。
- **处理建议（与只读制品一致，不入 git）**：
  1. **首选**：外置到 NAS/对象存储/内网共享，仓内只留 `SHA256` + 下载/拷贝说明（例如将来 `delivery_out/studio/images/IMAGE_MANIFEST.md`），避免拖慢备份与 IDE 索引。
  2. **次选**：迁到 `delivery_out/studio/images/` 做「与 patches 同域」归档，但工作副本仍会膨胀约 3G，需接受磁盘与同步成本。
- 说明：制包脚本默认导出名多为 `trajectory_annotation_studio_offline_image.tar`；根目录 `*_linux_amd64.tar` 为平台化/另存导出文件名，**用法相同**（`docker load` 后 `start_bundle.sh`）。

### 本回合清理
- 已删：`delivery_out/.DS_Store`。
- 已扫：`trajectory_annotation_studio/` 下 **0** 个 `__pycache__`、**0** 个 `.DS_Store`（此前已净或本机未生成）。

## 包元信息（`pyproject.toml`）
- 名：`trajectory-annotation-studio`，版本 `0.1.0`，`requires-python >= 3.11`。
- 构建：`setuptools`（`[build-system]` 要求 `setuptools>=68`），描述为 *Local stdlib-only trajectory review server baseline*。
- 说明：以 **README 为** `project.readme` 入口；**无** 在 `pyproject` 中列出运行时依赖，与「尽量标准库、轻量服务」的仓库边界一致（具体逻辑依赖见 `web/`、`scripts/` 与测试）。

## 适配器层速览（`adapters/README.md`）
- **目标**：新数据源不要直接改 `web/`，在 `adapters/<dataset>/` 用 `build_batch.py` 把输入投影为统一 `batch` 合同。
- **新接入**：`cp -R adapters/template adapters/my_dataset`，改 `build_batch.py`、`README.md`、`examples/`。
- **子目录结构**：`template/` 与每个数据集下均至少含 `README.md`、`build_batch.py`、`examples/`。
- **赛题现用实现**：S02-02 多段 + timeline 见 `adapters/arena_task02_travel_mode/`；S02-03 UID 级排序 + accept/reject 见 `adapters/arena_task03_occupation/`（两 README 中均有「本目录下 `build_batch.py` + `web/review_server` 指批次根」的用法）。

## 一句话说明
组内共享的轨迹审阅与标注 Web 应用（前端 + 单进程 Python `review_server`），把 Arena S02-02 / S02-03 的预测结果以多段标签 / Top-K accept-reject 形式交给人审阅与修正，并产出可回流到下游 pipeline 的 reviewer bundle。

## 当前活跃工作
- **Arena task02 / task03 适配器入库**：`adapters/arena_task02_travel_mode/`、`adapters/arena_task03_occupation/` 已落到主干；examples、`build_batch.py`、README 都齐了，是当前 Arena 二期 review 通道的事实入口。
- **离线 / 内网 Docker 交付**：`deploy/docker/` 下 `build_image_and_export.sh + assemble_delivery_bundle.sh + start_bundle.sh + stop_bundle.sh` 已成型，docker bundle = studio 代码 + `cellular_quality v311` + FMM vendor + 北京 map_assets + offline tiles。`20260424` 小补丁已归档在 `delivery_out/studio/patches/20260424/`（`web` + `scripts` + `tar.gz` 单点）。2026-06 最终答辩演示新增 `deploy/docker/assemble_final_demo_delivery.sh`，输出镜像 tar 分离的源码资产包：只预置 `signal_gps_v311_speed_sparsity_20260603` 最终批次和 `data/test` 的 8 条 `signal.csv/gate.csv/lbs.csv/gps.csv` 输入轨迹，同时生成 `signal_triplet_8routes_input.zip`、`docker-compose.yml`、`start.sh` 和镜像兼容性检查脚本；该交付包要求外部镜像为 Linux AMD64，且包含 `geopandas/fiona/pyproj/scikit-learn`、original FMM 与 `build_mainroad` FMM Linux 二进制。
- **前端拆分进行中**：`web/app/` 下 `runtime/`（boot/foundation/runtime_config/state）、`features/{review_flow, studio_admin, track_inspection, workspace}` 已拉出来，`web/index.html` 仍是主交互壳体；`docs/22-`、`docs/23-` 是这次重构计划。
- **Reviewer 命名空间**：`review/reviewers/<id>/{reviews,timeline_annotations} + aggregate/` 已是默认形态；旧批次走 `scripts/migrate_legacy_review_namespace.py` 迁移。
- **分段标签数据接口**：`docs/25-`（mock）+ `docs/26-`（对外版）已对齐 task02 的多段输入。
- **signal6 离线 / 上传管线**：`scripts/offline_signal6_batch.py` + `scripts/user_upload_adapter_lib.py` 是 v311 snap+OD+FMM 在 studio 侧的入口；`web/upload_center.html + web/upload_lib.py` 是用户自助上传 UI。`review_server.py --signal6-pipeline-mode` 默认 `v311`，正式处理会产出 `chain2` 五层 `raw/snap/od/fmm/line`；上传 blob 阶段仍先生成 legacy 原始预览，但 signal6 预览会忽略北京范围外的无效点并在 note 中报告行数，避免 `(0,0)` 等脏点阻断后续正式处理。上传 process 已产品化 `signal6_algorithm_profile`：默认 `speed_sparsity_90`，可选 `mainroad_weighted`、`major_roads`、`baseline_v311`；非 baseline profile 会强制进入 v311，即使服务启动参数是 legacy，避免展示算法被降级成单层预览。`speed_sparsity_90` 会运行 `mainroad_weighted` 与 `major_roads` 候选，按速度 * 信令稀疏度选择输出，并保留 02 类稀疏起步异常 guard；离线命令 `scripts/offline_signal6_batch.py --algorithm-profile` 默认同样走该方案。用户上传现已新增 `signal_triplet` 类型：上传一个 zip，内部每条轨迹一个文件夹，固定包含 `signal.csv`、`gate.csv`、`lbs.csv`，可选 `gps.csv`；正式处理会复用 `speed_sparsity_90` 算法，把 chain2 中间结果规范化成最终展示合同 `signal/gate/lbs/snap/od/reconstruction/gps`，有 `gps.csv` 时同时生成 `road_segment_compare.csv` 和 `gps_comparison_summary.json`。`signal_triplet` 输出会保留原始 `signal.csv` 的 `t_in/t_out` 算法口径，并为 `t_out-t_in<=1s` 的占位记录追加 `display_t_out/display_duration_ms/display_duration_source`，前端弹窗和时间轴优先用该展示结束时间。该流程依赖 pandas/geopandas/FMM 运行资产，本地 8016 服务推荐用 bundled Python 启动。底层 FMM 仍保留 `original` / `mainroad` 版本隔离；测试号演示可通过 `fmm_version=mainroad` / `scripts/run_signal6_v311_demo.py --fmm-version mainroad` 切到独立 `build_mainroad/` 二进制和带 `fmm_cost` 字段的主路偏好路网，机制说明见 `docs/34-fmm-mainroad-weighted-mechanism.md`。
- 2026-06-11 运行稳定性补充：`signal6` / `signal_triplet` 正式处理在单进程 server 内串行执行，避免多名用户同时触发多轮 FMM 把内网部署机打满；`signal_triplet` 会尊重传入的 `signal6_algorithm_profile`，不再强制覆盖成最重的 `speed_sparsity_90`。
- **信令还原 GPS 分段对齐演示**：`adapters/signal_gps_compare/` 已接入 2026-06 测试号 8 条路线（旧 5 条 UUID GPS CSV + 新 3 条 KML 真值）。v311 专用 adapter 统一在 `WGS84` 计算，UUID CSV 真值从 `BD09 Mercator` 转入，KML 按 `WGS84` 读入；CSV/KML 混合真值时会把 KML 固定分配给时间排序最后的新增信令段，避免几何最近匹配串到旧路线。当前已发布 `data/batches/signal_gps_v311_mainroad_weighted_20260602`（旧 5 条）、`data/batches/signal_gps_v311_mainroad_weighted_8routes_20260602`（8 条）、诊断批次 `data/batches/signal_gps_v311_hybrid_major06_08_20260602`（06/08 主辅路修正探索）、`data/batches/signal_gps_v311_speed_adaptive_mainroad_8routes_20260602`（速度自适应主路 fallback 探索）、`data/batches/signal_gps_v311_speed_startfix_80_40_20_20260603`（02 起步异常 snap 诊断修正 + 80/40/20 道路速度代价）和 `data/batches/signal_gps_v311_speed_sparsity_20260603`（速度 * 信令稀疏度道路等级先验诊断），最新展示层为 `signal/gate/lbs/snap/od/reconstruction/gps` 七层和 `fmm_algorithm` 元信息；其中 `gate` 是用 GPS 真值非均匀稀疏抽样生成的卡口定位演示输入层，`lbs` 是从 GPS 真值中已命中还原轨迹的稀疏短片段生成的 LBS 辅助定位演示输入层：短轨 1 段、长轨 2 段，单段几百米，按 UID 稳定伪随机错开位置与长度，且总覆盖不超过整条 GPS 轨迹长度的 10%。前端时间轴现在以当前 UID 中可用时间跨度最长的图层作为播放/显示窗口基准，避免切到短辅助层时把地图裁掉。8 条批次的 `signal.csv` 展示 v311 实际 `raw.csv` 输入点；OD 层区分移动 OD 和停留 OD，并基于 GPS 核心窗前后外延信令识别起点驻留/终点停留，`is_stationary=true` 时用带米级半径的停留圆，半径由周边信令数量、基站数量和空间离散度反推。06/08/04 的实验结论是：继续加大全路网 routing cost 的主路偏好不能修复主辅路错配；按速度或主辅路风险触发 `major_roads` 段级/路线级 fallback 可把严格 50m overall 提升到 `92.32%`。02 的主要失败点不是首尾窗口，而是第一段 OD 内 snap index `3-6` 的北侧异常块把 FMM 提前拉离莲花池东西向走廊；诊断性删除该块后使用主路 80km/h、辅/三级路 40km/h、小路 20km/h 的静态 travel-time 代价，8 条严格 50m overall 为 `93.55%`，02 为 `93.77%`。最新 `speed_sparsity` 批次把“速度越高越偏主路”和“信令越稀疏越偏主路，越密越保留小路”合成 `major_bias = speed_score * sparsity_score`，选择 04/06/07/08 走 `major_roads` fallback，01/03/05 保持完整路网，02 使用稀疏异常 snap 起步诊断修正；严格 50m overall 仍为 `93.55%`，100m overall 为 `95.34%`。这些 hybrid / start-fix / speed-sparsity 批次仍是诊断版，最终应把异常 snap 降权和速度 * 稀疏度道路等级先验进入 FMM 候选/转移概率，而不是依赖 GPS 真值人工删点。
- **跨城市信令真值可视化**：`adapters/transfer_recovery_signal_truth_layers/` 将 Dalian fingerprint 与 MySignals Chania 的原始信令、原始 GPS 和展开后的 GPS truth 投影为只读 `trajectory_layers` batch；输入 inventory 和输出 batch 都通过命令行参数指定，不把真实数据写入 Git。
- **Agent-native CLI**：`scripts/studio_agent_client.py` + `scripts/studio_agent_cli.py` 已落第一版，走现有 `review_server` 的 HTTP/JSON contract，不改 GUI truth boundary；覆盖 `batch/sample/reviewer/review/timeline/aggregate/bundle/dev roundtrip`。
- **Agent reviewer 分段回放**：GUI 的 reviewer aggregate 面板现在可直接回放 `studio-cli-codex-20260503` 等 agent reviewer 的 timeline annotations；已在 `20260416T152425Z_v3_11_samealgo_local1000_signal100_10d_uid1000_local / UID 100453` 验证，Ocean 人工分段显示 5 段，Studio CLI Codex 回放显示 108 段，地图仍为 Leaflet + Gaode。
- **多类出行状态 CLI 标注**：`mode-label candidates/apply` 已可扫描 `subway / low_speed / road / stay / flight / railway` 候选并按 reviewer 写入 timeline。2026-05-06 已用 `studio-cli-multimode-20260506` 在 0416 1000 UID batch 写入 35 个 UID / 36 个 segment，每类 6 段；`flight` 当前是 OD 高速/机场启发式候选，默认需人审。前端实测入口：搜索 `295435`，切到「已通过」列，点卡片后在「多人标注汇总」里回放 `Studio CLI Multimode 2026-05-06`，地图和时间轴分段层同时可见。

## 入口与命令
- 启动（共享批次根，推荐）：`python3 scripts/start_review_studio.py --port 8016`
- 启动（直接指批次）：`python3 web/review_server.py --port 8016 --batches-root <path>`
- 模块入口：`python3 -m trajectory_annotation_studio.web.review_server --help`
- Agent CLI（源码态、从本项目目录运行）：`python3 scripts/studio_agent_cli.py --help`
- Agent CLI（模块态）：在包父目录 `/Users/ocean/Documents/Playground/Cellular-projects` 运行 `python3 -m trajectory_annotation_studio.scripts.studio_agent_cli --help`，或安装 editable package 后使用 `studio-agent --help`
- 离线交付制包：`bash deploy/docker/build_image_and_export.sh`（构建镜像，默认导出名见脚本内 `trajectory_annotation_studio_offline_image*.tar`）+ `bash deploy/docker/assemble_delivery_bundle.sh`（输出 `delivery_out/trajectory_annotation_studio_offline_bundle_<时间戳>/.tar.gz`，若根目录有镜像 tar 会一并打进去）；Docker compose 默认限制容器为 `STUDIO_CONTAINER_CPUS=2.0`、`STUDIO_CONTAINER_MEM_LIMIT=4g`，默认 `STUDIO_RESTART_POLICY=no` 避免不兼容镜像反复重启，加载镜像前按 `STUDIO_DOCKER_MIN_FREE_GB=12` 检查 Docker 根目录可用空间。
- 离线交付**使用方**（`deploy/docker/README.offline.md`）：解压完整 bundle 后，在包根 `bash trajectory_annotation_studio/deploy/docker/start_bundle.sh`；停止用 `stop_bundle.sh`；入口 `http://127.0.0.1:8016/web/index.html`。可选无 FMM 构建：`SKIP_FMM=1` 前缀同一 build 脚本。
- 仅容器内跑 signal6 批处理（同 README）：`docker run ... trajectory-annotation-studio-offline:latest -m trajectory_annotation_studio.scripts.offline_signal6_batch --input ... --published-root ... --batch-name ...`
- 离线 signal6 → 批次：`python3 scripts/offline_signal6_batch.py --input <signal6.csv> --published-root <root> --batch-name <name> --algorithm-profile speed_sparsity_90`
- 用户上传多源包：Studio 管理面板选择「信令+卡口+LBS包」并上传 `.zip`；或 API 使用 `upload_type=signal_triplet`，zip 内每条轨迹一个文件夹，包含 `signal.csv/gate.csv/lbs.csv`，可选 `gps.csv`。
- 适配器：
  - `adapters/arena_task02_travel_mode/build_batch.py`（出行语义 · 多段标签 review）
  - `adapters/arena_task03_occupation/build_batch.py`（职业身份 · UID 级 accept/reject）
  - `adapters/template/build_batch.py`（接新数据复制这个）
- 提交前自检：`python3 scripts/check_docs_entrypoints.py && python3 -m unittest web.test_review_lib web.test_review_server scripts.tests.test_check_docs_entrypoints scripts.tests.test_server_batch_tools scripts.tests.test_research_arena_v15_layer_adapter scripts.tests.test_adapter_template && python3 scripts/check_index_html_inline_js.py`

## 数据依赖
- 读：
  - 适配器 examples（`adapters/*/examples/`）
  - 共享批次根：`project_data/cellular_quality_review_round1/workspace/review_batches/`
  - 用户上传：`data/incoming/`、`data/upload_samples/`
  - Arena 真实提交（在 `research_arena_personal/` 下，本仓不入 git）
- 写：
  - 单批次：`data/batches/<batch>/{result, review, accepted_assets}`
  - 共享批次：同上结构落到 `--batches-root`
  - 离线瓦片缓存：`data/offline_tiles_cache/`、`web/runtime/`
  - reviewer 导出：`accepted_assets/<reviewer_id>/`、`review/aggregate/`

## 可复用资产（待登记到全仓库 registry）

### 方法
- `studio_review_lib`：`web/review_lib.py` — 批次/审阅/timeline annotation 持久化（reviewer 命名空间 + aggregate）
- `studio_review_server`：`web/review_server.py` — 单进程 stdlib HTTP，提供批次/审阅/导出/上传/瓦片接口
- `studio_upload_lib`：`web/upload_lib.py`（+ `web/test_upload_lib.py`）— 上传链路解析、payload 校验
- `studio_offline_tile_lib`：`web/offline_tile_lib.py` — 内置 / 内网瓦片切换与缓存
- `studio_export_helpers`：`web/export_accepted_assets.py`、`web/export_review_aggregate.py`、`web/export_reviewed_subset.py`、`web/export_reviewer_bundle.py` — 多 reviewer 导出/汇总
- `studio_server_batch_lib`：`scripts/server_batch_lib.py` — 服务器侧批次发布、metadata、validate
- `studio_user_upload_adapter`：`scripts/user_upload_adapter_lib.py` — 上传 → result/manifest 的转换核心
- `studio_offline_signal6_pipeline`：`scripts/offline_signal6_batch.py` — 离线把 signal6 跑成 published batch
- `studio_adapter_signal_gps_compare`：`adapters/signal_gps_compare/build_batch.py` / `build_v311_comparison_batch.py` — 多天信令按 GPS 分段切片 + 信令还原结果对 GPS 真值分段比对，支持前端 `gps_comparison` 正确率展示；v311 入口会保留 `snap/od` 中间层和 FMM 版本元信息
- `studio_adapter_template`：`adapters/template/` — 接新数据源的最小起点
- `studio_adapter_arena_task02`：`adapters/arena_task02_travel_mode/build_batch.py` — 多段标签接入参考实现
- `studio_adapter_arena_task03`：`adapters/arena_task03_occupation/build_batch.py` — UID 级排序接入参考实现
- `studio_adapter_research_arena_v15`：`scripts/adapt_research_arena_v15_layers_batch.py` + `scripts/adapt_research_arena_tier_pair_batch.py`
- `studio_adapter_cellular_quality`：`scripts/adapt_cellular_quality_batch.py`
- `studio_publish_helpers`：`scripts/publish_server_batch.py`、`scripts/process_incoming_upload.py`、`scripts/validate_published_batch.py`、`scripts/init_179_server_layout.py`
- `studio_agent_cli_client`：`scripts/studio_agent_client.py` — agent / 自动化用 HTTP client，封装 batch/sample/review/timeline/export surfaces
- `studio_agent_cli`：`scripts/studio_agent_cli.py` — 与 GUI 并行的 CLI 入口，适合 agent review / materialize / dev roundtrip / mode-label batch annotation
- `studio_agent_mode_labeling`：`scripts/studio_agent_mode_labeling.py` — 多类出行状态候选发现与 reviewer timeline 写入辅助
- `studio_namespace_migrator`：`scripts/migrate_legacy_review_namespace.py` — 旧 review 结构 → reviewer namespace
- `studio_arena_jhy_review_builder`：`scripts/build_arena_jhy_review_batches.py`
- `studio_docs_entrypoint_check`：`scripts/check_docs_entrypoints.py`
- `studio_index_html_inline_js_check`：`scripts/check_index_html_inline_js.py`
- `studio_curate_valid_result_pool`：`scripts/curate_valid_result_pool.py`
- `studio_batch_contract`：`batch_contract.py`（仓根 module-level 合同对象）
- `studio_frontend_runtime`：`web/app/runtime/{boot,foundation,runtime_config,state}.js` + `web/app/studio_bootstrap.js`
- `studio_frontend_features`：`web/app/features/{review_flow,studio_admin,track_inspection,workspace}/*.js`

### 数据约定
- `studio_batch_layout`：`<batch>/batch_meta.json + source_batch.json + result/{manifest.json, states_index.json, <uid>/} + review/...` 是所有适配器共同遵守的批次结构
- `studio_reviewer_namespace`：`review/{system/reviewer_registry.json, reviewers/<rid>/{profile.json, reviews/{ledger.jsonl, latest_reviews.json}, timeline_annotations/{ledger.jsonl, <uid>.json}}, aggregate/{stats.json, by_uid/<uid>.json}}`
- `studio_timeline_annotation_segments`：`review/timeline_annotations/<uid>.json` 中的 `segments` 数组 = 多段任意标签（task02 出行语义沿用此结构）
- `studio_states_index`：`result/states_index.json: {uid: [tag, ...]}` —UID 级筛选/搜索 tag
- `studio_review_reference_files`：`manifest.review_reference_files = [...]` 指定 accept/reject 凭据图层（如 task02 的 `pred.csv`、task03 的 `profile.csv`）
- `studio_signal6_input_contract`：`uid,cid,lat,lon,t_in,t_out`（六元组 + 可选 `status`）—offline_signal6_batch / user_upload 共用入口
- `studio_signal_triplet_upload_contract`：`.zip` 包内每条轨迹一个目录，固定文件名 `signal.csv`、`gate.csv`、`lbs.csv`，可选 `gps.csv`；`signal.csv` 仍按 signal6 六元组读入，`gate/lbs/gps` 作为输入展示/真值比对图层并入最终七层批次；输出侧可追加 `display_t_out/display_duration_ms/display_duration_source`，用于修正占位式 1 秒信令持续时间的页面展示
- `studio_arena_task02_pred_contract`：`uid,(cid,lon,lat,)time,prediction ∈ {0,1,2,3}` → `subway/bus/highway/other`
- `studio_arena_task03_rank_contract`：`uid,score` 三个职业各一份 + `--top-k` + `--multi-label-threshold-rank`

## 关键文档
- 文档总入口：`docs/README.md`、`docs/INDEX.md`、`docs/DOCS_MAINTENANCE.md`
- Agent 启动契约：`AGENTS.md`
- 当前事实与协作：`README.md`、`CURRENT.md`、`CONTRIBUTING.md`
- 分类索引已替代数字平铺；后续找文档先看 `docs/INDEX.md`
- Agent review 渐进式加载：先读 `docs/33-agent-review-progressive-memory.md`，再读 `docs/29-32`
- 前端 GUI：`docs/22-`、`docs/23-`、`docs/28-`
- 后端 / 存储 / 批次合同：`docs/05-`、`docs/06-`、`docs/08-`、`docs/09-`、`docs/19-`、`docs/25-`、`docs/26-`
- CLI / Agent-native：`docs/29-`、`docs/30-`、`docs/32-`
- Agent 实验报告：`docs/31-`、`reports/studio_cli_system_report_20260503.md`、`reports/studio_cli_10_track_annotation_report_20260503.md`
- 测试 / 验证：`web/README.md`、`tests/*.md`、`web/test_*.py`、`scripts/tests/test_*.py`
- 部署 / 运维 / 交付：`docs/10-`、`docs/11-`、`docs/12-`、`docs/13-`、`docs/14-`、`docs/15-`、`docs/17-`、`docs/18-`、`docs/24-`、`deploy/docker/README.offline.md`
- 治理与适配器：`docs/03-`、`docs/07-`、`docs/20-`、`adapters/README.md`、`adapters/*/README.md`

## 离线交付制品对照
| 制品 | 位置 | 体量 | 用途 |
|------|------|------|------|
| 小补丁包（解压） | `delivery_out/studio/patches/20260424/` | ~420K | 增量覆盖 web/ 与 scripts/ 中的少数文件（review_server / review_lib / studio_management* / boot.js / index.html / user_upload_adapter_lib + 对应测试） |
| 小补丁包（tar.gz） | `delivery_out/studio/patches/20260424/trajectory_annotation_studio_delivery_patch_20260424.tar.gz` | ~70K | 同上的可搬运压缩版 |
| 完整最小 bundle（解压） | `delivery_out/trajectory_annotation_studio_min_bundle_20260424/` | ~823M | 完整离线源码 + cellular_quality + map_assets + tiles，配合镜像 tar 即可 `docker load + start_bundle` |
| 完整最小 bundle（tar.gz） | `delivery_out/trajectory_annotation_studio_min_bundle_20260424.tar.gz` | ~71M | 同上，对外搬运形态 |
| OCI 镜像 tar | `trajectory_annotation_studio_offline_image_linux_amd64.tar`（**仓库根，本梳理未移动**） | ~2.5G | `docker load` 用，配合 `start_bundle.sh`；与制包默认名 `trajectory_annotation_studio_offline_image.tar` 系同一类产物，仅文件名/导出参数不同 |

> patch 与 min_bundle 的关系：min_bundle 是「完整离线源码 + 资产」基线（一次性大包），patch 是 4-24 当天对该基线 + 主干上少数代码文件的增量覆盖（review server / 上传 / 前端 admin / boot 等热区）。

## 归本项目的根 `scripts/*` 脚本
（位于 `/Users/ocean/Documents/Playground/Cellular-projects/scripts/`，不在本项目目录树内，但功能上属于本项目链路）

### reusable（可复用方法 / 模式）
- `prepare_studio_signal6_upload.py` — 任意 signal6 CSV → studio 标准 6 列 + 北京 bbox 过滤 + 时间归一，是 studio 上传链路的通用前置器
- `start_sim_signal_visualization.py` — 复用 `web/review_server.py` 的「带批次根目录的可切换可视化」启动脚本
- `prepare_sim_signal_visualization_batch.py` — 通用：把 GPS / signal / 基站三图层组装成 studio 批次（轨迹可视化变体）
- `cellular_quality_build_preview_batch.py` — 通用：依据 `configs/review_preview_batches/*.json` 生成固定 UID×天数预览批次（README 示例链路）

### task-bound（绑定具体任务 / 一次性）
- `cellular_quality_local_review_loop.py`、`cellular_quality_rerun_local_raw_to_review.py`、`cellular_quality_sync_remote_results.py`、`export_cellular_review_evidence.py`、`export_cellular_review_map_segment_report.py` — 都绑定 `cellular_quality_review_round1` 一次性流程
- `research_arena_s02_make_competitor_studio_batches.py`、`research_arena_s02_make_smoke_studio_batch.py` — 绑定 S02-01 task01 制 studio 批次的一次性脚手架
- `research_arena_s02_01_signal6_v311_submission.py` — 绑定 S02-01 提交，但里面 `(path / "trajectory_annotation_studio").is_dir()` 走的就是本项目链路
- `research_arena_s02_02_task02_*`（共 11 个：`compact_preview_pack` / `export_preview_consumer` / `topcard_preview_subset` / `reviewer_decision_sheet` / `reviewer_handoff_packet` / `reviewer_verdict_capture` / `reviewer_signoff_demo` / `reviewer_final_handoff` / `reviewer_final_override_demo` / `reviewed_submission_skeleton`，外加 `delivery_writeback_demo`） — 都绑定 task02 reviewer 闭环的一次性脚手架，但承载的「reviewer decision / handoff / final override」语义可以反哺 studio 的 reviewer namespace 设计

> 全仓库整治阶段建议：reusable 4 个搬到 `trajectory_annotation_studio/scripts/` 或建一个 `scripts/studio_helpers/`；task-bound 留原位但在全局 registry 标 `studio-link`。

## 已知风险 / 待办
- 大 OCI 镜像 tar（2.5 G）仍在仓库根，污染 `git status`、IDE 索引、备份；待用户拍板搬迁去向（候选 A / B 见下方决策点）
- `_backup_web_20260410_222758/` 与 `_backup_new_stack_20260410_223335/` 是 4-10 备份的旧架构，已是只读归档；后续可考虑搬出仓外 archive
- `data/` 下有指向真实数据的 symlink（`result -> project_data/...`、`review -> data/batches/...`），换机后可能断链；与 `start_review_studio.py` 的默认 `--batches-root` 冲突，使用前需要确认
- `web/` 与 `scripts/` 各自有 `__pycache__`（已清，但运行单测后会重建，正常现象）；`.runtime/` 与 `.runtime_local_studio_8016.log` 也是本机运行残留，已在 `.gitignore`
- `delivery_out/trajectory_annotation_studio_min_bundle_20260424/` 体量 823 M，是当前 Arena 二期对外交付的 ground truth；下一次 patch / 全量发布时应固化命名（`min_bundle_20260424` → `min_bundle_<下一日期>`）

## 不再活跃 / 归档建议
- `_backup_web_20260410_222758/`、`_backup_new_stack_20260410_223335/` — 只读归档，不再演进
- `web/admin_upload.html` — 已被 `web/upload_center.html` + `web/app/features/studio_admin/` 取代，但仍保留兼容入口；下一轮如能确认无依赖可下线
- `data/` 内 symlink 与 `tmp_v311_probe/`、`sample_uploads/` 都是本机调试残留，不属代码事实源

## 待用户拍板的开放决策点
1. **大 OCI 镜像 tar 去向**：A）`mv trajectory_annotation_studio_offline_image_linux_amd64.tar delivery_out/studio/images/`（保持仓内、便于和 patches/min_bundle 同体系归档，但仓库目录会拖到 ~3 G）；B）外置存储（NAS / 蓝奏 / 内网共享），仓内只留 SHA256 + 下载说明（强烈推荐 B，配合 `delivery_out/studio/images/IMAGE_MANIFEST.md` 写清来源）。
2. **`delivery_out/trajectory_annotation_studio_min_bundle_20260424{,.tar.gz}` 是否同步搬到 `delivery_out/studio/bundles/20260424/`**：保持当前位置 vs. 与 `patches/`、`images/` 在同一 `delivery_out/studio/` 下统一管理；倾向后者以便后续多日期批次。
3. **根 `scripts/` 中 4 个 reusable 脚本是否搬入 `trajectory_annotation_studio/scripts/`（或新建 `trajectory_annotation_studio/scripts/studio_helpers/`）**：搬入更内聚但会破坏现有调用 `cd repo && python3 scripts/...` 的肌肉记忆，需要权衡（建议 Round 2 与全仓库 registry 一起决定）。
