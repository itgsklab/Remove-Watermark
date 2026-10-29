<script setup lang="ts">
import { computed } from 'vue'
import ImageMaskEditor from '@/components/ImageMaskEditor.vue'
import type {
  ImageMaskPolygon,
  ImageMaskPreview,
  ImageMaskRegion,
  ImageMetadata,
  PlanWarning,
} from '@/api/client'

interface RadiusPreview {
  radius: number
  url: string
}

const props = defineProps<{
  assetId: string
  metadata: ImageMetadata
  regions: ImageMaskRegion[]
  polygons: ImageMaskPolygon[]
  protectedRegions: ImageMaskRegion[]
  canUndo: boolean
  canRedo: boolean
  preview: ImageMaskPreview | null
  radiusPreviews: RadiusPreview[]
  previewBusy: boolean
  planWarnings: PlanWarning[]
  vlmAvailable: boolean
  vlmMessage: string
  vlmBusy: boolean
  vlmWarnings: string[]
  busy: boolean
}>()

const emit = defineEmits<{
  updateDraft: [regions: ImageMaskRegion[], polygons: ImageMaskPolygon[], protectedRegions: ImageMaskRegion[]]
  undo: []
  redo: []
  limitReached: []
  suggest: []
  validate: []
  compareRadii: []
  process: []
}>()

const radius = defineModel<number>('radius', { required: true })
const confirmedWarnings = defineModel<string[]>('confirmedWarnings', { required: true })

function updateDraft(
  regions: ImageMaskRegion[],
  polygons: ImageMaskPolygon[],
  protectedRegions: ImageMaskRegion[],
) {
  emit('updateDraft', regions, polygons, protectedRegions)
}

const complexityLabels = {
  low: '低风险',
  review: '建议复核',
  high: '高风险',
} as const

const repairGuidance = computed(() => {
  const preview = props.preview
  if (!preview) return null
  if (preview.complexity.level === 'high') {
    return {
      level: 'high',
      title: '建议先重新调整选区',
      summary: '当前背景包含难以连续重建的结构。缩小蒙版，避免覆盖人物五官、文字笔画或贯穿边缘，再重新验证。',
      actions: ['把一个大选区拆成多个紧贴水印的小选区', '使用保护区排除正文、五官和连续轮廓', '调整后比较多个修复半径并放大检查边界'],
    }
  }
  if (preview.complexity.level === 'review' || preview.selection_risk.level === 'review') {
    return {
      level: 'review',
      title: '建议比较预览后再处理',
      summary: '当前选区存在纹理、低对比度或面积风险。先比较修复半径，并重点检查边缘与主体细节。',
      actions: ['优先从半径 1–3 开始比较', '确认蒙版没有覆盖需要保留的内容'],
    }
  }
  return {
    level: 'low',
    title: '适合进行轻量修复预览',
    summary: '周围背景较平滑；仍建议先查看临时预览，再生成最终副本。',
    actions: [],
  }
})
</script>

<template>
  <section class="panel image-mask-panel">
    <div class="image-metadata-heading">
      <div>
        <p class="eyebrow">图片蒙版草稿</p>
        <h2>标记水印并保护正文</h2>
      </div>
      <dl class="image-metadata-grid">
        <div><dt>显示尺寸</dt><dd>{{ metadata.display_width }} × {{ metadata.display_height }}</dd></div>
        <div><dt>原始格式</dt><dd>{{ metadata.format }} · {{ metadata.mode }}</dd></div>
        <div><dt>透明通道</dt><dd>{{ metadata.has_alpha ? '有' : '无' }}</dd></div>
        <div><dt>帧数</dt><dd>{{ metadata.frames }}</dd></div>
        <div><dt>EXIF 方向</dt><dd>{{ metadata.exif_orientation }}</dd></div>
        <div><dt>ICC 配置</dt><dd>{{ metadata.has_icc_profile ? '有' : '无' }}</dd></div>
      </dl>
    </div>
    <section class="vlm-suggestion-panel">
      <div>
        <p class="eyebrow">可选本地模型</p>
        <h3>照片水印候选区域</h3>
        <p>{{ vlmMessage || '正在读取本地模型状态…' }}</p>
        <p class="hint">不会自动下载模型或修改图片；候选框只会填入下方蒙版草稿。</p>
      </div>
      <button
        class="secondary-button"
        :disabled="busy || vlmBusy || !vlmAvailable"
        @click="emit('suggest')"
      >
        {{ vlmBusy ? '正在生成建议…' : '使用本地模型建议区域' }}
      </button>
    </section>
    <p v-for="warning in vlmWarnings" :key="warning" class="warning">{{ warning }}</p>
    <ImageMaskEditor
      :asset-id="assetId"
      :metadata="metadata"
      :regions="regions"
      :polygons="polygons"
      :protected-regions="protectedRegions"
      :can-undo="canUndo"
      :can-redo="canRedo"
      @update:draft="updateDraft"
      @undo="emit('undo')"
      @redo="emit('redo')"
      @limit-reached="emit('limitReached')"
    />
    <div class="process-actions">
      <button :disabled="busy || regions.length + polygons.length === 0" @click="emit('validate')">
        {{ busy ? '正在验证…' : `验证蒙版草稿（${regions.length} 个矩形，${polygons.length} 个多边形，${protectedRegions.length} 个保护区）` }}
      </button>
      <p>先验证坐标和覆盖面积，再生成新的 PNG 副本。</p>
    </div>
    <template v-if="preview">
      <p class="mask-coverage">
        合并覆盖 {{ preview.covered_pixels.toFixed(0) }} 像素，约占图片
        {{ (preview.coverage_ratio * 100).toFixed(2) }}%。
      </p>
      <section
        class="selection-risk-summary"
        :class="{ 'needs-review': preview.selection_risk.level === 'review' }"
      >
        <div class="complexity-heading">
          <div>
            <p class="eyebrow">移动端水印风险</p>
            <h3>{{ preview.selection_risk.level === 'review' ? '执行前需要确认' : '未发现额外选区风险' }}</h3>
          </div>
          <span class="complexity-badge">
            {{ preview.selection_risk.level === 'review' ? '建议复核' : '正常' }}
          </span>
        </div>
        <p v-if="preview.selection_risk.large_selection" class="complexity-note">
          合并选区达到图片面积的 10%，大面积修复需要检查前后对比。
        </p>
        <article
          v-for="region in preview.selection_risk.regions"
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
      <section class="complexity-summary" :class="`risk-${preview.complexity.level}`">
        <div class="complexity-heading">
          <div>
            <p class="eyebrow">OpenCV 修复预检</p>
            <h3>背景复杂度：{{ complexityLabels[preview.complexity.level] }}</h3>
          </div>
          <span class="complexity-badge">{{ complexityLabels[preview.complexity.level] }}</span>
        </div>
        <article
          v-for="region in preview.complexity.regions"
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
      <aside
        v-if="repairGuidance"
        class="repair-guidance"
        :class="`guidance-${repairGuidance.level}`"
        aria-live="polite"
      >
        <p class="eyebrow">下一步建议</p>
        <h3>{{ repairGuidance.title }}</h3>
        <p>{{ repairGuidance.summary }}</p>
        <ul v-if="repairGuidance.actions.length">
          <li v-for="action in repairGuidance.actions" :key="action">{{ action }}</li>
        </ul>
      </aside>
      <p v-for="warning in preview.warnings" :key="warning" class="warning">{{ warning }}</p>
      <div v-if="preview.executable" class="image-process-options">
        <label for="image-radius">
          修复半径
          <input id="image-radius" v-model.number="radius" type="number" min="1" max="10" />
        </label>
        <p class="hint">建议从 3 开始；细小水印可用 1–3，较粗边缘可提高到 5–7。</p>
        <button class="secondary-button" :disabled="busy || previewBusy" @click="emit('compareRadii')">
          {{ previewBusy ? '正在生成对比…' : '比较修复半径效果' }}
        </button>
      </div>
      <section v-if="radiusPreviews.length" class="radius-preview-panel" aria-label="修复半径效果对比">
        <div class="complexity-heading">
          <div>
            <p class="eyebrow">处理前效果预览</p>
            <h3>选择修复半径</h3>
          </div>
          <span class="complexity-badge">临时生成</span>
        </div>
        <p class="hint">预览使用当前蒙版在内存中生成，不会保存结果文件；点击图片即可选用该半径。</p>
        <div class="radius-preview-grid">
          <button
            v-for="item in radiusPreviews"
            :key="item.radius"
            type="button"
            class="radius-preview-card"
            :class="{ selected: radius === item.radius }"
            :aria-pressed="radius === item.radius"
            :aria-label="`选用修复半径 ${item.radius}`"
            @click="radius = item.radius"
          >
            <img :src="item.url" :alt="`修复半径 ${item.radius} 的临时效果预览`" />
            <span>半径 {{ item.radius }}{{ radius === item.radius ? ' · 当前选择' : '' }}</span>
          </button>
        </div>
      </section>
      <template v-for="warning in planWarnings" :key="warning.code">
        <label v-if="warning.requires_acknowledgement" class="risk-confirm">
          <input
            v-model="confirmedWarnings"
            type="checkbox"
            :value="warning.code"
            :disabled="busy"
          />
          {{ warning.message }}我已检查并确认继续。
        </label>
        <p v-else class="warning">{{ warning.message }}</p>
      </template>
      <div v-if="preview.executable" class="process-actions">
        <button :disabled="busy || previewBusy" @click="emit('process')">
          {{ busy ? '正在处理…' : '使用 OpenCV 生成修复副本' }}
        </button>
        <p>结果使用无损 PNG、移除 EXIF/ICC 元数据，并验证蒙版外像素没有变化。</p>
      </div>
    </template>
  </section>
</template>
