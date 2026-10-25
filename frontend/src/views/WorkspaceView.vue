<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ApiError,
  cancelTask,
  createAnalysis,
  createTask,
  getAsset,
  getCapabilities,
  getRuntimeDiagnostics,
  getTask,
  previewImageMasks,
  previewRedactions,
  renderImageMaskPreview,
  suggestImageMasks,
  type Analysis,
  type ImageMaskPreview,
  type ImageMaskPolygon,
  type ImageMaskRegion,
  type PlanWarning,
  type ProcessingTask,
  type RedactionPreview,
  type RedactionRegion,
  type RuntimeDiagnostics,
  validateImagePlan,
  validatePlan,
  validateRedactionPlan,
} from '@/api/client'
import { useWorkspaceStore } from '@/stores/workspace'
import ImageMaskEditor from '@/components/ImageMaskEditor.vue'
import PdfRegionEditor from '@/components/PdfRegionEditor.vue'

const route = useRoute()
const store = useWorkspaceStore()
const analysis = ref<Analysis | null>(null)
const watermarkText = ref('')
const pdfPreset = ref<'codecv' | 'general'>('codecv')
const busy = ref(false)
const message = ref('')
const selectedCandidates = ref<string[]>([])
const confirmedAmbiguous = ref<string[]>([])
const planWarnings = ref<PlanWarning[]>([])
const task = ref<ProcessingTask | null>(null)
const redactionPreview = ref<RedactionPreview | null>(null)
const redactionPage = ref(1)
const redactionX0 = ref(0)
const redactionY0 = ref(0)
const redactionX1 = ref(100)
const redactionY1 = ref(100)
const redactionRegions = ref<RedactionRegion[]>([])
const confirmedRedactionOverlap = ref(false)
const pdfRegionStrategy = ref<'pymupdf_redaction' | 'raster_inpaint'>('pymupdf_redaction')
const pdfDeepDpi = ref(144)
const pdfDeepRadius = ref(3)
const runtimeDiagnostics = ref<RuntimeDiagnostics | null>(null)
const pdfOcrEnabled = ref(false)
const pdfOcrLanguages = ref<string[]>([])
const ocrDiagnosticsError = ref('')
const confirmedRasterization = ref(false)
interface ImageMaskDraft {
  regions: ImageMaskRegion[]
  polygons: ImageMaskPolygon[]
  protectedRegions: ImageMaskRegion[]
}
interface ImageRadiusPreview {
  radius: number
  url: string
}
const imageMasks = ref<ImageMaskRegion[]>([])
const imagePolygons = ref<ImageMaskPolygon[]>([])
const imageProtectedRegions = ref<ImageMaskRegion[]>([])
const imageMaskPast = ref<ImageMaskDraft[]>([])
const imageMaskFuture = ref<ImageMaskDraft[]>([])
const imageMaskPreview = ref<ImageMaskPreview | null>(null)
const imageRadius = ref(3)
const imageRadiusPreviews = ref<ImageRadiusPreview[]>([])
const imagePreviewBusy = ref(false)
const imagePlanWarnings = ref<PlanWarning[]>([])
const confirmedImageWarnings = ref<string[]>([])
const vlmBusy = ref(false)
const vlmWarnings = ref<string[]>([])
const assetId = computed(() => String(route.params.assetId))
const isDocx = computed(() => store.currentAsset?.kind === 'docx')
const isCodeCvPdf = computed(() => store.currentAsset?.kind === 'pdf')
const isImage = computed(() => ['png', 'jpeg', 'webp'].includes(store.currentAsset?.kind || ''))
const canInspect = computed(() => isDocx.value || isCodeCvPdf.value || isImage.value)
const canProcess = computed(() => (
  isDocx.value || (isCodeCvPdf.value && analysis.value?.preset === 'codecv')
))
const hasObjectCandidates = computed(() => analysis.value?.candidates.some(
  candidate => candidate.allowed_strategies.includes('object'),
) ?? false)
const outputArtifacts = computed(() => (
  task.value?.artifacts.filter(artifact => artifact.role === 'output') || []
))
const imageOutput = computed(() => outputArtifacts.value[0] || null)
const selectedPdfPage = computed(() => (
  analysis.value?.pdf_pages.find(page => page.page_number === redactionPage.value) || null
))
const redactionOverlapCount = computed(() => redactionPreview.value?.regions.reduce(
  (total, region) => total + region.overlaps.length,
  0,
) ?? 0)
const redactionDraftPageCount = computed(() => new Set(
  redactionRegions.value.map(region => region.page_number),
).size)
const canUndoImageMasks = computed(() => imageMaskPast.value.length > 0)
const canRedoImageMasks = computed(() => imageMaskFuture.value.length > 0)
const imageMaskHistoryLimit = 50
const ocrRuntimeReady = computed(() => runtimeDiagnostics.value?.ocr.status === 'ready')
const installedOcrLanguages = computed(() => runtimeDiagnostics.value?.ocr.languages || [])
const ocrSelectionValid = computed(() => (
  !pdfOcrEnabled.value || pdfOcrLanguages.value.length > 0
))

const complexityLabels = {
  low: '低风险',
  review: '建议复核',
  high: '高风险',
} as const
let imagePreviewRequestId = 0

onMounted(async () => {
  try {
    if (!store.capabilities) {
      store.capabilities = await getCapabilities()
    }
    if (store.currentAsset?.id !== assetId.value) {
      store.currentAsset = await getAsset(assetId.value)
    }
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法读取文件信息。'
  }
  if (isCodeCvPdf.value) await loadOcrDiagnostics()
})

onBeforeUnmount(() => clearImageRadiusPreviews())

async function loadOcrDiagnostics() {
  ocrDiagnosticsError.value = ''
  try {
    runtimeDiagnostics.value = await getRuntimeDiagnostics()
    const available = installedOcrLanguages.value
    if (runtimeDiagnostics.value.ocr.status === 'ready' && available.length) {
      pdfOcrLanguages.value = [available.includes('eng') ? 'eng' : available[0]!]
      pdfOcrEnabled.value = true
    } else {
      pdfOcrLanguages.value = []
      pdfOcrEnabled.value = false
    }
  } catch {
    runtimeDiagnostics.value = null
    pdfOcrLanguages.value = []
    pdfOcrEnabled.value = false
    ocrDiagnosticsError.value = '无法读取 OCR 语言包状态；当前计划将不执行 OCR。'
  }
}

async function inspect() {
  if (!canInspect.value) return
  busy.value = true
  message.value = ''
  try {
    analysis.value = await createAnalysis(
      assetId.value,
      watermarkText.value.trim() || null,
      isCodeCvPdf.value ? pdfPreset.value : isImage.value ? 'image' : null,
    )
    selectedCandidates.value = analysis.value.candidates
      .filter(candidate => candidate.classification === 'confirmed')
      .map(candidate => candidate.candidate_id)
    confirmedAmbiguous.value = []
    planWarnings.value = []
    task.value = null
    redactionPreview.value = null
    redactionRegions.value = []
    confirmedRedactionOverlap.value = false
    confirmedRasterization.value = false
    resetImageMasks()
    vlmWarnings.value = []
    const firstPage = analysis.value.pdf_pages[0]
    if (analysis.value.preset === 'general' && firstPage) {
      redactionPage.value = firstPage.page_number
      redactionX0.value = 0
      redactionY0.value = 0
      redactionX1.value = Math.min(100, firstPage.width)
      redactionY1.value = Math.min(100, firstPage.height)
    }
    if (analysis.value.preset === 'image' && analysis.value.image_metadata) {
      const metadata = analysis.value.image_metadata
      message.value = `图片检查完成：${metadata.display_width} × ${metadata.display_height} 像素。`
    } else if (analysis.value.candidates.length) {
      message.value = `发现 ${analysis.value.candidates.length} 个候选。扫描不会修改原文件。`
    } else if (isCodeCvPdf.value && pdfPreset.value === 'codecv') {
      message.value = '没有匹配 CodeCV 平铺水印的完整操作签名。'
    } else if (isCodeCvPdf.value) {
      message.value = '没有发现需要复核的通用 PDF 水印结构。'
    } else {
      message.value = '没有识别到受支持的页眉或页脚 VML 文字、DrawingML 图片候选。'
    }
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '扫描失败。'
  } finally {
    busy.value = false
  }
}

async function processSelection() {
  if (!analysis.value || selectedCandidates.value.length === 0) return
  busy.value = true
  message.value = ''
  planWarnings.value = []
  try {
    const acknowledgements = confirmedAmbiguous.value.map(
      candidateId => `AMBIGUOUS_CANDIDATE:${candidateId}`,
    )
    const plan = await validatePlan(
      analysis.value,
      selectedCandidates.value,
      acknowledgements,
    )
    planWarnings.value = plan.warnings
    if (!plan.valid || !plan.id) {
      message.value = '请确认所有需要复核的候选后再执行。'
      return
    }
    await waitForTask(await createTask(plan.id))
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '创建处理任务失败。'
  } finally {
    busy.value = false
  }
}

async function waitForTask(created: ProcessingTask) {
  task.value = created
  message.value = task.value.stage
  const deadline = Date.now() + 60_000
  while (['queued', 'running', 'cancelling'].includes(task.value.status)) {
    if (Date.now() > deadline) {
      message.value = '任务仍在后台运行，可以稍后刷新任务状态。'
      return
    }
    await new Promise(resolve => window.setTimeout(resolve, 400))
    task.value = await getTask(task.value.id)
    message.value = task.value.stage
  }
  if (task.value.status === 'failed') {
    message.value = task.value.error?.message || '处理失败。'
  } else if (task.value.status === 'cancelled') {
    message.value = '任务已取消，未保留未验证的输出文件。'
  }
}

async function requestCancellation() {
  if (!task.value || !['queued', 'running'].includes(task.value.status)) return
  try {
    task.value = await cancelTask(task.value.id)
    message.value = task.value.stage
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法取消任务。'
  }
}

function classificationLabel(candidate: Analysis['candidates'][number]) {
  if (candidate.kind === 'image' && candidate.allowed_strategies.length === 0) {
    return '图片待复核 · 只读'
  }
  if (candidate.classification === 'confirmed') {
    return analysis.value?.preset === 'general' ? '结构明确' : '与目标匹配'
  }
  if (candidate.classification === 'ambiguous') return '需要复核'
  return '正常内容'
}

function clearAnalysis() {
  analysis.value = null
  selectedCandidates.value = []
  message.value = ''
  redactionPreview.value = null
  redactionRegions.value = []
  confirmedRedactionOverlap.value = false
  resetImageMasks()
}

function updateImageDraft(regions: ImageMaskRegion[], polygons: ImageMaskPolygon[], protectedRegions: ImageMaskRegion[]) {
  if (regions.length > 100 || polygons.length > 32 || protectedRegions.length > 100) {
    reportImageMaskLimit()
    return
  }
  const next = cloneImageDraft({ regions, polygons, protectedRegions })
  if (sameImageDraft(currentImageDraft(), next)) return
  imageMaskPast.value.push(cloneImageDraft(currentImageDraft()))
  if (imageMaskPast.value.length > imageMaskHistoryLimit) imageMaskPast.value.shift()
  imageMaskFuture.value = []
  applyImageDraft(next)
  clearImageMaskPreview()
}

function undoImageMasks() {
  const previous = imageMaskPast.value.pop()
  if (!previous) return
  imageMaskFuture.value.push(cloneImageDraft(currentImageDraft()))
  applyImageDraft(previous)
  clearImageMaskPreview()
  message.value = `已撤销编辑，当前有 ${imageMasks.value.length} 个蒙版、${imageProtectedRegions.value.length} 个保护区。`
}

function redoImageMasks() {
  const next = imageMaskFuture.value.pop()
  if (!next) return
  imageMaskPast.value.push(cloneImageDraft(currentImageDraft()))
  applyImageDraft(next)
  clearImageMaskPreview()
  message.value = `已重做编辑，当前有 ${imageMasks.value.length} 个蒙版、${imageProtectedRegions.value.length} 个保护区。`
}

function resetImageMasks() {
  imageMasks.value = []
  imagePolygons.value = []
  imageProtectedRegions.value = []
  imageMaskPast.value = []
  imageMaskFuture.value = []
  clearImageMaskPreview()
}

function clearImageMaskPreview() {
  imageMaskPreview.value = null
  imagePlanWarnings.value = []
  confirmedImageWarnings.value = []
  clearImageRadiusPreviews()
}

function clearImageRadiusPreviews() {
  imagePreviewRequestId += 1
  for (const preview of imageRadiusPreviews.value) URL.revokeObjectURL(preview.url)
  imageRadiusPreviews.value = []
  imagePreviewBusy.value = false
}

function currentImageDraft(): ImageMaskDraft {
  return { regions: imageMasks.value, polygons: imagePolygons.value, protectedRegions: imageProtectedRegions.value }
}

function cloneImageDraft(draft: ImageMaskDraft): ImageMaskDraft {
  return {
    regions: draft.regions.map(region => ({ ...region })),
    polygons: draft.polygons.map(polygon => ({
      ...polygon,
      points: polygon.points.map(point => ({ ...point })),
    })),
    protectedRegions: draft.protectedRegions.map(region => ({ ...region })),
  }
}

function applyImageDraft(draft: ImageMaskDraft) {
  const copy = cloneImageDraft(draft)
  imageMasks.value = copy.regions
  imagePolygons.value = copy.polygons
  imageProtectedRegions.value = copy.protectedRegions
}

function sameImageRegions(left: ImageMaskRegion[], right: ImageMaskRegion[]) {
  return left.length === right.length && left.every((region, index) => {
    const other = right[index]
    return other !== undefined
      && region.x0 === other.x0
      && region.y0 === other.y0
      && region.x1 === other.x1
      && region.y1 === other.y1
      && region.transform_id === other.transform_id
  })
}

function sameImageDraft(left: ImageMaskDraft, right: ImageMaskDraft) {
  return sameImageRegions(left.regions, right.regions)
    && JSON.stringify(left.polygons) === JSON.stringify(right.polygons)
    && sameImageRegions(left.protectedRegions, right.protectedRegions)
}

function reportImageMaskLimit() {
  message.value = '一个图片草稿最多包含 100 个矩形蒙版、32 个多边形和 100 个保护区片段。'
}

async function requestVlmSuggestions() {
  if (!analysis.value || !store.capabilities?.vlm_localization.available) return
  vlmBusy.value = true
  message.value = ''
  vlmWarnings.value = []
  try {
    const result = await suggestImageMasks(analysis.value)
    vlmWarnings.value = result.warnings
    if (result.status === 'suggested') {
      updateImageDraft(result.regions, [], [])
      message.value = `本地模型提出 ${result.regions.length} 个候选区域。请逐个检查、调整并验证蒙版。`
    } else if (result.status === 'photo_gate_rejected') {
      message.value = '图片未通过照片场景门禁，模型没有运行；请继续手工框选。'
    } else {
      message.value = '本地模型没有提出候选区域；请继续手工框选。'
    }
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '本地模型候选建议失败，请继续手工框选。'
  } finally {
    vlmBusy.value = false
  }
}

async function previewImageMaskRisk() {
  if (!analysis.value || imageMasks.value.length + imagePolygons.value.length === 0) return
  busy.value = true
  message.value = ''
  try {
    imageMaskPreview.value = await previewImageMasks(
      analysis.value,
      imageMasks.value,
      imagePolygons.value,
      imageProtectedRegions.value,
    )
    const risk = complexityLabels[imageMaskPreview.value.complexity.level]
    const selection = imageMaskPreview.value.selection_risk.level === 'review'
      ? '，选区需要确认'
      : ''
    message.value = `蒙版草稿有效，覆盖图片面积的 ${(imageMaskPreview.value.coverage_ratio * 100).toFixed(2)}%，背景复杂度为${risk}${selection}。`
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法验证图片蒙版。'
  } finally {
    busy.value = false
  }
}

async function compareImageRadii() {
  if (!analysis.value || !imageMaskPreview.value?.executable) return
  const requestId = ++imagePreviewRequestId
  imagePreviewBusy.value = true
  message.value = ''
  const requestedRadius = Number(imageRadius.value)
  const selectedRadius = Number.isFinite(requestedRadius)
    ? Math.max(1, Math.min(10, Math.round(requestedRadius)))
    : 3
  const radii = [...new Set([1, selectedRadius, 7])].sort((left, right) => left - right)
  try {
    const rendered = await Promise.all(radii.map(async radius => ({
      radius,
      blob: await renderImageMaskPreview(
        analysis.value!,
        imageMasks.value,
        imagePolygons.value,
        imageProtectedRegions.value,
        radius,
      ),
    })))
    if (requestId !== imagePreviewRequestId) return
    for (const preview of imageRadiusPreviews.value) URL.revokeObjectURL(preview.url)
    imageRadiusPreviews.value = rendered.map(item => ({
      radius: item.radius,
      url: URL.createObjectURL(item.blob),
    }))
    message.value = `已生成 ${rendered.length} 个临时效果预览；请选择更合适的修复半径。`
  } catch (error) {
    if (requestId !== imagePreviewRequestId) return
    message.value = error instanceof ApiError ? error.message : '无法生成修复半径对比预览。'
  } finally {
    if (requestId === imagePreviewRequestId) imagePreviewBusy.value = false
  }
}

async function processImage() {
  if (!analysis.value || !imageMaskPreview.value?.executable) return
  busy.value = true
  message.value = ''
  try {
    const plan = await validateImagePlan(
      analysis.value,
      imageMasks.value,
      imagePolygons.value,
      imageProtectedRegions.value,
      imageRadius.value,
      confirmedImageWarnings.value,
    )
    imagePlanWarnings.value = plan.warnings
    if (!plan.valid || !plan.id) {
      message.value = '请确认所有高风险提示后再执行图片修复。'
      return
    }
    await waitForTask(await createTask(plan.id))
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '创建图片修复任务失败。'
  } finally {
    busy.value = false
  }
}

function useVisualRegion(region: {
  page_number: number
  x0: number
  y0: number
  x1: number
  y1: number
}) {
  redactionPage.value = region.page_number
  redactionX0.value = Number(region.x0.toFixed(2))
  redactionY0.value = Number(region.y0.toFixed(2))
  redactionX1.value = Number(region.x1.toFixed(2))
  redactionY1.value = Number(region.y1.toFixed(2))
  clearRedactionDraft()
}

function clearRedactionDraft() {
  redactionPreview.value = null
  confirmedRedactionOverlap.value = false
  confirmedRasterization.value = false
}

function currentRedactionRegion(): RedactionRegion | null {
  const page = selectedPdfPage.value
  if (!page) return null
  const values = [redactionX0.value, redactionY0.value, redactionX1.value, redactionY1.value]
  if (
    !values.every(Number.isFinite)
    || redactionX0.value < 0
    || redactionY0.value < 0
    || redactionX1.value > page.width
    || redactionY1.value > page.height
    || redactionX0.value >= redactionX1.value
    || redactionY0.value >= redactionY1.value
  ) return null
  return {
    page_number: page.page_number,
    x0: redactionX0.value,
    y0: redactionY0.value,
    x1: redactionX1.value,
    y1: redactionY1.value,
    transform_id: page.transform_id,
  }
}

function addRedactionRegion() {
  const region = currentRedactionRegion()
  if (!region) {
    message.value = '区域坐标无效或超出当前页面范围。'
    return
  }
  if (redactionRegions.value.length >= 100) {
    message.value = '一个 PDF 计划最多包含 100 个区域。'
    return
  }
  const duplicate = redactionRegions.value.some(item => (
    item.page_number === region.page_number
    && item.x0 === region.x0
    && item.y0 === region.y0
    && item.x1 === region.x1
    && item.y1 === region.y1
  ))
  if (duplicate) {
    message.value = '该区域已经在计划草稿中。'
    return
  }
  redactionRegions.value.push(region)
  clearRedactionDraft()
  message.value = `已加入第 ${region.page_number} 页区域，草稿共 ${redactionRegions.value.length} 项。`
}

function removeRedactionRegion(index: number) {
  redactionRegions.value.splice(index, 1)
  clearRedactionDraft()
  message.value = redactionRegions.value.length
    ? `已移除区域，草稿还剩 ${redactionRegions.value.length} 项。`
    : 'PDF 区域计划草稿已清空。'
}

async function previewRedactionRisk() {
  if (!analysis.value || redactionRegions.value.length === 0) return
  busy.value = true
  message.value = ''
  try {
    redactionPreview.value = await previewRedactions(
      analysis.value,
      redactionRegions.value,
      pdfRegionStrategy.value,
    )
    confirmedRedactionOverlap.value = false
    const count = redactionOverlapCount.value
    message.value = count
      ? `${redactionRegions.value.length} 个区域与 ${count} 个正文或交互对象相交，请检查下方风险。`
      : `${redactionRegions.value.length} 个区域未发现结构重叠；复杂 PDF 仍可能存在未列出的内容。`
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法生成区域风险预览。'
  } finally {
    busy.value = false
  }
}

async function processRedaction() {
  const regions = redactionPreview.value?.regions.map(item => item.region) || []
  if (!analysis.value || !redactionPreview.value?.executable || regions.length === 0) return
  if (pdfRegionStrategy.value === 'raster_inpaint' && !ocrSelectionValid.value) {
    message.value = '请至少选择一个已安装的 OCR 语言包，或关闭 OCR。'
    return
  }
  busy.value = true
  message.value = ''
  try {
    const acknowledgements: string[] = []
    if (confirmedRedactionOverlap.value) acknowledgements.push('PDF_REDACTION_OVERLAP')
    if (confirmedRasterization.value) acknowledgements.push('PDF_RASTERIZATION')
    const plan = await validateRedactionPlan(analysis.value, regions, acknowledgements, {
      strategy: pdfRegionStrategy.value,
      dpi: pdfDeepDpi.value,
      radius: pdfDeepRadius.value,
      ocr_languages: pdfOcrEnabled.value ? pdfOcrLanguages.value.join('+') : null,
    })
    if (!plan.valid || !plan.id) {
      message.value = '请确认区域重叠与处理方式风险后再执行。'
      return
    }
    await waitForTask(await createTask(plan.id))
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '创建 PDF 区域处理任务失败。'
  } finally {
    busy.value = false
  }
}

function sourceLabel(candidate: Analysis['candidates'][number]) {
  const locator = candidate.source_locator
  if (locator.part_name) return locator.part_name
  if (locator.page_numbers.length) return `第 ${locator.page_numbers.join('、')} 页`
  return '未知来源'
}
</script>

<template>
  <section v-if="store.currentAsset" class="workspace-head">
    <p class="eyebrow">文件工作区</p>
    <h1>{{ store.currentAsset.display_name }}</h1>
    <div class="meta-row">
      <span>{{ store.currentAsset.kind.toUpperCase() }}</span>
      <span>{{ (store.currentAsset.size_bytes / 1024).toFixed(1) }} KB</span>
      <span>SHA-256 {{ store.currentAsset.sha256.slice(0, 12) }}…</span>
    </div>
  </section>

  <section v-if="store.currentAsset" class="workspace-grid">
    <article class="panel preview-placeholder">
      <template v-if="isImage">
        <p class="eyebrow">原始图片</p>
        <img
          class="workspace-image-preview"
          :src="`/api/v1/assets/${encodeURIComponent(assetId)}/content`"
          alt="上传的原始图片"
        />
        <p>图片仅在本地服务中预览；检查和框选不会修改原文件。</p>
      </template>
      <template v-else>
        <p class="eyebrow">页面对比</p>
        <h2>处理完成后显示原件与副本</h2>
        <p>页面由本机 LibreOffice 和 Poppler 渲染，用于人工检查水印是否移除及正文布局是否保持。</p>
      </template>
    </article>

    <aside class="panel inspector-panel">
      <h2>扫描水印候选</h2>
      <template v-if="isDocx">
        <label for="watermark-text">目标文字（可选）</label>
        <input
          id="watermark-text"
          v-model="watermarkText"
          type="text"
          maxlength="200"
          placeholder="例如 DRAFT、草稿"
        />
        <p class="hint">同时扫描 DrawingML 嵌入图片；图片候选只供预览和复核，当前不会删除。</p>
        <button :disabled="busy" @click="inspect">{{ busy ? '正在扫描…' : '开始扫描' }}</button>
      </template>
      <template v-else-if="isCodeCvPdf">
        <label for="pdf-preset">扫描模式</label>
        <select id="pdf-preset" v-model="pdfPreset" :disabled="busy" @change="clearAnalysis">
          <option value="codecv">CodeCV 简历预设</option>
          <option value="general">通用 PDF 候选</option>
        </select>
        <template v-if="pdfPreset === 'general'">
          <label for="pdf-watermark-text">目标文字（可选）</label>
          <input
            id="pdf-watermark-text"
            v-model="watermarkText"
            type="text"
            maxlength="200"
            placeholder="例如 DRAFT、草稿"
          />
          <p>扫描重复文字、图片、Form、Pattern、注释和可选内容组。</p>
          <p class="hint">扫描后可框选区域，选择对象级删除或 Deep 栅格修复并生成新 PDF。</p>
        </template>
        <template v-else>
          <p>检查 CodeCV 平铺图案操作签名和对应资源对象。</p>
          <p class="hint">扫描后可选择完整匹配的候选生成新 PDF，原文件不会被覆盖。</p>
        </template>
        <button :disabled="busy" @click="inspect">
          {{ busy ? '正在扫描…' : pdfPreset === 'codecv' ? '扫描 CodeCV 结构' : '扫描通用 PDF' }}
        </button>
      </template>
      <template v-else-if="isImage">
        <p>读取图片尺寸、格式、色彩模式、透明通道、方向、色彩配置和动画帧数。</p>
        <p class="hint">检查完成后可框选多个水印区域并验证蒙版覆盖范围。</p>
        <button :disabled="busy" @click="inspect">
          {{ busy ? '正在检查…' : '检查图片并编辑蒙版' }}
        </button>
      </template>
      <p v-else class="message">该格式已安全保存，候选扫描仍在开发中。</p>
    </aside>
  </section>

  <p v-if="message" class="message status-message" role="status">{{ message }}</p>

  <section v-if="analysis" class="analysis-results">
    <div class="section-heading">
      <div>
        <p class="eyebrow">{{ analysis.preset === 'image' ? '图片检查结果' : '扫描结果' }}</p>
        <h2>{{ analysis.preset === 'image' ? '图片与蒙版' : '候选对象' }}</h2>
      </div>
      <span>{{ analysis.inspected_parts.length }} 个已检查位置</span>
    </div>
    <article v-for="candidate in analysis.candidates" :key="candidate.candidate_id" class="candidate-card">
      <div>
        <figure v-if="candidate.preview_url" class="candidate-image-preview">
          <img :src="candidate.preview_url" :alt="`${candidate.content || 'DrawingML 图片'}候选预览`" />
          <figcaption>DOCX 内嵌图片只读预览</figcaption>
        </figure>
        <label v-if="canProcess && candidate.allowed_strategies.includes('object')" class="candidate-select">
          <input
            v-model="selectedCandidates"
            type="checkbox"
            :value="candidate.candidate_id"
            :disabled="busy || candidate.classification === 'content'"
          />
          选择此候选
        </label>
        <span :class="['candidate-state', candidate.classification]">
          {{ classificationLabel(candidate) }}
        </span>
        <h3>{{ candidate.content || '无法读取文字' }}</h3>
        <p>{{ candidate.evidence }}</p>
        <label
          v-if="candidate.classification === 'ambiguous' && selectedCandidates.includes(candidate.candidate_id)"
          class="risk-confirm"
        >
          <input
            v-model="confirmedAmbiguous"
            type="checkbox"
            :value="candidate.candidate_id"
            :disabled="busy"
          />
          我已核对该对象，确认将它从输出副本中删除
        </label>
      </div>
      <dl>
        <dt>来源</dt><dd>{{ sourceLabel(candidate) }}</dd>
        <template v-if="candidate.source_locator.shape_id">
          <dt>形状 ID</dt><dd>{{ candidate.source_locator.shape_id }}</dd>
        </template>
        <template v-if="candidate.source_locator.drawing_index !== null">
          <dt>绘图序号</dt><dd>{{ candidate.source_locator.drawing_index + 1 }}</dd>
          <dt>图片关系</dt><dd>{{ candidate.source_locator.relationship_id }}</dd>
          <dt>内嵌资源</dt><dd>{{ candidate.source_locator.media_part_name }}</dd>
        </template>
        <template v-if="candidate.source_locator.resource_name">
          <dt>图案资源</dt><dd>{{ candidate.source_locator.resource_name }}</dd>
          <dt>PDF 对象</dt><dd>{{ candidate.source_locator.object_number ?? '直接对象' }}</dd>
        </template>
        <template v-if="candidate.source_locator.annotation_index !== null">
          <dt>注释序号</dt><dd>{{ candidate.source_locator.annotation_index + 1 }}</dd>
        </template>
        <template v-if="candidate.region">
          <dt>PDF 区域</dt>
          <dd>
            {{ candidate.region.approximate ? '约 ' : '' }}
            {{ candidate.region.x0.toFixed(1) }}, {{ candidate.region.y0.toFixed(1) }} →
            {{ candidate.region.x1.toFixed(1) }}, {{ candidate.region.y1.toFixed(1) }}
          </dd>
        </template>
        <template v-if="candidate.overlaps_protected_content">
          <dt>重叠风险</dt><dd>可能覆盖正文，禁止自动处理</dd>
        </template>
        <dt>允许策略</dt><dd>{{ candidate.allowed_strategies.join(' · ') || '只读检查' }}</dd>
      </dl>
    </article>
    <p v-if="analysis.preset !== 'image' && analysis.candidates.length === 0" class="panel empty-candidates">没有候选。此结果不证明文档不存在其他类型水印。</p>
    <p v-for="warning in analysis.warnings" :key="warning" class="warning">{{ warning }}</p>
    <p v-for="warning in planWarnings" :key="warning.code" class="warning">{{ warning.message }}</p>
    <section v-if="analysis.preset === 'image' && analysis.image_metadata" class="panel image-mask-panel">
      <div class="image-metadata-heading">
        <div>
          <p class="eyebrow">图片蒙版草稿</p>
          <h2>标记水印并保护正文</h2>
        </div>
        <dl class="image-metadata-grid">
          <div><dt>显示尺寸</dt><dd>{{ analysis.image_metadata.display_width }} × {{ analysis.image_metadata.display_height }}</dd></div>
          <div><dt>原始格式</dt><dd>{{ analysis.image_metadata.format }} · {{ analysis.image_metadata.mode }}</dd></div>
          <div><dt>透明通道</dt><dd>{{ analysis.image_metadata.has_alpha ? '有' : '无' }}</dd></div>
          <div><dt>帧数</dt><dd>{{ analysis.image_metadata.frames }}</dd></div>
          <div><dt>EXIF 方向</dt><dd>{{ analysis.image_metadata.exif_orientation }}</dd></div>
          <div><dt>ICC 配置</dt><dd>{{ analysis.image_metadata.has_icc_profile ? '有' : '无' }}</dd></div>
        </dl>
      </div>
      <section class="vlm-suggestion-panel">
        <div>
          <p class="eyebrow">可选本地模型</p>
          <h3>照片水印候选区域</h3>
          <p>{{ store.capabilities?.vlm_localization.message || '正在读取本地模型状态…' }}</p>
          <p class="hint">不会自动下载模型或修改图片；候选框只会填入下方蒙版草稿。</p>
        </div>
        <button
          class="secondary-button"
          :disabled="busy || vlmBusy || !store.capabilities?.vlm_localization.available"
          @click="requestVlmSuggestions"
        >
          {{ vlmBusy ? '正在生成建议…' : '使用本地模型建议区域' }}
        </button>
      </section>
      <p v-for="warning in vlmWarnings" :key="warning" class="warning">{{ warning }}</p>
      <ImageMaskEditor
        :asset-id="assetId"
        :metadata="analysis.image_metadata"
        :regions="imageMasks"
        :polygons="imagePolygons"
        :protected-regions="imageProtectedRegions"
        :can-undo="canUndoImageMasks"
        :can-redo="canRedoImageMasks"
        @update:draft="updateImageDraft"
        @undo="undoImageMasks"
        @redo="redoImageMasks"
        @limit-reached="reportImageMaskLimit"
      />
      <div class="process-actions">
        <button :disabled="busy || imageMasks.length + imagePolygons.length === 0" @click="previewImageMaskRisk">
          {{ busy ? '正在验证…' : `验证蒙版草稿（${imageMasks.length} 个矩形，${imagePolygons.length} 个多边形，${imageProtectedRegions.length} 个保护区）` }}
        </button>
        <p>先验证坐标和覆盖面积，再生成新的 PNG 副本。</p>
      </div>
      <template v-if="imageMaskPreview">
        <p class="mask-coverage">
          合并覆盖 {{ imageMaskPreview.covered_pixels.toFixed(0) }} 像素，约占图片
          {{ (imageMaskPreview.coverage_ratio * 100).toFixed(2) }}%。
        </p>
        <section
          class="selection-risk-summary"
          :class="{ 'needs-review': imageMaskPreview.selection_risk.level === 'review' }"
        >
          <div class="complexity-heading">
            <div>
              <p class="eyebrow">移动端水印风险</p>
              <h3>
                {{ imageMaskPreview.selection_risk.level === 'review' ? '执行前需要确认' : '未发现额外选区风险' }}
              </h3>
            </div>
            <span class="complexity-badge">
              {{ imageMaskPreview.selection_risk.level === 'review' ? '建议复核' : '正常' }}
            </span>
          </div>
          <p v-if="imageMaskPreview.selection_risk.large_selection" class="complexity-note">
            合并选区达到图片面积的 10%，大面积修复需要检查前后对比。
          </p>
          <article
            v-for="region in imageMaskPreview.selection_risk.regions"
            :key="region.region_index"
            class="complexity-region"
          >
            <div>
              <strong>区域 {{ region.region_index + 1 }}</strong>
              <span>{{ region.low_contrast ? '低对比度' : '对比度正常' }}</span>
            </div>
            <p>与周围平均亮度差异：{{ (region.mean_luma_delta * 100).toFixed(1) }}%</p>
            <p>{{ region.reason }}</p>
          </article>
        </section>
        <section class="complexity-summary" :class="`risk-${imageMaskPreview.complexity.level}`">
          <div class="complexity-heading">
            <div>
              <p class="eyebrow">OpenCV 修复预检</p>
              <h3>背景复杂度：{{ complexityLabels[imageMaskPreview.complexity.level] }}</h3>
            </div>
            <span class="complexity-badge">{{ complexityLabels[imageMaskPreview.complexity.level] }}</span>
          </div>
          <article
            v-for="region in imageMaskPreview.complexity.regions"
            :key="region.region_index"
            class="complexity-region"
          >
            <div>
              <strong>区域 {{ region.region_index + 1 }}</strong>
              <span>{{ complexityLabels[region.risk] }}</span>
            </div>
            <dl>
              <div><dt>纹理</dt><dd>{{ Math.round(region.texture_score * 100) }}</dd></div>
              <div><dt>边缘</dt><dd>{{ Math.round(region.edge_density * 100) }}</dd></div>
              <div><dt>周期性</dt><dd>{{ Math.round(region.periodicity_score * 100) }}</dd></div>
              <div><dt>结构线</dt><dd>{{ Math.round(region.structure_score * 100) }}</dd></div>
            </dl>
            <p v-for="reason in region.reasons" :key="reason">{{ reason }}</p>
          </article>
          <p class="complexity-note">分数用于修复前风险提示，不代表最终画质评分；高风险区域需要确认后才能处理。</p>
        </section>
        <p v-for="warning in imageMaskPreview.warnings" :key="warning" class="warning">{{ warning }}</p>
        <div v-if="imageMaskPreview.executable" class="image-process-options">
          <label for="image-radius">
            修复半径
            <input id="image-radius" v-model.number="imageRadius" type="number" min="1" max="10" />
          </label>
          <p class="hint">建议从 3 开始；细小水印可用 1–3，较粗边缘可提高到 5–7。</p>
          <button class="secondary-button" :disabled="busy || imagePreviewBusy" @click="compareImageRadii">
            {{ imagePreviewBusy ? '正在生成对比…' : '比较修复半径效果' }}
          </button>
        </div>
        <section v-if="imageRadiusPreviews.length" class="radius-preview-panel" aria-label="修复半径效果对比">
          <div class="complexity-heading">
            <div>
              <p class="eyebrow">处理前效果预览</p>
              <h3>选择修复半径</h3>
            </div>
            <span class="complexity-badge">临时生成</span>
          </div>
          <p class="hint">预览使用当前蒙版在内存中生成，不会保存结果文件；点击图片即可选用该半径。</p>
          <div class="radius-preview-grid">
            <button
              v-for="preview in imageRadiusPreviews"
              :key="preview.radius"
              type="button"
              class="radius-preview-card"
              :class="{ selected: imageRadius === preview.radius }"
              :aria-pressed="imageRadius === preview.radius"
              :aria-label="`选用修复半径 ${preview.radius}`"
              @click="imageRadius = preview.radius"
            >
              <img :src="preview.url" :alt="`修复半径 ${preview.radius} 的临时效果预览`" />
              <span>半径 {{ preview.radius }}{{ imageRadius === preview.radius ? ' · 当前选择' : '' }}</span>
            </button>
          </div>
        </section>
        <template v-for="warning in imagePlanWarnings" :key="warning.code">
          <label v-if="warning.requires_acknowledgement" class="risk-confirm">
            <input
              v-model="confirmedImageWarnings"
              type="checkbox"
              :value="warning.code"
              :disabled="busy"
            />
            {{ warning.message }}我已检查并确认继续。
          </label>
          <p v-else class="warning">{{ warning.message }}</p>
        </template>
        <div v-if="imageMaskPreview.executable" class="process-actions">
          <button :disabled="busy || imagePreviewBusy" @click="processImage">
            {{ busy ? '正在处理…' : '使用 OpenCV 生成修复副本' }}
          </button>
          <p>结果使用无损 PNG、移除 EXIF/ICC 元数据，并验证蒙版外像素没有变化。</p>
          <button
            v-if="task && ['queued', 'running', 'cancelling'].includes(task.status)"
            class="secondary-button"
            :disabled="task.status === 'cancelling'"
            @click="requestCancellation"
          >{{ task.status === 'cancelling' ? '正在取消…' : '取消任务' }}</button>
        </div>
      </template>
    </section>
    <section v-if="analysis.preset === 'general' && analysis.pdf_pages.length" class="panel redaction-panel">
      <div>
        <p class="eyebrow">PDF 区域处理</p>
        <h2>框选水印并选择处理方式</h2>
        <p>对象级删除适合普通 PDF；栅格修复适合无法单独删除的合成水印。</p>
      </div>
      <div class="pdf-strategy-options">
        <label for="pdf-region-strategy">
          处理方式
          <select id="pdf-region-strategy" v-model="pdfRegionStrategy" @change="clearRedactionDraft">
            <option value="pymupdf_redaction">对象级区域删除（保留页面结构）</option>
            <option value="raster_inpaint">Deep 栅格修复（OpenCV + 可搜索文字层）</option>
          </select>
        </label>
        <template v-if="pdfRegionStrategy === 'raster_inpaint'">
          <label>
            渲染 DPI
            <input v-model.number="pdfDeepDpi" type="number" min="96" max="300" step="12" @input="clearRedactionDraft" />
          </label>
          <label>
            修复半径
            <input v-model.number="pdfDeepRadius" type="number" min="1" max="10" @input="clearRedactionDraft" />
          </label>
        </template>
      </div>
      <section v-if="pdfRegionStrategy === 'raster_inpaint'" class="pdf-ocr-panel">
        <div>
          <p class="eyebrow">可搜索文字层</p>
          <h3>Tesseract OCR</h3>
          <p v-if="runtimeDiagnostics">{{ runtimeDiagnostics.ocr.message }}</p>
          <p v-else>{{ ocrDiagnosticsError || '正在读取已安装语言包…' }}</p>
        </div>
        <label class="pdf-ocr-toggle">
          <input
            v-model="pdfOcrEnabled"
            type="checkbox"
            :disabled="!ocrRuntimeReady"
            @change="clearRedactionDraft"
          />
          为没有原始文字层的页面执行 OCR
        </label>
        <label v-if="pdfOcrEnabled" for="pdf-ocr-languages" class="pdf-ocr-languages">
          已安装语言包（可多选）
          <select
            id="pdf-ocr-languages"
            v-model="pdfOcrLanguages"
            multiple
            :size="Math.min(6, Math.max(3, installedOcrLanguages.length))"
            @change="clearRedactionDraft"
          >
            <option v-for="language in installedOcrLanguages" :key="language" :value="language">
              {{ language }}
            </option>
          </select>
        </label>
        <p v-if="pdfOcrEnabled && !ocrSelectionValid" class="warning">
          请至少选择一个语言包；按住 Command 或 Ctrl 可以多选。
        </p>
        <p v-else-if="pdfOcrEnabled" class="hint">
          当前组合：{{ pdfOcrLanguages.join('+') }}。按住 Command 或 Ctrl 可以多选。
        </p>
        <p v-else class="hint">OCR 已关闭；原本没有文字层的页面会在报告中标记为不可搜索。</p>
      </section>
      <p v-if="pdfRegionStrategy === 'raster_inpaint'" class="hint">
        只栅格化被选中的页面；蒙版外原始文字会作为隐藏文字层回灌。图片型页面仅在本机安装 Tesseract 时执行 OCR。
      </p>
      <PdfRegionEditor
        v-if="selectedPdfPage"
        :asset-id="assetId"
        :page="selectedPdfPage"
        :regions="redactionRegions"
        @select="useVisualRegion"
      />
      <div class="redaction-fields">
        <label for="pdf-redaction-page">
          页面
          <select id="pdf-redaction-page" v-model.number="redactionPage" @change="clearRedactionDraft">
            <option v-for="page in analysis.pdf_pages" :key="page.page_number" :value="page.page_number">
              第 {{ page.page_number }} 页（{{ page.width.toFixed(0) }} × {{ page.height.toFixed(0) }}）
            </option>
          </select>
        </label>
        <label>X0 <input v-model.number="redactionX0" type="number" min="0" step="0.1" @input="clearRedactionDraft" /></label>
        <label>Y0 <input v-model.number="redactionY0" type="number" min="0" step="0.1" @input="clearRedactionDraft" /></label>
        <label>X1 <input v-model.number="redactionX1" type="number" min="0" step="0.1" @input="clearRedactionDraft" /></label>
        <label>Y1 <input v-model.number="redactionY1" type="number" min="0" step="0.1" @input="clearRedactionDraft" /></label>
      </div>
      <div class="process-actions">
        <button :disabled="busy" @click="addRedactionRegion">加入计划草稿</button>
        <button
          class="secondary-button"
          :disabled="busy || redactionRegions.length === 0"
          @click="previewRedactionRisk"
        >
          {{ busy ? '正在分析…' : `检查 ${redactionRegions.length} 个区域的重叠风险` }}
        </button>
        <p>可切换页面继续框选，一个计划最多包含 100 个区域。</p>
      </div>
      <section v-if="redactionRegions.length" class="redaction-draft" aria-label="PDF 区域计划草稿">
        <div class="redaction-draft-heading">
          <div>
            <p class="eyebrow">计划草稿</p>
            <h3>{{ redactionRegions.length }} 个区域 · {{ redactionDraftPageCount }} 页</h3>
          </div>
        </div>
        <ol>
          <li v-for="(region, index) in redactionRegions" :key="`${region.page_number}-${index}`">
            <span>
              第 {{ region.page_number }} 页 ·
              {{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} →
              {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}
            </span>
            <button
              class="text-button"
              :disabled="busy"
              :aria-label="`移除第 ${index + 1} 个 PDF 区域`"
              @click="removeRedactionRegion(index)"
            >移除</button>
          </li>
        </ol>
      </section>
      <template v-if="redactionPreview">
        <div v-if="redactionOverlapCount" class="overlap-list">
          <h3>相交对象</h3>
          <template v-for="(region, regionIndex) in redactionPreview.regions" :key="regionIndex">
            <h4 v-if="region.overlaps.length">区域 {{ regionIndex + 1 }} · 第 {{ region.region.page_number }} 页</h4>
            <ul v-if="region.overlaps.length">
              <li v-for="item in region.overlaps" :key="`${regionIndex}-${item.content_id}`">
                <strong>{{ item.kind }}</strong> · {{ item.summary }} · 相交面积 {{ item.intersection_area.toFixed(1) }}
              </li>
            </ul>
          </template>
        </div>
        <p v-for="warning in redactionPreview.warnings" :key="warning" class="warning">{{ warning }}</p>
        <label v-if="redactionPreview.requires_acknowledgement" class="risk-confirm">
          <input v-model="confirmedRedactionOverlap" type="checkbox" :disabled="busy" />
          {{ pdfRegionStrategy === 'raster_inpaint'
            ? '我已核对相交对象，确认在输出副本中栅格修复该区域'
            : '我已核对相交对象，确认从输出副本中物理删除该区域内容' }}
        </label>
        <label v-if="pdfRegionStrategy === 'raster_inpaint'" class="risk-confirm">
          <input v-model="confirmedRasterization" type="checkbox" :disabled="busy" />
          我确认所选页面将栅格化，链接、表单和矢量对象不会保留，并会检查输出文字层
        </label>
        <div v-if="redactionPreview.executable" class="process-actions">
          <button
            :disabled="busy || !ocrSelectionValid || (redactionPreview.requires_acknowledgement && !confirmedRedactionOverlap) || (pdfRegionStrategy === 'raster_inpaint' && !confirmedRasterization)"
            @click="processRedaction"
          >{{ busy ? '正在处理…' : pdfRegionStrategy === 'raster_inpaint' ? '生成栅格修复 PDF 副本' : '生成区域删除后的 PDF 副本' }}</button>
          <p>使用 AGPL 版 PyMuPDF；只生成新副本，不覆盖原文件。</p>
          <button
            v-if="task && ['queued', 'running', 'cancelling'].includes(task.status)"
            class="secondary-button"
            :disabled="task.status === 'cancelling'"
            @click="requestCancellation"
          >{{ task.status === 'cancelling' ? '正在取消…' : '取消任务' }}</button>
        </div>
      </template>
    </section>
    <div v-if="canProcess && hasObjectCandidates" class="process-actions">
      <button :disabled="busy || selectedCandidates.length === 0" @click="processSelection">
        {{ busy ? '正在处理…' : `生成无水印${isCodeCvPdf ? ' PDF' : ''}副本（已选 ${selectedCandidates.length} 项）` }}
      </button>
      <p>仅生成新文件，上传的原始文件不会被覆盖。</p>
      <button
        v-if="task && ['queued', 'running', 'cancelling'].includes(task.status)"
        class="secondary-button"
        :disabled="task.status === 'cancelling'"
        @click="requestCancellation"
      >{{ task.status === 'cancelling' ? '正在取消…' : '取消任务' }}</button>
    </div>
    <article v-if="task?.status === 'succeeded'" class="result-card">
      <div>
        <p class="eyebrow">处理完成</p>
        <h3>{{ task.stage }}</h3>
        <p v-if="task.artifacts[0]" class="result-meta">
          原件 {{ store.currentAsset?.sha256.slice(0, 12) }}… ·
          副本 {{ task.artifacts[0].sha256.slice(0, 12) }}… ·
          {{ (task.artifacts[0].size_bytes / 1024).toFixed(1) }} KB
        </p>
      </div>
      <a
        v-for="artifact in outputArtifacts"
        :key="artifact.id"
        class="download-button"
        :href="artifact.download_url"
      >下载 {{ artifact.display_name }}</a>
      <a class="secondary-button report-button" :href="task.report_url">下载处理报告</a>
    </article>
    <section v-if="isImage && task?.status === 'succeeded' && imageOutput" class="comparison-panel panel">
      <div class="comparison-heading">
        <div>
          <p class="eyebrow">图片前后对比</p>
          <h2>原图与 OpenCV 修复结果</h2>
        </div>
        <p>蒙版外像素已通过服务端一致性校验</p>
      </div>
      <div class="comparison-pair image-result-comparison">
        <figure>
          <figcaption>原始图片</figcaption>
          <img :src="`/api/v1/assets/${encodeURIComponent(assetId)}/content`" alt="原始图片" />
        </figure>
        <figure>
          <figcaption>修复副本</figcaption>
          <img :src="`${imageOutput.download_url}?inline=true`" alt="OpenCV 修复后的图片" />
        </figure>
      </div>
    </section>
    <section v-if="task?.comparison" class="comparison-panel panel">
      <div class="comparison-heading">
        <div>
          <p class="eyebrow">前后对比</p>
          <h2>页面预览</h2>
        </div>
        <p>
          删除 {{ task.comparison.removed_count }} 项 ·
          修改 {{ task.comparison.changed_parts.length }} 个位置
        </p>
      </div>
      <p v-if="task.comparison.changed_parts.length" class="changed-parts">
        {{ task.comparison.changed_parts.join(' · ') }}
      </p>
      <p v-if="task.comparison.warning" class="warning">{{ task.comparison.warning }}</p>
      <div v-if="task.comparison.available" class="comparison-pages">
        <article v-for="page in task.comparison.pages" :key="page.page_number" class="comparison-page">
          <h3>第 {{ page.page_number }} 页</h3>
          <div class="comparison-pair">
            <figure>
              <figcaption>原件</figcaption>
              <img v-if="page.source_url" :src="page.source_url" :alt="`原件第 ${page.page_number} 页`" loading="lazy" />
              <div v-else class="missing-preview">无此页</div>
            </figure>
            <figure>
              <figcaption>处理结果</figcaption>
              <img v-if="page.result_url" :src="page.result_url" :alt="`处理结果第 ${page.page_number} 页`" loading="lazy" />
              <div v-else class="missing-preview">无此页</div>
            </figure>
          </div>
        </article>
      </div>
    </section>
  </section>

  <section v-if="!store.currentAsset && message" class="empty-state">
    <h1>无法打开工作区</h1>
  </section>
</template>
