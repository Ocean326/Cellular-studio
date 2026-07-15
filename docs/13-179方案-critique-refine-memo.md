# 179 方案 Critique-Refine Memo

## 1. Proposal Brief

### Problem / Opportunity

需要把当前 `trajectory_annotation_studio` 从“本地/组内试用工具”推进到：

- 可部署到 `179`
- 能承载 `10天 * 10000 UID`
- GitHub 可协作
- 支持多人 reviewer 共享标注
- 支持个人导出自己的标注与原数据
- 支持上传自己的数据接入 studio

### Proposed Approach

- 采用 `GitHub 代码仓 + 179 服务器数据区` 的双层结构
- `10天 * 10000 UID` 冻结为一个 cohort，但发布成 `10 个 1000 UID shard`
- 用 `published / incoming / exports` 管共享批次、上传接入、导出
- 新增：
  - `validate/publish` 脚本
  - `reviewer bundle export`
  - Web 上传 zip 到 `incoming`

### Target User / Stakeholder

- 你：maintainer / operator / organizer
- 组内 reviewer
- 数据接入者
- 方法贡献者 / agent contributor

### Key Constraints

- 当前服务是 `stdlib + filesystem` 风格
- reviewer session 不是鉴权
- 当前锁是进程内锁，不适合多实例并发写
- 真实数据不能进 Git
- 179 当前从本机未验证直连可达

### Success Criteria

- 代码仓、批次、导出、上传边界清楚
- 能从 `incoming` 发布批次
- 能导出 reviewer bundle
- 能在 179 以单实例 + 反向代理运行

### Main Unknowns

- 179 真实网络连通与部署权限
- Lenovo -> 179 推送路径
- 首发 Web 上传的安全与体积边界

## 2. Review Stance

- `neutral`
- 偏 `evidence-first`

证据来源：

- `user-provided`
- `source-backed`
- `inference`

## 3. Round Summary

## Round 1

### Major Critiques

- `value lens`
  - strongest concern:
    - 直接把 `10天 * 10000 UID` 暴露成一个单批次，会让 reviewer 工作面和运营面都过重
  - what still holds up:
    - 冻结一个完整 cohort 是对的
  - assumption under attack:
    - “数据完整”不等于“reviewer-facing 体验也应该完整单批暴露”
  - why this matters now:
    - 一旦发布结构定错，后续批次治理会一直别扭
  - severity:
    - `high`
  - confidence:
    - `high`
  - evidence type:
    - `source-backed + inference`
  - concrete repair direction:
    - 完整 cohort 冻结，reviewer-facing 切成 `10 x 1000 shard`

- `feasibility lens`
  - strongest concern:
    - 当前 reviewer session 不是鉴权，若直接把服务暴露到 179 外网或宽内网，会误把“昵称”当身份
  - what still holds up:
    - reviewer namespace 本身是合理的
  - assumption under attack:
    - “已有 reviewer session”足以承担多人共享的身份安全
  - why this matters now:
    - 部署层设计必须先定外层安全边界
  - severity:
    - `critical`
  - confidence:
    - `high`
  - evidence type:
    - `source-backed`
  - concrete repair direction:
    - `localhost bind + nginx/caddy + auth`

### Verification Result

- 以上两点都属于首轮就必须修正的结构性问题

## Round 2

### Major Critiques

- `failure-mode lens`
  - strongest concern:
    - 若用户可直接写 `published`，批次扫描和线上可见性会失控
  - what still holds up:
    - 上传接入本身是必要能力
  - assumption under attack:
    - “上传区”和“已发布批次区”可以是同一个逻辑层
  - why this matters now:
    - 当前 `review_server.py` 会扫描 `batches-root` 的第一层目录
  - severity:
    - `critical`
  - confidence:
    - `high`
  - evidence type:
    - `source-backed`
  - concrete repair direction:
    - 把 `incoming` 放到扫描根之外，采用 `incoming -> validate -> publish`

- `feasibility lens`
  - strongest concern:
    - reviewer 导出如果只保留 `accepted_assets`，仍不足以满足“带走我的标注 + 原数据”
  - what still holds up:
    - 当前 `accepted export` 是一个好的子集能力
  - assumption under attack:
    - `accepted export` 已经等价于个人完整导出
  - why this matters now:
    - 用户明确把这条能力列为 Phase 3
  - severity:
    - `high`
  - confidence:
    - `high`
  - evidence type:
    - `user-provided + source-backed`
  - concrete repair direction:
    - 增加 `reviewer bundle export`

### Verification Result

- 方案必须显式包含：
  - 独立 `incoming`
  - 独立 `reviewer bundle export`

## Round 3

### Major Critiques

- `failure-mode lens`
  - strongest concern:
    - 计划如果默认多 worker 或多实例部署，会与当前文件锁模型冲突
  - what still holds up:
    - 单机共享服务仍然是合理首发形态
  - assumption under attack:
    - 服务器部署天然就应该多进程/多副本
  - why this matters now:
    - 这会直接影响 `systemd`、nginx 和运维说明
  - severity:
    - `high`
  - confidence:
    - `high`
  - evidence type:
    - `source-backed`
  - concrete repair direction:
    - 首发固定单实例

- `value lens`
  - strongest concern:
    - Web 上传若首发目标过重，会拖慢整个落地
  - what still holds up:
    - 做 Web 上传是对的
  - assumption under attack:
    - 首发就应该支持复杂目录级上传与自动打包
  - why this matters now:
    - 当前更需要一个能真正进站的 intake 入口
  - severity:
    - `medium`
  - confidence:
    - `high`
  - evidence type:
    - `inference`
  - concrete repair direction:
    - 首发只做 zip 上传到 `incoming`

### Verification Result

- 方案应显式去掉“首发复杂目录上传”的隐含期待

## 4. Issue Register Snapshot

- `I1`
  - issue:
    - `10k` reviewer-facing 单批次过重
  - severity:
    - `high`
  - confidence:
    - `high`
  - status:
    - `resolved`

- `I2`
  - issue:
    - reviewer session 被误当鉴权
  - severity:
    - `critical`
  - confidence:
    - `high`
  - status:
    - `resolved in plan`

- `I3`
  - issue:
    - `incoming` 与 `published` 未隔离
  - severity:
    - `critical`
  - confidence:
    - `high`
  - status:
    - `resolved`

- `I4`
  - issue:
    - 缺少个人完整导出能力
  - severity:
    - `high`
  - confidence:
    - `high`
  - status:
    - `resolved in plan`

- `I5`
  - issue:
    - 单实例/多实例边界未明确
  - severity:
    - `high`
  - confidence:
    - `high`
  - status:
    - `resolved`

## 5. Repairs Applied

- 将 `10天 * 10000 UID` 明确收敛为：
  - 一个完整 cohort
  - 十个 reviewer-facing shard

- 明确：
  - `incoming` 不在 `--batches-root` 扫描范围内
  - 只能通过 `validate -> publish` 进入共享批次

- 明确：
  - 179 首发采用 `single instance`
  - 外层由 `nginx/caddy` 承担鉴权边界

- 将导出闭环从：
  - 只有 `accepted_assets`
  - 修正为 `accepted export + reviewer bundle export`

- 将 Web 上传首发收敛为：
  - 上传 zip
  - 服务端写入 incoming
  - 基础校验与发布

## 6. Residual Risks

- 179 当前并未从本机验证可直连，真实部署仍依赖 operator 侧执行
- Lenovo -> 179 的数据同步链路尚未自动化
- Web 上传首发仍需额外安全约束：
  - 文件大小
  - 后缀
  - 路径穿越
  - 清理策略

## 7. Preserved Disagreements

- GitHub 是否要立刻完全公开
  - 当前建议仍是：先 `private + collaborators`

- Web 上传是否首发就做复杂目录打包
  - 当前建议仍是：首发只做 zip

## 8. Final Recommendation

- `proceed`

## 9. Next-Step Artifact

- `implementation plan`

## 10. Why This Pass Stops Here

停在这里的原因是：

- 结构性问题已经明确并修正
- 剩下的价值主要来自实现，而不是继续纸面争论
- 当前最优下一步是按 slice 并行实现，而不是继续扩写愿景
