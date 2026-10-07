# 桌面打包

## 当前产物

桌面版采用 PyInstaller `onedir` 打包。Vue 生产构建被放入应用资源目录，FastAPI 在随机回环端口同源提供页面和 `/api/v1`。包装层只负责：

- 选择并占用 `127.0.0.1` 的空闲端口；
- 建立平台数据目录；
- 启动本地服务并打开默认浏览器；
- 接收设置页发出的退出请求，等待任务监督器清理后关闭服务。

macOS 使用 `.app`，Windows 和 Linux 使用包含可执行文件及依赖的目录。每个平台必须在该平台上分别构建；当前仓库提供 GitHub Actions 三平台矩阵，但本地实测结论只覆盖 macOS Apple Silicon。

PyInstaller 官方文档建议 macOS 窗口应用使用 `onedir`，避免 `onefile` 每次启动解包的成本和签名限制：[Using PyInstaller](https://pyinstaller.org/en/stable/usage.html)。子进程入口在导入业务模块前调用 `multiprocessing.freeze_support()`，遵循官方的冻结进程要求：[Common Issues and Pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing)。

## 构建

要求：

- Python `3.12.10`
- Node.js `22.20.0`
- npm lockfile 对应依赖
- 当前平台所需的编译/运行库

首次安装打包依赖：

```bash
make desktop-install
```

构建和验证：

```bash
make desktop-build
make desktop-verify
make desktop-archive
```

完整的干净前端安装可直接运行：

```bash
backend/.venv/bin/python packaging/build_desktop.py
```

`packaging/constraints.txt` 固定 Python 打包环境版本；`frontend/package-lock.json` 固定前端依赖。构建脚本会写入 `build-info.json`，记录 Git 提交、构建平台、Python 版本，以及后端项目配置、Python 约束和前端锁文件的 SHA-256。时间来自 `SOURCE_DATE_EPOCH`，未设置时使用当前 Git 提交时间。

产物位置：

- macOS：`dist/Watermark Remover.app`
- Windows：`dist/Watermark Remover/Watermark Remover.exe`
- Linux：`dist/Watermark Remover/Watermark Remover`

CI 在上传前先生成 `.tar.gz`（macOS/Linux）或 `.zip`（Windows）。macOS/Linux 使用 tar 保留可执行权限和符号链接；直接把应用目录交给 GitHub Artifact 会丢失文件权限。

## 运行数据

桌面版默认将数据保存在：

- macOS：`~/Library/Application Support/Watermark Remover`
- Windows：`%LOCALAPPDATA%/Watermark Remover`
- Linux：`$XDG_DATA_HOME/watermark-remover`，未设置时为 `~/.local/share/watermark-remover`

可用 `WMRM_DATA_DIR` 或启动参数 `--data-dir` 覆盖。应用仍只监听 `127.0.0.1`；改变端口不会改变数据位置。

## 安全边界

- 打包后端只监听 IPv4 回环地址，不接受局域网连接。
- Vue 和 API 同源，不启用生产 CORS。
- 修改状态的请求如果带有其他站点的 `Origin`，服务会返回 `403 CROSS_ORIGIN_REQUEST`。
- `/api/v1/system/shutdown` 只在桌面模式启用，源码 API 服务无法通过页面关闭。
- 设置页采用两步确认；退出会触发 FastAPI lifespan，先停止任务调度和子进程，再关闭监听端口。
- 应用不会自动启用小红书页面联网读取，也不会下载模型。

## 已验证范围

本机已验证环境：

- macOS `15.7.3`
- Apple Silicon `arm64`
- Python `3.12.10`
- PyInstaller `6.22.3`

验证包括：Vue 生产构建、`.app` 生成、Mach-O `arm64` 架构、macOS ad-hoc 签名结构、健康接口、Vue History 路由、页面内退出，以及在冻结应用的 `spawn` 子进程中完成 OpenCV 图片修复并下载输出。

当前没有 Developer ID 签名、公证、DMG/MSI 安装器或自动更新。Windows/Linux 工作流属于待 CI 实跑的构建配置，不能据此宣称已经完成对应平台兼容验证。
