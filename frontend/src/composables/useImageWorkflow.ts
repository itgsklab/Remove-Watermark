import { computed, onScopeDispose, ref, type Ref } from 'vue'
import {
  ApiError,
  createTask,
  previewImageMasks,
  renderImageMaskPreview,
  suggestImageMasks,
  type Analysis,
  type ImageMaskPolygon,
  type ImageMaskPreview,
  type ImageMaskRegion,
  type PlanWarning,
  type ProcessingTask,
  validateImagePlan,
} from '@/api/client'
import { useImageMaskDraft } from '@/composables/useImageMaskDraft'

interface ImageRadiusPreview {
  radius: number
  url: string
}

interface ImageWorkflowOptions {
  analysis: Ref<Analysis | null>
  busy: Ref<boolean>
  message: Ref<string>
  vlmAvailable: () => boolean
  runTask: (task: ProcessingTask) => Promise<void>
}

const complexityLabels = {
  low: '低风险',
  review: '建议复核',
  high: '高风险',
} as const

export function useImageWorkflow(options: ImageWorkflowOptions) {
  const draft = useImageMaskDraft()
  const imageMaskPreview = ref<ImageMaskPreview | null>(null)
  const imageRadius = ref(3)
  const imageRadiusPreviews = ref<ImageRadiusPreview[]>([])
  const imagePreviewBusy = ref(false)
  const imagePlanWarnings = ref<PlanWarning[]>([])
  const confirmedImageWarnings = ref<string[]>([])
  const vlmBusy = ref(false)
  const vlmWarnings = ref<string[]>([])
  let previewRequestId = 0

  const imageMasks = draft.regions
  const imagePolygons = draft.polygons
  const imageProtectedRegions = draft.protectedRegions
  const canUndoImageMasks = computed(() => draft.canUndo.value)
  const canRedoImageMasks = computed(() => draft.canRedo.value)

  function clearImageRadiusPreviews() {
    previewRequestId += 1
    for (const preview of imageRadiusPreviews.value) URL.revokeObjectURL(preview.url)
    imageRadiusPreviews.value = []
    imagePreviewBusy.value = false
  }

  function clearImageMaskPreview() {
    imageMaskPreview.value = null
    imagePlanWarnings.value = []
    confirmedImageWarnings.value = []
    clearImageRadiusPreviews()
  }

  function updateImageDraft(
    regions: ImageMaskRegion[],
    polygons: ImageMaskPolygon[],
    protectedRegions: ImageMaskRegion[],
  ) {
    const result = draft.update({ regions, polygons, protectedRegions })
    if (result === 'limit-reached') {
      reportImageMaskLimit()
    } else if (result === 'updated') {
      clearImageMaskPreview()
    }
  }

  function undoImageMasks() {
    if (!draft.undo()) return
    clearImageMaskPreview()
    options.message.value = `已撤销编辑，当前有 ${imageMasks.value.length} 个蒙版、${imageProtectedRegions.value.length} 个保护区。`
  }

  function redoImageMasks() {
    if (!draft.redo()) return
    clearImageMaskPreview()
    options.message.value = `已重做编辑，当前有 ${imageMasks.value.length} 个蒙版、${imageProtectedRegions.value.length} 个保护区。`
  }

  function resetImageMasks() {
    draft.reset()
    vlmWarnings.value = []
    clearImageMaskPreview()
  }

  function reportImageMaskLimit() {
    options.message.value = '一个图片草稿最多包含 100 个矩形蒙版、32 个多边形和 100 个保护区片段。'
  }

  async function requestVlmSuggestions() {
    if (!options.analysis.value || !options.vlmAvailable()) return
    vlmBusy.value = true
    options.message.value = ''
    vlmWarnings.value = []
    try {
      const result = await suggestImageMasks(options.analysis.value)
      vlmWarnings.value = result.warnings
      if (result.status === 'suggested') {
        updateImageDraft(result.regions, [], [])
        options.message.value = `本地模型提出 ${result.regions.length} 个候选区域。请逐个检查、调整并验证蒙版。`
      } else if (result.status === 'photo_gate_rejected') {
        options.message.value = '图片未通过照片场景门禁，模型没有运行；请继续手工框选。'
      } else {
        options.message.value = '本地模型没有提出候选区域；请继续手工框选。'
      }
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '本地模型候选建议失败，请继续手工框选。'
    } finally {
      vlmBusy.value = false
    }
  }

  async function previewImageMaskRisk() {
    if (!options.analysis.value || imageMasks.value.length + imagePolygons.value.length === 0) return
    options.busy.value = true
    options.message.value = ''
    try {
      imageMaskPreview.value = await previewImageMasks(
        options.analysis.value,
        imageMasks.value,
        imagePolygons.value,
        imageProtectedRegions.value,
      )
      const risk = complexityLabels[imageMaskPreview.value.complexity.level]
      const selection = imageMaskPreview.value.selection_risk.level === 'review'
        ? '，选区需要确认'
        : ''
      options.message.value = `蒙版草稿有效，覆盖图片面积的 ${(imageMaskPreview.value.coverage_ratio * 100).toFixed(2)}%，背景复杂度为${risk}${selection}。`
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '无法验证图片蒙版。'
    } finally {
      options.busy.value = false
    }
  }

  async function compareImageRadii() {
    if (!options.analysis.value || !imageMaskPreview.value?.executable) return
    const requestId = ++previewRequestId
    imagePreviewBusy.value = true
    options.message.value = ''
    const requestedRadius = Number(imageRadius.value)
    const selectedRadius = Number.isFinite(requestedRadius)
      ? Math.max(1, Math.min(10, Math.round(requestedRadius)))
      : 3
    const radii = [...new Set([1, selectedRadius, 7])].sort((left, right) => left - right)
    try {
      const analysis = options.analysis.value
      const rendered = await Promise.all(radii.map(async radius => ({
        radius,
        blob: await renderImageMaskPreview(
          analysis,
          imageMasks.value,
          imagePolygons.value,
          imageProtectedRegions.value,
          radius,
        ),
      })))
      if (requestId !== previewRequestId) return
      for (const preview of imageRadiusPreviews.value) URL.revokeObjectURL(preview.url)
      imageRadiusPreviews.value = rendered.map(item => ({
        radius: item.radius,
        url: URL.createObjectURL(item.blob),
      }))
      options.message.value = `已生成 ${rendered.length} 个临时效果预览；请选择更合适的修复半径。`
    } catch (error) {
      if (requestId !== previewRequestId) return
      options.message.value = error instanceof ApiError ? error.message : '无法生成修复半径对比预览。'
    } finally {
      if (requestId === previewRequestId) imagePreviewBusy.value = false
    }
  }

  async function processImage() {
    if (!options.analysis.value || !imageMaskPreview.value?.executable) return
    options.busy.value = true
    options.message.value = ''
    try {
      const plan = await validateImagePlan(
        options.analysis.value,
        imageMasks.value,
        imagePolygons.value,
        imageProtectedRegions.value,
        imageRadius.value,
        confirmedImageWarnings.value,
      )
      imagePlanWarnings.value = plan.warnings
      if (!plan.valid || !plan.id) {
        options.message.value = '请确认所有高风险提示后再执行图片修复。'
        return
      }
      await options.runTask(await createTask(plan.id))
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '创建图片修复任务失败。'
    } finally {
      options.busy.value = false
    }
  }

  onScopeDispose(clearImageRadiusPreviews)

  return {
    imageMasks,
    imagePolygons,
    imageProtectedRegions,
    canUndoImageMasks,
    canRedoImageMasks,
    imageMaskPreview,
    imageRadius,
    imageRadiusPreviews,
    imagePreviewBusy,
    imagePlanWarnings,
    confirmedImageWarnings,
    vlmBusy,
    vlmWarnings,
    updateImageDraft,
    undoImageMasks,
    redoImageMasks,
    resetImageMasks,
    reportImageMaskLimit,
    requestVlmSuggestions,
    previewImageMaskRisk,
    compareImageRadii,
    processImage,
  }
}
