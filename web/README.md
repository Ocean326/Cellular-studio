# 信令轨迹演示、审核与 accepted 导出

## 启动方式

推荐直接使用本目录下的轻量 review server，在**项目根目录**（`cellular_quality`）执行：

```bash
cd /path/to/cellular_quality
python src/web/review_server.py --port 8000
```

然后打开浏览器访问：`http://127.0.0.1:8000/web/index.html`

若只想看静态页面，也可以继续使用：

```bash
python -m http.server 8000
```

但这种方式不会提供审核写回接口，页面中的审核保存会不可用。

## 功能说明

- **左侧面板**：可折叠（点击标题栏 ◀ 按钮）、可拖拽右侧边缘调整宽度（260px–600px），宽度会保存到 localStorage
- **UID 列表**：从 `data/result/manifest.json` 或 `data/result/` 目录扫描可用 UID
- **UID 状态筛选**：按 `road/subway/railway/unmatch/stay` 过滤 UID，支持“任一命中”与“全部命中”
- **分层展示**：按 uid 目录下存在的文件（raw.csv、snap.csv、od.csv、fmm.csv、line.csv）动态显示图层
- **图层样式**：每层可勾选显隐、修改颜色、透明度，并支持拖拽调整图层顺序（上层覆盖下层）
- **状态点样式**：可分别修改 `road/subway/railway/unmatch/stay` 的点颜色与点大小（影响 fmm/line）
- **方向箭头**：点与点的连线段中间绘制小箭头，便于查看轨迹方向
- **CSV 预览**：底部表格可切换 raw/snap/fmm/od/line 的前 50 行
- **整轨审核**：新增 `accept / reject / skip` 控件，可保存 `reviewer`、`notes`、`reference_source`
- **审核写回**：review server 提供 `/api/reviews` 读写当前 ledger
- **缓存优化**：
  - 地图实例与瓦片图层只初始化一次，避免切换 UID 时重复创建地图
  - 已渲染的 UID 图层按“当前样式签名”缓存，切回同 UID 时可直接复用

## 数据依赖

需先运行 `Pipeline_demo.py` 生成 `data/result/{uid}/` 下的 CSV。OD 优先从 `data/result/{uid}/od.csv` 读取，若无则回退到 `data/OD/od_{uid}.csv`。

若已有 `data/result/` 但无 `manifest.json`，可运行 `python web/gen_manifest.py` 生成。该脚本会同时生成 `manifest.json` 和 `states_index.json`（预计算各 uid 的 road/subway/railway/unmatch/stay 标签），用于**状态筛选时 instant 生效**；否则需按需解析 fmm/line/od，筛选会较慢。

## 审核 ledger 与 accepted 导出

- 默认 ledger 根目录：`data/review/`
- 审核主 ledger：`data/review/ledger.jsonl`
- 当前最新索引：`data/review/latest_reviews.json`
- accepted 导出目录：`data/review/accepted_assets/`

accepted 导出 CLI：

```bash
python src/web/export_accepted_assets.py --clean
```

导出结果会整理为：

- `data/review/accepted_assets/samples/{sample_id}/raw.csv`
- `data/review/accepted_assets/samples/{sample_id}/line.csv`，若不可用则回退为 `fmm.csv`
- `data/review/accepted_assets/samples/{sample_id}/review.json`
- `data/review/accepted_assets/export_manifest.json`
- `data/review/accepted_assets/accepted_reviews.jsonl`

## 说明

- 状态筛选会按需读取对应 UID 的 `fmm/line/od` 数据并缓存结果。首次筛选时若 UID 数较多，可能有短暂等待。
- 修改图层样式、状态样式或图层顺序后，会自动失效旧渲染缓存并按新样式重绘。
- review server 只面向本地 organizer 使用，不包含鉴权与并发冲突处理。
