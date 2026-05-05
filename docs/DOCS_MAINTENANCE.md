# 文档维护机制

这份文档是后续 human / agent 修改文档库时的执行契约。目标不是把所有内容搬到一个大文档里，而是让入口、分类、事实源和验证动作稳定下来。

## 文档事实层级

- `README.md`：仓库入口，放项目定位、运行方式和最短文档入口。
- `CURRENT.md`：少数活文档之一，记录当前事实、活跃工作、已知风险和开放决策点。
- `docs/README.md`：文档库根入口，只回答“从哪里开始读”。
- `docs/INDEX.md`：一级分类索引，按工作语义组织文档。
- `docs/DOCS_MAINTENANCE.md`：文档维护规则和 agent 启动契约。
- `AGENTS.md`：根目录 agent 执行契约，只放短规则和必读包。
- `docs/NN-*.md`：主题文档、规格、报告和阶段记录；编号保留用于稳定引用，不再作为主要阅读顺序。
- `web/README.md`、`tests/*.md`：本地 GUI / server 使用说明和功能级测试用例；从索引引用，但不替代实现测试。
- `reports/*.md`：实验 / agent 运行报告，可被索引引用，但默认不是产品合同或当前事实源。

## 分类规则

- 每个新文档必须有一个主分类，并登记到 `docs/INDEX.md`。
- 如果一个文档跨分类，只在主分类下完整登记；其他分类可用“另见”或短引用，避免重复扩散。
- 保留已有编号文件名，除非用户明确要求迁移；迁移时必须留下重定向说明或更新全部引用。
- 新增日期型报告应说明是否冻结；如果它改变当前行为，必须同步更新 `CURRENT.md`。
- 合同、接口、命令或目录结构发生变化时，只写报告不算完成，必须同步更新对应合同文档和示例。

## 常见变更对应更新

- 改前端 GUI：更新 `docs/INDEX.md` 的“开发：前端 GUI”，必要时更新 `docs/22-*`、`docs/23-*`、`docs/28-*` 和 UI contract 测试说明。
- 改后端 / 存储 / 批次合同：更新 `docs/05-*`、`docs/06-*`、`docs/08-*`、`docs/09-*`、`docs/19-*` 或 `docs/25-*` / `docs/26-*` 中对应合同。
- 改 CLI / agent-native 能力：更新 `docs/29-*`、`docs/30-*`、`docs/32-*`，若涉及 agent review 记忆则先更新 `docs/33-*`。
- 做 agent 实验报告：放在 `reports/` 或对应 `docs/31-*` / `docs/33-*`，并从 `docs/INDEX.md` 的“Agent 实验与渐进记忆”登记。
- 改 GUI smoke、contract test 或功能测试用例：更新 `web/README.md`、`tests/*.md` 或对应 `web/test_*.py` / `scripts/tests/test_*.py`，并从 `docs/INDEX.md` 的“测试 / 验证”登记。
- 改部署 / 离线交付：更新 `docs/10-*` 到 `docs/18-*`、`docs/24-*` 或 `deploy/docker/README.offline.md`。
- 改协作、分支、数据边界或发布流程：更新 `CONTRIBUTING.md`、`docs/03-*`、`docs/07-*`、`docs/20-*` 和本文件。
- 新增 adapter：更新 `adapters/README.md`、新增 adapter 自己的 `README.md`，并在 `docs/INDEX.md` 的“示例 / 模板 / 适配器”登记。

## Agent 启动包

后续 agent 进入本仓做非平凡改动时，先读：

```text
README.md
CURRENT.md
docs/README.md
docs/INDEX.md
docs/DOCS_MAINTENANCE.md
AGENTS.md
```

如果任务是 agent review、CLI 标注或地图辅助标注，再优先读：

```text
docs/33-agent-review-progressive-memory.md
docs/29-agent-native-cli.md
docs/30-agent-native-cli-progress-report.md
docs/31-agent-map-cli-review-report.md
docs/32-studio-cli-development-plan.md
```

## Agent 修改规则

- 不要把数字编号当成阅读顺序；先按 `docs/INDEX.md` 找分类。
- 不要新增孤立文档；新增后必须登记到索引。
- 不要把运行日志、一次性命令输出、真实数据路径写成长期合同。
- 不要用报告替代合同；报告可以记录过程，合同文档要描述当前可执行约定。
- 修改代码边界时必须同步修改文档边界；如果暂时不能改文档，要在 closeout 中明确指出缺口。
- 修改 `README.md`、`CURRENT.md`、`docs/README.md`、`docs/INDEX.md`、`docs/DOCS_MAINTENANCE.md`、`AGENTS.md` 时，要把它们当成同一套入口系统检查一致性。

## 提交前检查

至少运行一轮引用检查：

```bash
python3 scripts/check_docs_entrypoints.py
```

这个脚本会同时检查：

- `README.md`、`CONTRIBUTING.md`、`CURRENT.md`、`AGENTS.md`、`docs/README.md`、`docs/INDEX.md`、`docs/DOCS_MAINTENANCE.md` 这些入口文档是否都存在
- 上述入口文档里的本地 Markdown 链接是否都能解析到真实文件
- `docs/*.md`（去掉入口文件）、`tests/*.md`、`web/README.md`、`deploy/docker/README.offline.md`、`adapters/README.md` 与各 adapter `README.md` 是否都已经登记到 `docs/INDEX.md`

如果修改了 `scripts/check_docs_entrypoints.py` 本身，再补跑：

```bash
python3 -m unittest scripts.tests.test_check_docs_entrypoints
```

代码行为改动仍然要跑对应单测或 smoke；文档检查不能代替功能验证。
