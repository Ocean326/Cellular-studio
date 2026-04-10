# trajectory_annotation_studio

`trajectory_annotation_studio` 是 `Cellular-projects` 内用于轨迹审阅、整轨审核、分段标注与标注资产导出的独立子项目。

它的定位不是替代 `cellular_quality`，而是站在 `cellular_quality` 之上，承接以下工作：

- 读取 `cellular_quality` 产出的 `raw/snap/od/fmm/line` 结果
- 支持按批次 (`batch`) 管理审阅任务
- 支持整轨 `accept / reject / skip`
- 支持 `accept` 后的二级标签与分段标签
- 支持多天长轨迹 (`multi-day long track`) 的时间窗口审阅
- 支持 organizer 任意时刻导出已审核样本

## 当前状态

本仓当前是规划与落仓阶段，已经固定：

- 子项目名称与仓库边界
- 文档目录
- v1 需求范围
- 分阶段开发计划
- 本地 Git / worktree 协作规范

## 目录

- `docs/`
  产品需求、开发计划、协作规范
- `src/`
  后续前后端与数据适配代码
- `configs/`
  后续项目配置模板

## 与 `cellular_quality` 的关系

- `cellular_quality` 仍是上游算法与结果生成源
- `trajectory_annotation_studio` 负责“看、审、标、导”
- 两者短期在同一工作区内协同，后续可按需要继续解耦

## 首发目标

v1 先解决四件事：

1. 同一人跨多天、任意时间窗口的轨迹审阅
2. 整轨审核 + `accept` 后二级自定义标签
3. 时间轴驱动的分段标注
4. 可持续协作的独立仓库与 `git worktree` 工作流

## 文档入口

- [docs/README.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/README.md)

