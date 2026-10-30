<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ApiError,
  createAnalysis,
  getAsset,
  getCapabilities,
  type Analysis,
} from '@/api/client'
import { useWorkspaceStore } from '@/stores/workspace'
import AnalysisSummaryPanel from '@/components/AnalysisSummaryPanel.vue'
import CandidateList from '@/components/CandidateList.vue'
import ImageWorkflowPanel from '@/components/ImageWorkflowPanel.vue'
import ObjectCandidateActions from '@/components/ObjectCandidateActions.vue'
import PdfStrategyPanel from '@/components/PdfStrategyPanel.vue'
import TaskOutcomePanel from '@/components/TaskOutcomePanel.vue'
import WorkspaceInspectionPanel from '@/components/WorkspaceInspectionPanel.vue'
import { useImageWorkflow } from '@/composables/useImageWorkflow'
import { useObjectCandidateWorkflow } from '@/composables/useObjectCandidateWorkflow'
import { usePdfRedactionWorkflow } from '@/composables/usePdfRedactionWorkflow'
import { useTaskExecution } from '@/composables/useTaskExecution'

const route = useRoute()
const store = useWorkspaceStore()
const analysis = ref<Analysis | null>(null)
const watermarkText = ref('')
const pdfPreset = ref<'codecv' | 'general'>('codecv')
const busy = ref(false)
const message = ref('')
const assetId = computed(() => String(route.params.assetId))
const sourceSha256 = computed(() => store.currentAsset?.sha256 || '')
const isDocx = computed(() => store.currentAsset?.kind === 'docx')
const isCodeCvPdf = computed(() => store.currentAsset?.kind === 'pdf')
const isImage = computed(() => ['png', 'jpeg', 'webp'].includes(store.currentAsset?.kind || ''))
const canInspect = computed(() => isDocx.value || isCodeCvPdf.value || isImage.value)

const {
  task,
  resetTask,
  runTask: waitForTask,
  requestCancellation,
} = useTaskExecution({ message })

const {
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
} = usePdfRedactionWorkflow({
  analysis,
  busy,
  message,
  runTask: waitForTask,
})

const {
  selectedCandidates,
  confirmedAmbiguous,
  planWarnings,
  canProcess,
  hasObjectCandidates,
  resetObjectCandidates,
  processSelection,
} = useObjectCandidateWorkflow({
  analysis,
  busy,
  message,
  confirmedSignatureInvalidation,
  canProcess: () => isDocx.value || (isCodeCvPdf.value && analysis.value?.preset === 'codecv'),
  runTask: waitForTask,
})

const {
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
} = useImageWorkflow({
  analysis,
  busy,
  message,
  vlmAvailable: () => store.capabilities?.vlm_localization.available || false,
  runTask: waitForTask,
})

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
    resetObjectCandidates(analysis.value)
    resetTask()
    resetPdfRedaction(analysis.value)
    resetImageMasks()
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

function clearAnalysis() {
  analysis.value = null
  resetTask()
  resetObjectCandidates()
  message.value = ''
  resetPdfRedaction()
  resetImageMasks()
}

</script>

<template>
  <WorkspaceInspectionPanel
    v-if="store.currentAsset"
    v-model:watermark-text="watermarkText"
    v-model:pdf-preset="pdfPreset"
    :asset="store.currentAsset"
    :asset-id="assetId"
    :busy="busy"
    @inspect="inspect"
    @clear-analysis="clearAnalysis"
  />

  <p v-if="message" class="message status-message" role="status">{{ message }}</p>

  <section v-if="analysis" class="analysis-results">
    <AnalysisSummaryPanel :analysis="analysis" />
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
    <ObjectCandidateActions
      v-if="canProcess && hasObjectCandidates"
      v-model:confirmed-signature="confirmedSignatureInvalidation"
      :busy="busy"
      :selected-count="selectedCandidates.length"
      :is-pdf="isCodeCvPdf"
      :pdf-has-digital-signatures="analysis.pdf_has_digital_signatures"
      @process="processSelection"
    />
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
