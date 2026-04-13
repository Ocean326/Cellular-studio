# 仓库治理与 GitHub-服务器协作

## 1. 目标

这份文档固定 `Cellular-studio` 的长期协作边界：

- 代码在哪管理
- 数据在哪管理
- 谁可以改什么
- 如何从 GitHub 代码仓发布到服务器运行环境

目标不是做复杂流程，而是避免以后出现：

- 大家直接共改线上目录
- 真实数据误进 Git
- 某个人为自己数据改坏通用逻辑
- 代码版本和运行版本说不清

## 2. 固定双层结构

本项目长期采用双层结构：

### 2.1 GitHub 私有仓

用途：

- 管代码
- 管文档
- 管模板
- 管适配器

这是代码事实源 (`source of truth`)。

### 2.2 服务器数据区

用途：

- 管真实数据
- 管批次结果
- 管 review 写回
- 管 accepted 导出

这是数据事实源。

## 3. 推荐服务器目录

推荐结构：

```text
/srv/Cellular-studio/
  app/
    trajectory_annotation_studio/     # 运行中的代码副本
  data/
    batches/                          # 真实批次与写回
  workspaces/
    <user_a>/trajectory_annotation_studio/
    <user_b>/trajectory_annotation_studio/
```

说明：

- `app/` 只承载当前运行版本
- `data/batches/` 承载真实批次目录
- `workspaces/` 是大家自己的开发副本，不是线上运行目录

## 4. 权限建议

### 4.1 `app/`

建议只有维护者可写：

- 你
- 明确授权的 1 到 2 位维护者

其他人可读，不建议直接写。

### 4.2 `data/batches/`

根据角色分层：

- organizer / reviewer：可读写
- 数据提供方：可写自己负责的批次输入区
- 普通参与者：按需要只读

### 4.3 `workspaces/`

每人只写自己的目录。

## 5. 角色分工

建议固定 4 类角色：

### 5.1 Maintainer

负责：

- 审核 PR
- 维护 `main`
- 部署到服务器 `app/`
- 冻结合同与目录规则

### 5.2 Adapter Owner

负责：

- 自己数据源的接入脚本
- `adapters/` 下对应目录
- 批次转换与 manifest 生成

### 5.3 Organizer / Reviewer

负责：

- 准备批次
- 执行审阅
- 导出 `accepted_assets`

### 5.4 Participant

负责：

- 使用既有批次
- 不直接改核心逻辑

## 6. 代码与数据边界

### 6.1 会进 GitHub 的内容

- `web/`
- `scripts/`
- `adapters/`
- `docs/`
- 测试
- 示例模板

### 6.2 不会进 GitHub 的内容

- 真实数据
- 真实批次
- review 写回结果
- accepted 导出
- 地图包
- 缓存
- 本地路径覆盖
- 个人 scratch 文件

## 7. 接自己数据的正确方式

如果某位同学需要支持自己的数据，不推荐直接改：

- `web/index.html`
- `web/review_server.py`

推荐方式是：

1. 在 `adapters/` 下建立自己的适配目录
2. 写数据转换脚本
3. 输出到统一批次格式
4. 再由 studio 直接消费

也就是说：

- 数据差异优先在适配层消化
- 核心仓只承接通用能力

## 8. 分支与提交流程

推荐流程：

1. 从 `main` 拉新分支
2. 本地开发或在个人 `workspace` 开发
3. 跑最小验证
4. 提 PR
5. maintainer 合并到 `main`
6. maintainer 部署到服务器 `app/`

推荐分支前缀：

- `feature/`
- `fix/`
- `docs/`
- `adapter/`
- `spike/`

## 9. 发布流程

推荐发布方式：

1. GitHub `main` 合并完成
2. 在服务器 `app/trajectory_annotation_studio/` 拉取最新代码
3. 重启 review server
4. 在 `data/batches/` 上继续工作

不要把“开发目录”和“线上运行目录”混成同一个目录。

## 10. 最小治理规则

固定 5 条：

1. `main` 必须保持可运行
2. 真实数据不进 Git
3. 私有路径不进 Git
4. 个性化数据差异优先进 `adapters/`
5. 影响合同的改动必须先改文档

## 11. 推荐落地顺序

如果现在开始正式接到 GitHub 和服务器，建议顺序是：

1. 先把本仓整理成可推送状态
2. 再把 GitHub 私有仓建出来并绑定 `origin`
3. 再在服务器准备 `app/`、`data/`、`workspaces/`
4. 再把当前批次迁到服务器数据区
5. 最后才开放组内协作
