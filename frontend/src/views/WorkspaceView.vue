<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  ApiError,
  cancelTask,
  createAnalysis,
  createTask,
  getAsset,
  getTask,
  previewImageMasks,
  previewRedactions,
  type Analysis,
  type ImageMaskPreview,
  type ImageMaskRegion,
  type PlanWarning,
  type ProcessingTask,
  type RedactionPreview,
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
const confirmedRedactionOverlap = ref(false)
const imageMasks = ref<ImageMaskRegion[]>([])
const imageMaskPreview = ref<ImageMaskPreview | null>(null)
const imageRadius = ref(3)
const imagePlanWarnings = ref<PlanWarning[]>([])
const confirmedImageWarnings = ref<string[]>([])
const assetId = computed(() => String(route.params.assetId))
const isDocx = computed(() => store.currentAsset?.kind === 'docx')
const isCodeCvPdf = computed(() => store.currentAsset?.kind === 'pdf')
const isImage = computed(() => ['png', 'jpeg', 'webp'].includes(store.currentAsset?.kind || ''))
const canInspect = computed(() => isDocx.value || isCodeCvPdf.value || isImage.value)
const canProcess = computed(() => (
  isDocx.value || (isCodeCvPdf.value && analysis.value?.preset === 'codecv')
))
const outputArtifacts = computed(() => (
  task.value?.artifacts.filter(artifact => artifact.role === 'output') || []
))
const imageOutput = computed(() => outputArtifacts.value[0] || null)
const selectedPdfPage = computed(() => (
  analysis.value?.pdf_pages.find(page => page.page_number === redactionPage.value) || null
))

const complexityLabels = {
  low: '低风险',
  review: '建议复核',
  high: '高风险',
} as const

onMounted(async () => {
  try {
    if (store.currentAsset?.id !== assetId.value) {
      store.currentAsset = await getAsset(assetId.value)
    }
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法读取文件信息。'
  }
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
    selectedCandidates.value = analysis.value.candidates
      .filter(candidate => candidate.classification === 'confirmed')
      .map(candidate => candidate.candidate_id)
    confirmedAmbiguous.value = []
    planWarnings.value = []
    task.value = null
    redactionPreview.value = null
    confirmedRedactionOverlap.value = false
    imageMasks.value = []
    imageMaskPreview.value = null
    imagePlanWarnings.value = []
    confirmedImageWarnings.value = []
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
      message.value = '没有识别到受支持的 VML 文字水印候选。'
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
  confirmedRedactionOverlap.value = false
  imageMasks.value = []
  imageMaskPreview.value = null
  imagePlanWarnings.value = []
  confirmedImageWarnings.value = []
}

function updateImageMasks(regions: ImageMaskRegion[]) {
  imageMasks.value = regions
  imageMaskPreview.value = null
  imagePlanWarnings.value = []
  confirmedImageWarnings.value = []
}

async function previewImageMaskRisk() {
  if (!analysis.value || imageMasks.value.length === 0) return
  busy.value = true
  message.value = ''
  try {
    imageMaskPreview.value = await previewImageMasks(analysis.value, imageMasks.value)
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

async function processImage() {
  if (!analysis.value || !imageMaskPreview.value?.executable) return
  busy.value = true
  message.value = ''
  try {
    const plan = await validateImagePlan(
      analysis.value,
      imageMasks.value,
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
}

async function previewRedactionRisk() {
  if (!analysis.value || !selectedPdfPage.value) return
  busy.value = true
  message.value = ''
  try {
    redactionPreview.value = await previewRedactions(analysis.value, {
      page_number: redactionPage.value,
      x0: redactionX0.value,
      y0: redactionY0.value,
      x1: redactionX1.value,
      y1: redactionY1.value,
      transform_id: selectedPdfPage.value.transform_id,
    })
    confirmedRedactionOverlap.value = false
    const count = redactionPreview.value.regions[0]?.overlaps.length || 0
    message.value = count
      ? `区域与 ${count} 个正文或交互对象相交，请检查下方风险。`
      : '结构扫描未发现区域重叠；复杂 PDF 仍可能存在未列出的内容。'
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法生成区域风险预览。'
  } finally {
    busy.value = false
  }
}

async function processRedaction() {
  const region = redactionPreview.value?.regions[0]?.region
  if (!analysis.value || !redactionPreview.value?.executable || !region) return
  busy.value = true
  message.value = ''
  try {
    const acknowledgements = confirmedRedactionOverlap.value
      ? ['PDF_REDACTION_OVERLAP']
      : []
    const plan = await validateRedactionPlan(analysis.value, [region], acknowledgements)
    if (!plan.valid || !plan.id) {
      message.value = '该区域与正文或交互对象相交，请确认风险后再执行。'
      return
    }
    await waitForTask(await createTask(plan.id))
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '创建 PDF 区域删除任务失败。'
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
        <p class="hint">完全匹配目标文字且符合 Word 水印形状时，候选会标记为已确认。</p>
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
          <p class="hint">扫描后可框选区域，经重叠风险确认后生成应用物理删除的新 PDF。</p>
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
          <p class="eyebrow">矩形蒙版草稿</p>
          <h2>框选水印所在区域</h2>
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
      <ImageMaskEditor
        :asset-id="assetId"
        :metadata="analysis.image_metadata"
        :regions="imageMasks"
        @update:regions="updateImageMasks"
      />
      <div class="process-actions">
        <button :disabled="busy || imageMasks.length === 0" @click="previewImageMaskRisk">
          {{ busy ? '正在验证…' : `验证蒙版草稿（${imageMasks.length} 个区域）` }}
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
        </div>
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
          <button :disabled="busy" @click="processImage">
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
        <p class="eyebrow">区域删除风险预览</p>
        <h2>输入 PDF 点坐标</h2>
        <p>先验证坐标和相交对象，再由 PyMuPDF 生成物理删除后的新文件。</p>
      </div>
      <PdfRegionEditor
        v-if="selectedPdfPage"
        :asset-id="assetId"
        :page="selectedPdfPage"
        @select="useVisualRegion"
      />
      <div class="redaction-fields">
        <label>
          页面
          <select v-model.number="redactionPage" @change="clearRedactionDraft">
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
      <button :disabled="busy" @click="previewRedactionRisk">
        {{ busy ? '正在分析…' : '检查区域重叠风险' }}
      </button>
      <template v-if="redactionPreview">
        <div v-if="redactionPreview.regions[0]?.overlaps.length" class="overlap-list">
          <h3>相交对象</h3>
          <ul>
            <li v-for="item in redactionPreview.regions[0].overlaps" :key="item.content_id">
              <strong>{{ item.kind }}</strong> · {{ item.summary }} · 相交面积 {{ item.intersection_area.toFixed(1) }}
            </li>
          </ul>
        </div>
        <p v-for="warning in redactionPreview.warnings" :key="warning" class="warning">{{ warning }}</p>
        <label v-if="redactionPreview.requires_acknowledgement" class="risk-confirm">
          <input v-model="confirmedRedactionOverlap" type="checkbox" :disabled="busy" />
          我已核对相交对象，确认从输出副本中物理删除该区域内容
        </label>
        <div v-if="redactionPreview.executable" class="process-actions">
          <button
            :disabled="busy || (redactionPreview.requires_acknowledgement && !confirmedRedactionOverlap)"
            @click="processRedaction"
          >{{ busy ? '正在处理…' : '生成区域删除后的 PDF 副本' }}</button>
          <p>使用 AGPL 版 PyMuPDF；原始上传文件不会被覆盖。</p>
          <button
            v-if="task && ['queued', 'running', 'cancelling'].includes(task.status)"
            class="secondary-button"
            :disabled="task.status === 'cancelling'"
            @click="requestCancellation"
          >{{ task.status === 'cancelling' ? '正在取消…' : '取消任务' }}</button>
        </div>
      </template>
    </section>
    <div v-if="canProcess && analysis.candidates.length" class="process-actions">
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
