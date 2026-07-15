# Studio 离线 / 内网 Docker 交付说明

## 1. 交付目标

这套交付包面向“可联网制包 + 内网/无网运行”两种场景，包含：

- Studio 前端与 `review_server` 单入口
- 用户上传 `trajectory4` 与 `signal6`
- `signal6` 默认处理链路：`snap + OD + fmm (v311)`
- 本地离线瓦片服务：`/offline_tiles/beijing/{z}/{x}/{y}.png`
- 前端底图切换：`在线 / 离线 / 内网`
- 可直接搬运的 Docker 镜像 tar 与 bundle 压缩包

## 2. 目录说明

- `trajectory_annotation_studio/`：Studio 平台代码
- `my_history_methods/cellular_quality/`：`signal6 v311` 处理代码
- `my_history_methods/map_matching/vendor/fmm/`：FMM 源码，Docker 构建时会在容器内编译
- `project_data/map_assets/`：北京道路 / 地铁 / 铁路 shapefile，供离线底图渲染使用
- `runtime/`：容器运行时持久化目录，不放任何真实信令数据

## 3. 制包方操作

### 3.1 构建完整离线镜像

在可联网构建机执行：

```bash
trajectory_annotation_studio/deploy/docker/build_image_and_export.sh
```

默认产物：

- 镜像标签：`trajectory-annotation-studio-offline:latest`
- 镜像 tar：`trajectory_annotation_studio_offline_image.tar`

如只需要基础环境，也可导出无 FMM 版本：

```bash
SKIP_FMM=1 trajectory_annotation_studio/deploy/docker/build_image_and_export.sh
```

> 2026-06 final demo note: the `speed_sparsity_90` upload flow requires
> `geopandas/fiona/pyproj/scikit-learn` and both original FMM plus
> `build_mainroad/` FMM binaries in the image. Reusing an older image is only
> safe after checking it with the final-demo bundle's `verify_image_tar.sh`.

### 3.2 组装最终交付包

```bash
trajectory_annotation_studio/deploy/docker/assemble_delivery_bundle.sh
```

默认会输出：

- bundle 目录：`delivery_out/trajectory_annotation_studio_offline_bundle_<timestamp>/`
- 压缩包：`delivery_out/trajectory_annotation_studio_offline_bundle_<timestamp>.tar.gz`

如果 bundle 根目录检测到 `trajectory_annotation_studio_offline_image.tar`，会自动一并带入交付包。

### 3.3 最终答辩演示包（镜像与源码资产分离）

如果只交付 `speed_sparsity_90` 最终展示批次和 8 条可上传输入轨迹，使用：

```bash
trajectory_annotation_studio/deploy/docker/assemble_final_demo_delivery.sh
```

默认输出：

- `delivery_out/signal_studio_final_demo_assets_<timestamp>/`
- `delivery_out/signal_studio_final_demo_assets_<timestamp>.tar.gz`

这个包不内置镜像 tar；镜像 tar 单独交付，便于之后只替换源码资产包做热更新。包内只预置：

- `runtime/published/signal_gps_v311_speed_sparsity_20260603/`
- `input_trajectories/eight_routes/`
- `data/test/`（同一份 8 条上传输入轨迹，保留本地验收目录名）
- `input_trajectories/signal_triplet_8routes_input.zip`

启动时把兼容的 `trajectory_annotation_studio_offline_image_linux_amd64.tar`
放到资产包同级或包根，或设置 `IMAGE_TAR=/path/to/image.tar`，然后在资产包根执行：

```bash
bash start.sh
```

如果已有镜像 tag 不是 `trajectory-annotation-studio-offline:latest`，可在
`final-demo.env` 中调整 `STUDIO_IMAGE_TAG`。

## 4. 使用方操作（内网 / 无网）

### 4.1 前置条件

- 已安装 Docker / Docker Compose
- 拿到完整 bundle 压缩包
- 如需“内网底图”，能访问内网瓦片服务器

### 4.2 解压并启动

```bash
tar -xzf trajectory_annotation_studio_offline_bundle_<timestamp>.tar.gz
cd trajectory_annotation_studio_offline_bundle_<timestamp>
bash trajectory_annotation_studio/deploy/docker/start_bundle.sh
```

默认入口：

- Studio: `http://127.0.0.1:8016/web/index.html`

停止：

```bash
bash trajectory_annotation_studio/deploy/docker/stop_bundle.sh
```

### 4.3 启动脚本做了什么

`start_bundle.sh` 会自动：

1. 创建 `runtime/` 所需目录
2. 检查本机是否已有 `trajectory-annotation-studio-offline:latest`
3. 若本机没有镜像，则自动从 bundle 根目录加载 `trajectory_annotation_studio_offline_image.tar`
4. 用 `docker-compose.bundle.yml` 启动 Studio

默认容器资源上限在 `bundle.env` 中配置：

- `STUDIO_CONTAINER_CPUS=2.0`
- `STUDIO_CONTAINER_MEM_LIMIT=4g`
- `STUDIO_RESTART_POLICY=no`
- `STUDIO_DOCKER_MIN_FREE_GB=12`

如果内网部署机器配置较低，可以先把内存限制降到 `2g`，或把 CPU 限制降到 `1.0`。首次 `docker load` 大镜像仍然会明显吃磁盘 IO，建议在机器空闲时执行。
首次部署默认不启用 `unless-stopped` 自动重启，避免镜像或挂载不兼容时反复拉起容器。确认容器稳定后再把 `STUDIO_RESTART_POLICY` 改为 `unless-stopped`。

如果有人绕过项目脚本直接 `docker build`，仓库根的 `.dockerignore` 会排除 `data/`、`delivery_out/`、镜像 tar 和临时目录，避免把真实数据或大制品作为 build context 传给 Docker。

## 5. 底图模式与配置

右下角图层面板内有“底图”分组，可在三种模式中切换：

- `离线`：容器内离线瓦片服务，基于北京道路 / 地铁 / 铁路矢量资产按需渲染并缓存
- `内网`：指向内网瓦片服务
- `在线`：公网高德底图

默认配置文件：

- `trajectory_annotation_studio/deploy/docker/bundle.env`

关键参数：

- `STUDIO_TILE_DEFAULT_MODE=offline|intranet|online`
- `STUDIO_TILE_INTRANET_URL`
- `STUDIO_TILE_INTRANET_ATTRIBUTION`
- `STUDIO_TILE_INTRANET_COORDINATE_SYSTEM`
- `STUDIO_TILE_INTRANET_MIN_ZOOM`
- `STUDIO_TILE_INTRANET_MAX_NATIVE_ZOOM`
- `STUDIO_TILE_INTRANET_MAX_ZOOM`
- `STUDIO_TILE_INTRANET_DETECT_RETINA`

`STUDIO_TILE_INTRANET_URL` 支持两类模板：

- XYZ 路径：`http://host/styles/basic/{z}/{x}/{y}.png`
- Query 模板：`http://host/tiles?x={x}&y={y}&z={z}`

## 6. 上传与处理

- `trajectory4`：直接生成 `trajectory_layers` 批次
- `signal6`：默认进入 `v311` 链路，输出 `raw.csv / snap.csv / od.csv / fmm.csv / line.csv`

容器内默认处理模式：

- `STUDIO_SIGNAL6_PIPELINE_MODE=v311`

## 7. 仅做离线批处理

如果不进 Web，只想用同一镜像在外部先处理出可搬运 batch，可执行：

```bash
docker run --rm \
  -v /path/to/signal6.csv:/data/in/signal6.csv:ro \
  -v /path/to/published_parent:/data/published \
  --entrypoint python3 \
  trajectory-annotation-studio-offline:latest \
  -m trajectory_annotation_studio.scripts.offline_signal6_batch \
  --input /data/in/signal6.csv \
  --published-root /data/published \
  --batch-name my_offline_batch_001 \
  --force
```

说明：

- `--published-root` 为父目录；产物目录为 `/data/published/my_offline_batch_001/`
- 默认 `--pipeline-mode v311`，即 `snap + OD + FMM`
- 处理完成后会把 `result/` 拷入批次目录，便于直接搬运进内网
- 排错可加 `--keep-workspace`，保留临时目录与 FMM 中间产物

## 8. 数据持久化与注意事项

Compose 默认把宿主机 `./runtime` 映射到容器 `/opt/studio/runtime`。

关键子目录：

- `runtime/incoming/`
- `runtime/catalog/`
- `runtime/datasets/user_assets/`
- `runtime/published/`
- `runtime/offline_tiles_cache/`

注意：

- 不要把真实信令数据直接烤进镜像
- 删除容器不会删除 `runtime/` 里的数据
- 如果要整机迁移，可直接拷贝 `runtime/` 与 bundle 压缩包

## 9. 内网端口建议

如果要让内网其他机器访问当前部署节点，至少需要打通：

- Studio HTTP 端口：默认 `8016`
- 如启用内网瓦片服务，还需确保 Studio 所在机器能访问 `STUDIO_TILE_INTRANET_URL` 对应端口

例如默认示例中，内网瓦片服务端口是 `8077`。

## 10. 验收建议

建议按下面顺序验收：

1. 打开 `http://<host>:8016/web/index.html`
2. 切到底图面板，验证 `离线 / 内网 / 在线` 三种模式都能切换
3. 上传一个 `trajectory4` CSV，确认能直接打开批次
4. 上传一个 `signal6` CSV，确认处理结果含 `raw / snap / od / fmm / line`
5. 重启容器后再次进入，确认历史上传与批次仍存在

## 11. 兼容性说明

- 默认中心点：北京 `[39.9, 116.4]`，`zoom=11`
- 离线底图精度目标是“约 1km 级别可视化”，不追求精细制图
- `signal6` 仍限制在北京范围内
- 离线瓦片按需渲染并缓存到磁盘，首次访问局部区域会偏慢，二次访问会明显加快
