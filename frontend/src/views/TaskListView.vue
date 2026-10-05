<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  ApiError,
  cancelTask,
  getTasks,
  type ProcessingTask,
} from '@/api/client'

const tasks = ref<ProcessingTask[]>([])
const loading = ref(true)
const message = ref('')
let timer: number | undefined

const hasActiveTasks = computed(() => tasks.value.some(
  task => ['queued', 'running', 'cancelling'].includes(task.status),
))

onMounted(async () => {
  await refresh()
  timer = window.setInterval(() => {
    if (hasActiveTasks.value) void refresh(false)
  }, 1000)
})

onUnmounted(() => {
  if (timer !== undefined) window.clearInterval(timer)
})

async function refresh(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    tasks.value = await getTasks()
    message.value = ''
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法读取任务列表。'
  } finally {
    loading.value = false
  }
}

async function cancel(task: ProcessingTask) {
  try {
    const updated = await cancelTask(task.id)
    tasks.value = tasks.value.map(item => item.id === updated.id ? updated : item)
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '无法取消任务。'
  }
}

function statusLabel(status: ProcessingTask['status']) {
  return {
    queued: '等待中',
    running: '处理中',
    cancelling: '正在取消',
    cancelled: '已取消',
    succeeded: '已完成',
    failed: '失败',
  }[status]
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>

<template>
  <section class="tasks-head">
    <div>
      <p class="eyebrow">本地任务</p>
      <h1>处理记录</h1>
      <p class="intro">任务保存在本机。刷新页面或重启服务后，可以继续查看状态和下载仍在保留期内的结果。</p>
    </div>
    <button class="secondary-button" :disabled="loading" @click="refresh()">刷新</button>
  </section>

  <p v-if="message" class="warning" role="alert">{{ message }}</p>
  <p v-if="loading && tasks.length === 0" class="message">正在读取任务…</p>
  <section v-else-if="tasks.length" class="task-list">
    <article v-for="task in tasks" :key="task.id" class="panel task-row">
      <div class="task-main">
        <div class="task-title-row">
          <span :class="['task-status', task.status]">{{ statusLabel(task.status) }}</span>
          <code>{{ task.id.slice(0, 8) }}</code>
        </div>
        <h2>{{ task.stage }}</h2>
        <p>{{ formatTime(task.created_at) }} · {{ Math.round(task.progress * 100) }}%</p>
        <div class="progress-track" aria-hidden="true">
          <span :style="{ width: `${task.progress * 100}%` }"></span>
        </div>
        <p v-if="task.error" class="task-error">{{ task.error.message }}</p>
      </div>
      <div class="task-actions">
        <button
          v-if="['queued', 'running'].includes(task.status)"
          class="secondary-button"
          @click="cancel(task)"
        >取消</button>
        <a
          v-for="artifact in task.artifacts.filter(item => item.role === 'output')"
          :key="artifact.id"
          class="download-button"
          :href="artifact.download_url"
        >下载结果</a>
      </div>
    </article>
  </section>
  <section v-else class="empty-state task-empty">
    <p class="eyebrow">暂无记录</p>
    <h1>还没有处理任务</h1>
    <p>生成 DOCX、PDF 或图片修复副本后，任务会显示在这里。</p>
  </section>
</template>
