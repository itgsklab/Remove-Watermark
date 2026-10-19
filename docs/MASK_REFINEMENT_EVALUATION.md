# 候选框蒙版细化评测

## 当前结论

项目已经建立模型无关的“候选框 → 像素蒙版”合同和可复现评分器，但尚未选择、下载或接入真实分割模型。当前提交的预测是几何合同夹具，只证明评分器和门禁按设计工作，不能作为模型效果、节省时间或可发布能力的证据。

默认安装、Web 服务和发布产物没有新增模型依赖或权重。现有矩形、画笔、橡皮、保护区、风险预览与人工确认仍是完整且默认的图片流程。

## 运行合同

[`WatermarkMaskRefiner`](../backend/src/wmrm/adapters/images/segmentation.py) 接收本地图片路径和经过校验的候选框，返回与原图对齐的不可变二值蒙版。`SegmentationMask` 要求：

- 宽高为正数；
- 行优先像素数量严格等于 `width × height`；
- 每个像素只能是 `0` 或 `1`；
- 运行适配器必须公开模型 ID、固定 revision 和脱敏运行元数据。

该合同不会把模型结果直接转换为处理任务。未来真实适配器仍需限制输出数量和面积、拒绝越界或非有限数据，并把结果放入现有可编辑草稿；保护区、复杂度检查和用户确认不能被绕过。

## 评分内容

[`mask_refinement.py`](../backend/src/wmrm/benchmarks/mask_refinement.py) 同时校验来源图片、真实蒙版和预测蒙版的 SHA-256、尺寸、灰度模式及二值像素，然后报告：

- 像素级 Precision、Recall 和 IoU；
- 预测蒙版落在候选框外的像素数；
- 直接使用候选框时需要人工修正的像素数；
- 使用细化蒙版后仍需人工修正的像素数及减少比例；
- 每个真实模型样本的耗时和峰值内存；
- “纯手工”“VLM 框”“VLM + 分割”三条路径的人工操作时间。

发布声明必须同时满足指标、证据数量和人工计时三类门禁。合同夹具即使获得完美像素分数，也会因为 `is_model_output=false` 且没有人工计时而保持 `release_claim_allowed=false`。

## 初始合同语料

固定语料包含 8 个仓库生成样本：4 个正例覆盖半透明文字、时间戳、印章和签名，4 个负例覆盖人脸、正常签名、品牌标识和正文文字。每个样本包含原图、真实二值蒙版、候选框、预测夹具、尺寸、SHA-256 和人工复核状态。

当前合同报告见：

- [`mask-refinement-contract.json`](benchmarks/mask-refinement-contract.json)
- [`mask-refinement-contract.md`](benchmarks/mask-refinement-contract.md)

可重复生成并评分：

```bash
make mask-refinement-corpus
make mask-refinement-contract
```

## 下一阶段

真实模型接入前仍需完成：

1. 对候选模型的代码许可证、权重许可证、固定 revision、文件摘要和远程代码需求进行独立审查；
2. 使用独立真实照片和负例生成模型预测，禁止把真实蒙版作为输入；
3. 在 CPU、Apple Silicon 和至少一种 CUDA 环境记录耗时与峰值内存；
4. 由人工完成三条路径的盲测计时，并记录每个样本的修正量；
5. 只有真实模型指标、证据和计时门禁全部通过后，才评估是否作为默认关闭的可编辑蒙版建议接入 Web。
