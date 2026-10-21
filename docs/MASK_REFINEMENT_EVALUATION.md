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

## 独立留出集结果

为了避免把开发语料结果误当成泛化证据，项目在模型推理前冻结了 8 个全新 NASA 来源组成的 16 个成对样本。构建器强制检查来源组与开发集交集为零，并固定官方记录页、资产 URL、使用条款、SHA-256、转换方式和精确像素差异真值。合同报告见 [`mask-refinement-holdout-contract.json`](benchmarks/mask-refinement-holdout-contract.json) 与 [`mask-refinement-holdout-contract.md`](benchmarks/mask-refinement-holdout-contract.md)。

相同的 Florence-2、SAM2 revision、`watermark` 提示词和 IoU 0.5 候选门禁没有重新调参。候选级门禁拒绝 8/8 个干净负例，接受 7/8 个水印正例，Precision 为 1.000、Recall 为 0.875；漏检样本的最佳定位 IoU 为 0.274。像素级组合结果没有通过预先设定的门禁：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.937 | 0.673 | 0.643 | 0.730 | 失败 |
| CPU | 0.855 | 0.801 | 0.705 | 0.758 | 失败 |

完整报告见：

- [`mask-refinement-holdout-gate-mps.json`](benchmarks/mask-refinement-holdout-gate-mps.json) 与 [`mask-refinement-holdout-gate-mps.md`](benchmarks/mask-refinement-holdout-gate-mps.md)；
- [`mask-refinement-holdout-gate-cpu.json`](benchmarks/mask-refinement-holdout-gate-cpu.json) 与 [`mask-refinement-holdout-gate-cpu.md`](benchmarks/mask-refinement-holdout-gate-cpu.md)；
- 脱敏的 Florence-2 原始输出见 [`mask-refinement-holdout-florence2-predictions.json`](benchmarks/mask-refinement-holdout-florence2-predictions.json)。

留出结果说明候选拒绝在这批新来源上没有产生误接受，但 SAM2 对不同背景和半透明文字的像素边界仍不稳定。该留出集不会被用于回调阈值；本阶段停止在失败证据，不执行人工计时，也不接入 Web。

复现语料合同与真实评测：

```bash
make mask-refinement-holdout-corpus
make mask-refinement-holdout-localization
make mask-refinement-holdout-model-mps
make mask-refinement-holdout-model-cpu
make mask-refinement-holdout-gate-mps
make mask-refinement-holdout-gate-cpu
```

## 多候选蒙版开发实验

冻结留出集失败后，项目只在原 16 来源开发语料上研究 SAM2 的多候选输出。新策略要求
SAM2 为每个候选框输出三个蒙版，并直接选择模型预测 IoU 最高的一项；选择过程不读取像素
真值，也不改变 Florence-2 的 `watermark` 提示词或 IoU 0.5 候选确认阈值。默认单蒙版
行为保持不变，该模式仅能通过显式评测参数启用。

开发语料结果为：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.942 | 0.848 | 0.806 | 0.852 | 通过 |
| CPU | 0.924 | 0.887 | 0.826 | 0.865 | 通过 |

完整报告见：

- [`mask-refinement-multimask-candidate-gate-mps.json`](benchmarks/mask-refinement-multimask-candidate-gate-mps.json) 与 [`mask-refinement-multimask-candidate-gate-mps.md`](benchmarks/mask-refinement-multimask-candidate-gate-mps.md)；
- [`mask-refinement-multimask-candidate-gate-cpu.json`](benchmarks/mask-refinement-multimask-candidate-gate-cpu.json) 与 [`mask-refinement-multimask-candidate-gate-cpu.md`](benchmarks/mask-refinement-multimask-candidate-gate-cpu.md)。

这些结果只证明新策略在开发数据上达到像素阈值。此前冻结的留出集不会在本阶段重跑或
用于选择策略；人工计时仍为空，`release_claim_allowed=false`，Web 产品没有新增模型入口。

可在已有固定权重和隔离环境中复现：

```bash
make mask-refinement-multimask-mps
make mask-refinement-multimask-cpu
```

## 第二确认集结果

在多候选策略冻结后，项目从 NASA 官方图片库固定了 8 个全新来源，生成 16 个正负成对
样本。构建器同时校验来源组和原图 SHA-256 与开发语料、第一留出集均无交集。语料及真值
先以独立提交冻结，再运行固定的 Florence-2 revision、`watermark` 提示词、IoU 0.5 候选
门禁和 SAM2 `highest-iou` 策略。

候选门禁拒绝 8/8 个干净负例，接受 7/8 个水印正例，Precision 为 1.000、Recall 为
0.875。漏检样本的最佳定位 IoU 为 0.279。像素结果为：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.955 | 0.756 | 0.730 | 0.798 | 失败 |
| CPU | 0.877 | 0.794 | 0.714 | 0.770 | 失败 |

完整证据见：

- [`mask-refinement-confirmation-contract.json`](benchmarks/mask-refinement-confirmation-contract.json) 与 [`mask-refinement-confirmation-contract.md`](benchmarks/mask-refinement-confirmation-contract.md)；
- [`mask-refinement-confirmation-gate-mps.json`](benchmarks/mask-refinement-confirmation-gate-mps.json) 与 [`mask-refinement-confirmation-gate-mps.md`](benchmarks/mask-refinement-confirmation-gate-mps.md)；
- [`mask-refinement-confirmation-gate-cpu.json`](benchmarks/mask-refinement-confirmation-gate-cpu.json) 与 [`mask-refinement-confirmation-gate-cpu.md`](benchmarks/mask-refinement-confirmation-gate-cpu.md)；
- 脱敏的 Florence-2 原始输出见 [`mask-refinement-confirmation-florence2-predictions.json`](benchmarks/mask-refinement-confirmation-florence2-predictions.json)。

确认集像素门禁失败，因此本阶段停止，不收集人工计时，也不接入 Web。该语料不会被用于
回调候选阈值、提示词或蒙版选择策略。

复现命令：

```bash
make mask-refinement-confirmation-corpus
make mask-refinement-confirmation-localization
make mask-refinement-confirmation-model-mps
make mask-refinement-confirmation-model-cpu
make mask-refinement-confirmation-gate-mps
make mask-refinement-confirmation-gate-cpu
```

## 文字局部对比度开发实验

第二确认失败后，两个确认集均保持冻结。本轮只在原开发语料上测试一个确定性文字补充
策略：候选框长宽比至少为 5:1 时，用半径 1.5 的高斯模糊估计局部背景；任一 RGB 通道与
背景差值至少为 20 的像素会与 SAM2 蒙版合并。该步骤只读取输入图片和候选框，不读取
标注；普通角标不触发该规则。开发时比较了半径 1.0–3.0 和差值 12–24 的小型固定网格，
选择在 MPS、CPU 间表现均衡的 1.5/20 组合。

固定开发语料结果为：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.931 | 0.880 | 0.826 | 0.865 | 通过 |
| CPU | 0.913 | 0.897 | 0.827 | 0.864 | 通过 |

完整报告见：

- [`mask-refinement-text-contrast-candidate-gate-mps.json`](benchmarks/mask-refinement-text-contrast-candidate-gate-mps.json) 与 [`mask-refinement-text-contrast-candidate-gate-mps.md`](benchmarks/mask-refinement-text-contrast-candidate-gate-mps.md)；
- [`mask-refinement-text-contrast-candidate-gate-cpu.json`](benchmarks/mask-refinement-text-contrast-candidate-gate-cpu.json) 与 [`mask-refinement-text-contrast-candidate-gate-cpu.md`](benchmarks/mask-refinement-text-contrast-candidate-gate-cpu.md)。

该阶段只拥有开发证据，且没有在此前两个确认集上重跑。后续第三确认结果见下一节；人工
计时为空，`release_claim_allowed=false`，Web 产品行为不变。

```bash
make mask-refinement-text-contrast-mps
make mask-refinement-text-contrast-cpu
```

## 第三确认集结果

文字局部对比度策略冻结后，项目从 NASA 官方图片库固定了第三组 8 个新来源，生成 16 个
正负成对样本。语料在模型运行前以独立提交冻结，构建器强制检查来源组和原图 SHA-256
与开发语料、第一留出集及第二确认集的全部 32 个来源无交集。

固定的 Florence-2 `watermark` 提示词和 IoU 0.5 候选门禁拒绝 8/8 个干净负例，接受
7/8 个水印正例；Precision 为 1.000、Recall 为 0.875。漏检角标的最佳定位 IoU 为
0.274。SAM2 多候选与文字局部对比度组合结果为：

| 设备 | Precision | Recall | IoU | 修正量减少 | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | --- |
| MPS | 0.908 | 0.770 | 0.714 | 0.777 | 失败 |
| CPU | 0.872 | 0.802 | 0.718 | 0.772 | 失败 |

完整证据见：

- [`mask-refinement-confirmation-third-contract.json`](benchmarks/mask-refinement-confirmation-third-contract.json) 与 [`mask-refinement-confirmation-third-contract.md`](benchmarks/mask-refinement-confirmation-third-contract.md)；
- [`mask-refinement-confirmation-third-gate-mps.json`](benchmarks/mask-refinement-confirmation-third-gate-mps.json) 与 [`mask-refinement-confirmation-third-gate-mps.md`](benchmarks/mask-refinement-confirmation-third-gate-mps.md)；
- [`mask-refinement-confirmation-third-gate-cpu.json`](benchmarks/mask-refinement-confirmation-third-gate-cpu.json) 与 [`mask-refinement-confirmation-third-gate-cpu.md`](benchmarks/mask-refinement-confirmation-third-gate-cpu.md)；
- 脱敏 Florence-2 输出见 [`mask-refinement-confirmation-third-florence2-predictions.json`](benchmarks/mask-refinement-confirmation-third-florence2-predictions.json)。

确认指标失败，因此第三确认集保持冻结，不回调提示词、候选阈值或蒙版规则；人工计时与
Web 接入继续停止。

```bash
make mask-refinement-confirmation-third-corpus
make mask-refinement-confirmation-third-localization
make mask-refinement-confirmation-third-model-mps
make mask-refinement-confirmation-third-model-cpu
make mask-refinement-confirmation-third-gate-mps
make mask-refinement-confirmation-third-gate-cpu
```

## 候选包含关系开发实验

第三确认失败后，三套确认语料保持冻结。本轮只检查原开发集的候选定位行为。唯一漏检的
角标并非没有定位结果：Florence-2 检测框完全位于候选框内部，但检测面积只占候选面积
0.269，导致传统框 IoU 同为 0.269，低于 0.5 门槛。

新增的显式评测策略继续接受 IoU 至少 0.5 的匹配；否则只有检测框至少 90% 被候选框
包含、且检测面积至少占候选面积 15% 时才接受。面积下限阻止极小内部噪点直接通过。
默认 `iou` 策略保持不变，Web 产品也不调用新策略。

固定开发语料结果为：

| 设备 | 候选 Precision | 候选 Recall | 像素 Precision | 像素 Recall | 像素 IoU | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| MPS | 1.000 | 1.000 | 0.937 | 0.973 | 0.914 | 通过 |
| CPU | 1.000 | 1.000 | 0.921 | 0.993 | 0.915 | 通过 |

16 个正例全部接受，16 个干净负例全部拒绝；只有既有漏检样本通过新增包含关系分支。
完整报告见：

- [`mask-refinement-contained-detection-mps.json`](benchmarks/mask-refinement-contained-detection-mps.json) 与 [`mask-refinement-contained-detection-mps.md`](benchmarks/mask-refinement-contained-detection-mps.md)；
- [`mask-refinement-contained-detection-cpu.json`](benchmarks/mask-refinement-contained-detection-cpu.json) 与 [`mask-refinement-contained-detection-cpu.md`](benchmarks/mask-refinement-contained-detection-cpu.md)。

```bash
make mask-refinement-contained-detection-mps
make mask-refinement-contained-detection-cpu
```

## 第四确认集结果

候选包含关系策略冻结后，项目在任何模型推理前固定了第四组 8 个 NASA 官方来源和 16 个
成对样本。来源组和原图 SHA-256 与开发集及此前三套确认集的全部 40 个来源无交集。

固定策略只运行一次：Florence-2 使用 `watermark` 提示词，SAM2 使用模型预测 IoU 最高
的蒙版和既定文字局部对比度规则；候选匹配保留 IoU 0.5，并使用 90% 包含率与 15% 面积
下限。8/8 个正例接受，8/8 个干净负例拒绝。只有一个角标通过新增包含关系分支，其传统
IoU 为 0.269；其余七个正例由原 IoU 规则通过。

| 设备 | 候选 Precision | 候选 Recall | 像素 Precision | 像素 Recall | 像素 IoU | 指标门禁 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| MPS | 1.000 | 1.000 | 0.943 | 0.909 | 0.861 | 通过 |
| CPU | 1.000 | 1.000 | 0.914 | 0.995 | 0.910 | 通过 |

完整证据见：

- [`mask-refinement-confirmation-fourth-contract.json`](benchmarks/mask-refinement-confirmation-fourth-contract.json) 与 [`mask-refinement-confirmation-fourth-contract.md`](benchmarks/mask-refinement-confirmation-fourth-contract.md)；
- [`mask-refinement-confirmation-fourth-gate-mps.json`](benchmarks/mask-refinement-confirmation-fourth-gate-mps.json) 与 [`mask-refinement-confirmation-fourth-gate-mps.md`](benchmarks/mask-refinement-confirmation-fourth-gate-mps.md)；
- [`mask-refinement-confirmation-fourth-gate-cpu.json`](benchmarks/mask-refinement-confirmation-fourth-gate-cpu.json) 与 [`mask-refinement-confirmation-fourth-gate-cpu.md`](benchmarks/mask-refinement-confirmation-fourth-gate-cpu.md)；
- 脱敏 Florence-2 输出见 [`mask-refinement-confirmation-fourth-florence2-predictions.json`](benchmarks/mask-refinement-confirmation-fourth-florence2-predictions.json)。

```bash
make mask-refinement-confirmation-fourth-corpus
make mask-refinement-confirmation-fourth-localization
make mask-refinement-confirmation-fourth-model-mps
make mask-refinement-confirmation-fourth-model-cpu
make mask-refinement-confirmation-fourth-gate-mps
make mask-refinement-confirmation-fourth-gate-cpu
```

确认指标已经通过，但人工计时证据仍为空，`release_claim_allowed=false`，Web 产品行为不变。

## 人工盲测协议冻结

在收集人工数据前，项目固定了 `wmrm-mask-refinement-human-timing-v1` 协议及门禁。协议从
第四确认集选取 8 个正样本，每名参与者完成纯手工、候选框和模型细化共 24 个任务；三分块
平衡顺序避免同一图片连续出现，并让每个样本完整覆盖三种工作流。

新增命令为匿名参与者生成带摘要的会话与结果模板，并审计任务完整性、重复参与者、语料一致
性、耗时范围和失败原因。公开协议基线见
[`mask-refinement-timing-protocol.json`](benchmarks/mask-refinement-timing-protocol.json) 与
[`mask-refinement-timing-protocol.md`](benchmarks/mask-refinement-timing-protocol.md)，执行说明见
[`MASK_REFINEMENT_TIMING_PROTOCOL.md`](MASK_REFINEMENT_TIMING_PROTOCOL.md)。当前参与者和试次
均为 0，计时及发布门禁继续失败；没有生成或填造人工结果。

协议配套界面独立运行于 `127.0.0.1`，不挂载到正式 Web 产品。它在图片和初始建议加载完成
后启动服务器总计时，累计画笔主动修正时间，并逐任务原子保存。界面向参与者只显示方案
A/B/C，不暴露工作流名称、样本 ID、真值或模型指标；启动和提供素材前均重新校验冻结摘要。

现场协调工具使用随机代码和随机种子建立权限受限的匿名目录，不持久化原始代码；状态命令
只显示匿名 ID 与完成数量，整体审计会在任一会话未完成时失败，避免挑选性排除中断数据。

## 下一阶段

真实模型接入前仍需完成：

1. 已冻结三类工作流的匿名盲测协议、顺序生成器、结果模板和审计门禁；按
   [`MASK_REFINEMENT_TIMING_PROTOCOL.md`](MASK_REFINEMENT_TIMING_PROTOCOL.md) 组织至少三名
   真实参与者完成计时，记录总耗时、修正耗时和失败原因；
2. 人工计时通过前保持 `release_claim_allowed=false`，不接入 Web；所有确认语料继续冻结；
3. 在至少一种 CUDA 环境复跑固定 revision，记录耗时、峰值内存和像素差异；
4. 只有真实模型指标、证据和计时门禁全部通过后，才评估是否作为默认关闭的可编辑蒙版建议接入 Web。
