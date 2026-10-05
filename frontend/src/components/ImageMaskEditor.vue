<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImageMaskRegion, ImageMetadata } from '@/api/client'

const props = defineProps<{
  assetId: string
  metadata: ImageMetadata
  regions: ImageMaskRegion[]
}>()

const emit = defineEmits<{
  'update:regions': [regions: ImageMaskRegion[]]
}>()

const imageElement = ref<HTMLImageElement | null>(null)
const loading = ref(true)
const error = ref('')
const start = ref<{ x: number; y: number } | null>(null)
const end = ref<{ x: number; y: number } | null>(null)
const dragging = ref(false)

const sourceUrl = computed(
  () => `/api/v1/assets/${encodeURIComponent(props.assetId)}/content`,
)

const draftStyle = computed(() => {
  if (!start.value || !end.value) return null
  return regionStyle({
    x0: Math.min(start.value.x, end.value.x),
    y0: Math.min(start.value.y, end.value.y),
    x1: Math.max(start.value.x, end.value.x),
    y1: Math.max(start.value.y, end.value.y),
    transform_id: props.metadata.transform_id,
  })
})

function point(event: PointerEvent) {
  const image = imageElement.value
  if (!image) return null
  const bounds = image.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(
      props.metadata.display_width,
      (event.clientX - bounds.left) / bounds.width * props.metadata.display_width,
    )),
    y: Math.max(0, Math.min(
      props.metadata.display_height,
      (event.clientY - bounds.top) / bounds.height * props.metadata.display_height,
    )),
  }
}

function begin(event: PointerEvent) {
  if (loading.value || error.value) return
  const selected = point(event)
  if (!selected) return
  start.value = selected
  end.value = selected
  dragging.value = true
  imageElement.value?.setPointerCapture(event.pointerId)
}

function move(event: PointerEvent) {
  if (!dragging.value) return
  const selected = point(event)
  if (selected) end.value = selected
}

function finish(event: PointerEvent) {
  if (!dragging.value || !start.value) return
  const selected = point(event)
  if (selected) end.value = selected
  dragging.value = false
  imageElement.value?.releasePointerCapture(event.pointerId)
  if (!selected) return
  const region = {
    x0: Math.min(start.value.x, selected.x),
    y0: Math.min(start.value.y, selected.y),
    x1: Math.max(start.value.x, selected.x),
    y1: Math.max(start.value.y, selected.y),
    transform_id: props.metadata.transform_id,
  }
  if (region.x1 - region.x0 < 2 || region.y1 - region.y0 < 2) {
    start.value = null
    end.value = null
    return
  }
  emit('update:regions', [...props.regions, roundRegion(region)])
  start.value = null
  end.value = null
}

function cancel(event: PointerEvent) {
  dragging.value = false
  start.value = null
  end.value = null
  imageElement.value?.releasePointerCapture(event.pointerId)
}

function remove(index: number) {
  emit('update:regions', props.regions.filter((_, itemIndex) => itemIndex !== index))
}

function clear() {
  emit('update:regions', [])
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
  return {
    ...region,
    x0: Number(region.x0.toFixed(2)),
    y0: Number(region.y0.toFixed(2)),
    x1: Number(region.x1.toFixed(2)),
    y1: Number(region.y1.toFixed(2)),
  }
}
</script>

<template>
  <div class="image-mask-editor">
    <p v-if="loading" class="hint">正在加载图片预览…</p>
    <p v-if="error" class="warning">{{ error }}</p>
    <div class="image-mask-canvas" :class="{ loading }">
      <img
        ref="imageElement"
        :src="sourceUrl"
        alt="待框选水印区域的原始图片"
        draggable="false"
        @load="loading = false"
        @error="loading = false; error = '图片预览加载失败。'"
        @pointerdown="begin"
        @pointermove="move"
        @pointerup="finish"
        @pointercancel="cancel"
      />
      <div
        v-for="(region, index) in regions"
        :key="`${index}-${region.x0}-${region.y0}`"
        class="image-mask-region"
        :style="regionStyle(region)"
      ><span>{{ index + 1 }}</span></div>
      <div v-if="draftStyle" class="image-mask-region draft" :style="draftStyle" />
    </div>
    <div class="image-mask-toolbar">
      <p class="hint">在图片上拖拽矩形，可添加多个蒙版区域。</p>
      <button v-if="regions.length" class="secondary-button" type="button" @click="clear">
        清空蒙版
      </button>
    </div>
    <ol v-if="regions.length" class="mask-region-list">
      <li v-for="(region, index) in regions" :key="`mask-${index}`">
        <span>
          区域 {{ index + 1 }}：{{ region.x0.toFixed(1) }}, {{ region.y0.toFixed(1) }} →
          {{ region.x1.toFixed(1) }}, {{ region.y1.toFixed(1) }}
        </span>
        <button class="secondary-button" type="button" @click="remove(index)">移除</button>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.image-mask-editor { margin-top: 18px; }
.image-mask-canvas { position: relative; width: min(100%, 920px); line-height: 0; overflow: hidden; border: 1px solid #c8d0c8; border-radius: 12px; background: #eef0eb; touch-action: none; }
.image-mask-canvas.loading { min-height: 240px; opacity: .55; }
.image-mask-canvas img { display: block; width: 100%; height: auto; cursor: crosshair; user-select: none; }
.image-mask-region { position: absolute; border: 2px solid #d24832; background: rgba(210, 72, 50, .2); pointer-events: none; }
.image-mask-region.draft { border-style: dashed; }
.image-mask-region span { position: absolute; top: 4px; left: 4px; min-width: 22px; height: 22px; display: grid; place-items: center; border-radius: 999px; color: white; background: #b73524; font: 700 12px/1 system-ui; }
.image-mask-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.mask-region-list { display: grid; gap: 8px; padding-left: 22px; }
.mask-region-list li { padding-left: 4px; color: #536057; }
.mask-region-list li::marker { color: #b73524; font-weight: 700; }
.mask-region-list button { float: right; padding: 5px 9px; font-size: .78rem; }
</style>
