<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { PdfPageGeometry, RedactionRegion } from '@/api/client'

const props = defineProps<{
  assetId: string
  page: PdfPageGeometry
}>()

const emit = defineEmits<{
  select: [region: RedactionRegion]
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
const loading = ref(true)
const error = ref('')
const dragStart = ref<{ x: number; y: number } | null>(null)
const dragEnd = ref<{ x: number; y: number } | null>(null)
const dragging = ref(false)
let documentProxy: PDFDocumentProxy | null = null
let pageProxy: PDFPageProxy | null = null
let viewport: ReturnType<PDFPageProxy['getViewport']> | null = null
let loadToken = 0
let pdfjsModule: typeof import('pdfjs-dist') | null = null

const selectionStyle = computed(() => {
  const element = canvas.value
  const start = dragStart.value
  const end = dragEnd.value
  if (!element || !start || !end || !element.width || !element.height) return null
  const x0 = Math.min(start.x, end.x)
  const y0 = Math.min(start.y, end.y)
  const x1 = Math.max(start.x, end.x)
  const y1 = Math.max(start.y, end.y)
  return {
    left: `${x0 / element.width * 100}%`,
    top: `${y0 / element.height * 100}%`,
    width: `${(x1 - x0) / element.width * 100}%`,
    height: `${(y1 - y0) / element.height * 100}%`,
  }
})

async function loadDocument() {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  try {
    pdfjsModule ||= await import('pdfjs-dist')
    pdfjsModule.GlobalWorkerOptions.workerSrc = workerUrl
    if (documentProxy) await documentProxy.destroy()
    documentProxy = await pdfjsModule.getDocument(
      `/api/v1/assets/${encodeURIComponent(props.assetId)}/content`,
    ).promise
    if (token !== loadToken) return
    await renderPage()
  } catch (cause) {
    if (token === loadToken) error.value = cause instanceof Error ? cause.message : 'PDF 加载失败。'
  } finally {
    if (token === loadToken) loading.value = false
  }
}

async function renderPage() {
  if (!documentProxy || !canvas.value) return
  loading.value = true
  error.value = ''
  dragStart.value = null
  dragEnd.value = null
  try {
    pageProxy?.cleanup()
    pageProxy = await documentProxy.getPage(props.page.page_number)
    const baseViewport = pageProxy.getViewport({ scale: 1 })
    const scale = Math.min(1.5, 900 / baseViewport.width)
    viewport = pageProxy.getViewport({ scale })
    canvas.value.width = Math.ceil(viewport.width)
    canvas.value.height = Math.ceil(viewport.height)
    await pageProxy.render({ canvas: canvas.value, viewport }).promise
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '页面渲染失败。'
  } finally {
    loading.value = false
  }
}

function canvasPoint(event: PointerEvent) {
  const element = canvas.value
  if (!element) return null
  const bounds = element.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(element.width, (event.clientX - bounds.left) * element.width / bounds.width)),
    y: Math.max(0, Math.min(element.height, (event.clientY - bounds.top) * element.height / bounds.height)),
  }
}

function startSelection(event: PointerEvent) {
  const point = canvasPoint(event)
  if (!point || loading.value) return
  dragging.value = true
  dragStart.value = point
  dragEnd.value = point
  canvas.value?.setPointerCapture(event.pointerId)
}

function moveSelection(event: PointerEvent) {
  if (!dragging.value) return
  const point = canvasPoint(event)
  if (point) dragEnd.value = point
}

function finishSelection(event: PointerEvent) {
  if (!dragging.value || !dragStart.value || !viewport) return
  const point = canvasPoint(event)
  if (point) dragEnd.value = point
  dragging.value = false
  canvas.value?.releasePointerCapture(event.pointerId)
  const end = dragEnd.value
  if (!end) return
  const width = Math.abs(end.x - dragStart.value.x)
  const height = Math.abs(end.y - dragStart.value.y)
  if (width < 3 || height < 3) return
  const first = viewport.convertToPdfPoint(dragStart.value.x, dragStart.value.y)
  const second = viewport.convertToPdfPoint(end.x, end.y)
  const x0 = Math.max(0, Math.min(first[0], second[0]) - props.page.crop_x)
  const y0 = Math.max(0, Math.min(first[1], second[1]) - props.page.crop_y)
  const x1 = Math.min(props.page.width, Math.max(first[0], second[0]) - props.page.crop_x)
  const y1 = Math.min(props.page.height, Math.max(first[1], second[1]) - props.page.crop_y)
  emit('select', {
    page_number: props.page.page_number,
    x0,
    y0,
    x1,
    y1,
    transform_id: props.page.transform_id,
  })
}

watch(() => props.assetId, loadDocument)
watch(() => props.page.page_number, renderPage)

onMounted(loadDocument)
onBeforeUnmount(async () => {
  loadToken += 1
  pageProxy?.cleanup()
  if (documentProxy) await documentProxy.destroy()
})
</script>

<template>
  <div class="pdf-region-editor">
    <p v-if="loading" class="pdf-canvas-state">正在渲染第 {{ page.page_number }} 页…</p>
    <p v-if="error" class="warning">{{ error }}</p>
    <div class="pdf-canvas-wrap" :class="{ loading }">
      <canvas
        ref="canvas"
        aria-label="PDF 页面区域选择器"
        @pointerdown="startSelection"
        @pointermove="moveSelection"
        @pointerup="finishSelection"
        @pointercancel="finishSelection"
      />
      <div v-if="selectionStyle" class="pdf-selection" :style="selectionStyle" />
    </div>
    <p class="hint">在页面上拖拽矩形。框选坐标会转换为 PDF crop-box 点坐标。</p>
  </div>
</template>

<style scoped>
.pdf-region-editor { margin: 18px 0; }
.pdf-canvas-wrap { position: relative; width: min(100%, 900px); overflow: hidden; border: 1px solid #c8d0c8; border-radius: 12px; background: white; touch-action: none; }
.pdf-canvas-wrap.loading { opacity: .55; }
canvas { display: block; width: 100%; height: auto; cursor: crosshair; }
.pdf-selection { position: absolute; border: 2px solid #d24832; background: rgba(210, 72, 50, .18); pointer-events: none; }
.pdf-canvas-state { color: #536057; }
</style>
