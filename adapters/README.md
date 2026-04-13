# adapters

这个目录是 `Cellular-studio` 的适配层入口。

使用原则：

- 某个人的数据格式不同，优先在这里适配
- 不把个性化数据判断直接写进 `web/`
- 适配脚本的目标是输出统一批次结构

推荐子目录结构：

```text
adapters/
  <owner_or_dataset>/
    README.md
    build_batch.py
    examples/
```

一个适配器至少应说明：

- 输入数据是什么
- 输出到什么批次结构
- 依赖哪些字段
- 是否依赖服务器私有路径
