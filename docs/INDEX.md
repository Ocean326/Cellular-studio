# 文档一级索引

本索引按工作语义组织文档，不按编号顺序阅读。编号文件名暂时保留，避免打断历史引用、issue、会话记忆和既有链接。

## 怎么读

- 想快速恢复项目状态：先读[当前状态](../CURRENT.md)，再读[文档根入口](README.md)。
- 想找某类资料：直接从下面的一级分类进入。
- 想新增或改文档：先读[文档维护机制](DOCS_MAINTENANCE.md)，再决定文档归类。
- 想做 agent review / CLI 标注实验：先读[Agent Review 渐进式加载记忆](33-agent-review-progressive-memory.md)，再回看 `29-32`。

## 快速入口与当前状态

- [../README.md](../README.md) - 仓库定位、运行方式、常用入口。
- [../CURRENT.md](../CURRENT.md) - 当前事实源、活跃工作、风险和开放决策点。
- [../CONTRIBUTING.md](../CONTRIBUTING.md) - 协作边界、提交前自查与验证基线。
- [README.md](README.md) - 文档库入口和维护指针。
- [04-当前落成情况.md](04-当前落成情况.md) - 已落成能力、真实写回位置与未完成边界。
- [16-快速接入指南.md](16-快速接入指南.md) - 接入者最小必读说明。

## 产品需求与路线

- [01-需求文档.md](01-需求文档.md) - 独立标注工具的需求背景与 v1 目标。
- [02-开发计划.md](02-开发计划.md) - 分阶段开发计划、接口与验收标准。
- [21-用户自助上传与批次产品化升级规划.md](21-用户自助上传与批次产品化升级规划.md) - 自助上传、批次管理和产品化边界。
- [27-长期可维护性整改与轨迹标注平台升级总方案.md](27-长期可维护性整改与轨迹标注平台升级总方案.md) - 长期可维护性、架构边界和升级路线。
- [28-轨迹编辑模式与严格分段导出技术规格.md](28-轨迹编辑模式与严格分段导出技术规格.md) - 轨迹编辑模式、严格分段语义与导出规格。

## 开发：前端 GUI

- [22-index前端模块化重构方案.md](22-index前端模块化重构方案.md) - `index.html` 到 `web/app/* + web/styles/*` 的模块化方案。
- [23-index前端重构落地计划.md](23-index前端重构落地计划.md) - 前端模块化重构的阶段、顺序和验证面。
- [24-20260420小版本更新与179重部署说明.md](24-20260420小版本更新与179重部署说明.md) - 前端、上传、批次合同和 179 重部署兼容记录。
- [28-轨迹编辑模式与严格分段导出技术规格.md](28-轨迹编辑模式与严格分段导出技术规格.md) - GUI 轨迹编辑和导出工作区规格。

## 开发：后端 / 存储 / 批次合同

- [05-组内共享部署与数据接入规范.md](05-组内共享部署与数据接入规范.md) - 共享部署目录、批次合同、输入格式与输出位置。
- [06-后台逻辑与存储说明.md](06-后台逻辑与存储说明.md) - review、reviewer namespace、timeline annotation 和筛选逻辑。
- [08-reviewer-命名空间与多人标注汇总设计.md](08-reviewer-命名空间与多人标注汇总设计.md) - reviewer session、多人汇总与导出设计。
- [09-reviewer-命名空间开发与验证计划.md](09-reviewer-命名空间开发与验证计划.md) - reviewer namespace 实施、验证与回滚。
- [19-异构多图层轨迹接入架构与Arena-V15适配.md](19-异构多图层轨迹接入架构与Arena-V15适配.md) - manifest 驱动的多图层合同与 Arena V1.5 适配。
- [25-分段标签Mock数据格式说明.md](25-分段标签Mock数据格式说明.md) - 分段标签 mock 数据、示例和校验规则。
- [26-分段标签数据接口说明-对外版.md](26-分段标签数据接口说明-对外版.md) - 对外版分段标签数据接口。

## 开发：CLI / Agent-native

- [29-agent-native-cli.md](29-agent-native-cli.md) - 与 GUI 并行的 agent-friendly CLI 入口和命令树。
- [30-agent-native-cli-progress-report.md](30-agent-native-cli-progress-report.md) - CLI 化进展、验证结果和风险。
- [32-studio-cli-development-plan.md](32-studio-cli-development-plan.md) - Studio CLI 的后续开发计划、worker 切片和集成规则。

## Agent 实验与渐进记忆

- [33-agent-review-progressive-memory.md](33-agent-review-progressive-memory.md) - agent review 会话的优先启动记忆。
- [31-agent-map-cli-review-report.md](31-agent-map-cli-review-report.md) - CLI 与地图辅助标注试验汇报。
- [../reports/studio_cli_system_report_20260503.md](../reports/studio_cli_system_report_20260503.md) - Studio CLI 系统进展与开发计划报告。
- [../reports/studio_cli_10_track_annotation_report_20260503.md](../reports/studio_cli_10_track_annotation_report_20260503.md) - 10 条轨迹 CLI 测试标注报告。
- [../reports/studio_cli_multimode_labeling_report_20260506.md](../reports/studio_cli_multimode_labeling_report_20260506.md) - 六类出行状态 CLI 候选发现、Cursor 审计与 reviewer 写入结果。

## 测试 / 验证

- [../web/README.md](../web/README.md) - review server、本地页面启动、GUI 功能说明和最小前端 smoke。
- [../tests/studio-management-upload-test-cases.md](../tests/studio-management-upload-test-cases.md) - Studio 管理上传模块测试用例。
- [../tests/date-window-quick-segment-test-cases.md](../tests/date-window-quick-segment-test-cases.md) - 日期窗口固定间隔与整段快标测试用例。
- [../tests/trajectory-edit-export-layout-test-cases.md](../tests/trajectory-edit-export-layout-test-cases.md) - 轨迹编辑、严格分段导出与工作区布局测试用例。

## 部署 / 运维 / 交付

- [10-179服务器共享标注与开放协作方案.md](10-179服务器共享标注与开放协作方案.md) - 179 共享标注、GitHub 协作、上传接入和权限边界。
- [11-179服务器运行、权限与批次流转手册.md](11-179服务器运行、权限与批次流转手册.md) - 179 目录、权限、批次发布、上传和导出流程。
- [12-179部署与共享标注实施计划.md](12-179部署与共享标注实施计划.md) - Phase 1-4 的可执行交付计划。
- [13-179方案-critique-refine-memo.md](13-179方案-critique-refine-memo.md) - 179 方案 critique-refine 记录。
- [14-179部署指南.md](14-179部署指南.md) - 179 首次部署步骤。
- [15-179详细操作手册.md](15-179详细操作手册.md) - operator 日常运行、首轮批次发布和排障。
- [17-179首轮真实试运行记录.md](17-179首轮真实试运行记录.md) - 真实 179 首轮试运行记录。
- [18-179试运行复盘与第二轮优化建议.md](18-179试运行复盘与第二轮优化建议.md) - 第二轮优化建议和执行清单。
- [24-20260420小版本更新与179重部署说明.md](24-20260420小版本更新与179重部署说明.md) - 重部署前兼容性与验证结论。
- [../deploy/docker/README.offline.md](../deploy/docker/README.offline.md) - 离线 / 内网 Docker 交付说明。

## 治理与协作

- [03-协作与仓库规范.md](03-协作与仓库规范.md) - Git、worktree、分支与批次命名方式。
- [07-仓库治理与 GitHub-服务器协作.md](07-仓库治理与%20GitHub-服务器协作.md) - 代码仓、服务器数据仓、权限和发布流程。
- [20-阶段性仓库代码架构体检与治理升级方案.md](20-阶段性仓库代码架构体检与治理升级方案.md) - 仓库健康、架构风险、治理机制与升级路线。
- [DOCS_MAINTENANCE.md](DOCS_MAINTENANCE.md) - 文档库维护机制和后续 agent 规则。
- [../AGENTS.md](../AGENTS.md) - agent 启动包和本仓执行契约。

## 示例 / 模板 / 适配器

- [examples/batch_meta.example.json](examples/batch_meta.example.json) - 批次元信息示例。
- [examples/manifest.chain2.example.json](examples/manifest.chain2.example.json) - chain2 manifest 示例。
- [examples/manifest.trajectory_layers.example.json](examples/manifest.trajectory_layers.example.json) - 多图层轨迹 manifest 示例。
- [examples/manifest.sim_signal.example.json](examples/manifest.sim_signal.example.json) - sim signal manifest 示例。
- [examples/1001_signal.mock.csv](examples/1001_signal.mock.csv) - 分段标签 signal mock CSV。
- [examples/1001_gps.mock.csv](examples/1001_gps.mock.csv) - 分段标签 GPS mock CSV。
- [../adapters/README.md](../adapters/README.md) - adapter 总入口。
- [../adapters/template/README.md](../adapters/template/README.md) - 新数据源 adapter 模板。
- [../adapters/arena_task02_travel_mode/README.md](../adapters/arena_task02_travel_mode/README.md) - S02-02 出行语义多段标签 adapter。
- [../adapters/arena_task03_occupation/README.md](../adapters/arena_task03_occupation/README.md) - S02-03 职业身份 accept/reject adapter。
