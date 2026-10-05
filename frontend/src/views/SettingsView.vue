<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, getCapabilities, shutdownDesktop, type Capabilities } from '@/api/client'

const capabilities = ref<Capabilities | null>(null)
const message = ref('')
const confirming = ref(false)
const busy = ref(false)

onMounted(async () => {
  try {
    capabilities.value = await getCapabilities()
  } catch {
    message.value = '无法读取本地服务状态。'
  }
})

async function shutdown() {
  if (!confirming.value) {
    confirming.value = true
    return
  }
  busy.value = true
  try {
    await shutdownDesktop()
    message.value = '本地服务已关闭，可以关闭这个页面。'
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '关闭本地服务失败。'
    busy.value = false
    confirming.value = false
  }
}
</script>

<template>
  <section class="settings-head">
    <p class="eyebrow">本机设置</p>
    <h1>运行与退出</h1>
    <p class="intro">文件、任务记录和处理结果保存在本机。桌面版退出时会先停止后台任务调度，再关闭本地服务。</p>
  </section>

  <section class="panel settings-panel">
    <div>
      <h2>本地服务</h2>
      <p v-if="capabilities?.desktop_mode" class="hint">桌面模式正在运行。关闭后，当前页面将无法继续访问。</p>
      <p v-else class="hint">开发服务正在运行，请回到启动它的终端退出。</p>
    </div>
    <div v-if="capabilities?.desktop_mode" class="shutdown-actions">
      <button class="danger-button" :disabled="busy" @click="shutdown">
        {{ busy ? '正在关闭…' : confirming ? '确认关闭本地服务' : '关闭本地服务' }}
      </button>
      <button v-if="confirming && !busy" class="secondary-button" @click="confirming = false">取消</button>
    </div>
    <p v-if="message" class="message" role="status">{{ message }}</p>
  </section>
</template>
