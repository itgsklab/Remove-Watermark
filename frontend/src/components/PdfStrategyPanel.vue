<script setup lang="ts">
import { computed } from 'vue'
import PdfRegionEditor from '@/components/PdfRegionEditor.vue'
import type {
  Analysis,
  RedactionPreview,
  RedactionRegion,
  RuntimeDiagnostics,
} from '@/api/client'

const props = defineProps<{
  assetId: string
  pages: Analysis['pdf_pages']
  regions: RedactionRegion[]
  preview: RedactionPreview | null
  runtimeDiagnostics: RuntimeDiagnostics | null
  ocrDiagnosticsError: string
  ocrRuntimeReady: boolean
  installedOcrLanguages: string[]
  ocrSelectionValid: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  clearDraft: []
  select: [region: RedactionRegion]
  addRegion: []
  preview: []
  removeRegion: [index: number]
  process: []
}>()

const strategy = defineModel<'pymupdf_redaction' | 'raster_inpaint'>('strategy', { required: true })
const dpi = defineModel<number>('dpi', { required: true })
const radius = defineModel<number>('radius', { required: true })
const ocrEnabled = defineModel<boolean>('ocrEnabled', { required: true })
const ocrLanguages = defineModel<string[]>('ocrLanguages', { required: true })
const page = defineModel<number>('page', { required: true })
const x0 = defineModel<number>('x0', { required: true })
const y0 = defineModel<number>('y0', { required: true })
const x1 = defineModel<number>('x1', { required: true })
const y1 = defineModel<number>('y1', { required: true })
const confirmedOverlap = defineModel<boolean>('confirmedOverlap', { required: true })
const confirmedSignature = defineModel<boolean>('confirmedSignature', { required: true })
const confirmedRasterization = defineModel<boolean>('confirmedRasterization', { required: true })

const selectedPage = computed(() => props.pages.find(item => item.page_number === page.value) || null)
const draftPageCount = computed(() => new Set(props.regions.map(region => region.page_number)).size)
const overlapCount = computed(() => props.preview?.regions.reduce(
  (total, region) => total + region.overlaps.length,
  0,
) ?? 0)
</script>

<template>
  <section class="panel redaction-panel">
    <div>
      <p class="eyebrow">PDF 区域处理</p>
      <h2>框选水印并选择处理方式</h2>
      <p>对象级删除适合普通 PDF；栅格修复适合无法单独删除的合成水印。</p>
    </div>
    <div class="pdf-strategy-options">
      <label for="pdf-region-strategy">
        处理方式
        <select id="pdf-region-strategy" v-model="strategy" @change="emit('clearDraft')">
          <option value="pymupdf_redaction">对象级区域删除（保留页面结构）</option>
          <option value="raster_inpaint">Deep 栅格修复（OpenCV + 可搜索文字层）</option>
        </select>
      </label>
      <template v-if="strategy === 'raster_inpaint'">
        <label>
          渲染 DPI
          <input v-model.number="dpi" type="number" min="96" max="300" step="12" @input="emit('clearDraft')" />
        </label>
        <label>
          修复半径
          <input v-model.number="radius" type="number" min="1" max="10" @input="emit('clearDraft')" />
        </label>
      </template>
    </div>
    <section v-if="strategy === 'raster_inpaint'" class="pdf-ocr-panel">
      <div>
        <p class="eyebrow">可搜索文字层</p>
        <h3>Tesseract OCR</h3>
        <p v-if="runtimeDiagnostics">{{ runtimeDiagnostics.ocr.message }}</p>
        <p v-else>{{ ocrDiagnosticsError || '正在读取已安装语言包…' }}</p>
      </div>
      <label class="pdf-ocr-toggle">
        <input
          v-model="ocrEnabled"
          type="checkbox"
          :disabled="!ocrRuntimeReady"
          @change="emit('clearDraft')"
        />
        为没有原始文字层的页面执行 OCR
      </label>
      <label v-if="ocrEnabled" for="pdf-ocr-languages" class="pdf-ocr-languages">
        已安装语言包（可多选）
        <select
          id="pdf-ocr-languages"
          v-model="ocrLanguages"
          multiple
          :size="Math.min(6, Math.max(3, installedOcrLanguages.length))"
          @change="emit('clearDraft')"
        >
          <option v-for="language in installedOcrLanguages" :key="language" :value="language">
            {{ language }}
          </option>
        </select>
      </label>
      <p v-if="ocrEnabled && !ocrSelectionValid" class="warning">
        请至少选择一个语言包；按住 Command 或 Ctrl 可以多选。
      </p>
      <p v-else-if="ocrEnabled" class="hint">
        当前组合：{{ ocrLanguages.join('+') }}。按住 Command 或 Ctrl 可以多选。
      </p>
      <p v-else class="hint">OCR 已关闭；原本没有文字层的页面会在报告中标记为不可搜索。</p>
    </section>
    <p v-if="strategy === 'raster_inpaint'" class="hint">
      只栅格化被选中的页面；蒙版外原始文字会作为隐藏文字层回灌。图片型页面仅在本机安装 Tesseract 时执行 OCR。
    </p>
    <PdfRegionEditor
      v-if="selectedPage"
      :asset-id="assetId"
      :page="selectedPage"
      :regions="regions"
      @select="emit('select', $event)"
    />
    <div class="redaction-fields">
      <label for="pdf-redaction-page">
        页面
        <select id="pdf-redaction-page" v-model.number="page" @change="emit('clearDraft')">
          <option v-for="item in pages" :key="item.page_number" :value="item.page_number">
            第 {{ item.page_number }} 页（{{ item.width.toFixed(0) }} × {{ item.height.toFixed(0) }}）
          </option>
        </select>
      </label>
      <label>X0 <input v-model.number="x0" type="number" min="0" step="0.1" @input="emit('clearDraft')" /></label>
      <label>Y0 <input v-model.number="y0" type="number" min="0" step="0.1" @input="emit('clearDraft')" /></label>
      <label>X1 <input v-model.number="x1" type="number" min="0" step="0.1" @input="emit('clearDraft')" /></label>
      <label>Y1 <input v-model.number="y1" type="number" min="0" step="0.1" @input="emit('clearDraft')" /></label>
    </div>
    <div class="process-actions">
      <button :disabled="busy" @click="emit('addRegion')">加入计划草稿</button>
      <button
        class="secondary-button"
        :disabled="busy || regions.length === 0"
        @click="emit('preview')"
      >
        {{ busy ? '正在分析…' : `检查 ${regions.length} 个区域的重叠风险` }}
      </button>
      <p>可切换页面继续框选，一个计划最多包含 100 个区域。</p>
    </div>
    <section v-if="regions.length" class="redaction-draft" aria-label="PDF 区域计划草稿">
      <div class="redaction-draft-heading">
        <div>
          <p class="eyebrow">计划草稿</p>
          <h3>{{ regions.length }} 个区域 · {{ draftPageCount }} 页</h3>
        </div>
      </div>
      <ol>
        <li v-for="(region, index) in regions" :key="`${region.page_number}-${index}`">
          <span>
            第 {{ region.page_number }} 页 ·
            {{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} →
            {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}
          </span>
          <button
            class="text-button"
            :disabled="busy"
            :aria-label="`移除第 ${index + 1} 个 PDF 区域`"
            @click="emit('removeRegion', index)"
          >移除</button>
        </li>
      </ol>
    </section>
    <template v-if="preview">
      <div v-if="overlapCount" class="overlap-list">
        <h3>相交对象</h3>
        <template v-for="(region, regionIndex) in preview.regions" :key="regionIndex">
          <h4 v-if="region.overlaps.length">区域 {{ regionIndex + 1 }} · 第 {{ region.region.page_number }} 页</h4>
          <ul v-if="region.overlaps.length">
            <li v-for="item in region.overlaps" :key="`${regionIndex}-${item.content_id}`">
              <strong>{{ item.kind }}</strong> · {{ item.summary }} · 相交面积 {{ item.intersection_area.toFixed(1) }}
            </li>
          </ul>
        </template>
      </div>
      <p v-for="warning in preview.warnings" :key="warning" class="warning">{{ warning }}</p>
      <label v-if="preview.requires_acknowledgement" class="risk-confirm">
        <input v-model="confirmedOverlap" type="checkbox" :disabled="busy" />
        {{ strategy === 'raster_inpaint'
          ? '我已核对相交对象，确认在输出副本中栅格修复该区域'
          : '我已核对相交对象，确认从输出副本中物理删除该区域内容' }}
      </label>
      <label v-if="preview.digital_signature_present" class="risk-confirm signature-confirm">
        <input v-model="confirmedSignature" type="checkbox" :disabled="busy" />
        我知道原 PDF 的现有数字签名将在新副本中失效，并确认继续处理
      </label>
      <label v-if="strategy === 'raster_inpaint'" class="risk-confirm">
        <input v-model="confirmedRasterization" type="checkbox" :disabled="busy" />
        我确认所选页面将栅格化，链接、表单和矢量对象不会保留，并会检查输出文字层
      </label>
      <div v-if="preview.executable" class="process-actions">
        <button
          :disabled="busy || !ocrSelectionValid || (preview.requires_acknowledgement && !confirmedOverlap) || (preview.digital_signature_present && !confirmedSignature) || (strategy === 'raster_inpaint' && !confirmedRasterization)"
          @click="emit('process')"
        >{{ busy ? '正在处理…' : strategy === 'raster_inpaint' ? '生成栅格修复 PDF 副本' : '生成区域删除后的 PDF 副本' }}</button>
        <p>使用 AGPL 版 PyMuPDF；只生成新副本，不覆盖原文件。</p>
      </div>
    </template>
  </section>
</template>
