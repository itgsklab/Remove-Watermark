<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ApiError,
  cancelTask,
  createAnalysis,
  createTask,
  getAsset,
  getCapabilities,
  getTask,
  type Analysis,
  type PlanWarning,
  type ProcessingTask,
  validatePlan,
} from '@/api/client'
import { useWorkspaceStore } from '@/stores/workspace'
import CandidateList from '@/components/CandidateList.vue'
import ImageWorkflowPanel from '@/components/ImageWorkflowPanel.vue'
import PdfStrategyPanel from '@/components/PdfStrategyPanel.vue'
import TaskOutcomePanel from '@/components/TaskOutcomePanel.vue'
import WorkspaceInspectionPanel from '@/components/WorkspaceInspectionPanel.vue'
import { useImageWorkflow } from '@/composables/useImageWorkflow'
import { usePdfRedactionWorkflow } from '@/composables/usePdfRedactionWorkflow'

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
const codeCvDiagnosticPayload = computed(() => {
  if (!analysis.value?.codecv_diagnostics || analysis.value.preset !== 'codecv') return ''
  return JSON.stringify({
    schema_version: 1,
    match_status: analysis.value.match_status,
    ...analysis.value.codecv_diagnostics,
  }, null, 2)
})

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
  resetPdfRedaction()
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
