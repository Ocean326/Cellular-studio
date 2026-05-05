# Agent-Native CLI 化进展汇报

更新时间：2026-05-03

## 先回答

当前标注平台的 CLI 化已经进入「第一版可用」状态，不只是方案草稿。已经落地的核心是 `Agent-Native CLI`（面向 agent / 自动化的命令行入口）：它不替代 GUI，也不另建一套 review truth，而是通过现有 `review_server` 的 HTTP/JSON contract 读取批次、样本、review、timeline annotation、aggregate 和 export。

一句话说：GUI 继续负责人审和可视化理解，CLI 负责让 agent 能稳定地拿上下文、写判断、导出结果、做开发期 smoke。

## 这条 CLI 化到底是什么

它不是把前端 DOM 自动化一遍，而是在现有服务端事实源外面包一层 agent-friendly 的命令面：

- `web/review_server.py` 仍是服务端 API 与批次状态入口。
- `web/review_lib.py` 仍负责 review/timeline/track edit 等持久化语义。
- `scripts/studio_agent_client.py` 是标准库 HTTP client，封装 server API。
- `scripts/studio_agent_cli.py` 是命令树入口，提供给人、agent、自动化脚本使用。
- `pyproject.toml` 注册了安装后的 console script：`studio-agent`。

这个边界是健康的：CLI 化没有把 GUI 的可视化复杂度搬走，也没有发明第二套 review 存储；它做的是把已有事实源变成 agent 可读写、可测试、可脚本化的接口。

## 已经实际落实了什么

### 1. 命令树已经成型

当前 CLI 覆盖这些命令面：

- `health`
- `batch list/show`
- `sample list/inspect/materialize`
- `reviewer start/list`
- `review get/submit`
- `timeline get/put`
- `aggregate uid/export`
- `bundle export`
- `dev roundtrip`

全局参数包括：

- `--base-url`
- `--batch`
- `--timeout`
- `--json`

其中 `sample inspect` 是最 agent-native 的入口：它可以一次性返回样本上下文、预览 CSV、review reference files、review aggregate、timeline aggregate，让 agent 不需要先理解 GUI 页面结构。

### 2. HTTP client 已经独立出来

`scripts/studio_agent_client.py` 已经把命令解析和网络请求分开，主要能力包括：

- 批次 health/list 和 batch-data 拉取。
- 读取 `manifest.json` 并列出样本。
- 样本上下文 inspect/materialize。
- reviewer session 创建和 reviewer list。
- review 读取、提交、聚合。
- timeline annotation 读取、提交、聚合。
- review aggregate export。
- reviewer bundle export。

这意味着后续不一定只能走命令行；别的 agent worker 或 Python 自动化也能直接复用 client。

### 3. server API 基本对齐

`web/review_server.py` 中已经有与 client 对齐的主要端点：

- `GET /api/health`
- `GET /api/batches`
- `GET /api/reviewers`
- `POST /api/reviewers/session`
- `GET/POST /api/reviews`
- `GET /api/reviews/aggregate`
- `GET/POST /api/timeline-annotations`
- `GET /api/timeline-annotations/aggregate`
- `POST /api/export/review-aggregate`
- `POST /api/export/reviewer-bundle`
- `GET /batch-data/<batch>/...`

另外，服务端已经有 `GET/POST /api/track-edits`，但 CLI 还没有单独封装这一块。

### 4. README / CURRENT / 专门设计文档已经登记

已有文档入口：

- `README.md`：新增 `Agent-Native CLI` 使用说明。
- `CURRENT.md`：把 `studio_agent_client` 和 `studio_agent_cli` 登记为当前活跃能力。
- `docs/29-agent-native-cli.md`：记录目标、命令面、推荐用法、边界和测试命令。

这说明 CLI 化已经进入项目显式合同，不是隐藏脚本。

### 5. 测试已覆盖第一版关键路径

`scripts/tests/test_studio_agent_cli.py` 会启动临时 `ThreadingHTTPServer` + `ReviewRequestHandler`，走真实 CLI main 函数，覆盖：

- `sample list --review-status`
- `sample inspect`
- `sample materialize`
- `reviewer start`
- `review submit`
- `dev roundtrip`
- `--with-segment` 写 timeline segment
- aggregate 回读

这类测试比只测 argparse 更有价值，因为它验证的是 CLI -> client -> server -> review_lib 的实际链路。

## 本轮验证结果

本轮在本地跑过这些检查：

```bash
python3 scripts/studio_agent_cli.py --help
python3 scripts/studio_agent_cli.py sample --help
python3 scripts/studio_agent_cli.py dev --help
```

结果：命令树可正常展开。

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m trajectory_annotation_studio.scripts.studio_agent_cli --help
```

结果：模块入口可正常展开。

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m unittest \
  trajectory_annotation_studio.scripts.tests.test_studio_agent_cli \
  trajectory_annotation_studio.web.test_review_server \
  trajectory_annotation_studio.web.test_review_lib
```

结果：`Ran 57 tests ... OK`。

```bash
cd /Users/ocean/Documents/Playground/Cellular-projects
python3 -m unittest \
  trajectory_annotation_studio.scripts.tests.test_studio_agent_cli \
  trajectory_annotation_studio.web.test_review_server \
  trajectory_annotation_studio.web.test_review_lib \
  trajectory_annotation_studio.scripts.tests.test_server_batch_tools \
  trajectory_annotation_studio.scripts.tests.test_adapter_template
```

结果：`Ran 65 tests ... OK`。

```bash
git diff --check
```

结果：无输出，未发现 whitespace error。

## Cursor 子代理复核

本轮按 `$subagent-cursor` 走了只读 Cursor subagent 复核：

- model：`composer-2-fast`
- mode：`plan`
- permission：`safe`
- result：success

当前 `cursor-agent models` 可见：

- `auto`
- `composer-2-fast`
- `composer-2`
- `composer-1.5`
- `grok-4-20`
- `grok-4-20-thinking`
- `kimi-k2.5`

子代理结论是 `partial`：核心 CLI 已落地，但还存在工程边界，尤其是样本队列性能、`track_edits` CLI 封装、提交前回归命令登记。

## 还没完成 / 风险

### 1. `sample list --review-status` 已能用，但不是大规模队列编排

现在 `studio_agent_client.list_samples` 在需要按 review 状态或 reviewer 过滤时，会对每个 UID 调用一次 `review_aggregate`。这在小批次上可以接受，但大批量 agent 扫队列会变成 N+1 HTTP 模式。

更准确的状态是：

- 已实现 reviewer-aware 的样本过滤。
- 还没有高效的批量 aggregate snapshot / queue API。

`docs/29-agent-native-cli.md` 里前文和边界段落有一点口径不一致：前文说 `sample list --review-status` 已支持，边界又说大规模队列编排还没有。实际应保留这两个层次：功能已有，规模化队列 API 未有。

### 2. `track_edits` 服务端有，CLI 还没包

服务端已经支持：

- `GET /api/track-edits`
- `POST /api/track-edits`

但当前 CLI 命令树还没有 `track-edits get/put` 或类似入口。所以 CLI 已覆盖 review/timeline/export 主线，但还没有覆盖轨迹点级编辑链路。

### 3. CLI 目前适合 agent smoke / 弱监督闭环，不适合替代 GUI 精细几何判断

复杂可视化判断、地图层对比、精细 track patch，仍然应该保留在 GUI。CLI 的强项是结构化读写和批处理，不是视觉审阅。

### 4. 远端多人协作仍依赖 server 当前权限边界

CLI 继承现有 HTTP server 的权限模型，没有额外发明鉴权层。远端部署时仍需要靠端口暴露、网络边界、reviewer namespace 和运行约束保证安全。

### 5. 工作树尚未收敛到提交状态

当前工作树包含大量已修改和未跟踪文件，CLI 相关文件也还在未跟踪/未提交集合里。也就是说，从工程事实上它已经落地，但从版本治理上还没完成最终收口。

## 下一步建议

优先做一个小而关键的增量：补一个批量样本状态 API，让 server 一次返回每个 UID 的 review 摘要，然后让 `sample list --review-status` 走这个快照，而不是每个 UID 单独打 aggregate。

这个增量能直接提升 CLI 作为 agent 队列入口的可信度。完成后再做两件小收口：

- 把 `track_edits get/put` 纳入 CLI 命令树。
- 把 `test_studio_agent_cli` 写进 README 的提交前自检命令。

## 结论

这次 CLI 化的主线已经立起来了：入口、client、server contract、文档、测试都具备。它现在最适合承担 agent/native review worker 的基础入口和开发期 smoke lane。

更谨慎的判断是：它不是“完成全部平台 CLI 化”，而是“完成第一版 agent-native review CLI，并暴露出下一阶段需要补的队列性能和 track edit 收口点”。
