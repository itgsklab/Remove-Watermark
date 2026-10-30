import { onScopeDispose, ref, type Ref } from 'vue'

import {
  ApiError,
  cancelTask,
  getTask,
  type ProcessingTask,
} from '@/api/client'

interface TaskExecutionOptions {
  message: Ref<string>
  pollIntervalMs?: number
  pollTimeoutMs?: number
}

const ACTIVE_STATUSES: ProcessingTask['status'][] = ['queued', 'running', 'cancelling']

export function useTaskExecution(options: TaskExecutionOptions) {
  const task = ref<ProcessingTask | null>(null)
  let pollingGeneration = 0

  function resetTask() {
    pollingGeneration += 1
    task.value = null
  }

  async function runTask(created: ProcessingTask) {
    const generation = ++pollingGeneration
    task.value = created
    options.message.value = created.stage
    const deadline = Date.now() + (options.pollTimeoutMs ?? 60_000)

    while (
      generation === pollingGeneration
      && task.value
      && ACTIVE_STATUSES.includes(task.value.status)
    ) {
      if (Date.now() > deadline) {
        options.message.value = '任务仍在后台运行，可以稍后刷新任务状态。'
        return
      }
      await new Promise<void>(resolve => window.setTimeout(
        resolve,
        options.pollIntervalMs ?? 400,
      ))
      if (generation !== pollingGeneration || !task.value) return
      const taskId = task.value.id
      const updatedTask = await getTask(taskId)
      if (generation !== pollingGeneration || task.value?.id !== taskId) return
      task.value = updatedTask
      options.message.value = task.value.stage
    }

    if (generation !== pollingGeneration || !task.value) return
    if (task.value.status === 'failed') {
      options.message.value = task.value.error?.message || '处理失败。'
    } else if (task.value.status === 'cancelled') {
      options.message.value = '任务已取消，未保留未验证的输出文件。'
    }
  }

  async function requestCancellation() {
    if (!task.value || !['queued', 'running'].includes(task.value.status)) return
    const generation = pollingGeneration
    const taskId = task.value.id
    try {
      const updatedTask = await cancelTask(taskId)
      if (generation !== pollingGeneration || task.value?.id !== taskId) return
      task.value = updatedTask
      options.message.value = task.value.stage
    } catch (error) {
      if (generation !== pollingGeneration) return
      options.message.value = error instanceof ApiError ? error.message : '无法取消任务。'
    }
  }

  onScopeDispose(() => {
    pollingGeneration += 1
  })

  return {
    task,
    resetTask,
    runTask,
    requestCancellation,
  }
}
