<script setup lang="ts">
import { computed } from 'vue'

import type { ProcessingTask } from '@/api/client'

const props = defineProps<{
  task: ProcessingTask
  sourceSha256: string
  assetId: string
  isImage: boolean
}>()

defineEmits<{
  cancel: []
}>()

const active = computed(() => ['queued', 'running', 'cancelling'].includes(props.task.status))
const outputArtifacts = computed(() => (
  props.task.artifacts.filter(artifact => artifact.role === 'output')
))
const imageOutput = computed(() => outputArtifacts.value[0] || null)

const statusLabels: Record<ProcessingTask['status'], string> = {
  queued: '等待处理',
  running: '正在处理',
  cancelling: '正在取消',
  cancelled: '已取消',
  succeeded: '已完成',
  failed: '处理失败',
}
</script>

<template>
  <section class="panel workspace-task-panel" aria-labelledby="workspace-task-title">
    <div class="workspace-task-heading">
      <div>
        <p class="eyebrow">本地处理任务</p>
        <h2 id="workspace-task-title">{{ task.stage }}</h2>
      </div>
      <span :class="['task-status', task.status]">{{ statusLabels[task.status] }}</span>
    </div>
    <p class="workspace-task-meta">
      进度 {{ Math.round(task.progress * 100) }}%
      <template v-if="task.duration_seconds !== null">
        · 用时 {{ task.duration_seconds.toFixed(1) }} 秒
      </template>
      <template v-if="task.warning_codes.length">
        · 已确认 {{ task.warning_codes.length }} 项风险
      </template>
    </p>
    <div
      class="progress-track"
      role="progressbar"
      aria-label="任务进度"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="Math.round(task.progress * 100)"
    >
      <span :style="{ width: `${task.progress * 100}%` }"></span>
    </div>
    <p v-if="task.error" class="task-error" role="alert">{{ task.error.message }}</p>
    <p v-else-if="task.status === 'cancelled'" class="workspace-task-note">
      任务已取消，未保留未经验证的输出文件。
    </p>
    <div v-if="active || ['cancelled', 'failed'].includes(task.status)" class="workspace-task-actions">
      <button
        v-if="active"
        class="secondary-button"
        :disabled="task.status === 'cancelling'"
        @click="$emit('cancel')"
      >{{ task.status === 'cancelling' ? '正在取消…' : '取消任务' }}</button>
      <a
        v-if="['cancelled', 'failed'].includes(task.status)"
        class="secondary-button report-button"
        :href="task.report_url"
      >下载处理报告</a>
    </div>
  </section>

  <article v-if="task.status === 'succeeded'" class="result-card">
    <div>
      <p class="eyebrow">处理完成</p>
      <h3>{{ task.stage }}</h3>
      <p v-if="outputArtifacts[0]" class="result-meta">
        原件 {{ sourceSha256.slice(0, 12) }}… ·
        副本 {{ outputArtifacts[0].sha256.slice(0, 12) }}… ·
        {{ (outputArtifacts[0].size_bytes / 1024).toFixed(1) }} KB
      </p>
    </div>
    <a
      v-for="artifact in outputArtifacts"
      :key="artifact.id"
      class="download-button"
      :href="artifact.download_url"
    >下载 {{ artifact.display_name }}</a>
    <a class="secondary-button report-button" :href="task.report_url">下载处理报告</a>
  </article>

  <section v-if="isImage && task.status === 'succeeded' && imageOutput" class="comparison-panel panel">
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

  <section v-if="task.comparison" class="comparison-panel panel">
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
</template>
