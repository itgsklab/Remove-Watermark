<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
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
import { useWorkspaceAnalysis } from '@/composables/useWorkspaceAnalysis'
import { useWorkspaceBootstrap } from '@/composables/useWorkspaceBootstrap'

const route = useRoute()
const store = useWorkspaceStore()
const busy = ref(false)
const message = ref('')
const assetId = computed(() => String(route.params.assetId))
const sourceSha256 = computed(() => store.currentAsset?.sha256 || '')

const {
  analysis,
  watermarkText,
  pdfPreset,
  isDocx,
  isCodeCvPdf,
  isImage,
  inspect,
  clearAnalysis,
} = useWorkspaceAnalysis({
  assetId,
  busy,
  message,
  assetKind: () => store.currentAsset?.kind || null,
})

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

watch(analysis, nextAnalysis => {
  resetObjectCandidates(nextAnalysis)
  resetTask()
  resetPdfRedaction(nextAnalysis)
  resetImageMasks()
})

useWorkspaceBootstrap({
  assetId,
  message,
  store,
  loadPdfDiagnostics: loadOcrDiagnostics,
  resetWorkspace: clearAnalysis,
})
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
