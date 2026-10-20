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

## 候选模型供应链审查

第一候选已经固定为 Meta 官方 `facebook/sam2-hiera-tiny`，仅批准用于离线独立评测。选择该候选是因为它接受候选框提示、Hiera-T 体积相对较小，并且官方仓库提供 Transformers 可加载的 Safetensors 权重。固定清单见 [`models/sam2-hiera-tiny.json`](models/sam2-hiera-tiny.json)，自动审查报告见：

- [`sam2-hiera-tiny-supply-chain.json`](benchmarks/sam2-hiera-tiny-supply-chain.json)
- [`sam2-hiera-tiny-supply-chain.md`](benchmarks/sam2-hiera-tiny-supply-chain.md)

本轮也比较了两个轻量或高质量候选：

| 候选 | 审查 revision | 结论 |
| --- | --- | --- |
| [SAM2 Hiera-T](https://github.com/facebookresearch/sam2/tree/2b90b9f5ceec907a1c18123530e92e794ad901a4) | `2b90b9f5ceec907a1c18123530e92e794ad901a4` | 采用为第一评测候选；官方模型仓库提供固定 Safetensors 文件。 |
| [MobileSAM](https://github.com/ChaoningZhang/MobileSAM/tree/f706ad9c4eb7f219c00d9050e46328518ffb65d2) | `f706ad9c4eb7f219c00d9050e46328518ffb65d2` | 暂缓；官方使用说明以 `.pt` checkpoint 为主，本轮未找到同等来源的固定 Safetensors 运行清单。 |
| [HQ-SAM](https://github.com/SysCV/sam-hq/tree/e696978d60352dc9a26b12631cd91781502c6546) | `e696978d60352dc9a26b12631cd91781502c6546` | 暂缓；需要额外 checkpoint 组合，当前分发面和依赖面大于首轮评测需要。 |

清单固定模型 revision、上游代码 revision、Apache-2.0 许可来源、五个允许文件的大小与 SHA-256，以及独立评测环境的精确依赖版本。同仓库的 Pickle `.pt` 权重被明确排除；只允许一个 `model.safetensors`，禁止远程代码、自动下载、随发行包分发和产品接入。SAM2 评测使用已经修复已知高危公告的 Transformers 5.10.4，而现有 Florence-2 运行时固定在 4.49 系列，因此真实评测必须使用隔离虚拟环境，不能修改默认 Web 环境。

可重复检查清单：

```bash
make model-supply-chain-review
```

供应链阶段报告中的 `local_files_verified=false` 记录当时尚未下载 156 MB 权重。后续首轮真实评测已经通过显式命令下载并验证五个允许文件；模型和隔离运行环境仍只存在于被 Git 忽略的 `work/` 目录。

## 首轮真实模型结果

固定的 8 样本合同语料已经在 Apple Silicon 的 CPU 与 MPS 路径各运行一次。公开报告只保留脱敏的模型、运行时、指标、耗时和进程峰值常驻内存，不包含本地路径、权重或预测蒙版：

- [`mask-refinement-sam2-mps.json`](benchmarks/mask-refinement-sam2-mps.json) 与 [`mask-refinement-sam2-mps.md`](benchmarks/mask-refinement-sam2-mps.md)
- [`mask-refinement-sam2-cpu.json`](benchmarks/mask-refinement-sam2-cpu.json) 与 [`mask-refinement-sam2-cpu.md`](benchmarks/mask-refinement-sam2-cpu.md)

两条路径均通过 8 样本/4 负例/8 类别证据门禁，但都没有通过指标门禁：MPS 的 Precision/Recall/IoU 为 0.228/0.917/0.223，CPU 为 0.231/0.981/0.230。四个正例中时间戳、印章和签名细化明显优于直接使用候选框；半透明文字仍不稳定。四个负例都会因为候选框提示产生对象蒙版，说明 SAM2 只能细化边界，不能判断候选本身是否应删除。

固定仓库的源配置类型是 `sam2_video`，图像评测按 Transformers 官方图像 API 加载为 `Sam2Model`。运行时会要求 checkpoint 的 missing、unexpected、mismatched keys 和加载错误全部为 0，并把结果写入报告；上游类型提示不能被静默忽略。

预测在适配器边界被裁剪到已验证候选框，因此框外像素保持为 0。CPU 与 MPS 的像素结果略有差异，必须继续按设备分别报告。首样本包含模型暖机成本；`peak_memory_mb` 是进程截至该样本的峰值常驻内存，而不是单次增量。

当前结论保持 `release_claim_allowed=false`：指标门禁失败，且尚无三条人工工作流计时。真实模型结果不会进入 Web，也不会改变手工流程。

## 独立实景成对语料

第二轮评测复用仓库中已经固定来源与摘要的 NASA、Wikimedia 实景照片，形成 16 个独立来源、32 个样本。每个来源包含一张仓库生成水印的正例和一张同图同候选框的干净负例；正例真值由成对 RGB 像素差异生成，负例真值为空。审计会拒绝缺少公开 HTTPS 来源、使用条款、许可、署名、原图摘要、转换记录、标注方法或成对一致性的样本，也会拒绝包含用户数据的声明。

- [`mask-refinement-photo-contract.json`](benchmarks/mask-refinement-photo-contract.json) 与 [`mask-refinement-photo-contract.md`](benchmarks/mask-refinement-photo-contract.md) 验证语料、指标实现和来源门禁，不代表模型性能。
- [`mask-refinement-sam2-photo-mps.json`](benchmarks/mask-refinement-sam2-photo-mps.json) 与 [`mask-refinement-sam2-photo-mps.md`](benchmarks/mask-refinement-sam2-photo-mps.md) 记录 MPS 真实输出。
- [`mask-refinement-sam2-photo-cpu.json`](benchmarks/mask-refinement-sam2-photo-cpu.json) 与 [`mask-refinement-sam2-photo-cpu.md`](benchmarks/mask-refinement-sam2-photo-cpu.md) 记录 CPU 真实输出。

MPS 的 Precision/Recall/IoU 为 0.515/0.911/0.490，CPU 为 0.580/0.978/0.573。两条路径均通过 32 样本、16 负例、4 类别、16 独立来源及成对一致性门禁，但指标门禁失败：16 个干净负例仍会被候选框提示为对象蒙版。该结果在更多真实背景上确认了首轮结论，SAM2 可以细化已经确认的水印边界，却不能判断候选是否应该删除。

由于指标门禁已经失败，本阶段不填造或提前收集人工计时。人工盲测需要实际参与者按统一流程完成；在候选拒绝门禁使精度达到阈值前，计时结果也不能改变发布结论。

## Florence-2 候选确认门禁

候选拒绝实验复用了已经固定 revision、提示词和真实输出的 Florence-2 定位结果。门禁要求定位框与外部候选框的 IoU 至少为 0.5，达到阈值后才采用 SAM2 蒙版；该阈值与现有定位基准一致，没有针对本轮结果重新调参。公开的脱敏原始定位输入见 [`vlm-photo-gated-predictions.json`](benchmarks/vlm-photo-gated-predictions.json)。

在 16 对固定实景样本上，门禁接受 15 个水印正例、拒绝全部 16 个干净同框负例，并漏掉 1 个水印正例；候选级 Precision 为 1.000，Recall 为 0.938。组合后的像素结果为：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.958 | 0.823 | 0.795 | 0.846 | 通过 |
| CPU | 0.919 | 0.883 | 0.819 | 0.858 | 通过 |

完整报告见：

- [`mask-refinement-candidate-gate-mps.json`](benchmarks/mask-refinement-candidate-gate-mps.json) 与 [`mask-refinement-candidate-gate-mps.md`](benchmarks/mask-refinement-candidate-gate-mps.md)；
- [`mask-refinement-candidate-gate-cpu.json`](benchmarks/mask-refinement-candidate-gate-cpu.json) 与 [`mask-refinement-candidate-gate-cpu.md`](benchmarks/mask-refinement-candidate-gate-cpu.md)。

该实验适用于确认人工或其他来源给出的候选框。若候选框本身也由同一次 Florence-2 推理生成，则这不是独立的二次确认，不能据此推断相同的拒绝能力。当前结果来自开发语料，尚需独立留出语料复核；人工计时门禁仍为失败，`release_claim_allowed=false`，组合模型不会进入 Web。

可用已有真实模型输出复现组合评分，不会下载权重或重新推理：

```bash
make mask-refinement-candidate-gate-mps
make mask-refinement-candidate-gate-cpu
```

## 下一阶段

真实模型接入前仍需完成：

1. 用独立留出实景语料复核 Florence-2 候选确认门禁，避免把开发语料结果当成泛化证据；
2. 留出语料的候选与像素指标达到阈值后，再由人工完成“纯手工”“VLM 框”“VLM + 分割”三条路径的盲测计时；
3. 在至少一种 CUDA 环境复跑相同固定 revision，记录耗时、峰值内存和像素差异；
4. 只有真实模型指标、证据和计时门禁全部通过后，才评估是否作为默认关闭的可编辑蒙版建议接入 Web。
