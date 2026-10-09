# Watermark Remover

面向 DOCX、PDF、CodeCV 简历和小红书图片的本地优先水印处理工具。

> 当前状态：`0.1.0rc1` 发布候选后的开发版本。已完成 DOCX VML、CodeCV PDF 平铺水印、通用 PDF 区域物理删除、PDF Deep 栅格修复与可搜索文字层、静态图片矩形蒙版的处理闭环，以及小红书分享链接解析与公开封面安全导入。用户界面采用 Vue Web 页面，不提供原生桌面 App。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、PDF.js
- 后端：Python 3.12、FastAPI、SQLAlchemy、SQLite、PyMuPDF、Pillow、NumPy、OpenCV
- 部署：本地服务，仅监听 `127.0.0.1`
- 可选预览：LibreOffice、Poppler `pdftoppm`

## 目录

```text
backend/   Python API、领域模型、任务与处理适配器
frontend/  Vue 本地 Web 界面
docs/      技术说明、安全边界与可复现基准
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

## 生产 Web 启动

先安装后端与前端依赖，然后构建 Vue 生产资源并由 FastAPI 同源提供页面和 API：

```bash
make backend-install
make web-build
make web-run
```

浏览器访问 `http://127.0.0.1:8765/`。生产模式关闭开发 CORS，只监听本机回环地址，并为静态资源设置缓存和 CSP 等安全响应头。可使用 `wmrm-web --help` 查看前端目录、端口和数据目录参数；停止服务时回到启动终端按 `Ctrl+C`。

## 命令行

安装后可使用 `wmrm doctor` 检查本机 PDF/OCR 运行环境。`wmrm pdf-deep` 和
`wmrm pdf-redact` 分别提供栅格修复与对象级区域删除；`wmrm image-plan` 和
`wmrm image-apply` 提供先审阅风险计划、再执行图片蒙版修复的流程；`wmrm docx-plan`、
`wmrm docx-apply`、`wmrm codecv-plan` 和 `wmrm codecv-apply` 提供候选证据审阅、逐项确认与
精确对象删除。命令都使用独立输出路径，并可通过 `--json` 返回机器可读结果。参数、坐标
约定和退出码见 [docs/CLI.md](docs/CLI.md)。
首个公开版本的稳定命令、JSON 信封、退出码及计划 schema 约定见
[docs/release/CLI_COMPATIBILITY_V1.md](docs/release/CLI_COMPATIBILITY_V1.md)。

## 当前可用 API

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `POST /api/v1/xiaohongshu/preview`（解析分享文案；可选读取标题、描述和不含 URL 的封面候选）
- `POST /api/v1/xiaohongshu/import`（重新校验页面和候选后，将公开封面保存为本地图片资产）
- `POST /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`（受控提供本地预览源文件）
- `DELETE /api/v1/assets/{asset_id}`
- `POST /api/v1/analyses`（支持 DOCX VML、`codecv` / `general` PDF 预设和 `image` 图片预设）
- `GET /api/v1/analyses/{analysis_id}`
- `POST /api/v1/plans/validate`（校验 DOCX/CodeCV PDF 候选、策略、文件摘要与风险确认）
- `POST /api/v1/redactions/preview`（校验通用 PDF 区域并列出正文、图形和交互对象重叠）
- `POST /api/v1/redaction-plans/validate`（创建对象级删除或 Deep 栅格修复计划）
- `POST /api/v1/image-masks/preview`（校验坐标、计算蒙版并集，并预检周围背景复杂度）
- `POST /api/v1/image-plans/validate`（创建 OpenCV 图片修复计划并校验风险确认）
- `POST /api/v1/tasks`（后台生成新的 DOCX、PDF 或图片副本）
- `GET /api/v1/tasks`（读取本机任务记录）
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}`

## DOCX 当前处理流程

1. 上传 DOCX 并进行只读扫描。
2. 选择页眉或页脚中的 VML 文字水印候选。
3. 对未与目标文字完全匹配的候选进行显式确认。
4. 服务端再次校验文件摘要和候选定位信息。
5. worker 生成新 DOCX，仅重写包含所选形状的 XML 部件。
6. 校验压缩包结构、必需部件、修改部件 XML，以及所有非目标部件的字节一致性。
7. 使用本机 LibreOffice 和 Poppler 渲染原件与结果，按页并排检查。

原始上传文件不会被覆盖。当前版本只识别 Word 页眉/页脚中的 VML `textpath` 文字形状，无法处理图片水印、正文背景或旧版 `.doc`。

页面预览属于可选能力。缺少渲染工具或转换失败时，DOCX 处理任务仍会成功，界面会保留结果下载并说明预览不可用。可通过 `WMRM_DOCX_PREVIEW_ENABLED=false` 关闭预览。

CodeCV PDF 只删除扫描阶段确认的内容流操作序列，不按固定资源名删除所有 `/Pattern`。输出后会重新检查页数、页面框、旋转、正文文字操作和目标签名数量。PDF 对比使用 Poppler，可通过 `WMRM_PDF_PREVIEW_ENABLED=false` 关闭。

通用 PDF 支持框选一个区域、检查与正文及交互对象的重叠，并在用户明确确认后通过 PyMuPDF 应用物理 redaction。执行会删除区域内文字、清除相交图片像素、移除相交矢量图和链接，再以完整垃圾回收写入新 PDF；原文件不会被覆盖。坐标摘要、页面尺寸和旋转会在执行前后重新校验。

对于无法对象级分离的合成水印，通用 PDF 还支持 Deep 栅格修复：只渲染被选中的页面，使用 OpenCV Telea 修复水印区域，并把蒙版外的原始文字重新写入隐藏可搜索层。原本没有文字层的页面会在本机存在 Tesseract 时尝试 OCR；缺少 OCR 时任务会明确列出不可搜索页面。选中页面的链接、表单和矢量对象不会保留，执行前必须确认这一风险。

PNG、JPEG 和 WebP 可以进行元数据检查和矩形蒙版编辑。蒙版预览会分析区域周围的纹理、边缘、周期性和结构线，并对高复杂度背景要求显式确认。覆盖达到图片面积 10% 或选区与周围平均亮度差异低于 4% 时，也会提示大面积或半透明水印风险并要求确认。静态图片使用 OpenCV Telea 算法修复所选区域，在独立 worker 中生成无损 PNG 副本；输出会重新解码，并验证尺寸以及蒙版外像素完全一致。输出会应用 EXIF 方向并移除原始 EXIF、ICC 等元数据。动态图仍只支持检查。

小红书入口可以从分享文案中提取 HTTPS 笔记直链或短链。纯链接解析不访问网络；页面读取和图片导入分别通过 `WMRM_XHS_METADATA_ENABLED=true`、`WMRM_XHS_MEDIA_IMPORT_ENABLED=true` 显式启用。预览只返回不含 CDN URL 的候选编号；导入时后端重新读取页面并校验候选，再将公开页面声明的 JPEG、PNG 或 WebP 封面保存到本地资产库，随后复用现有图片检查和蒙版修复流程。它不执行页面 JavaScript、不使用登录 Cookie、不处理视频，也不承诺封面候选是原始全尺寸图片。安全模型和配置见 [docs/XIAOHONGSHU_LINKS.md](docs/XIAOHONGSHU_LINKS.md)。

任务元数据保存在 SQLite 中。单个任务在独立的 `spawn` 子进程中处理，由常驻监督线程串行调度；子进程崩溃会转为明确的失败状态，取消超时会强制终止子进程。服务重启后，排队或意外中断的任务会重新校验并执行，正在取消的任务会完成取消。取消宽限期默认 2 秒，可通过 `WMRM_WORKER_CANCEL_GRACE_SECONDS` 调整。

默认保留产物 30 天、未被计划引用的上传文件 7 天、遗留临时文件 24 小时；分别可通过 `WMRM_ARTIFACT_RETENTION_DAYS`、`WMRM_UNREFERENCED_ASSET_RETENTION_DAYS` 和 `WMRM_FAILED_WORK_RETENTION_HOURS` 调整。任务进程的边界和恢复语义见 [docs/WORKER.md](docs/WORKER.md)。

执行全部已实现检查：

```bash
make check
```

验证发布依赖清单、SPDX SBOM 和全新虚拟环境中的 wheel 安装：

```bash
make release-metadata-check
make wheel-check
```

版本变化见 [CHANGELOG.md](CHANGELOG.md)，第三方依赖清单见
[docs/THIRD_PARTY_DEPENDENCIES.md](docs/THIRD_PARTY_DEPENDENCIES.md)，机器可读的 SPDX 2.3 SBOM 位于
[docs/release/sbom.spdx.json](docs/release/sbom.spdx.json)。

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

DOCX 的结构兼容配置、证据等级和当前边界见 [docs/DOCX_COMPATIBILITY.md](docs/DOCX_COMPATIBILITY.md)。
CodeCV PDF 的操作签名、批量语料审计和当前边界见 [docs/CODECV_PDF.md](docs/CODECV_PDF.md)。
通用 PDF 的候选分类、坐标和误判边界见 [docs/GENERAL_PDF.md](docs/GENERAL_PDF.md)。
区域删除的风险预览、PyMuPDF 一致性探针、跨生成器语料审计与执行后端边界见 [docs/PDF_REDACTION.md](docs/PDF_REDACTION.md)。
PDF Deep 栅格修复、文字层回灌、可选 OCR 和当前限制见 [docs/PDF_DEEP.md](docs/PDF_DEEP.md)。
图片检查、坐标合同和蒙版边界见 [docs/IMAGE_MASKS.md](docs/IMAGE_MASKS.md)。
小红书分享链接的允许域名、SSRF 防护和元数据边界见 [docs/XIAOHONGSHU_LINKS.md](docs/XIAOHONGSHU_LINKS.md)。
OpenCV 基准结果见 [docs/benchmarks/opencv-telea-baseline.md](docs/benchmarks/opencv-telea-baseline.md)，移动端水印基准见 [docs/benchmarks/mobile-watermark-baseline.md](docs/benchmarks/mobile-watermark-baseline.md)，复杂度真实样本校准见 [docs/benchmarks/image-complexity-calibration.md](docs/benchmarks/image-complexity-calibration.md)，LaMa 打包审查见 [docs/LAMA_EVALUATION.md](docs/LAMA_EVALUATION.md)。

## 许可证

本项目采用 [GNU Affero General Public License v3.0 only](LICENSE)。通过网络向用户提供修改版本时，需要按 AGPL-3.0 第 13 条向这些用户提供对应源代码。PyMuPDF 使用其 AGPL 路径；如需不受该路径约束的专有发行版，需要另行取得 PyMuPDF 商业授权，并单独评估本项目代码的授权安排。
