# Cellular-studio

`Cellular-studio` 是面向组内共享的轨迹审阅与标注代码仓，当前主应用目录与运行入口仍叫 `trajectory_annotation_studio`。

这个仓库的长期原则已经固定：

- `GitHub` 私有仓是代码事实源
- 服务器保存真实数据、批次、审核结果与导出结果
- 接自己的数据，优先写适配器 (`adapter`)，不直接污染核心逻辑
- 仓库保持 `零数据 Git`

## 仓库定位

当前仓库主要承载：

- 标注 studio 前端与轻量服务端
- 批次接入与转换脚本
- GitHub 协作、服务器部署、数据接入文档
- 适配层约定
- reviewer 命名空间、多人标注汇总与导出

当前主目录：

- [web/](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/web)
  审阅页面、review server、review/timeline annotation 持久化逻辑
- [scripts/](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/scripts)
  批次适配、启动脚本
- [docs/](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs)
  需求、规划、治理、部署与接入文档
- [adapters/](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/adapters)
  各类数据源或个人数据接入适配器约定，内含可复制的 `template/`

## 协作模型

推荐采用：

- `GitHub 私有仓` 管代码
- `服务器 batches-root` 管真实数据与输出
- `main` 只保留可运行代码
- 个性化数据接入放进 `adapters/` 或独立转换脚本
- 线上运行目录不作为大家直接共改的开发目录

先看：

- [CONTRIBUTING.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/CONTRIBUTING.md)
- [docs/03-协作与仓库规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/03-%E5%8D%8F%E4%BD%9C%E4%B8%8E%E4%BB%93%E5%BA%93%E8%A7%84%E8%8C%83.md)
- [docs/07-仓库治理与 GitHub-服务器协作.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/07-%E4%BB%93%E5%BA%93%E6%B2%BB%E7%90%86%E4%B8%8E%20GitHub-%E6%9C%8D%E5%8A%A1%E5%99%A8%E5%8D%8F%E4%BD%9C.md)

## 运行方式

最常用有两种启动方式。

单批次 / 本地开发模式：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 web/review_server.py --port 8016
```

共享批次根模式：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 scripts/start_review_studio.py --port 8016
```

打开入口：

- `http://127.0.0.1:8016/web/index.html`

首次进入 reviewer 模式时，页面会要求输入 `姓名/昵称`，作为当前批次里的标注来源。
这是一层轻量 `reviewer session`，用于命名空间隔离和多人汇总，不是权限鉴权。

如果要做包入口 smoke 或 CI 校验，可在父目录执行：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m trajectory_annotation_studio.web.review_server --help
```

如果需要指定数据位置，可以显式传参：

```bash
python3 web/review_server.py \
  --host 127.0.0.1 \
  --port 8016 \
  --result-root ./data/result \
  --review-root ./data/review \
  --export-root ./data/review/accepted_assets
```

如果继续沿用批次目录，也可以直接指向某个批次：

```bash
python3 web/review_server.py \
  --host 127.0.0.1 \
  --port 8016 \
  --result-root ./data/batches/20260408T070420Z_v2_linefix_local_raw9995/result \
  --review-root ./data/batches/20260408T070420Z_v2_linefix_local_raw9995/review \
  --export-root ./data/batches/20260408T070420Z_v2_linefix_local_raw9995/accepted_assets
```

如果要做“服务器共享 + 多批次切换”，更推荐直接指定批次根：

```bash
python3 web/review_server.py \
  --host 0.0.0.0 \
  --port 8016 \
  --project-root /path/to/trajectory_annotation_studio \
  --batches-root /path/to/shared/batches
```

## Agent-Native CLI

仓库现在有一条与 GUI 并行的 agent-friendly CLI 入口：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m trajectory_annotation_studio.scripts.studio_agent_cli --help
```

或者在安装了 console script 之后：

```bash
studio-agent --help
```

这条入口适合：

- agent / 自动化读 `sample` 上下文
- 写 `review` / `timeline`
- 批量发现并写入 `subway / low_speed / road / stay / flight / railway` 候选分段
- 导 `aggregate` / `reviewer bundle`
- 开发期做 `dev roundtrip` smoke

快速例子：

```bash
python3 -m trajectory_annotation_studio.scripts.studio_agent_cli \
  --base-url http://127.0.0.1:8016 \
  batch list

python3 -m trajectory_annotation_studio.scripts.studio_agent_cli \
  --base-url http://127.0.0.1:8016 \
  --batch my_batch \
  sample inspect --uid 6001
```

详细设计与 ten-day 示例见：

- [docs/29-agent-native-cli.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/29-agent-native-cli.md)

后续 agent 接手时，优先从该文档的「Agent 快速上手」开始：先连同一个 `review_server`，再用独立 reviewer id 写 `review/timeline`，最后回到 GUI 的「多人标注汇总」验证可回放。

## 默认预览流程

现在推荐把 `trajectory_annotation_studio` 直接挂到共享的 `review_batches/` 根目录，而不是手动改 `result-root`。

1. 生成固定 `10 UID * 10天` 预览批次：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 scripts/cellular_quality_build_preview_batch.py
```

2. 启动 studio：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 scripts/start_review_studio.py --port 8016
```

说明：

- 第一步会在 `project_data/cellular_quality_review_round1/workspace/review_batches/` 下生成一个新的 `preview10x10` 批次。
- 第二步会让 studio 直接发现这个共享批次根，最新批次会自动成为默认批次。
- 也可以直接打开：
  `http://127.0.0.1:8016/web/index.html?batch=<batch_name>`
- 固定样本集配置在：
  [`configs/review_preview_batches/cellular_quality_preview10x10_v1.json`](/Users/ocean/Documents/Playground/Cellular-projects/configs/review_preview_batches/cellular_quality_preview10x10_v1.json)

## 文档入口

文档库现在按分类维护，不再把 `01-33` 当作主要阅读顺序。

- [CURRENT.md](CURRENT.md)
  当前事实源、活跃工作、风险和开放决策点
- [docs/README.md](docs/README.md)
  文档库根入口
- [docs/INDEX.md](docs/INDEX.md)
  一级分类索引：产品、前端 GUI、后端、CLI、Agent 实验、部署、治理和示例
- [docs/DOCS_MAINTENANCE.md](docs/DOCS_MAINTENANCE.md)
  文档维护机制，后续 agent 新增或修改文档前必须读
- [AGENTS.md](AGENTS.md)
  agent 启动包和本仓执行契约

常用快速入口：

- 接入者：看 [docs/16-快速接入指南.md](docs/16-快速接入指南.md)
- 批次 / 后端合同：看 [docs/05-组内共享部署与数据接入规范.md](docs/05-组内共享部署与数据接入规范.md) 和 [docs/06-后台逻辑与存储说明.md](docs/06-后台逻辑与存储说明.md)
- 前端 GUI 重构：看 [docs/22-index前端模块化重构方案.md](docs/22-index前端模块化重构方案.md)、[docs/23-index前端重构落地计划.md](docs/23-index前端重构落地计划.md) 和 [docs/28-轨迹编辑模式与严格分段导出技术规格.md](docs/28-轨迹编辑模式与严格分段导出技术规格.md)
- Agent CLI / 实验：先看 [docs/33-agent-review-progressive-memory.md](docs/33-agent-review-progressive-memory.md)，再看 [docs/29-agent-native-cli.md](docs/29-agent-native-cli.md)
- 测试 / 验证：看 [web/README.md](web/README.md) 和 [tests/](tests/)
- 部署与离线交付：看 [docs/14-179部署指南.md](docs/14-179部署指南.md)、[docs/15-179详细操作手册.md](docs/15-179详细操作手册.md) 和 [deploy/docker/README.offline.md](deploy/docker/README.offline.md)

## 当前 reviewer 命名空间模型

当前默认存储已经不是“全局一个 latest_reviews.json”，而是：

```text
<batch_root>/review/
  system/
    reviewer_registry.json
  reviewers/
    <reviewer_id>/
      profile.json
      reviews/
        ledger.jsonl
        latest_reviews.json
      timeline_annotations/
        ledger.jsonl
        <uid>.json
  aggregate/
    stats.json
    by_uid/
      <uid>.json
```

这意味着：

- triage 默认按“当前 reviewer”工作
- 同一条轨迹可以汇总多个 reviewer 的最新审核
- `accepted_assets` 默认按 reviewer 分目录导出

如需把旧批次的 legacy review 结构迁到 reviewer 命名空间，可使用：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 scripts/migrate_legacy_review_namespace.py --review-root /path/to/batch/review --clean-target
```

## Git 边界

会进 Git：

- `web/`
- `scripts/`
- `adapters/`
- `docs/`
- 配置模板、示例 JSON、测试代码

不会进 Git：

- `data/`
- `project_data/`
- 真实批次结果
- `review/`
- `accepted_assets/`
- 本地路径覆盖配置
- 本地备份与 scratch 目录

## 仓库健康基线

当前主干固定执行以下轻量规则：

- `.runtime/` 只放本机运行时脚本、pid 和日志，已默认忽略，不作为共享资产。
- `_backup_*` 只作为历史归档快照，只读保留，不再作为当前实现的一部分继续演进。
- `web/` 与 `scripts/` 入口同时兼容“模块运行”和“直接脚本运行”，但测试不再依赖手工 `sys.path` 兜底。
- `web/app/studio_bootstrap.js` 承担前端稳定 bootstrap 配置层，`index.html` 继续保留主交互壳体。
- `adapters/template/` 是当前默认 adapter 起点，接新数据优先复制模板而不是改核心壳体。
- 仓库最小护栏固化在 [repo-health.yml](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/.github/workflows/repo-health.yml)。

提交前建议至少跑：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 scripts/check_docs_entrypoints.py
python3 -m unittest web.test_review_lib web.test_review_server scripts.tests.test_check_docs_entrypoints scripts.tests.test_server_batch_tools scripts.tests.test_research_arena_v15_layer_adapter scripts.tests.test_adapter_template
python3 scripts/check_index_html_inline_js.py
```

## 当前目录取舍

为避免两套服务形态并存，原先新架构的目录已整体备份：

- `_backup_web_20260410_222758/`
- `_backup_new_stack_20260410_223335/`

这些目录现在视为“只读归档”，用于回溯，不再接受日常功能修改。后续若还需要做大备份，优先移到仓外或独立 archive 位置。

其中 `_backup_new_stack_20260410_223335/` 保存了此前的：

- `src/`
- `scripts/`
- `tests/`
- `configs/`

`docs/` 与 `data/` 仍保留，方便后续继续整理需求和接入真实数据。
