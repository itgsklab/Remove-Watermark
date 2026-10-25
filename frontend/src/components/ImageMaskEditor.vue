<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { ImageMaskPolygon, ImageMaskRegion, ImageMetadata } from '@/api/client'

type EditorTool = 'rectangle' | 'polygon' | 'edit-polygon' | 'brush' | 'eraser' | 'protect' | 'pan'
type Point = { x: number; y: number }
type VertexDrag = { polygonIndex: number; pointIndex: number }
type PanGesture = { clientX: number; clientY: number; scrollLeft: number; scrollTop: number }

const props = defineProps<{
  assetId: string
  metadata: ImageMetadata
  regions: ImageMaskRegion[]
  polygons: ImageMaskPolygon[]
  protectedRegions: ImageMaskRegion[]
  canUndo: boolean
  canRedo: boolean
}>()

const emit = defineEmits<{
  'update:draft': [regions: ImageMaskRegion[], polygons: ImageMaskPolygon[], protectedRegions: ImageMaskRegion[]]
  undo: []
  redo: []
  'limit-reached': []
}>()

const editorElement = ref<HTMLDivElement | null>(null)
const viewportElement = ref<HTMLDivElement | null>(null)
const canvasElement = ref<HTMLDivElement | null>(null)
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
const polygonPoints = ref<Point[]>([])
const editedPolygon = ref<ImageMaskPolygon | null>(null)
const vertexDrag = ref<VertexDrag | null>(null)
const editMessage = ref('')
const dragging = ref(false)
const zoom = ref(1)
const panGesture = ref<PanGesture | null>(null)

const sourceUrl = computed(() => `/api/v1/assets/${encodeURIComponent(props.assetId)}/content`)
const displayedPolygons = computed(() => props.polygons.map((polygon, index) => (
  vertexDrag.value?.polygonIndex === index && editedPolygon.value ? editedPolygon.value : polygon
)))
const polygonHandleRadius = computed(() => (
  Math.max(1.5 / zoom.value, Math.min(props.metadata.display_width, props.metadata.display_height) * 0.012 / zoom.value)
))
const stageStyle = computed(() => ({ width: `${zoom.value * 100}%` }))
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
  polygon: '依次点击水印边界顶点，至少三个点后按 Enter 或点击完成。',
  'edit-polygon': '拖动多边形顶点调整边界；聚焦顶点后也可用方向键微调。',
  brush: '沿水印涂抹；一次笔画会生成若干连续蒙版片段。',
  eraser: '擦过蒙版即可删除触碰到的整个片段。',
  protect: '涂抹需要保留的内容；保护区会从最终修复蒙版中扣除。',
  pan: '拖动图片查看放大后的其他位置；平移不会改变任何蒙版坐标。',
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
  if (tool.value === 'pan') {
    const viewport = viewportElement.value
    if (!viewport || zoom.value <= 1) return
    event.preventDefault()
    panGesture.value = {
      clientX: event.clientX,
      clientY: event.clientY,
      scrollLeft: viewport.scrollLeft,
      scrollTop: viewport.scrollTop,
    }
    dragging.value = true
    canvasElement.value?.setPointerCapture(event.pointerId)
    return
  }
  const selected = point(event)
  if (!selected) return
  if (tool.value === 'edit-polygon') return
  if (tool.value === 'polygon') {
    const rounded = roundPoint(selected)
    const previous = polygonPoints.value.at(-1)
    if (!previous || Math.hypot(previous.x - rounded.x, previous.y - rounded.y) >= 2) {
      polygonPoints.value.push(rounded)
    }
    return
  }
  start.value = selected
  end.value = selected
  lastPoint.value = selected
  draftRegions.value = tool.value === 'rectangle' ? [] : [brushStamp(selected)]
  dragging.value = true
  canvasElement.value?.setPointerCapture(event.pointerId)
}

function move(event: PointerEvent) {
  if (panGesture.value) {
    const viewport = viewportElement.value
    if (!viewport) return
    viewport.scrollLeft = panGesture.value.scrollLeft - (event.clientX - panGesture.value.clientX)
    viewport.scrollTop = panGesture.value.scrollTop - (event.clientY - panGesture.value.clientY)
    return
  }
  if (vertexDrag.value && editedPolygon.value) {
    const selected = point(event)
    if (!selected) return
    editedPolygon.value.points[vertexDrag.value.pointIndex] = roundPoint(selected)
    return
  }
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
  if (panGesture.value) {
    releasePointer(event)
    panGesture.value = null
    return
  }
  if (vertexDrag.value) {
    finishVertexDrag(event)
    return
  }
  if (tool.value === 'polygon') return
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
      appendWithLimit([...props.regions, region], props.polygons, props.protectedRegions)
    }
  } else if (tool.value === 'brush') {
    appendWithLimit([...props.regions, ...draftRegions.value], props.polygons, props.protectedRegions)
  } else if (tool.value === 'protect') {
    appendWithLimit(props.regions, props.polygons, [...props.protectedRegions, ...draftRegions.value])
  } else {
    const remaining = props.regions.filter(region => !draftRegions.value.some(stamp => intersects(region, stamp)))
    const remainingPolygons = props.polygons.filter(polygon => (
      !draftRegions.value.some(stamp => polygonTouchesRegion(polygon, stamp))
    ))
    emit('update:draft', remaining, remainingPolygons, props.protectedRegions)
  }
  resetGesture()
}

function cancel(event: PointerEvent) {
  if (panGesture.value) {
    releasePointer(event)
    panGesture.value = null
    return
  }
  if (vertexDrag.value) {
    releasePointer(event)
    resetVertexDrag()
    return
  }
  releasePointer(event)
  resetGesture()
}

function releasePointer(event: PointerEvent) {
  dragging.value = false
  const canvas = canvasElement.value
  if (canvas?.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
}

function resetGesture() {
  dragging.value = false
  start.value = null
  end.value = null
  lastPoint.value = null
  draftRegions.value = []
  panGesture.value = null
}

function selectTool(next: EditorTool) {
  resetGesture()
  resetVertexDrag()
  editMessage.value = ''
  polygonPoints.value = []
  tool.value = next
  if (next === 'protect') protectionVisible.value = true
  else maskVisible.value = true
}

async function setZoom(next: number) {
  const viewport = viewportElement.value
  const bounded = Math.max(1, Math.min(4, next))
  if (!viewport || bounded === zoom.value) return
  const horizontalCenter = (viewport.scrollLeft + viewport.clientWidth / 2) / Math.max(1, viewport.scrollWidth)
  const verticalCenter = (viewport.scrollTop + viewport.clientHeight / 2) / Math.max(1, viewport.scrollHeight)
  zoom.value = bounded
  await nextTick()
  viewport.scrollLeft = horizontalCenter * viewport.scrollWidth - viewport.clientWidth / 2
  viewport.scrollTop = verticalCenter * viewport.scrollHeight - viewport.clientHeight / 2
  if (bounded === 1 && tool.value === 'pan') selectTool('rectangle')
}

async function resetView() {
  await setZoom(1)
  const viewport = viewportElement.value
  if (viewport) viewport.scrollTo({ left: 0, top: 0 })
}

function beginVertexDrag(event: PointerEvent, polygonIndex: number, pointIndex: number) {
  if (tool.value !== 'edit-polygon') return
  const polygon = props.polygons[polygonIndex]
  if (!polygon) return
  event.preventDefault()
  editorElement.value?.focus()
  vertexDrag.value = { polygonIndex, pointIndex }
  editedPolygon.value = clonePolygon(polygon)
  editMessage.value = ''
  dragging.value = true
  canvasElement.value?.setPointerCapture(event.pointerId)
}

function finishVertexDrag(event: PointerEvent) {
  const active = vertexDrag.value
  const polygon = editedPolygon.value
  const selected = point(event)
  if (active && polygon && selected) polygon.points[active.pointIndex] = roundPoint(selected)
  releasePointer(event)
  if (!active || !polygon) return resetVertexDrag()
  if (polygonArea(polygon.points) < 1) {
    editMessage.value = '本次调整会让多边形退化，已恢复原顶点。'
    resetVertexDrag()
    return
  }
  const polygons = props.polygons.map((item, index) => (
    index === active.polygonIndex ? clonePolygon(polygon) : item
  ))
  resetVertexDrag()
  emit('update:draft', props.regions, polygons, props.protectedRegions)
}

function resetVertexDrag() {
  vertexDrag.value = null
  editedPolygon.value = null
  dragging.value = false
}

function nudgePolygonPoint(event: KeyboardEvent, polygonIndex: number, pointIndex: number) {
  if (tool.value !== 'edit-polygon') return
  const movement = {
    ArrowLeft: { x: -1, y: 0 },
    ArrowRight: { x: 1, y: 0 },
    ArrowUp: { x: 0, y: -1 },
    ArrowDown: { x: 0, y: 1 },
  }[event.key]
  if (!movement) return
  const source = props.polygons[polygonIndex]
  if (!source) return
  event.preventDefault()
  const step = event.shiftKey ? 10 : 1
  const polygon = clonePolygon(source)
  const current = polygon.points[pointIndex]
  if (!current) return
  polygon.points[pointIndex] = roundPoint({
    x: Math.max(0, Math.min(props.metadata.display_width, current.x + movement.x * step)),
    y: Math.max(0, Math.min(props.metadata.display_height, current.y + movement.y * step)),
  })
  if (polygonArea(polygon.points) < 1) {
    editMessage.value = '该方向会让多边形退化，顶点未移动。'
    return
  }
  editMessage.value = ''
  emit('update:draft', props.regions, props.polygons.map((item, index) => (
    index === polygonIndex ? polygon : item
  )), props.protectedRegions)
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

function appendWithLimit(regions: ImageMaskRegion[], polygons: ImageMaskPolygon[], protectedRegions: ImageMaskRegion[]) {
  if (regions.length > 100 || polygons.length > 32 || protectedRegions.length > 100) {
    emit('limit-reached')
    return
  }
  emit('update:draft', regions, polygons, protectedRegions)
}

function completePolygon() {
  if (polygonPoints.value.length < 3) return
  const polygon: ImageMaskPolygon = {
    points: polygonPoints.value.map(roundPoint),
    transform_id: props.metadata.transform_id,
  }
  appendWithLimit(props.regions, [...props.polygons, polygon], props.protectedRegions)
  polygonPoints.value = []
}

function removeMask(index: number) {
  emit('update:draft', props.regions.filter((_, itemIndex) => itemIndex !== index), props.polygons, props.protectedRegions)
}

function removePolygon(index: number) {
  emit('update:draft', props.regions, props.polygons.filter((_, itemIndex) => itemIndex !== index), props.protectedRegions)
}

function removeProtection(index: number) {
  emit('update:draft', props.regions, props.polygons, props.protectedRegions.filter((_, itemIndex) => itemIndex !== index))
}

function clearMasks() { emit('update:draft', [], [], props.protectedRegions) }
function clearProtections() { emit('update:draft', props.regions, props.polygons, []) }

function handleKeydown(event: KeyboardEvent) {
  if (tool.value === 'polygon' && event.key === 'Enter' && polygonPoints.value.length >= 3) {
    event.preventDefault()
    completePolygon()
    return
  }
  if (tool.value === 'polygon' && event.key === 'Escape' && polygonPoints.value.length) {
    event.preventDefault()
    polygonPoints.value = []
    return
  }
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

function roundPoint(selected: Point): Point {
  return { x: Number(selected.x.toFixed(2)), y: Number(selected.y.toFixed(2)) }
}

function clonePolygon(polygon: ImageMaskPolygon): ImageMaskPolygon {
  return {
    ...polygon,
    points: polygon.points.map(item => ({ ...item })),
  }
}

function polygonArea(points: readonly Point[]) {
  return Math.abs(points.reduce((total, item, index) => {
    const next = points[(index + 1) % points.length]
    if (!next) return total
    return total + item.x * next.y - next.x * item.y
  }, 0)) / 2
}

function polygonPointsAttribute(polygon: ImageMaskPolygon | { points: Point[] }) {
  return polygon.points.map(item => `${item.x},${item.y}`).join(' ')
}

function polygonTouchesRegion(polygon: ImageMaskPolygon, region: ImageMaskRegion) {
  const bounds = {
    x0: Math.min(...polygon.points.map(item => item.x)),
    y0: Math.min(...polygon.points.map(item => item.y)),
    x1: Math.max(...polygon.points.map(item => item.x)),
    y1: Math.max(...polygon.points.map(item => item.y)),
    transform_id: polygon.transform_id,
  }
  return intersects(bounds, region)
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
      <button type="button" :aria-pressed="tool === 'polygon'" @click="selectTool('polygon')">多边形</button>
      <button type="button" :aria-pressed="tool === 'edit-polygon'" :disabled="polygons.length === 0" @click="selectTool('edit-polygon')">编辑顶点</button>
      <button type="button" :aria-pressed="tool === 'brush'" @click="selectTool('brush')">画笔</button>
      <button type="button" :aria-pressed="tool === 'eraser'" @click="selectTool('eraser')">橡皮</button>
      <button type="button" :aria-pressed="tool === 'protect'" @click="selectTool('protect')">保护区</button>
      <button type="button" :aria-pressed="tool === 'pan'" :disabled="zoom <= 1" @click="selectTool('pan')">平移</button>
      <button v-if="tool === 'polygon'" type="button" :disabled="polygonPoints.length < 3" @click="completePolygon">完成多边形</button>
      <button v-if="tool === 'polygon'" type="button" :disabled="polygonPoints.length === 0" @click="polygonPoints = []">取消绘制</button>
      <label v-if="tool === 'brush' || tool === 'eraser' || tool === 'protect'" class="brush-size-control">笔刷 {{ brushSize }} px <input v-model.number="brushSize" type="range" min="4" max="80" step="2" /></label>
      <button type="button" class="visibility-button" :aria-pressed="maskVisible" @click="maskVisible = !maskVisible">{{ maskVisible ? '隐藏蒙版' : '显示蒙版' }}</button>
      <button type="button" class="visibility-button" :aria-pressed="protectionVisible" @click="protectionVisible = !protectionVisible">{{ protectionVisible ? '隐藏保护区' : '显示保护区' }}</button>
    </div>
    <div class="image-view-controls" role="toolbar" aria-label="图片视图控制">
      <button type="button" class="secondary-button" aria-label="缩小图片" :disabled="zoom <= 1" @click="setZoom(zoom - 0.5)">−</button>
      <output aria-live="polite" aria-label="当前缩放比例">{{ Math.round(zoom * 100) }}%</output>
      <button type="button" class="secondary-button" aria-label="放大图片" :disabled="zoom >= 4" @click="setZoom(zoom + 0.5)">＋</button>
      <button type="button" class="secondary-button" :disabled="zoom === 1" @click="resetView">复位视图</button>
      <span>放大后选择“平移”拖动画布；切回绘制工具即可继续标记。</span>
    </div>
    <p class="hint">{{ instruction }} 最多 100 个矩形、32 个多边形和 100 个保护区片段。</p>
    <p v-if="editMessage" class="warning" role="status">{{ editMessage }}</p>
    <p v-if="loading" class="hint">正在加载图片预览…</p>
    <p v-if="error" class="warning">{{ error }}</p>
    <div ref="viewportElement" class="image-mask-viewport" tabindex="0" aria-label="可缩放图片视口">
      <div class="image-mask-stage" :style="stageStyle">
        <div ref="canvasElement" class="image-mask-canvas" :class="[{ loading }, `tool-${tool}`]" @pointerdown="begin" @pointermove="move" @pointerup="finish" @pointercancel="cancel">
          <img ref="imageElement" :src="sourceUrl" alt="待编辑水印蒙版的原始图片" draggable="false" @load="loading = false" @error="loading = false; error = '图片预览加载失败。'" />
          <template v-if="maskVisible">
            <div v-for="(region, index) in regions" :key="`mask-${index}-${region.x0}-${region.y0}`" class="image-mask-region" :style="regionStyle(region)"><span>{{ index + 1 }}</span></div>
            <svg class="image-polygon-layer" :class="{ editing: tool === 'edit-polygon' }" :viewBox="`0 0 ${metadata.display_width} ${metadata.display_height}`" preserveAspectRatio="none" role="group" aria-label="多边形蒙版顶点">
              <template v-for="(polygon, polygonIndex) in displayedPolygons" :key="`polygon-${polygonIndex}`">
                <polygon :points="polygonPointsAttribute(polygon)" class="image-mask-polygon" :class="{ active: vertexDrag?.polygonIndex === polygonIndex }" />
                <circle
                  v-for="(item, pointIndex) in polygon.points"
                  v-show="tool === 'edit-polygon'"
                  :key="`polygon-${polygonIndex}-point-${pointIndex}`"
                  :cx="item.x"
                  :cy="item.y"
                  :r="polygonHandleRadius"
                  class="polygon-edit-handle"
                  tabindex="0"
                  role="button"
                  :aria-label="`多边形 ${polygonIndex + 1} 顶点 ${pointIndex + 1}`"
                  @pointerdown.stop="beginVertexDrag($event, polygonIndex, pointIndex)"
                  @keydown="nudgePolygonPoint($event, polygonIndex, pointIndex)"
                />
              </template>
              <polyline v-if="polygonPoints.length" :points="polygonPointsAttribute({ points: polygonPoints })" class="image-mask-polygon draft" />
              <circle v-for="(item, index) in polygonPoints" :key="`polygon-point-${index}`" :cx="item.x" :cy="item.y" :r="polygonHandleRadius" class="polygon-point" />
            </svg>
          </template>
          <template v-if="protectionVisible">
            <div v-for="(region, index) in protectedRegions" :key="`protected-${index}-${region.x0}-${region.y0}`" class="image-protected-region" :style="regionStyle(region)"><span>P{{ index + 1 }}</span></div>
          </template>
          <div v-if="rectangleDraft" class="image-mask-region draft" :style="regionStyle(rectangleDraft)" />
          <div v-for="(region, index) in draftRegions" :key="`draft-${index}`" :class="tool === 'protect' ? 'image-protected-region draft' : tool === 'eraser' ? 'image-eraser-region draft' : 'image-mask-region draft'" :style="regionStyle(region)" />
        </div>
      </div>
    </div>
    <div class="image-mask-toolbar">
      <p class="hint">编辑器聚焦时可用 ⌘/Ctrl+Z 撤销，⌘/Ctrl+Shift+Z 或 Ctrl+Y 重做。</p>
      <div class="image-mask-actions">
        <button class="secondary-button" type="button" :disabled="!canUndo" @click="emit('undo')">撤销</button>
        <button class="secondary-button" type="button" :disabled="!canRedo" @click="emit('redo')">重做</button>
        <button class="secondary-button" type="button" :disabled="!regions.length && !polygons.length" @click="clearMasks">清空蒙版</button>
        <button class="secondary-button" type="button" :disabled="!protectedRegions.length" @click="clearProtections">清空保护区</button>
      </div>
    </div>
    <div v-if="regions.length || polygons.length || protectedRegions.length" class="mask-region-lists">
      <section v-if="regions.length"><h3>修复蒙版 · {{ regions.length }}</h3><ol class="mask-region-list"><li v-for="(region, index) in regions" :key="`mask-list-${index}`"><span>区域 {{ index + 1 }}：{{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} → {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}</span><button class="secondary-button" type="button" @click="removeMask(index)">移除</button></li></ol></section>
      <section v-if="polygons.length"><h3>多边形蒙版 · {{ polygons.length }}</h3><ol class="mask-region-list"><li v-for="(polygon, index) in polygons" :key="`polygon-list-${index}`"><span>多边形 {{ index + 1 }}：{{ polygon.points.length }} 个顶点</span><button class="secondary-button" type="button" @click="removePolygon(index)">移除</button></li></ol></section>
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
.image-view-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 10px 0; }
.image-view-controls button { min-width: 42px; padding: 7px 11px; }
.image-view-controls output { min-width: 58px; color: #315143; font-weight: 750; text-align: center; }
.image-view-controls span { color: #607068; font-size: .8rem; }
.image-mask-viewport { width: min(100%, 920px); max-height: 720px; overflow: auto; overscroll-behavior: contain; border: 1px solid #c8d0c8; border-radius: 12px; background: #eef0eb; }
.image-mask-viewport:focus-visible { outline: 3px solid rgba(32, 92, 67, .28); outline-offset: 2px; }
.image-mask-stage { min-width: 100%; }
.image-mask-canvas { position: relative; width: 100%; line-height: 0; overflow: hidden; background: #eef0eb; touch-action: none; }
.image-mask-canvas.loading { min-height: 240px; opacity: .55; }
.image-mask-canvas img { display: block; width: 100%; height: auto; cursor: crosshair; user-select: none; }
.image-mask-canvas.tool-brush img { cursor: cell; }
.image-mask-canvas.tool-polygon img { cursor: crosshair; }
.image-mask-canvas.tool-edit-polygon img { cursor: default; }
.image-mask-canvas.tool-eraser img { cursor: not-allowed; }
.image-mask-canvas.tool-protect img { cursor: copy; }
.image-mask-canvas.tool-pan img { cursor: grab; }
.image-mask-canvas.tool-pan:active img { cursor: grabbing; }
.image-mask-region, .image-protected-region, .image-eraser-region { position: absolute; box-sizing: border-box; pointer-events: none; }
.image-polygon-layer { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.image-polygon-layer.editing { pointer-events: auto; }
.image-mask-polygon { fill: rgba(210, 72, 50, .22); stroke: #d24832; stroke-width: 2; vector-effect: non-scaling-stroke; }
.image-mask-polygon.active { fill: rgba(210, 72, 50, .3); stroke-width: 3; }
.image-mask-polygon.draft { fill: none; stroke-dasharray: 7 5; }
.polygon-point { fill: #fff; stroke: #b73524; stroke-width: 2; vector-effect: non-scaling-stroke; }
.polygon-edit-handle { fill: #fff; stroke: #b73524; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: grab; pointer-events: all; }
.polygon-edit-handle:active { cursor: grabbing; }
.polygon-edit-handle:focus { outline: none; fill: #ffecb5; stroke: #7b281e; stroke-width: 3; }
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
@media (max-width: 720px) { .image-editor-tools .visibility-button { margin-left: 0; } .image-view-controls span { flex-basis: 100%; } .image-mask-viewport { max-height: 70vh; } .image-mask-toolbar { align-items: flex-start; flex-direction: column; } }
</style>
