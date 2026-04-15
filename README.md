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
  各类数据源或个人数据接入适配器约定

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

在项目根目录执行：

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio
python3 web/review_server.py --port 8016
```

打开：

- `http://127.0.0.1:8016/web/index.html`

首次进入 reviewer 模式时，页面会要求输入 `姓名/昵称`，作为当前批次里的标注来源。
这是一层轻量 `reviewer session`，用于命名空间隔离和多人汇总，不是权限鉴权。

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

- [docs/README.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/README.md)
  总索引
- [docs/04-当前落成情况.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/04-%E5%BD%93%E5%89%8D%E8%90%BD%E6%88%90%E6%83%85%E5%86%B5.md)
  当前已经落成了什么、哪些边界还没做
- [docs/05-组内共享部署与数据接入规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/05-%E7%BB%84%E5%86%85%E5%85%B1%E4%BA%AB%E9%83%A8%E7%BD%B2%E4%B8%8E%E6%95%B0%E6%8D%AE%E6%8E%A5%E5%85%A5%E8%A7%84%E8%8C%83.md)
  批次目录、输入格式、输出位置
- [docs/06-后台逻辑与存储说明.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/06-%E5%90%8E%E5%8F%B0%E9%80%BB%E8%BE%91%E4%B8%8E%E5%AD%98%E5%82%A8%E8%AF%B4%E6%98%8E.md)
  review / reviewer namespace / timeline annotation / 左侧筛选逻辑
- [docs/07-仓库治理与 GitHub-服务器协作.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/07-%E4%BB%93%E5%BA%93%E6%B2%BB%E7%90%86%E4%B8%8E%20GitHub-%E6%9C%8D%E5%8A%A1%E5%99%A8%E5%8D%8F%E4%BD%9C.md)
  代码仓、服务器、权限、发布流程
- [docs/08-reviewer-命名空间与多人标注汇总设计.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/08-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E4%B8%8E%E5%A4%9A%E4%BA%BA%E6%A0%87%E6%B3%A8%E6%B1%87%E6%80%BB%E8%AE%BE%E8%AE%A1.md)
  reviewer session、多人汇总与导出设计
- [docs/09-reviewer-命名空间开发与验证计划.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/09-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E5%BC%80%E5%8F%91%E4%B8%8E%E9%AA%8C%E8%AF%81%E8%AE%A1%E5%88%92.md)
  reviewer namespace 功能实施与验证计划
- [docs/14-179部署指南.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/14-179%E9%83%A8%E7%BD%B2%E6%8C%87%E5%8D%97.md)
  面向 179 的首次部署步骤
- [docs/15-179详细操作手册.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/15-179%E8%AF%A6%E7%BB%86%E6%93%8D%E4%BD%9C%E6%89%8B%E5%86%8C.md)
  operator 日常运行与首轮批次发布操作
- [docs/16-快速接入指南.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/16-%E5%BF%AB%E9%80%9F%E6%8E%A5%E5%85%A5%E6%8C%87%E5%8D%97.md)
  接入者最小必读文档
- [docs/17-179首轮真实试运行记录.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/17-179%E9%A6%96%E8%BD%AE%E7%9C%9F%E5%AE%9E%E8%AF%95%E8%BF%90%E8%A1%8C%E8%AE%B0%E5%BD%95.md)
  记录真实 179 试运行中暴露的约束、已验证路径和后续优化点

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

## 当前目录取舍

为避免两套服务形态并存，原先新架构的目录已整体备份：

- `_backup_web_20260410_222758/`
- `_backup_new_stack_20260410_223335/`

其中 `_backup_new_stack_20260410_223335/` 保存了此前的：

- `src/`
- `scripts/`
- `tests/`
- `configs/`

`docs/` 与 `data/` 仍保留，方便后续继续整理需求和接入真实数据。
