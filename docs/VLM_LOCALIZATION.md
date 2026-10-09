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

## 可复现基准

基准清单包含三张有水印正样本和两张无水印负样本。底图来自仓库中已记录来源与摘要的 NASA 图片；水印由项目确定性生成。评分包括：

- IoU 大于等于 0.5 的一对一匹配；
- Precision、Recall、F1 和匹配框平均 IoU；
- 无水印负样本上的误报；
- 图片 SHA-256、尺寸、边界和人工复核状态校验。

当前提交的预测文件是几何合同夹具，用于证明评分器会通过正确框、拒绝越界框并统计负样本误报。它明确设置 `is_model_output=false`，因此即使指标门禁通过，也不能形成模型效果声明。真实模型评估必须使用 `--require-model-output`，并至少达到 Precision 0.75、Recall 0.85；扩大语料之前仍不得进入默认产品流程。

2026-10-09 的首次真实模型运行记录在
[`benchmarks/vlm-localization-model.md`](benchmarks/vlm-localization-model.md)：单一 `watermark`
提示命中 3 个正样本中的 2 个，但在两个干净负样本上均产生误报，Precision 0.400、Recall
0.667、F1 0.500，未通过门禁。因此适配器仍仅用于显式离线评估，不进入 API 或 Web 自动选择。

复现合同评分：

```bash
make vlm-localization-contract
```

输出为 [`benchmarks/vlm-localization-contract.json`](benchmarks/vlm-localization-contract.json) 和 [`benchmarks/vlm-localization-contract.md`](benchmarks/vlm-localization-contract.md)。
