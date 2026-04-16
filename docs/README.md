# trajectory_annotation_studio docs

## 文档索引

- [01-需求文档.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/01-%E9%9C%80%E6%B1%82%E6%96%87%E6%A1%A3.md)
  说明为什么要把标注工具升级为独立子项目，以及 v1 要解决哪些问题。
- [02-开发计划.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/02-%E5%BC%80%E5%8F%91%E8%AE%A1%E5%88%92.md)
  给出分阶段实施方案、接口与验收标准。
- [03-协作与仓库规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/03-%E5%8D%8F%E4%BD%9C%E4%B8%8E%E4%BB%93%E5%BA%93%E8%A7%84%E8%8C%83.md)
  约定本地 Git 仓库、`worktree`、分支与批次命名方式。
- [04-当前落成情况.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/04-%E5%BD%93%E5%89%8D%E8%90%BD%E6%88%90%E6%83%85%E5%86%B5.md)
  汇总当前已经落成的能力、真实写回位置、以及还未完成的平台化边界。
- [05-组内共享部署与数据接入规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/05-%E7%BB%84%E5%86%85%E5%85%B1%E4%BA%AB%E9%83%A8%E7%BD%B2%E4%B8%8E%E6%95%B0%E6%8D%AE%E6%8E%A5%E5%85%A5%E8%A7%84%E8%8C%83.md)
  固定组内共享时的目录结构、批次合同、CSV 接入方式与输出位置。
- [06-后台逻辑与存储说明.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/06-%E5%90%8E%E5%8F%B0%E9%80%BB%E8%BE%91%E4%B8%8E%E5%AD%98%E5%82%A8%E8%AF%B4%E6%98%8E.md)
  从现有实现角度解释自定义数据接入、标注落盘和左侧筛选逻辑。
- [07-仓库治理与 GitHub-服务器协作.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/07-%E4%BB%93%E5%BA%93%E6%B2%BB%E7%90%86%E4%B8%8E%20GitHub-%E6%9C%8D%E5%8A%A1%E5%99%A8%E5%8D%8F%E4%BD%9C.md)
  固定代码仓、服务器数据仓、权限、提交流程与发布流程。
- [08-reviewer-命名空间与多人标注汇总设计.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/08-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E4%B8%8E%E5%A4%9A%E4%BA%BA%E6%A0%87%E6%B3%A8%E6%B1%87%E6%80%BB%E8%AE%BE%E8%AE%A1.md)
  设计 reviewer session、按 reviewer 落盘、多人轨迹汇总、导出语义与兼容迁移。
- [09-reviewer-命名空间开发与验证计划.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/09-reviewer-%E5%91%BD%E5%90%8D%E7%A9%BA%E9%97%B4%E5%BC%80%E5%8F%91%E4%B8%8E%E9%AA%8C%E8%AF%81%E8%AE%A1%E5%88%92.md)
  给出 reviewer 命名空间功能的实施阶段、测试矩阵、风险与回滚策略。
- [10-179服务器共享标注与开放协作方案.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/10-179%E6%9C%8D%E5%8A%A1%E5%99%A8%E5%85%B1%E4%BA%AB%E6%A0%87%E6%B3%A8%E4%B8%8E%E5%BC%80%E6%94%BE%E5%8D%8F%E4%BD%9C%E6%96%B9%E6%A1%88.md)
  面向 179 服务器的共享标注、GitHub 协作、上传接入、导出与权限边界总体方案。
- [11-179服务器运行、权限与批次流转手册.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/11-179%E6%9C%8D%E5%8A%A1%E5%99%A8%E8%BF%90%E8%A1%8C%E3%80%81%E6%9D%83%E9%99%90%E4%B8%8E%E6%89%B9%E6%AC%A1%E6%B5%81%E8%BD%AC%E6%89%8B%E5%86%8C.md)
  偏运维和执行，说明 179 上的目录、权限、批次发布、上传和导出流程。
- [12-179部署与共享标注实施计划.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/12-179%E9%83%A8%E7%BD%B2%E4%B8%8E%E5%85%B1%E4%BA%AB%E6%A0%87%E6%B3%A8%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md)
  将 Phase 1-4 压成可执行交付计划，明确 deliverables、slice、验收与风险。
- [13-179方案-critique-refine-memo.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/13-179%E6%96%B9%E6%A1%88-critique-refine-memo.md)
  对 179 部署与共享标注方案做一轮 critique-refine，保留修正依据和未决边界。
- [14-179部署指南.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/14-179%E9%83%A8%E7%BD%B2%E6%8C%87%E5%8D%97.md)
  面向 operator 的首次部署步骤，包含目录初始化、release、systemd、nginx 和 smoke 检查。
- [15-179详细操作手册.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/15-179%E8%AF%A6%E7%BB%86%E6%93%8D%E4%BD%9C%E6%89%8B%E5%86%8C.md)
  面向 operator 的日常运行文档，覆盖首轮批次发布、incoming 处理、导出和常见排障。
- [16-快速接入指南.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/16-%E5%BF%AB%E9%80%9F%E6%8E%A5%E5%85%A5%E6%8C%87%E5%8D%97.md)
  面向接入者的最小上手说明，讲清楚要准备什么、怎么上传、如何拿回自己的标注数据。
- [17-179首轮真实试运行记录.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/17-179%E9%A6%96%E8%BD%AE%E7%9C%9F%E5%AE%9E%E8%AF%95%E8%BF%90%E8%A1%8C%E8%AE%B0%E5%BD%95.md)
  沉淀真实 179 首轮试运行的约束、通过项和后续优化点。
- [18-179试运行复盘与第二轮优化建议.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/18-179%E8%AF%95%E8%BF%90%E8%A1%8C%E5%A4%8D%E7%9B%98%E4%B8%8E%E7%AC%AC%E4%BA%8C%E8%BD%AE%E4%BC%98%E5%8C%96%E5%BB%BA%E8%AE%AE.md)
  把首轮真实执行压成可复用复盘，并明确第二轮优先级和不建议现在就做的事。
- [19-异构多图层轨迹接入架构与Arena-V15适配.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/19-%E5%BC%82%E6%9E%84%E5%A4%9A%E5%9B%BE%E5%B1%82%E8%BD%A8%E8%BF%B9%E6%8E%A5%E5%85%A5%E6%9E%B6%E6%9E%84%E4%B8%8EArena-V15%E9%80%82%E9%85%8D.md)
  说明 manifest 驱动的异构图层合同、review reference 兼容策略，以及 `research_arena` V1.5 的 GPS+tier1-4 接入方式。

## 当前定位

这里优先沉淀两类文档：

- 能指导实现和协作的文档
- 能指导部署、接入和运维的文档

后续若开始实现，可继续在本目录补充：

- 接口说明
- 数据合同
- 交互草图
- 运行手册
- 迁移记录
- 样例模板
