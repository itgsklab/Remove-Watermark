# Remove Watermark

面向 DOCX、PDF、CodeCV 简历和小红书图片的本地优先水印处理工具。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、PDF.js
- 后端：Python 3.12、FastAPI、SQLAlchemy、SQLite、PyMuPDF、Pillow、NumPy、OpenCV
- 部署：本地服务，仅监听 `127.0.0.1`
- 可选预览：LibreOffice、Poppler `pdftoppm`

## 目录

```text
backend/   Python API、领域模型、任务与处理适配器
frontend/  Vue 本地 Web 界面
docs/      技术说明、兼容性记录与基准报告
```

## 开发启动

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
wmrm-api
```

前端：

```bash
cd frontend
npm install
npm run dev
```

Vite 默认把 `/api` 代理到 `http://127.0.0.1:8765`。

## 桌面预览包

安装固定的 PyInstaller 构建依赖，并使用现有前端依赖生成当前平台产物：

```bash
make desktop-install
make desktop-build
make desktop-verify
```

macOS 产物为 `dist/Watermark Remover.app`。桌面启动器在随机本地端口同源提供 Vue 与 API，自动打开浏览器；可以在“设置”页面经过二次确认后安全退出。Windows、macOS 和 Linux 必须分别在对应平台构建。已验证的构建环境为 macOS 15.7.3 / Apple Silicon。详细构建输入、数据目录、安全边界及代码签名说明见 [docs/DESKTOP_PACKAGING.md](docs/DESKTOP_PACKAGING.md)。

## API

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `POST /api/v1/system/shutdown`（仅桌面启动器启用）
- `POST /api/v1/xiaohongshu/preview`（解析分享文案；可选读取标题/描述，不返回或下载媒体）
- `POST /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`（受控提供本地预览源文件）
- `DELETE /api/v1/assets/{asset_id}`
- `POST /api/v1/analyses`（支持 DOCX VML、`codecv` / `general` PDF 预设和 `image` 图片预设）
- `GET /api/v1/analyses/{analysis_id}`
- `POST /api/v1/plans/validate`（校验 DOCX/CodeCV PDF 候选、策略、文件摘要与风险确认）
- `POST /api/v1/redactions/preview`（校验通用 PDF 区域并列出正文、图形和交互对象重叠）
- `POST /api/v1/redaction-plans/validate`（确认区域删除风险并创建 PyMuPDF 处理计划）
- `POST /api/v1/image-masks/preview`（校验坐标、计算蒙版并集，并预检周围背景复杂度）
- `POST /api/v1/image-plans/validate`（创建 OpenCV 图片修复计划并校验风险确认）
- `POST /api/v1/tasks`（后台生成新的 DOCX、PDF 或图片副本）
- `GET /api/v1/tasks`（读取本机任务记录）
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}`

## DOCX 处理流程

1. 上传 DOCX 并进行只读扫描。
2. 选择页眉或页脚中的 VML 文字水印候选。
3. 对未与目标文字完全匹配的候选进行显式确认。
4. 服务端再次校验文件摘要和候选定位信息。
5. worker 生成新 DOCX，仅重写包含所选形状的 XML 部件。
6. 校验压缩包结构、必需部件、修改部件 XML，以及所有非目标部件的字节一致性。
7. 使用本机 LibreOffice 和 Poppler 渲染原件与结果，按页并排检查。

原始上传文件不会被覆盖。该流程只识别 Word 页眉/页脚中的 VML `textpath` 文字形状，无法处理图片水印、正文背景或旧版 `.doc`。

页面预览属于可选能力。缺少渲染工具或转换失败时，DOCX 处理任务仍会成功，界面会保留结果下载并说明预览不可用。可通过 `WMRM_DOCX_PREVIEW_ENABLED=false` 关闭预览。

CodeCV PDF 只删除扫描阶段确认的内容流操作序列，不按固定资源名删除所有 `/Pattern`。输出后会重新检查页数、页面框、旋转、正文文字操作和目标签名数量。PDF 对比使用 Poppler，可通过 `WMRM_PDF_PREVIEW_ENABLED=false` 关闭。

通用 PDF 支持框选一个区域、检查与正文及交互对象的重叠，并在用户明确确认后通过 PyMuPDF 应用物理 redaction。执行会删除区域内文字、清除相交图片像素、移除相交矢量图和链接，再以完整垃圾回收写入新 PDF；原文件不会被覆盖。坐标摘要、页面尺寸和旋转会在执行前后重新校验。

PNG、JPEG 和 WebP 可以进行元数据检查和矩形蒙版编辑。蒙版预览会分析区域周围的纹理、边缘、周期性和结构线，并对高复杂度背景要求显式确认。覆盖达到图片面积 10% 或选区与周围平均亮度差异低于 4% 时，也会提示大面积或半透明水印风险并要求确认。静态图片使用 OpenCV Telea 算法修复所选区域，在独立 worker 中生成无损 PNG 副本；输出会重新解码，并验证尺寸以及蒙版外像素完全一致。输出会应用 EXIF 方向并移除原始 EXIF、ICC 等元数据。动态图仍只支持检查。

小红书入口可以从分享文案中提取 HTTPS 笔记直链或短链。纯链接解析不访问网络；可选页面元数据读取默认关闭，启用后也只返回标题、描述、作者、规范地址和缩略图存在标记，不返回、代理或下载图片和视频 URL。通过 `WMRM_XHS_METADATA_ENABLED=true` 显式启用，安全模型和配置见 [docs/XIAOHONGSHU_LINKS.md](docs/XIAOHONGSHU_LINKS.md)。需要处理图片时，用户仍应上传自己有权处理的本地文件。

任务元数据保存在 SQLite 中。单个任务在独立的 `spawn` 子进程中处理，由常驻监督线程串行调度；子进程崩溃会转为明确的失败状态，取消超时会强制终止子进程。服务重启后，排队或意外中断的任务会重新校验并执行，正在取消的任务会完成取消。取消宽限期默认 2 秒，可通过 `WMRM_WORKER_CANCEL_GRACE_SECONDS` 调整。

默认保留产物 30 天、未被计划引用的上传文件 7 天、遗留临时文件 24 小时；分别可通过 `WMRM_ARTIFACT_RETENTION_DAYS`、`WMRM_UNREFERENCED_ASSET_RETENTION_DAYS` 和 `WMRM_FAILED_WORK_RETENTION_HOURS` 调整。任务进程的边界和恢复语义见 [docs/WORKER.md](docs/WORKER.md)。

执行完整检查：

```bash
make check
```

重新生成不含第三方素材的图片修复基准和报告：

```bash
make image-benchmark
```

重新生成移动端竖图的小水印、半透明水印和多行覆盖基准：

```bash
make mobile-watermark-benchmark
```

复核带来源记录的真实照片背景移动端选区语料：

```bash
make mobile-selection-corpus
```

复核带来源记录的真实照片和项目截图复杂度阈值：

```bash
make complexity-calibration
```

验证 CodeCV 批量语料审计器（仓库生成夹具）：

```bash
make codecv-corpus
```

私有真实导出样本放入被 Git 忽略的 `backend/private-fixtures/codecv/` 后，可运行 `make codecv-real-corpus`。该命令要求至少包含一个已人工复核的真实导出文件。

验证 Chrome、LibreOffice 和 Microsoft Word 导出的通用 PDF 区域删除兼容性：

```bash
make pdf-redaction-corpus
```

DOCX 的结构兼容配置、证据等级和处理边界见 [docs/DOCX_COMPATIBILITY.md](docs/DOCX_COMPATIBILITY.md)。
CodeCV PDF 的操作签名、批量语料审计和处理边界见 [docs/CODECV_PDF.md](docs/CODECV_PDF.md)。
通用 PDF 的候选分类、坐标和误判边界见 [docs/GENERAL_PDF.md](docs/GENERAL_PDF.md)。
区域删除的风险预览、PyMuPDF 一致性探针、跨生成器语料审计与执行后端边界见 [docs/PDF_REDACTION.md](docs/PDF_REDACTION.md)。
图片检查、坐标合同和蒙版边界见 [docs/IMAGE_MASKS.md](docs/IMAGE_MASKS.md)。
小红书分享链接的允许域名、SSRF 防护和元数据边界见 [docs/XIAOHONGSHU_LINKS.md](docs/XIAOHONGSHU_LINKS.md)。
桌面同源部署、构建矩阵和已验证平台见 [docs/DESKTOP_PACKAGING.md](docs/DESKTOP_PACKAGING.md)。
OpenCV 基准结果见 [docs/benchmarks/opencv-telea-baseline.md](docs/benchmarks/opencv-telea-baseline.md)，移动端水印基准见 [docs/benchmarks/mobile-watermark-baseline.md](docs/benchmarks/mobile-watermark-baseline.md)，复杂度真实样本校准见 [docs/benchmarks/image-complexity-calibration.md](docs/benchmarks/image-complexity-calibration.md)，LaMa 打包审查见 [docs/LAMA_EVALUATION.md](docs/LAMA_EVALUATION.md)。

## 许可证

本项目采用 [GNU Affero General Public License v3.0 only](LICENSE)。通过网络向用户提供修改版本时，需要按 AGPL-3.0 第 13 条向这些用户提供对应源代码。PyMuPDF 使用其 AGPL 路径；如需不受该路径约束的专有发行版，需要另行取得 PyMuPDF 商业授权，并单独评估本项目代码的授权安排。
