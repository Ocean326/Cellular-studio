# Contributing To Cellular-studio

## 1. 先看这 3 条

1. `GitHub` 私有仓只管代码与文档，不管真实数据。
2. 真实数据、批次结果、review 写回全部放服务器或本地仓外目录。
3. 个人数据差异优先写成 `adapter`，不要直接改核心页面逻辑。

## 2. 你可以改什么

可以直接在仓里贡献的内容：

- `web/` 里的通用前端和服务端能力
- `scripts/` 里的通用脚本
- `adapters/` 里的数据接入脚本
- `docs/` 里的合同、部署和使用文档

不应提交：

- 真实数据
- `data/` 下的运行产物
- 本地路径
- 服务器私有路径
- 缓存、日志、备份

## 3. 当你的数据格式不同

正确做法：

1. 在 `adapters/` 下建立自己的目录
2. 把原始数据转换成统一批次结构
3. 生成 `batch_meta.json` 和 `result/manifest.json`
4. 再让 studio 去读这批数据

不推荐做法：

- 在 `web/index.html` 里增加一堆“如果是某某同学的数据就……”分支
- 在 `review_server.py` 里硬编码个人路径

## 4. 分支命名

推荐前缀：

- `feature/`
- `fix/`
- `docs/`
- `adapter/`
- `spike/`

## 5. 提交前自查

提交前请确认：

- 没有真实数据进入 Git
- 没有私有路径进入 Git
- 改合同时已更新 `docs/`
- 你的改动属于核心逻辑还是适配层，边界清楚

## 6. 进一步阅读

- [README.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/README.md)
- [docs/03-协作与仓库规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/03-%E5%8D%8F%E4%BD%9C%E4%B8%8E%E4%BB%93%E5%BA%93%E8%A7%84%E8%8C%83.md)
- [docs/05-组内共享部署与数据接入规范.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/05-%E7%BB%84%E5%86%85%E5%85%B1%E4%BA%AB%E9%83%A8%E7%BD%B2%E4%B8%8E%E6%95%B0%E6%8D%AE%E6%8E%A5%E5%85%A5%E8%A7%84%E8%8C%83.md)
- [docs/07-仓库治理与 GitHub-服务器协作.md](/Users/ocean/Documents/Playground/Cellular-projects/trajectory_annotation_studio/docs/07-%E4%BB%93%E5%BA%93%E6%B2%BB%E7%90%86%E4%B8%8E%20GitHub-%E6%9C%8D%E5%8A%A1%E5%99%A8%E5%8D%8F%E4%BD%9C.md)
