# trajectory_annotation_studio docs

这里是 `trajectory_annotation_studio` 的文档根目录。现在的阅读入口不再按 `01`、`02`、`03` 这样的数字顺序平铺，而是先按工作类别进入，再回到具体编号文档。

## 首读入口

- [../CURRENT.md](../CURRENT.md) - 当前事实源、活跃工作、风险和开放决策点。
- [INDEX.md](INDEX.md) - 一级分类索引，按产品、前端 GUI、后端、CLI、Agent 实验、部署和治理组织。
- [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) - 文档维护机制，后续 agent 新增或修改文档前必须读。
- [../AGENTS.md](../AGENTS.md) - agent 启动包和执行契约。

## 分类入口

- [快速入口与当前状态](INDEX.md#快速入口与当前状态)
- [产品需求与路线](INDEX.md#产品需求与路线)
- [开发：前端 GUI](INDEX.md#开发前端-gui)
- [开发：后端 / 存储 / 批次合同](INDEX.md#开发后端--存储--批次合同)
- [开发：CLI / Agent-native](INDEX.md#开发cli--agent-native)
- [Agent 实验与渐进记忆](INDEX.md#agent-实验与渐进记忆)
- [测试 / 验证](INDEX.md#测试--验证)
- [部署 / 运维 / 交付](INDEX.md#部署--运维--交付)
- [治理与协作](INDEX.md#治理与协作)
- [示例 / 模板 / 适配器](INDEX.md#示例--模板--适配器)

## 维护原则

- 编号文件名保留，用作稳定引用，不再代表主要阅读顺序。
- 新增文档必须登记到 [INDEX.md](INDEX.md) 的一个主分类。
- 影响当前行为、命令、合同或目录结构的改动，必须同步更新 [../CURRENT.md](../CURRENT.md) 或对应合同文档。
- 过程报告默认放 `reports/`，从索引引用；不要让报告替代当前合同。
