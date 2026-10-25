# Watermark Remover

[![Continuous integration](https://github.com/itgsklab/Remove-Watermark/actions/workflows/ci.yml/badge.svg)](https://github.com/itgsklab/Remove-Watermark/actions/workflows/ci.yml)
[![Release readiness](https://github.com/itgsklab/Remove-Watermark/actions/workflows/release-readiness.yml/badge.svg)](https://github.com/itgsklab/Remove-Watermark/actions/workflows/release-readiness.yml)
[![CodeQL](https://github.com/itgsklab/Remove-Watermark/actions/workflows/codeql.yml/badge.svg)](https://github.com/itgsklab/Remove-Watermark/actions/workflows/codeql.yml)

面向 DOCX、PDF、CodeCV 简历和小红书图片的本地优先水印处理工具。

> 最新稳定版是 `v0.1.0`，采用 Vue Web 页面和本机 Python/FastAPI 服务，不提供原生桌面 App。当前 `main` 还包含尚未进入稳定下载的 `[Unreleased]` 改动；请以[发布状态、支持矩阵与已知限制](docs/release/RELEASE_STATUS.md)区分稳定版、主分支和实验性能力。

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
正式版不会仅凭 CI 通过自动发布；两个不可变 RC 的摘要、反馈记录和阻断条件见
[docs/release/STABLE_RELEASE.md](docs/release/STABLE_RELEASE.md)。

## 当前主分支可用 API

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `GET /api/v1/diagnostics`（返回脱敏的 OCR、小红书网络能力和本地 VLM 运行状态）
- `POST /api/v1/xiaohongshu/preview`（解析分享文案；可选读取标题、描述和不含 URL 的封面/图集候选）
- `POST /api/v1/xiaohongshu/import`（重新校验页面和候选后，将公开页面图片保存为本地图片资产）
- `POST /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`（受控提供本地预览源文件）
- `DELETE /api/v1/assets/{asset_id}`
- `POST /api/v1/analyses`（支持 DOCX VML 与 DrawingML 图片候选、`codecv` / `general` PDF 预设和 `image` 图片预设）
- `GET /api/v1/analyses/{analysis_id}`
- `GET /api/v1/analyses/{analysis_id}/candidates/{candidate_id}/preview`（受控读取可安全显示的 DOCX 内嵌图片候选）
- `POST /api/v1/plans/validate`（校验 DOCX/CodeCV PDF 候选、策略、文件摘要与风险确认）
- `POST /api/v1/redactions/preview`（校验通用 PDF 区域并列出正文、图形和交互对象重叠）
- `POST /api/v1/redaction-plans/validate`（创建对象级删除或 Deep 栅格修复计划）
- `POST /api/v1/image-masks/preview`（校验坐标、计算蒙版并集，并预检周围背景复杂度）
- `POST /api/v1/image-masks/render-preview`（使用当前蒙版临时渲染指定修复半径的 PNG 效果，不保存结果）
- `POST /api/v1/image-plans/validate`（创建 OpenCV 图片修复计划并校验风险确认）
- `POST /api/v1/tasks`（后台生成新的 DOCX、PDF 或图片副本）
- `GET /api/v1/tasks`（读取本机任务记录）
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/report`（下载不含文件名、本地路径和用户内容的任务报告；PDF Deep 报告包含逐页 OCR 状态、实际回灌文字数量和不可搜索原因码）
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}`

## DOCX 当前处理流程

1. 上传 DOCX 并进行只读扫描。
2. 选择页眉或页脚中的 VML 文字水印候选；DrawingML 图片候选仅供预览复核。
3. 对未与目标文字完全匹配的候选进行显式确认。
4. 服务端再次校验文件摘要和候选定位信息。
5. worker 生成新 DOCX，仅重写包含所选形状的 XML 部件。
6. 校验压缩包结构、必需部件、修改部件 XML，以及所有非目标部件的字节一致性。
7. 使用本机 LibreOffice 和 Poppler 渲染原件与结果，按页并排检查。

原始上传文件不会被覆盖。当前版本可识别 Word 页眉/页脚中的 VML `textpath` 文字形状，以及通过内部图片关系嵌入的 DrawingML 图片。DrawingML 图片保持只读，不会进入删除计划；正文背景、外部图片关系、旧版 `.doc` 和浏览器不支持的图片格式不会被猜测性处理。

页面预览属于可选能力。缺少渲染工具或转换失败时，DOCX 处理任务仍会成功，界面会保留结果下载并说明预览不可用。可通过 `WMRM_DOCX_PREVIEW_ENABLED=false` 关闭预览。

CodeCV PDF 只删除扫描阶段确认的内容流操作序列，不按固定资源名删除所有 `/Pattern`。输出后会重新检查页数、页面框、旋转、正文文字操作和目标签名数量。PDF 对比使用 Poppler，可通过 `WMRM_PDF_PREVIEW_ENABLED=false` 关闭。

通用 PDF 支持跨页面连续框选多个区域并组成一个计划草稿，统一检查与正文及交互对象的重叠，再在用户明确确认后通过 PyMuPDF 应用物理 redaction。执行会删除区域内文字、清除相交图片像素、移除相交矢量图和链接，再以完整垃圾回收写入新 PDF；原文件不会被覆盖。坐标摘要、页面尺寸和旋转会在执行前后重新校验。

对于无法对象级分离的合成水印，通用 PDF 还支持 Deep 栅格修复：只渲染被选中的页面，使用 OpenCV Telea 修复水印区域，并把蒙版外的原始文字重新写入隐藏可搜索层。原本没有文字层的页面可以使用本机 Tesseract OCR；界面只列出诊断接口确认已安装的语言包，支持多选组合或明确关闭 OCR，后端会拒绝未安装、重复或无法确认的语言。缺少或关闭 OCR 时，任务会明确列出不可搜索页面。选中页面的链接、表单和矢量对象不会保留，执行前必须确认这一风险。

PNG、JPEG 和 WebP 可以进行元数据检查，并使用矩形、多边形、画笔、橡皮和保护区编辑蒙版。完成后的多边形可以拖动顶点，也可以使用方向键逐像素微调；一次拖动只产生一条撤销记录。草稿最多包含 100 个矩形片段、32 个多边形和 100 个保护区片段，手工编辑、清空和本地模型建议均进入同一条 50 步撤销/重做历史；蒙版和保护区可分别隐藏，任何数据编辑都会使旧风险预览失效。后端使用与执行阶段相同的像素栅格规则合并矩形和多边形，再扣除保护区，并拒绝保护区清空全部蒙版的计划。蒙版预览会分析区域周围的纹理、边缘、周期性和结构线，并对高复杂度背景要求显式确认。覆盖达到图片面积 10% 或选区与周围平均亮度差异低于 4% 时，也会提示大面积或半透明水印风险并要求确认。用户可以在正式创建任务前临时生成半径 1、当前值和半径 7 的效果对比，点击预览即可选用对应半径；这些预览只在浏览器会话中显示，不会进入资产库或生成下载文件。静态图片使用 OpenCV Telea 算法修复所选区域，在独立 worker 中生成无损 PNG 副本；输出会重新解码，并验证尺寸以及最终蒙版外（包括保护区）像素完全一致。输出会应用 EXIF 方向并移除原始 EXIF、ICC 等元数据。动态图仍只支持检查。

小红书入口可以从分享文案中提取 HTTPS 笔记直链或短链。纯链接解析不访问网络；页面读取和图片导入分别通过 `WMRM_XHS_METADATA_ENABLED=true`、`WMRM_XHS_MEDIA_IMPORT_ENABLED=true` 显式启用。预览只返回不含 CDN URL 的候选编号、页面声明的候选尺寸、解析规则版本和结构诊断；导入时后端重新读取页面并校验规则版本与候选，再将公开页面声明的 JPEG、PNG 或 WebP 封面/图集图片保存到本地资产库，随后复用现有图片检查和蒙版修复流程。页面中由受限 CDN 以 HTTP 形式声明的图片会先升级为 HTTPS，实际请求不会使用明文 HTTP。使用 fake-IP DNS 的本机可通过 `WMRM_XHS_HTTPS_PROXY=http://127.0.0.1:<port>` 显式启用受限回环代理；项目不会自动继承系统代理。它不执行页面 JavaScript、不使用登录 Cookie、不处理视频，也不承诺图片候选是原始全尺寸图片或完整图集。安全模型和配置见 [docs/XIAOHONGSHU_LINKS.md](docs/XIAOHONGSHU_LINKS.md)。

可选 VLM 水印定位可以由本机管理员显式接入 Web 图片流程，只在像素通过照片场景门禁后提出矩形蒙版草稿。默认安装和默认配置均关闭此能力，不会下载或分发权重；模型建议不会直接处理图片，也不会绕过蒙版预览、风险提示和人工确认。模型不可用、推理失败或门禁拒绝时，界面继续保留手工框选流程。候选框细化为像素蒙版目前只有模型无关合同和评测门禁，尚未接入真实分割模型或产品流程。启用步骤、固定 Safetensors 摘要、禁止远程代码策略和真实模型门禁见 [docs/VLM_LOCALIZATION.md](docs/VLM_LOCALIZATION.md)，蒙版细化的评测边界见 [docs/MASK_REFINEMENT_EVALUATION.md](docs/MASK_REFINEMENT_EVALUATION.md)。

任务元数据保存在 SQLite 中。单个任务在独立的 `spawn` 子进程中处理，由常驻监督线程串行调度；子进程崩溃会转为明确的失败状态，取消超时会强制终止子进程。服务重启后，排队或意外中断的任务会重新校验并执行，正在取消的任务会完成取消。取消宽限期默认 2 秒，可通过 `WMRM_WORKER_CANCEL_GRACE_SECONDS` 调整。

设置页集中显示 Tesseract OCR 版本与语言包、小红书页面读取/图片导入开关、受限代理是否配置，以及本地 VLM 的可用状态。重新检查只读取本机组件和配置，不访问小红书页面，也不加载模型。可复制的 schema v2 诊断摘要不会包含文件名、用户内容、任务记录、本地路径、可执行文件位置、代理地址或模型目录。

默认保留产物 30 天、未被计划引用的上传文件 7 天、遗留临时文件 24 小时；分别可通过 `WMRM_ARTIFACT_RETENTION_DAYS`、`WMRM_UNREFERENCED_ASSET_RETENTION_DAYS` 和 `WMRM_FAILED_WORK_RETENTION_HOURS` 调整。任务进程的边界和恢复语义见 [docs/WORKER.md](docs/WORKER.md)。

执行全部已实现检查：

```bash
make check
```

首次安装 Chromium 测试运行时并执行 DOCX、通用 PDF 和图片的真实浏览器流程：

```bash
make browser-install
make browser-check
```

浏览器测试只使用运行时生成的公开合成夹具，数据写入 Git 忽略的 `work/e2e-data`，并在每次运行前清空。

验证发布依赖清单、SPDX SBOM 和全新虚拟环境中的 wheel 安装：

```bash
make api-contract-check
make error-contract-check
make release-metadata-check
make wheel-check
```

`docs/release/openapi-v1.json` 是当前 `/api/v1/` Web API 的机器可读兼容性基线。
Vue 客户端类型由该基线生成，并由 `cd frontend && npm run api:check` 检查是否过期。
接口演进规则见 [docs/release/API_COMPATIBILITY_V1.md](docs/release/API_COMPATIBILITY_V1.md)。
Web API 与 CLI 的符号错误码及状态映射见
[docs/release/ERROR_CODES_V1.md](docs/release/ERROR_CODES_V1.md)。

版本变化见 [CHANGELOG.md](CHANGELOG.md)，第三方依赖清单见
[docs/THIRD_PARTY_DEPENDENCIES.md](docs/THIRD_PARTY_DEPENDENCIES.md)，机器可读的 SPDX 2.3 SBOM 位于
[docs/release/sbom.spdx.json](docs/release/sbom.spdx.json)。

## 反馈与贡献

可复现的程序错误、文档兼容性问题和功能建议请使用 GitHub 的结构化 Issue 表单。不要公开上传真实简历、合同、私人图片、有效分享链接、凭据、本地路径或其他个人信息；请优先提供脱敏的生成样本或生成脚本。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，`0.1.x` 问题分级和补丁门禁见 [docs/MAINTENANCE.md](docs/MAINTENANCE.md)。

涉及安全边界或隐私泄露的问题请勿创建公开 Issue，改用 [私密漏洞报告](https://github.com/itgsklab/Remove-Watermark/security/advisories/new)。支持版本和披露流程见 [SECURITY.md](SECURITY.md)。

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

复现不下载模型的 VLM 定位评分合同：

```bash
make vlm-localization-contract
```

显式安装可选模型依赖、下载固定版本 Florence-2 并运行本地真实模型评估的步骤见
[docs/VLM_LOCALIZATION.md](docs/VLM_LOCALIZATION.md)。模型权重和预测结果均保留在被 Git 忽略的
`work/` 目录，不进入 Web 发行物。

复核 SAM2 Hiera-T 分割候选的固定来源、许可、Safetensors 文件摘要和隔离运行策略：

```bash
make model-supply-chain-review
```

该门禁只批准离线评测，不下载模型、不加入默认依赖，也不开放 Web 产品入口。详情见
[docs/MASK_REFINEMENT_EVALUATION.md](docs/MASK_REFINEMENT_EVALUATION.md)。

显式建立隔离环境、下载固定 SAM2 文件并运行 CPU/MPS 本地评测：

```bash
make mask-refinement-model-env
make mask-refinement-model-fetch
make mask-refinement-model
```

上述命令将约 156 MB 权重、隔离依赖、预测蒙版和完整运行报告保留在 Git 忽略的 `work/`
目录。公开仓库只保存脱敏汇总，当前指标门禁与人工计时门禁均未通过。

扩充并复核 16 个独立实景来源组成的 32 样本成对语料，再运行 CPU/MPS 对照：

```bash
make mask-refinement-photo-corpus
make mask-refinement-photo-model
make mask-refinement-photo-model-cpu
```

实景语料要求每个正例都有同图同框的干净负例，并固定公开来源、使用条款、原图摘要、
转换方式和像素真值生成方法。原始 SAM2 结果仍未通过精度门禁。加入 Florence-2 候选确认后，CPU 与 MPS 的指标门禁均通过；复现组合评分：

```bash
make mask-refinement-candidate-gate-mps
make mask-refinement-candidate-gate-cpu
```

随后使用 8 个全新来源组成的 16 样本冻结留出集复核。候选门禁拒绝全部干净负例，但组合像素指标未通过：MPS IoU 为 0.643，CPU IoU 为 0.705。留出集不用于回调阈值，人工计时保持未开始，模型能力不会进入 Web 产品入口。详情见 [独立评测文档](docs/MASK_REFINEMENT_EVALUATION.md)。

开发语料上的后续实验可让 SAM2 返回多个蒙版，并按模型自己的预测 IoU 选择每个候选框的
蒙版。该策略在 CPU 与 MPS 开发评测中通过像素门禁，但仍需第二个未见来源确认集：

```bash
make mask-refinement-multimask-mps
make mask-refinement-multimask-cpu
```

第二套 8 来源确认集在策略冻结后运行，候选门禁仍拒绝全部干净负例，但 MPS/CPU IoU
分别只有 0.730/0.714，未通过像素门禁。项目因此不开始人工计时，也不开放 Web 模型入口。

后续开发实验为细长文字候选增加确定性局部 RGB 对比度蒙版，MPS/CPU 开发 IoU 分别为
0.826/0.827。后续第三套未见来源确认未通过，因此仍不能用于发布声明或 Web 产品入口。

第三套 8 来源确认集在策略冻结后只运行一次，MPS/CPU IoU 分别为 0.714/0.718，仍未
通过像素门禁。主要阻断项是 Florence-2 漏掉一个完整角标候选，因此继续停止人工计时。

开发集上的候选匹配实验保留 IoU 0.5，并补充“检测框至少 90% 位于候选内且面积至少占
候选 15%”的规则。候选 Precision/Recall 达到 1.000/1.000，MPS/CPU 像素 IoU 为
0.914/0.915。第四套 8 来源未见确认集只运行一次，候选 Precision/Recall 仍为
1.000/1.000，MPS/CPU 像素 IoU 为 0.861/0.910，确认门禁通过。人工盲测计时完成前仍不
进入 Web。

人工计时协议已在采集前冻结：每名参与者对 8 个正样本分别完成纯手工、候选框和模型细化
三种工作流，使用三分块平衡顺序，并记录总耗时、修正耗时与失败原因。协议要求至少 3 名
匿名参与者；真实数据尚未采集，因此计时门禁和发布门禁仍为失败。详情见
[人工盲测计时协议](docs/MASK_REFINEMENT_TIMING_PROTOCOL.md)。
协议配套的本地计时界面独立于正式 Web 产品，支持方案盲化、画笔增删、撤销、恢复初始蒙版、
服务器总计时、主动修正计时、失败原因和逐任务原子保存。现场采集协调命令可随机创建权限
受限的匿名会话、查看完成进度，并在所有会话完整后统一审计，原始随机代码不会写入磁盘。

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
VLM 定位候选模型、权重供应链边界和评分门禁见 [docs/VLM_LOCALIZATION.md](docs/VLM_LOCALIZATION.md)。
OpenCV 基准结果见 [docs/benchmarks/opencv-telea-baseline.md](docs/benchmarks/opencv-telea-baseline.md)，移动端水印基准见 [docs/benchmarks/mobile-watermark-baseline.md](docs/benchmarks/mobile-watermark-baseline.md)，复杂度真实样本校准见 [docs/benchmarks/image-complexity-calibration.md](docs/benchmarks/image-complexity-calibration.md)，VLM 定位评分合同见 [docs/benchmarks/vlm-localization-contract.md](docs/benchmarks/vlm-localization-contract.md)，首次真实模型结果见 [docs/benchmarks/vlm-localization-model.md](docs/benchmarks/vlm-localization-model.md)，LaMa 打包审查见 [docs/LAMA_EVALUATION.md](docs/LAMA_EVALUATION.md)。

## 许可证

本项目采用 [GNU Affero General Public License v3.0 only](LICENSE)。通过网络向用户提供修改版本时，需要按 AGPL-3.0 第 13 条向这些用户提供对应源代码。PyMuPDF 使用其 AGPL 路径；如需不受该路径约束的专有发行版，需要另行取得 PyMuPDF 商业授权，并单独评估本项目代码的授权安排。
