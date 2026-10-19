<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImageMaskRegion, ImageMetadata } from '@/api/client'

type EditorTool = 'rectangle' | 'brush' | 'eraser' | 'protect'
type Point = { x: number; y: number }

const props = defineProps<{
  assetId: string
  metadata: ImageMetadata
  regions: ImageMaskRegion[]
  protectedRegions: ImageMaskRegion[]
  canUndo: boolean
  canRedo: boolean
}>()

const emit = defineEmits<{
  'update:draft': [regions: ImageMaskRegion[], protectedRegions: ImageMaskRegion[]]
  undo: []
  redo: []
  'limit-reached': []
}>()

const editorElement = ref<HTMLDivElement | null>(null)
const imageElement = ref<HTMLImageElement | null>(null)
const loading = ref(true)
const error = ref('')
const tool = ref<EditorTool>('rectangle')
const brushSize = ref(20)
const maskVisible = ref(true)
const protectionVisible = ref(true)
const start = ref<Point | null>(null)
const end = ref<Point | null>(null)
const lastPoint = ref<Point | null>(null)
const draftRegions = ref<ImageMaskRegion[]>([])
const dragging = ref(false)

const sourceUrl = computed(() => `/api/v1/assets/${encodeURIComponent(props.assetId)}/content`)
const rectangleDraft = computed(() => {
  if (tool.value !== 'rectangle' || !start.value || !end.value) return null
  return roundRegion({
    x0: Math.min(start.value.x, end.value.x),
    y0: Math.min(start.value.y, end.value.y),
    x1: Math.max(start.value.x, end.value.x),
    y1: Math.max(start.value.y, end.value.y),
    transform_id: props.metadata.transform_id,
  })
})
const instruction = computed(() => ({
  rectangle: '拖拽矩形覆盖规则水印。',
  brush: '沿水印涂抹；一次笔画会生成若干连续蒙版片段。',
  eraser: '擦过蒙版即可删除触碰到的整个片段。',
  protect: '涂抹需要保留的内容；保护区会从最终修复蒙版中扣除。',
}[tool.value]))

function point(event: PointerEvent): Point | null {
  const image = imageElement.value
  if (!image) return null
  const bounds = image.getBoundingClientRect()
  if (!bounds.width || !bounds.height) return null
  return {
    x: Math.max(0, Math.min(props.metadata.display_width, (event.clientX - bounds.left) / bounds.width * props.metadata.display_width)),
    y: Math.max(0, Math.min(props.metadata.display_height, (event.clientY - bounds.top) / bounds.height * props.metadata.display_height)),
  }
}

function begin(event: PointerEvent) {
  if (loading.value || error.value) return
  editorElement.value?.focus()
  const selected = point(event)
  if (!selected) return
  start.value = selected
  end.value = selected
  lastPoint.value = selected
  draftRegions.value = tool.value === 'rectangle' ? [] : [brushStamp(selected)]
  dragging.value = true
  imageElement.value?.setPointerCapture(event.pointerId)
}

function move(event: PointerEvent) {
  if (!dragging.value) return
  const selected = point(event)
  if (!selected) return
  end.value = selected
  if (tool.value !== 'rectangle' && lastPoint.value) {
    appendStroke(lastPoint.value, selected)
    lastPoint.value = selected
  }
}

function finish(event: PointerEvent) {
  if (!dragging.value || !start.value) return
  const selected = point(event)
  if (selected) {
    end.value = selected
    if (tool.value !== 'rectangle' && lastPoint.value) appendStroke(lastPoint.value, selected)
  }
  releasePointer(event)
  if (!selected) return resetGesture()
  if (tool.value === 'rectangle') {
    const region = rectangleDraft.value
    if (region && region.x1 - region.x0 >= 2 && region.y1 - region.y0 >= 2) {
      appendWithLimit([...props.regions, region], props.protectedRegions)
    }
  } else if (tool.value === 'brush') {
    appendWithLimit([...props.regions, ...draftRegions.value], props.protectedRegions)
  } else if (tool.value === 'protect') {
    appendWithLimit(props.regions, [...props.protectedRegions, ...draftRegions.value])
  } else {
    const remaining = props.regions.filter(region => !draftRegions.value.some(stamp => intersects(region, stamp)))
    emit('update:draft', remaining, props.protectedRegions)
  }
  resetGesture()
}

function cancel(event: PointerEvent) {
  releasePointer(event)
  resetGesture()
}

function releasePointer(event: PointerEvent) {
  dragging.value = false
  const image = imageElement.value
  if (image?.hasPointerCapture(event.pointerId)) image.releasePointerCapture(event.pointerId)
}

function resetGesture() {
  dragging.value = false
  start.value = null
  end.value = null
  lastPoint.value = null
  draftRegions.value = []
}

function selectTool(next: EditorTool) {
  resetGesture()
  tool.value = next
  if (next === 'protect') protectionVisible.value = true
  else maskVisible.value = true
}

function appendStroke(from: Point, to: Point) {
  const distance = Math.hypot(to.x - from.x, to.y - from.y)
  const step = Math.max(2, brushSize.value * 0.45)
  const segments = Math.max(1, Math.ceil(distance / step))
  const additions: ImageMaskRegion[] = []
  for (let index = 1; index <= segments; index += 1) {
    additions.push(brushStamp({
      x: from.x + (to.x - from.x) * index / segments,
      y: from.y + (to.y - from.y) * index / segments,
    }))
  }
  draftRegions.value = compactStroke([...draftRegions.value, ...additions])
}

function brushStamp(selected: Point): ImageMaskRegion {
  const half = brushSize.value / 2
  return roundRegion({
    x0: Math.max(0, selected.x - half),
    y0: Math.max(0, selected.y - half),
    x1: Math.min(props.metadata.display_width, selected.x + half),
    y1: Math.min(props.metadata.display_height, selected.y + half),
    transform_id: props.metadata.transform_id,
  })
}

function compactStroke(regions: ImageMaskRegion[]) {
  const compacted: ImageMaskRegion[] = []
  for (const region of regions) {
    const previous = compacted.at(-1)
    if (previous && Math.abs(previous.x0 - region.x0) < 0.5 && Math.abs(previous.y0 - region.y0) < 0.5) continue
    compacted.push(region)
  }
  return compacted
}

function appendWithLimit(regions: ImageMaskRegion[], protectedRegions: ImageMaskRegion[]) {
  if (regions.length > 100 || protectedRegions.length > 100) {
    emit('limit-reached')
    return
  }
  emit('update:draft', regions, protectedRegions)
}

function removeMask(index: number) {
  emit('update:draft', props.regions.filter((_, itemIndex) => itemIndex !== index), props.protectedRegions)
}

function removeProtection(index: number) {
  emit('update:draft', props.regions, props.protectedRegions.filter((_, itemIndex) => itemIndex !== index))
}

function clearMasks() { emit('update:draft', [], props.protectedRegions) }
function clearProtections() { emit('update:draft', props.regions, []) }

function handleKeydown(event: KeyboardEvent) {
  const modifier = event.metaKey || event.ctrlKey
  if (!modifier) return
  if (event.key.toLowerCase() === 'z') {
    const redo = event.shiftKey
    if ((redo && !props.canRedo) || (!redo && !props.canUndo)) return
    event.preventDefault()
    if (redo) emit('redo')
    else emit('undo')
  } else if (event.ctrlKey && event.key.toLowerCase() === 'y' && props.canRedo) {
    event.preventDefault()
    emit('redo')
  }
}

function regionStyle(region: ImageMaskRegion) {
  return {
    left: `${region.x0 / props.metadata.display_width * 100}%`,
    top: `${region.y0 / props.metadata.display_height * 100}%`,
    width: `${(region.x1 - region.x0) / props.metadata.display_width * 100}%`,
    height: `${(region.y1 - region.y0) / props.metadata.display_height * 100}%`,
  }
}

function roundRegion(region: ImageMaskRegion): ImageMaskRegion {
  return { ...region, x0: Number(region.x0.toFixed(2)), y0: Number(region.y0.toFixed(2)), x1: Number(region.x1.toFixed(2)), y1: Number(region.y1.toFixed(2)) }
}

function intersects(first: ImageMaskRegion, second: ImageMaskRegion) {
  return Math.min(first.x1, second.x1) > Math.max(first.x0, second.x0)
    && Math.min(first.y1, second.y1) > Math.max(first.y0, second.y0)
}
</script>

<template>
  <div ref="editorElement" class="image-mask-editor" tabindex="0" aria-label="图片蒙版编辑器" @keydown="handleKeydown">
    <div class="image-editor-tools" role="toolbar" aria-label="蒙版绘制工具">
      <button type="button" :aria-pressed="tool === 'rectangle'" @click="selectTool('rectangle')">矩形</button>
      <button type="button" :aria-pressed="tool === 'brush'" @click="selectTool('brush')">画笔</button>
      <button type="button" :aria-pressed="tool === 'eraser'" @click="selectTool('eraser')">橡皮</button>
      <button type="button" :aria-pressed="tool === 'protect'" @click="selectTool('protect')">保护区</button>
      <label v-if="tool !== 'rectangle'" class="brush-size-control">笔刷 {{ brushSize }} px <input v-model.number="brushSize" type="range" min="4" max="80" step="2" /></label>
      <button type="button" class="visibility-button" :aria-pressed="maskVisible" @click="maskVisible = !maskVisible">{{ maskVisible ? '隐藏蒙版' : '显示蒙版' }}</button>
      <button type="button" class="visibility-button" :aria-pressed="protectionVisible" @click="protectionVisible = !protectionVisible">{{ protectionVisible ? '隐藏保护区' : '显示保护区' }}</button>
    </div>
    <p class="hint">{{ instruction }} 蒙版与保护区各最多 100 个片段。</p>
    <p v-if="loading" class="hint">正在加载图片预览…</p>
    <p v-if="error" class="warning">{{ error }}</p>
    <div class="image-mask-canvas" :class="[{ loading }, `tool-${tool}`]">
      <img ref="imageElement" :src="sourceUrl" alt="待编辑水印蒙版的原始图片" draggable="false" @load="loading = false" @error="loading = false; error = '图片预览加载失败。'" @pointerdown="begin" @pointermove="move" @pointerup="finish" @pointercancel="cancel" />
      <template v-if="maskVisible">
        <div v-for="(region, index) in regions" :key="`mask-${index}-${region.x0}-${region.y0}`" class="image-mask-region" :style="regionStyle(region)"><span>{{ index + 1 }}</span></div>
      </template>
      <template v-if="protectionVisible">
        <div v-for="(region, index) in protectedRegions" :key="`protected-${index}-${region.x0}-${region.y0}`" class="image-protected-region" :style="regionStyle(region)"><span>P{{ index + 1 }}</span></div>
      </template>
      <div v-if="rectangleDraft" class="image-mask-region draft" :style="regionStyle(rectangleDraft)" />
      <div v-for="(region, index) in draftRegions" :key="`draft-${index}`" :class="tool === 'protect' ? 'image-protected-region draft' : tool === 'eraser' ? 'image-eraser-region draft' : 'image-mask-region draft'" :style="regionStyle(region)" />
    </div>
    <div class="image-mask-toolbar">
      <p class="hint">编辑器聚焦时可用 ⌘/Ctrl+Z 撤销，⌘/Ctrl+Shift+Z 或 Ctrl+Y 重做。</p>
      <div class="image-mask-actions">
        <button class="secondary-button" type="button" :disabled="!canUndo" @click="emit('undo')">撤销</button>
        <button class="secondary-button" type="button" :disabled="!canRedo" @click="emit('redo')">重做</button>
        <button class="secondary-button" type="button" :disabled="!regions.length" @click="clearMasks">清空蒙版</button>
        <button class="secondary-button" type="button" :disabled="!protectedRegions.length" @click="clearProtections">清空保护区</button>
      </div>
    </div>
    <div v-if="regions.length || protectedRegions.length" class="mask-region-lists">
      <section v-if="regions.length"><h3>修复蒙版 · {{ regions.length }}</h3><ol class="mask-region-list"><li v-for="(region, index) in regions" :key="`mask-list-${index}`"><span>区域 {{ index + 1 }}：{{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} → {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}</span><button class="secondary-button" type="button" @click="removeMask(index)">移除</button></li></ol></section>
      <section v-if="protectedRegions.length"><h3>保护区 · {{ protectedRegions.length }}</h3><ol class="mask-region-list protected-list"><li v-for="(region, index) in protectedRegions" :key="`protected-list-${index}`"><span>保护 {{ index + 1 }}：{{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} → {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}</span><button class="secondary-button" type="button" @click="removeProtection(index)">移除</button></li></ol></section>
    </div>
  </div>
</template>

<style scoped>
.image-mask-editor { margin-top: 18px; border-radius: 14px; outline: none; }
.image-mask-editor:focus-visible { box-shadow: 0 0 0 3px rgba(32, 92, 67, .22); }
.image-editor-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.image-editor-tools button { padding: 8px 12px; border: 1px solid #b9c6bc; border-radius: 9px; background: #fff; color: #315143; }
.image-editor-tools button[aria-pressed="true"] { border-color: #315143; background: #315143; color: #fff; }
.image-editor-tools .visibility-button { margin-left: auto; }
.image-editor-tools .visibility-button + .visibility-button { margin-left: 0; }
.brush-size-control { display: flex; align-items: center; gap: 8px; color: #536057; font-size: .82rem; }
.brush-size-control input { width: 120px; }
.image-mask-canvas { position: relative; width: min(100%, 920px); line-height: 0; overflow: hidden; border: 1px solid #c8d0c8; border-radius: 12px; background: #eef0eb; touch-action: none; }
.image-mask-canvas.loading { min-height: 240px; opacity: .55; }
.image-mask-canvas img { display: block; width: 100%; height: auto; cursor: crosshair; user-select: none; }
.image-mask-canvas.tool-brush img { cursor: cell; }
.image-mask-canvas.tool-eraser img { cursor: not-allowed; }
.image-mask-canvas.tool-protect img { cursor: copy; }
.image-mask-region, .image-protected-region, .image-eraser-region { position: absolute; box-sizing: border-box; pointer-events: none; }
.image-mask-region { border: 2px solid #d24832; background: rgba(210, 72, 50, .22); }
.image-protected-region { border: 2px solid #16786b; background: rgba(22, 120, 107, .2); }
.image-eraser-region { border: 2px dashed #313936; background: rgba(255, 255, 255, .55); }
.draft { border-style: dashed; }
.image-mask-region span, .image-protected-region span { position: absolute; top: 3px; left: 3px; min-width: 22px; height: 22px; display: grid; place-items: center; border-radius: 999px; color: white; background: #b73524; font: 700 11px/1 system-ui; }
.image-protected-region span { background: #14675d; }
.image-mask-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.image-mask-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.mask-region-lists { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin-top: 12px; }
.mask-region-lists h3 { margin: 0 0 8px; font-size: .9rem; }
.mask-region-list { display: grid; max-height: 260px; gap: 8px; overflow: auto; padding-left: 22px; }
.mask-region-list li { min-height: 30px; padding-left: 4px; color: #536057; }
.mask-region-list li::marker { color: #b73524; font-weight: 700; }
.protected-list li::marker { color: #14675d; }
.mask-region-list button { float: right; padding: 5px 9px; font-size: .78rem; }
@media (max-width: 720px) { .image-editor-tools .visibility-button { margin-left: 0; } .image-mask-toolbar { align-items: flex-start; flex-direction: column; } }
</style>
