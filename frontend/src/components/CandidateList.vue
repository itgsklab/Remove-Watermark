<script setup lang="ts">
import type { Analysis, Candidate } from '@/api/client'

const props = defineProps<{
  candidates: Candidate[]
  preset: Analysis['preset']
  canProcess: boolean
  busy: boolean
  selectedCandidateIds: string[]
  confirmedCandidateIds: string[]
}>()

const emit = defineEmits<{
  'update:selectedCandidateIds': [value: string[]]
  'update:confirmedCandidateIds': [value: string[]]
}>()

function classificationLabel(candidate: Candidate) {
  if (candidate.kind === 'image' && candidate.allowed_strategies.length === 0) {
    return '图片待复核 · 只读'
  }
  if (candidate.classification === 'confirmed') {
    return props.preset === 'general' ? '结构明确' : '与目标匹配'
  }
  if (candidate.classification === 'ambiguous') return '需要复核'
  return '正常内容'
}

function sourceLabel(candidate: Candidate) {
  const locator = candidate.source_locator
  if (locator.part_name) return locator.part_name
  if (locator.page_numbers.length) return `第 ${locator.page_numbers.join('、')} 页`
  return '未知来源'
}

function updateSelection(candidateId: string, checked: boolean) {
  emit(
    'update:selectedCandidateIds',
    checked
      ? [...props.selectedCandidateIds, candidateId]
      : props.selectedCandidateIds.filter(item => item !== candidateId),
  )
}

function updateConfirmation(candidateId: string, checked: boolean) {
  emit(
    'update:confirmedCandidateIds',
    checked
      ? [...props.confirmedCandidateIds, candidateId]
      : props.confirmedCandidateIds.filter(item => item !== candidateId),
  )
}
</script>

<template>
  <div class="candidate-list">
    <article
      v-for="candidate in candidates"
      :key="candidate.candidate_id"
      class="candidate-card"
      :aria-labelledby="`candidate-title-${candidate.candidate_id}`"
    >
      <div>
        <figure v-if="candidate.preview_url" class="candidate-image-preview">
          <img :src="candidate.preview_url" :alt="`${candidate.content || 'DrawingML 图片'}候选预览`" />
          <figcaption>DOCX 内嵌图片处理前预览</figcaption>
        </figure>
        <label v-if="canProcess && candidate.allowed_strategies.includes('object')" class="candidate-select">
          <input
            type="checkbox"
            :checked="selectedCandidateIds.includes(candidate.candidate_id)"
            :disabled="busy || candidate.classification === 'content'"
            @change="updateSelection(candidate.candidate_id, ($event.target as HTMLInputElement).checked)"
          />
          选择此候选
        </label>
        <span :class="['candidate-state', candidate.classification]">
          {{ classificationLabel(candidate) }}
        </span>
        <h3 :id="`candidate-title-${candidate.candidate_id}`">
          {{ candidate.content || '无法读取文字' }}
        </h3>
        <p>{{ candidate.evidence }}</p>
        <label
          v-if="candidate.classification === 'ambiguous' && selectedCandidateIds.includes(candidate.candidate_id)"
          class="risk-confirm"
        >
          <input
            type="checkbox"
            :checked="confirmedCandidateIds.includes(candidate.candidate_id)"
            :disabled="busy"
            @change="updateConfirmation(candidate.candidate_id, ($event.target as HTMLInputElement).checked)"
          />
          我已核对该对象，确认将它从输出副本中删除
        </label>
      </div>
      <dl>
        <dt>来源</dt><dd>{{ sourceLabel(candidate) }}</dd>
        <template v-if="candidate.source_locator.shape_id">
          <dt>形状 ID</dt><dd>{{ candidate.source_locator.shape_id }}</dd>
        </template>
        <template v-if="candidate.source_locator.drawing_index !== null">
          <dt>绘图序号</dt><dd>{{ candidate.source_locator.drawing_index + 1 }}</dd>
          <dt>图片关系</dt><dd>{{ candidate.source_locator.relationship_id }}</dd>
          <dt>内嵌资源</dt><dd>{{ candidate.source_locator.media_part_name }}</dd>
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
  </div>
</template>
