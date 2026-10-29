import { computed, ref } from 'vue'
import type { ImageMaskPolygon, ImageMaskRegion } from '@/api/client'

export interface ImageMaskDraft {
  regions: ImageMaskRegion[]
  polygons: ImageMaskPolygon[]
  protectedRegions: ImageMaskRegion[]
}

export type ImageMaskDraftUpdate = 'updated' | 'unchanged' | 'limit-reached'

const historyLimit = 50
const regionLimit = 100
const polygonLimit = 32

export function useImageMaskDraft() {
  const regions = ref<ImageMaskRegion[]>([])
  const polygons = ref<ImageMaskPolygon[]>([])
  const protectedRegions = ref<ImageMaskRegion[]>([])
  const past = ref<ImageMaskDraft[]>([])
  const future = ref<ImageMaskDraft[]>([])

  const canUndo = computed(() => past.value.length > 0)
  const canRedo = computed(() => future.value.length > 0)

  function current(): ImageMaskDraft {
    return {
      regions: regions.value,
      polygons: polygons.value,
      protectedRegions: protectedRegions.value,
    }
  }

  function apply(draft: ImageMaskDraft) {
    const copy = cloneDraft(draft)
    regions.value = copy.regions
    polygons.value = copy.polygons
    protectedRegions.value = copy.protectedRegions
  }

  function update(draft: ImageMaskDraft): ImageMaskDraftUpdate {
    if (
      draft.regions.length > regionLimit
      || draft.polygons.length > polygonLimit
      || draft.protectedRegions.length > regionLimit
    ) return 'limit-reached'

    const next = cloneDraft(draft)
    if (sameDraft(current(), next)) return 'unchanged'
    past.value.push(cloneDraft(current()))
    if (past.value.length > historyLimit) past.value.shift()
    future.value = []
    apply(next)
    return 'updated'
  }

  function undo() {
    const previous = past.value.pop()
    if (!previous) return false
    future.value.push(cloneDraft(current()))
    apply(previous)
    return true
  }

  function redo() {
    const next = future.value.pop()
    if (!next) return false
    past.value.push(cloneDraft(current()))
    apply(next)
    return true
  }

  function reset() {
    regions.value = []
    polygons.value = []
    protectedRegions.value = []
    past.value = []
    future.value = []
  }

  return {
    regions,
    polygons,
    protectedRegions,
    canUndo,
    canRedo,
    update,
    undo,
    redo,
    reset,
  }
}

function cloneDraft(draft: ImageMaskDraft): ImageMaskDraft {
  return {
    regions: draft.regions.map(region => ({ ...region })),
    polygons: draft.polygons.map(polygon => ({
      ...polygon,
      points: polygon.points.map(point => ({ ...point })),
    })),
    protectedRegions: draft.protectedRegions.map(region => ({ ...region })),
  }
}

function sameRegions(left: ImageMaskRegion[], right: ImageMaskRegion[]) {
  return left.length === right.length && left.every((region, index) => {
    const other = right[index]
    return other !== undefined
      && region.x0 === other.x0
      && region.y0 === other.y0
      && region.x1 === other.x1
      && region.y1 === other.y1
      && region.transform_id === other.transform_id
  })
}

function sameDraft(left: ImageMaskDraft, right: ImageMaskDraft) {
  return sameRegions(left.regions, right.regions)
    && JSON.stringify(left.polygons) === JSON.stringify(right.polygons)
    && sameRegions(left.protectedRegions, right.protectedRegions)
}
