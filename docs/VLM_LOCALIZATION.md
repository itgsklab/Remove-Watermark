# 可选 VLM 水印定位边界

## 当前结论

VLM 只负责提出像素坐标边界框，不直接修改图片，也不绕过现有的区域预览、风险提示、用户确认和 OpenCV 修复流程。第一候选是 `microsoft/Florence-2-base`，原因是：

- 官方模型卡标注 MIT，并提供独立 MIT `LICENSE`；
- 约 0.23B 参数，固定 revision 的 Safetensors 权重为 463,221,266 字节；
- Transformers 官方文档原生列出 Caption-to-Phrase Grounding 和 Open Vocabulary Detection，并提供边界框后处理；
- 可以本地推理，不要求把用户图片发给远程 API。

模型选择和文件摘要固定在 [`models/florence-2-base.json`](models/florence-2-base.json)。来源：

- [Microsoft Florence-2-base 模型卡](https://huggingface.co/microsoft/Florence-2-base)
- [固定 revision 的 MIT 许可证](https://huggingface.co/microsoft/Florence-2-base/blob/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/LICENSE)
- [Transformers Florence-2 官方文档](https://huggingface.co/docs/transformers/model_doc/florence2)

## 供应链边界

- 权重不进入 Git、Python wheel、Web bundle 或 GitHub Release。
- 默认不下载模型；后续运行适配器必须由本机管理员显式启用。
- 只接受清单里的固定 revision、文件名、大小和 SHA-256。
- 只加载 `model.safetensors`，拒绝同仓库的 `pytorch_model.bin`。
- 固定 revision 的模型实现以 Apache-2.0 代码随项目审计保存；运行时直接导入该本地代码，
  `trust_remote_code`/模型目录 Python 代码执行保持关闭。文件摘要记录在模型清单中。
- 模型缓存必须位于本机数据目录之外的明确模型缓存区；删除缓存不能影响用户资产或任务记录。
- MIT 许可证允许使用和再分发，但如果将来决定随发行物分发权重，必须重新生成 SBOM、附带许可证并发布新的 RC。

适配器位于 `wmrm.adapters.images.florence2`。普通安装不会安装 PyTorch/Transformers，
也不会访问网络。管理员决定运行本地评估时才执行：

```bash
cd backend
.venv/bin/pip install -e '.[vlm]'
cd ..
make vlm-model-fetch
make vlm-localization-model
```

`vlm-model-fetch` 只下载清单允许的文件到被 Git 忽略的 `work/models/`，每个文件必须同时
匹配固定大小和 SHA-256。`vlm-localization-model` 先生成真实预测，再以
`--require-model-output` 运行指标门禁，结果保留在本机 `work/` 中供复核。

固定模型仓库的旧参数命名与 Transformers 4.50 之后的原生 Florence-2 类不兼容。可选依赖
因此限定为已验证的 `transformers>=4.49,<4.50`，并使用同一模型 revision 的 3 个实现文件；这些文件
保留上游 Apache-2.0 版权头及完整许可证。模型目录中的同名 `.py` 文件仍被拒绝。

## 定位合同

[`LocalizationBox`](../backend/src/wmrm/adapters/images/detection.py) 使用原图像素坐标，包含 `x0/y0/x1/y1`、非空标签和 `[0,1]` 置信度。`WatermarkLocalizer` 只接收本地图片路径和提示词，返回不可变边界框集合。

初始提示词合同使用单一目标类别，避免模型把逗号列表解释为一个长短语：

```text
watermark
```

模型输出仍然是不可信候选：后端必须再次校验有限数值、图像边界、面积和重叠，再转换为现有图片蒙版计划。定位失败返回空集合，不自动扩大到整张图片。
Florence-2 的生成式边界框没有经过校准的置信度，因此适配器使用固定的 `1.0` 仅满足统一
数据结构；当前评分不把该值解释为概率，也不设置基于它的产品阈值。

适配器拒绝覆盖超过原图 `30%` 的单个候选框。首次负样本运行中的两个错误候选分别覆盖
`46.1%` 和 `44.2%`，而复核正样本最大候选覆盖 `20.8%`。该规则只删除不适合作为自动
局部蒙版的超大框，不把超大区域缩成看似精确的小框。

## 可复现基准

基准清单目前包含 24 张有水印正样本和 24 张无水印负样本。除 NASA 图片、6 张 Commons
CC0 实拍照片和无用户数据的项目 UI 截图外，共有 21 组可重建的干净/带水印配对场景，覆盖自然照片、普通
Web UI、文档、代码编辑器、排版海报和移动信息流。所有生成样本都可以用
`make vlm-localization-corpus` 重建。评分包括：

- IoU 大于等于 0.5 的一对一匹配；
- Precision、Recall、F1 和匹配框平均 IoU；
- 无水印负样本上的误报；
- 按场景类型拆分的 Precision、Recall 和 F1；
- 同一底图干净版无误报且带水印版正确命中的配对诊断；
- 图片 SHA-256、尺寸、边界和人工复核状态校验。

当前提交的合同预测文件是几何夹具，用于证明评分器会通过正确框、拒绝越界框并统计负样本
误报。它明确设置 `is_model_output=false`，因此即使指标门禁通过，也不能形成模型效果声明。
真实模型评估必须使用 `--require-model-output`，达到 Precision 0.75、Recall 0.85，并至少
覆盖 20 个样本、其中 10 个负样本、4 类场景和 7 组正负配对。严格模式只有指标和证据
多样性同时通过才返回成功。

2026-10-11 的当前真实模型运行记录在
[`benchmarks/vlm-localization-model.md`](benchmarks/vlm-localization-model.md)：单一 `watermark`
提示在自然照片子集得到 Precision 0.750、Recall 0.947；全量结果为 Precision 0.487、
Recall 0.792、F1 0.603。新增难例继续暴露无水印照片上的误报，也保留了 UI、文档和
排版场景中的误报。证据门禁通过，指标门禁失败。此前对 `transparent watermark`、
`watermark overlay`、`logo watermark` 和 `overlaid watermark` 的本地对照也没有同时改善
误报与漏报。因此
`release_claim_allowed=false`，因此它不能作为全场景自动定位器。Web 只在本机管理员显式启用、
固定模型文件校验通过且照片场景门禁通过时提供人工复核的蒙版草稿。

## 自然照片场景门禁

[`PhotoSceneGate`](../backend/src/wmrm/adapters/images/photo_scene.py) 在 VLM 推理前只读取解码后的
像素，不读取文件名、扩展名、EXIF、模型检测结果、文字标签或水印坐标。它把图像最长边缩小
到 256 像素，保留原有的亮度熵和量化色彩路径，并增加两条通用证据路径：亮度标准差配合
非平坦梯度比例识别连续色调，亮度分布配合梯度方向熵识别暗场景中的分散细节。任一路径通过
才允许 Florence-2 运行；其余图片回退到现有手动框选流程。阈值和计算参数全部随报告记录。

扩充后的固定 48 样本来自 16 个独立照片来源，包含灰度月壤、低色彩火星影像、暗背景行星、
夜景、科学合成图，以及雪地、针叶林、雾林、沙漠和黑白森林实拍。门禁分类 Precision、
Recall 和 Specificity 均为 1.000，21 组配对在加水印前后全部保持同一判定。门禁后的自然
照片定位 Precision 0.750、Recall 0.947；全场景结果为 Precision 0.750、Recall 0.750，
因为门禁会主动放弃 UI、文档和排版场景。详细结果见
[`benchmarks/vlm-photo-gate.md`](benchmarks/vlm-photo-gate.md) 和
[`benchmarks/vlm-photo-gated-localization.md`](benchmarks/vlm-photo-gated-localization.md)。

来源清单、资产 URL、署名和 SHA-256 位于
[`vlm_photo_sources/manifest.json`](../backend/tests/fixtures/vlm_photo_sources/manifest.json)。当前
照片专用门禁已经达到分类、来源、配对稳定性和照片范围定位要求，因此照片门禁报告设置
`release_claim_allowed=true`。全场景报告仍为 `false`，因为照片专用策略会主动放弃非照片
内容，不应作为通用自动定位器。API/Web 通过显式本地配置接入这一可选模型路径。它默认关闭，
不接受客户端提供模型路径，不自动下载模型；非照片样本不会加载模型或执行推理。返回的候选框
只会填入现有蒙版编辑器，用户仍需逐个检查、调整、验证风险并主动创建处理任务。当前也可以
在本机显式复现评估：

```bash
make vlm-localization-model-photo-gated
make vlm-photo-gate
```

## Web 显式启用

先安装可选依赖并通过显式命令获取固定模型文件：

```bash
cd backend
.venv/bin/pip install -e '.[vlm]'
cd ..
make vlm-model-fetch
```

然后只在启动本地 Web 服务时设置以下配置：

```bash
WMRM_VLM_ENABLED=true \
WMRM_VLM_MODEL_DIR="$PWD/work/models/florence-2-base" \
WMRM_VLM_MODEL_MANIFEST="$PWD/docs/models/florence-2-base.json" \
make web-run
```

`WMRM_VLM_DEVICE` 可设为 `auto`（默认）、`cpu`、`mps` 或 `cuda`。能力状态接口只公开是否
就绪和固定模型 ID，不公开本机目录。模型在第一次通过照片门禁的建议请求中才懒加载；配置
错误、缺少运行依赖和推理失败都会返回可恢复状态，原有手工框选始终可用。

复现合同评分：

```bash
make vlm-localization-contract
```

输出为 [`benchmarks/vlm-localization-contract.json`](benchmarks/vlm-localization-contract.json) 和 [`benchmarks/vlm-localization-contract.md`](benchmarks/vlm-localization-contract.md)。
