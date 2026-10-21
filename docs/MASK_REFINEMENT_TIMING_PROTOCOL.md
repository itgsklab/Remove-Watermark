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
标记 `failed` 并填写失败原因，不能删除失败试次。

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

操作员按照 `session.json` 的顺序执行任务，并在 `results.json` 中填写总耗时、修正耗时、
完成状态和失败原因。不得编辑会话文件；其摘要变化会导致审计失败。

## 审计真实结果

收集至少三套真实结果后运行：

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
