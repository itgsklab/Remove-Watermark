<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getCapabilities, type Capabilities } from '@/api/client'

const capabilities = ref<Capabilities | null>(null)
const diagnosticsError = ref('')
const copyMessage = ref('')

const diagnostics = computed(() => {
  if (!capabilities.value) return ''

  return JSON.stringify({
    schema_version: 1,
    application: 'Watermark Remover',
    version: capabilities.value.version,
    interface: 'web',
    max_upload_mb: Math.round(capabilities.value.max_upload_bytes / 1024 / 1024),
    formats: capabilities.value.formats.map((item) => ({
      id: item.id,
      status: item.status,
      strategies: item.strategies,
    })),
    vlm_localization: {
      enabled: capabilities.value.vlm_localization.enabled,
      available: capabilities.value.vlm_localization.available,
      status: capabilities.value.vlm_localization.status,
      automatic_download: capabilities.value.vlm_localization.automatic_download,
      requires_manual_review: capabilities.value.vlm_localization.requires_manual_review,
    },
  }, null, 2)
})

async function loadDiagnostics() {
  diagnosticsError.value = ''
  try {
    capabilities.value = await getCapabilities()
  } catch {
    diagnosticsError.value = '无法读取本地服务状态。请确认 Web 服务仍在运行后重试。'
  }
}

async function copyDiagnostics() {
  if (!diagnostics.value) return
  copyMessage.value = ''
  try {
    await navigator.clipboard.writeText(diagnostics.value)
    copyMessage.value = '诊断摘要已复制。提交前仍可检查并删除不需要的字段。'
  } catch {
    copyMessage.value = '浏览器未允许复制。可以直接选择下方文本并手动复制。'
  }
}

onMounted(loadDiagnostics)
</script>

<template>
  <section class="settings-head">
    <p class="eyebrow">本机设置</p>
    <h1>本地数据与服务</h1>
    <p class="intro">文件、任务记录和处理结果都保存在运行 FastAPI 的本机目录中。</p>
  </section>

  <section class="panel settings-panel">
    <div>
      <h2>Web 服务</h2>
      <p class="hint">页面与 API 由同一个本地服务提供。需要停止服务时，请回到启动它的终端并按 Ctrl+C。</p>
    </div>
  </section>

  <section class="panel settings-panel feedback-panel">
    <div>
      <p class="eyebrow">项目反馈</p>
      <h2>报告可复现的问题</h2>
      <p class="hint">GitHub 表单会引导你提供版本、运行环境、最小步骤和预期结果。</p>
    </div>
    <div class="feedback-actions">
      <a
        class="external-action primary-action"
        href="https://github.com/itgsklab/Remove-Watermark/issues/new/choose"
        target="_blank"
        rel="noopener noreferrer"
      >报告问题</a>
      <a
        class="external-action secondary-action"
        href="https://github.com/itgsklab/Remove-Watermark/issues"
        target="_blank"
        rel="noopener noreferrer"
      >查看现有问题</a>
    </div>
    <p class="privacy-note" role="note">
      请使用生成或彻底脱敏的最小样本。不要公开上传真实简历、合同、私人图片、凭据、有效分享链接、本地路径或其他个人信息。
    </p>
  </section>

  <section class="panel settings-panel diagnostics-panel">
    <div>
      <p class="eyebrow">安全诊断</p>
      <h2>复制运行能力摘要</h2>
      <p class="hint">摘要只包含应用版本、支持格式、处理策略和功能开关，不包含文件名、文档内容、任务记录、本地路径、网络地址或浏览器信息。</p>
    </div>
    <p v-if="diagnosticsError" class="warning" role="alert">{{ diagnosticsError }}</p>
    <template v-else-if="diagnostics">
      <textarea
        class="diagnostics-output"
        aria-label="安全诊断摘要"
        :value="diagnostics"
        readonly
        spellcheck="false"
      />
      <div class="diagnostics-actions">
        <button type="button" @click="copyDiagnostics">复制诊断摘要</button>
        <p v-if="copyMessage" aria-live="polite">{{ copyMessage }}</p>
      </div>
    </template>
    <p v-else class="hint" aria-live="polite">正在读取本地服务状态…</p>
  </section>

  <section class="panel settings-panel security-panel">
    <div>
      <p class="eyebrow">安全与隐私</p>
      <h2>私密报告安全漏洞</h2>
      <p class="hint">涉及文件泄露、任意文件读写、SSRF、命令执行或绕过人工确认时，请使用 GitHub 私密漏洞报告，不要创建公开 Issue。</p>
    </div>
    <a
      class="external-action secondary-action"
      href="https://github.com/itgsklab/Remove-Watermark/security/advisories/new"
      target="_blank"
      rel="noopener noreferrer"
    >打开私密报告</a>
  </section>
</template>
