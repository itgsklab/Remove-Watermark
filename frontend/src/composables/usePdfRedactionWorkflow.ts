import { computed, ref, type Ref } from 'vue'
import {
  ApiError,
  createTask,
  getRuntimeDiagnostics,
  previewRedactions,
  type Analysis,
  type ProcessingTask,
  type RedactionPreview,
  type RedactionRegion,
  type RuntimeDiagnostics,
  validateRedactionPlan,
} from '@/api/client'

interface PdfRedactionWorkflowOptions {
  analysis: Ref<Analysis | null>
  busy: Ref<boolean>
  message: Ref<string>
  runTask: (task: ProcessingTask) => Promise<void>
}

export function usePdfRedactionWorkflow(options: PdfRedactionWorkflowOptions) {
  const redactionPreview = ref<RedactionPreview | null>(null)
  const redactionPage = ref(1)
  const redactionX0 = ref(0)
  const redactionY0 = ref(0)
  const redactionX1 = ref(100)
  const redactionY1 = ref(100)
  const redactionRegions = ref<RedactionRegion[]>([])
  const confirmedRedactionOverlap = ref(false)
  const confirmedSignatureInvalidation = ref(false)
  const confirmedRasterization = ref(false)
  const pdfRegionStrategy = ref<'pymupdf_redaction' | 'raster_inpaint'>('pymupdf_redaction')
  const pdfDeepDpi = ref(144)
  const pdfDeepRadius = ref(3)
  const runtimeDiagnostics = ref<RuntimeDiagnostics | null>(null)
  const pdfOcrEnabled = ref(false)
  const pdfOcrLanguages = ref<string[]>([])
  const ocrDiagnosticsError = ref('')

  const selectedPdfPage = computed(() => (
    options.analysis.value?.pdf_pages.find(page => page.page_number === redactionPage.value) || null
  ))
  const redactionOverlapCount = computed(() => redactionPreview.value?.regions.reduce(
    (total, region) => total + region.overlaps.length,
    0,
  ) ?? 0)
  const ocrRuntimeReady = computed(() => runtimeDiagnostics.value?.ocr.status === 'ready')
  const installedOcrLanguages = computed(() => runtimeDiagnostics.value?.ocr.languages || [])
  const ocrSelectionValid = computed(() => (
    !pdfOcrEnabled.value || pdfOcrLanguages.value.length > 0
  ))

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

  function resetPdfRedaction(nextAnalysis: Analysis | null = null) {
    redactionPreview.value = null
    redactionRegions.value = []
    confirmedRedactionOverlap.value = false
    confirmedSignatureInvalidation.value = false
    confirmedRasterization.value = false
    const firstPage = nextAnalysis?.preset === 'general' ? nextAnalysis.pdf_pages[0] : null
    if (firstPage) {
      redactionPage.value = firstPage.page_number
      redactionX0.value = 0
      redactionY0.value = 0
      redactionX1.value = Math.min(100, firstPage.width)
      redactionY1.value = Math.min(100, firstPage.height)
    }
  }

  function useVisualRegion(region: RedactionRegion) {
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
      options.message.value = '区域坐标无效或超出当前页面范围。'
      return
    }
    if (redactionRegions.value.length >= 100) {
      options.message.value = '一个 PDF 计划最多包含 100 个区域。'
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
      options.message.value = '该区域已经在计划草稿中。'
      return
    }
    redactionRegions.value.push(region)
    clearRedactionDraft()
    options.message.value = `已加入第 ${region.page_number} 页区域，草稿共 ${redactionRegions.value.length} 项。`
  }

  function removeRedactionRegion(index: number) {
    redactionRegions.value.splice(index, 1)
    clearRedactionDraft()
    options.message.value = redactionRegions.value.length
      ? `已移除区域，草稿还剩 ${redactionRegions.value.length} 项。`
      : 'PDF 区域计划草稿已清空。'
  }

  async function previewRedactionRisk() {
    if (!options.analysis.value || redactionRegions.value.length === 0) return
    options.busy.value = true
    options.message.value = ''
    try {
      redactionPreview.value = await previewRedactions(
        options.analysis.value,
        redactionRegions.value,
        pdfRegionStrategy.value,
      )
      confirmedRedactionOverlap.value = false
      confirmedSignatureInvalidation.value = false
      const count = redactionOverlapCount.value
      options.message.value = count
        ? `${redactionRegions.value.length} 个区域与 ${count} 个正文或交互对象相交，请检查下方风险。`
        : `${redactionRegions.value.length} 个区域未发现结构重叠；复杂 PDF 仍可能存在未列出的内容。`
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '无法生成区域风险预览。'
    } finally {
      options.busy.value = false
    }
  }

  async function processRedaction() {
    const regions = redactionPreview.value?.regions.map(item => item.region) || []
    if (!options.analysis.value || !redactionPreview.value?.executable || regions.length === 0) return
    if (pdfRegionStrategy.value === 'raster_inpaint' && !ocrSelectionValid.value) {
      options.message.value = '请至少选择一个已安装的 OCR 语言包，或关闭 OCR。'
      return
    }
    options.busy.value = true
    options.message.value = ''
    try {
      const acknowledgements: string[] = []
      if (confirmedRedactionOverlap.value) acknowledgements.push('PDF_REDACTION_OVERLAP')
      if (confirmedSignatureInvalidation.value) {
        acknowledgements.push('PDF_DIGITAL_SIGNATURE_INVALIDATION')
      }
      if (confirmedRasterization.value) acknowledgements.push('PDF_RASTERIZATION')
      const plan = await validateRedactionPlan(options.analysis.value, regions, acknowledgements, {
        strategy: pdfRegionStrategy.value,
        dpi: pdfDeepDpi.value,
        radius: pdfDeepRadius.value,
        ocr_languages: pdfOcrEnabled.value ? pdfOcrLanguages.value.join('+') : null,
      })
      if (!plan.valid || !plan.id) {
        options.message.value = '请确认区域重叠与处理方式风险后再执行。'
        return
      }
      await options.runTask(await createTask(plan.id))
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '创建 PDF 区域处理任务失败。'
    } finally {
      options.busy.value = false
    }
  }

  return {
    redactionPreview,
    redactionPage,
    redactionX0,
    redactionY0,
    redactionX1,
    redactionY1,
    redactionRegions,
    confirmedRedactionOverlap,
    confirmedSignatureInvalidation,
    confirmedRasterization,
    pdfRegionStrategy,
    pdfDeepDpi,
    pdfDeepRadius,
    runtimeDiagnostics,
    pdfOcrEnabled,
    pdfOcrLanguages,
    ocrDiagnosticsError,
    ocrRuntimeReady,
    installedOcrLanguages,
    ocrSelectionValid,
    loadOcrDiagnostics,
    resetPdfRedaction,
    useVisualRegion,
    clearRedactionDraft,
    addRedactionRegion,
    removeRedactionRegion,
    previewRedactionRisk,
    processRedaction,
  }
}
