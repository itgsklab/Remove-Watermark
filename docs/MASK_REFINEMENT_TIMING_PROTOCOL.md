# 蒙版细化人工盲测计时协议

本协议用于比较三种图片水印蒙版工作流的实际人工操作时间。它只用于离线评测，不会把
模型入口接入正式 Web 产品，也不会自动下载模型权重。

## 固定实验设计

使用第四套独立确认集中的 8 个正样本。每名参与者完成 24 个任务，每个样本分别使用：

1. `manual`：从空蒙版开始，完全手工绘制；
2. `box`：以 Florence-2 确认后的候选框作为初始蒙版，再由人工修正；
3. `refined`：以固定 Florence-2 + SAM2 + 文字局部对比度 + 候选包含关系策略产生的蒙版
   作为初始蒙版，再由人工修正。

任务由种子确定的三分块平衡顺序生成。相同图片不会连续出现，每个样本在三个分块中各
使用一次工作流。执行界面只能显示“方案 A/B/C”，不能向参与者显示工作流名称、像素真值、
模型指标或预期结果。

计时在图片和初始蒙版完整可见时开始，在参与者确认最终可用蒙版时停止。`total_seconds`
记录全部任务时间，`correction_seconds` 记录主动编辑蒙版的时间。无法得到可用蒙版时必须
标记 `failed` 并从“无法得到可用蒙版、编辑器异常、超时、其他”四个固定原因中选择，不能
删除失败试次。结果不保存自由文本，避免把姓名、路径或其他私人信息带入公开汇总。

## 冻结门禁

- 至少 3 名不同参与者；
- 至少 8 个三工作流均完成的配对样本；
- 每种工作流的失败率不超过 10%；
- `refined` 总时间中位数不超过 `manual` 的 75%；
- `refined` 总时间中位数不超过 `box` 的 90%。

门禁在采集数据前固定。未达到任一条件时，`timing_gate=fail`，不得据此宣称模型工作流
可以发布或进入 Web 产品。

## 准备匿名会话

参与者代码应使用实验现场分配的随机代码，不得使用姓名、邮箱、系统账户名或 GitHub
用户名。工具只保存参与者代码的单向摘要。会话与原始计时结果保存在被 Git 忽略的
`work/` 目录，不应提交公开仓库。

现场采集优先使用协调工具。它使用密码学随机参与者代码和种子建立私有目录，将目录与文件
权限限制为当前系统用户可读写，并且不会把原始参与者代码写入磁盘：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing_collect new \
  --manifest tests/fixtures/mask_refinement_confirmation_fourth/manifest.json \
  --refined-predictions ../work/mask-refinement-confirmation-fourth/gated-mps/predictions.json \
  --root ../work/mask-refinement-timing/participants
```

命令只输出匿名参与者 ID、会话路径和结果路径。为参与者启动界面时，把输出路径传给下一节
的本地计时界面。每名真实参与者只建立一个会话，不要预填或复制计时结果。

以下手工命令只用于需要固定种子复现会话生成的情况：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing prepare \
  --manifest tests/fixtures/mask_refinement_confirmation_fourth/manifest.json \
  --refined-predictions ../work/mask-refinement-confirmation-fourth/gated-mps/predictions.json \
  --participant-code operator-01 \
  --seed 20261021 \
  --session ../work/mask-refinement-timing/operator-01/session.json \
  --results ../work/mask-refinement-timing/operator-01/results.json
```

不要手工编辑 `session.json` 或 `results.json`。启动独立的本地计时界面：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing_ui \
  --manifest tests/fixtures/mask_refinement_confirmation_fourth/manifest.json \
  --refined-predictions ../work/mask-refinement-confirmation-fourth/gated-mps/predictions.json \
  --session ../work/mask-refinement-timing/operator-01/session.json \
  --results ../work/mask-refinement-timing/operator-01/results.json \
  --port 8776
```

随后在同一台电脑打开 `http://127.0.0.1:8776/`。页面只显示方案 A/B/C，不显示工作流
名称、样本 ID、像素真值或模型指标。图片与初始蒙版完整加载后由服务器开始总计时；页面
累计每次画笔按下到抬起之间的主动修正时间。每次确认或失败后结果立即原子写入本机，刷新
页面可继续尚未完成的任务，已经完成的试次不能从页面修改。

计时服务只监听环回地址，启动时重新验证会话、确认集、MPS 预测文件和每个图片/蒙版摘要。
任一文件变化都会拒绝启动。界面不会接入正式产品路由，也不发送网络请求到本机之外。

## 审计真实结果

采集过程中可以查看匿名完成进度，不会输出工作流、样本或计时值：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing_collect status \
  --root ../work/mask-refinement-timing/participants
```

收集至少三套真实结果后，优先对采集目录整体审计。只要其中存在未完成会话，命令就会拒绝
生成报告，避免静默排除失败或中断的参与者：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing_collect audit \
  --root ../work/mask-refinement-timing/participants \
  --report-json ../work/mask-refinement-timing/report.json \
  --report-md ../work/mask-refinement-timing/report.md
```

也可以显式列出每组会话与结果：

```bash
cd backend
.venv/bin/python -m wmrm.benchmarks.mask_refinement_timing audit \
  --pair ../work/mask-refinement-timing/operator-01/session.json:../work/mask-refinement-timing/operator-01/results.json \
  --pair ../work/mask-refinement-timing/operator-02/session.json:../work/mask-refinement-timing/operator-02/results.json \
  --pair ../work/mask-refinement-timing/operator-03/session.json:../work/mask-refinement-timing/operator-03/results.json \
  --report-json ../work/mask-refinement-timing/report.json \
  --report-md ../work/mask-refinement-timing/report.md
```

审计器要求每个任务恰好出现一次，校验会话摘要、参与者去重、语料一致性、计时范围、失败
原因和固定门禁。公开报告前应再次确认报告只含匿名参与者 ID，不含原始自由文本或本机路径。
