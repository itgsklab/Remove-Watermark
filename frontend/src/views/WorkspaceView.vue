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
import CandidateList from '@/components/CandidateList.vue'
import ImageWorkflowPanel from '@/components/ImageWorkflowPanel.vue'
import PdfStrategyPanel from '@/components/PdfStrategyPanel.vue'
import TaskOutcomePanel from '@/components/TaskOutcomePanel.vue'

const route = useRoute()
const store = useWorkspaceStore()
const analysis = ref<Analysis | null>(null)
const watermarkText = ref('')
const pdfPreset = ref<'codecv' | 'general'>('codecv')
const busy = ref(false)
const message = ref('')
const codeCvDiagnosticCopyState = ref('')
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
const confirmedSignatureInvalidation = ref(false)
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
const sourceSha256 = computed(() => store.currentAsset?.sha256 || '')
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
const selectedPdfPage = computed(() => (
  analysis.value?.pdf_pages.find(page => page.page_number === redactionPage.value) || null
))
const redactionOverlapCount = computed(() => redactionPreview.value?.regions.reduce(
  (total, region) => total + region.overlaps.length,
  0,
) ?? 0)
const canUndoImageMasks = computed(() => imageMaskPast.value.length > 0)
const canRedoImageMasks = computed(() => imageMaskFuture.value.length > 0)
const imageMaskHistoryLimit = 50
const ocrRuntimeReady = computed(() => runtimeDiagnostics.value?.ocr.status === 'ready')
const installedOcrLanguages = computed(() => runtimeDiagnostics.value?.ocr.languages || [])
const ocrSelectionValid = computed(() => (
  !pdfOcrEnabled.value || pdfOcrLanguages.value.length > 0
))
const codeCvDiagnosticPayload = computed(() => {
  if (!analysis.value?.codecv_diagnostics || analysis.value.preset !== 'codecv') return ''
  return JSON.stringify({
    schema_version: 1,
    match_status: analysis.value.match_status,
    ...analysis.value.codecv_diagnostics,
  }, null, 2)
})

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
  codeCvDiagnosticCopyState.value = ''
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
    confirmedSignatureInvalidation.value = false
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
    if (confirmedSignatureInvalidation.value) {
      acknowledgements.push('PDF_DIGITAL_SIGNATURE_INVALIDATION')
    }
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

function clearAnalysis() {
  analysis.value = null
  selectedCandidates.value = []
  message.value = ''
  codeCvDiagnosticCopyState.value = ''
  redactionPreview.value = null
  redactionRegions.value = []
  confirmedRedactionOverlap.value = false
  confirmedSignatureInvalidation.value = false
  resetImageMasks()
}

async function copyCodeCvDiagnostics() {
  if (!codeCvDiagnosticPayload.value) return
  try {
    await navigator.clipboard.writeText(codeCvDiagnosticPayload.value)
    codeCvDiagnosticCopyState.value = '已复制脱敏诊断。'
  } catch {
    codeCvDiagnosticCopyState.value = '浏览器未允许复制，请手动记录下方统计。'
  }
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
  confirmedSignatureInvalidation.value = false
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
    confirmedSignatureInvalidation.value = false
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
    if (confirmedSignatureInvalidation.value) {
      acknowledgements.push('PDF_DIGITAL_SIGNATURE_INVALIDATION')
    }
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
        <p class="hint">同时扫描 DrawingML 嵌入图片；可安全预览的内部图片经人工确认后可从输出副本删除。</p>
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
    <section
      v-if="analysis.preset === 'codecv' && analysis.codecv_diagnostics"
      class="panel codecv-diagnostics"
      aria-labelledby="codecv-diagnostics-title"
    >
      <div class="codecv-diagnostics-heading">
        <div>
          <p class="eyebrow">脱敏兼容诊断</p>
          <h3 id="codecv-diagnostics-title">CodeCV 结构匹配统计</h3>
          <p>只包含规则版本和聚合数量，不包含简历正文、文件名、路径、资源名或 PDF 对象内容。</p>
        </div>
        <button class="secondary-button" type="button" @click="copyCodeCvDiagnostics">复制诊断</button>
      </div>
      <dl class="codecv-diagnostics-grid">
        <div><dt>扫描页数</dt><dd>{{ analysis.codecv_diagnostics.pages_scanned }}</dd></div>
        <div><dt>含 Pattern 的页面</dt><dd>{{ analysis.codecv_diagnostics.pages_with_pattern_resources }}</dd></div>
        <div><dt>Pattern 资源</dt><dd>{{ analysis.codecv_diagnostics.pattern_resource_count }}</dd></div>
        <div><dt>Tiling Pattern</dt><dd>{{ analysis.codecv_diagnostics.tiling_pattern_resource_count }}</dd></div>
        <div><dt>完整操作签名</dt><dd>{{ analysis.codecv_diagnostics.complete_signature_count }}</dd></div>
        <div><dt>已确认 / 待复核</dt><dd>{{ analysis.codecv_diagnostics.confirmed_signature_count }} / {{ analysis.codecv_diagnostics.ambiguous_signature_count }}</dd></div>
      </dl>
      <p class="codecv-rule-version">规则 {{ analysis.codecv_diagnostics.rule_version }}</p>
      <p v-if="codeCvDiagnosticCopyState" class="hint" role="status">{{ codeCvDiagnosticCopyState }}</p>
    </section>
    <CandidateList
      :candidates="analysis.candidates"
      :preset="analysis.preset"
      :can-process="canProcess"
      :busy="busy"
      :selected-candidate-ids="selectedCandidates"
      :confirmed-candidate-ids="confirmedAmbiguous"
      @update:selected-candidate-ids="selectedCandidates = $event"
      @update:confirmed-candidate-ids="confirmedAmbiguous = $event"
    />
    <p v-if="analysis.preset !== 'image' && analysis.candidates.length === 0" class="panel empty-candidates">没有候选。此结果不证明文档不存在其他类型水印。</p>
    <p v-for="warning in analysis.warnings" :key="warning" class="warning">{{ warning }}</p>
    <p v-for="warning in planWarnings" :key="warning.code" class="warning">{{ warning.message }}</p>
    <ImageWorkflowPanel
      v-if="analysis.preset === 'image' && analysis.image_metadata"
      v-model:radius="imageRadius"
      v-model:confirmed-warnings="confirmedImageWarnings"
      :asset-id="assetId"
      :metadata="analysis.image_metadata"
      :regions="imageMasks"
      :polygons="imagePolygons"
      :protected-regions="imageProtectedRegions"
      :can-undo="canUndoImageMasks"
      :can-redo="canRedoImageMasks"
      :preview="imageMaskPreview"
      :radius-previews="imageRadiusPreviews"
      :preview-busy="imagePreviewBusy"
      :plan-warnings="imagePlanWarnings"
      :vlm-available="store.capabilities?.vlm_localization.available || false"
      :vlm-message="store.capabilities?.vlm_localization.message || ''"
      :vlm-busy="vlmBusy"
      :vlm-warnings="vlmWarnings"
      :busy="busy"
      @update-draft="updateImageDraft"
      @undo="undoImageMasks"
      @redo="redoImageMasks"
      @limit-reached="reportImageMaskLimit"
      @suggest="requestVlmSuggestions"
      @validate="previewImageMaskRisk"
      @compare-radii="compareImageRadii"
      @process="processImage"
    />
    <PdfStrategyPanel
      v-if="analysis.preset === 'general' && analysis.pdf_pages.length"
      v-model:strategy="pdfRegionStrategy"
      v-model:dpi="pdfDeepDpi"
      v-model:radius="pdfDeepRadius"
      v-model:ocr-enabled="pdfOcrEnabled"
      v-model:ocr-languages="pdfOcrLanguages"
      v-model:page="redactionPage"
      v-model:x0="redactionX0"
      v-model:y0="redactionY0"
      v-model:x1="redactionX1"
      v-model:y1="redactionY1"
      v-model:confirmed-overlap="confirmedRedactionOverlap"
      v-model:confirmed-signature="confirmedSignatureInvalidation"
      v-model:confirmed-rasterization="confirmedRasterization"
      :asset-id="assetId"
      :pages="analysis.pdf_pages"
      :regions="redactionRegions"
      :preview="redactionPreview"
      :runtime-diagnostics="runtimeDiagnostics"
      :ocr-diagnostics-error="ocrDiagnosticsError"
      :ocr-runtime-ready="ocrRuntimeReady"
      :installed-ocr-languages="installedOcrLanguages"
      :ocr-selection-valid="ocrSelectionValid"
      :busy="busy"
      @clear-draft="clearRedactionDraft"
      @select="useVisualRegion"
      @add-region="addRedactionRegion"
      @preview="previewRedactionRisk"
      @remove-region="removeRedactionRegion"
      @process="processRedaction"
    />
    <div v-if="canProcess && hasObjectCandidates" class="process-actions">
      <label v-if="analysis?.pdf_has_digital_signatures" class="risk-confirm signature-confirm">
        <input v-model="confirmedSignatureInvalidation" type="checkbox" :disabled="busy" />
        我知道原 PDF 的现有数字签名将在 CodeCV 清理副本中失效，并确认继续处理
      </label>
      <button
        :disabled="busy || selectedCandidates.length === 0 || (analysis?.pdf_has_digital_signatures && !confirmedSignatureInvalidation)"
        @click="processSelection"
      >
        {{ busy ? '正在处理…' : `生成无水印${isCodeCvPdf ? ' PDF' : ''}副本（已选 ${selectedCandidates.length} 项）` }}
      </button>
      <p>仅生成新文件，上传的原始文件不会被覆盖。</p>
    </div>
    <TaskOutcomePanel
      v-if="task"
      :task="task"
      :source-sha256="sourceSha256"
      :asset-id="assetId"
      :is-image="isImage"
      @cancel="requestCancellation"
    />
  </section>

  <section v-if="!store.currentAsset && message" class="empty-state">
    <h1>无法打开工作区</h1>
  </section>
</template>
