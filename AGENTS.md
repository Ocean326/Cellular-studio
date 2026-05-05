# Agent Contract

本文件是后续 agent 进入 `trajectory_annotation_studio` 时的短启动契约。详细文档维护规则在 [docs/DOCS_MAINTENANCE.md](docs/DOCS_MAINTENANCE.md)。

## 必读启动包

非平凡改动前先读：

- [README.md](README.md)
- [CURRENT.md](CURRENT.md)
- [docs/README.md](docs/README.md)
- [docs/INDEX.md](docs/INDEX.md)
- [docs/DOCS_MAINTENANCE.md](docs/DOCS_MAINTENANCE.md)

Agent review、CLI 标注、地图辅助标注相关任务，再先读：

- [docs/33-agent-review-progressive-memory.md](docs/33-agent-review-progressive-memory.md)
- [docs/29-agent-native-cli.md](docs/29-agent-native-cli.md)
- [docs/30-agent-native-cli-progress-report.md](docs/30-agent-native-cli-progress-report.md)
- [docs/31-agent-map-cli-review-report.md](docs/31-agent-map-cli-review-report.md)
- [docs/32-studio-cli-development-plan.md](docs/32-studio-cli-development-plan.md)

## 执行边界

- 保持 `Git` 管代码和文档、真实数据留在仓外或服务器的边界。
- 新数据源优先走 `adapters/`，不要直接把个人数据分支写进核心 `web/` 或 `review_server.py`。
- 文档不再按数字平铺检索；先从 [docs/INDEX.md](docs/INDEX.md) 的分类进入。
- 新增或修改文档时，同步维护 [docs/INDEX.md](docs/INDEX.md)。
- 改当前行为、命令、合同、目录结构或运行边界时，同步更新 [CURRENT.md](CURRENT.md) 和对应合同文档。
- 报告可以记录过程，但不能替代当前事实源或合同文档。

## 验证

- 文档-only 改动至少跑 `python3 scripts/check_docs_entrypoints.py`，检查入口引用、索引覆盖和新增链接是否存在。
- 代码行为改动必须跑对应单测、smoke 或 contract test。
- closeout 必须说明改了什么、怎么验证、还有什么风险。
