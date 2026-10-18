<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getCapabilities,
  getRuntimeDiagnostics,
  type Capabilities,
  type RuntimeDiagnostics,
} from '@/api/client'

const capabilities = ref<Capabilities | null>(null)
const runtime = ref<RuntimeDiagnostics | null>(null)
const diagnosticsError = ref('')
const copyMessage = ref('')
const loading = ref(false)

const ocrLanguageSummary = computed(() => {
  const languages = runtime.value?.ocr.languages || []
  if (!languages.length) return '无'
  const visible = languages.slice(0, 12).join('、')
  return languages.length > 12 ? `${visible} 等 ${languages.length} 个` : visible
})

const diagnostics = computed(() => {
  if (!capabilities.value || !runtime.value) return ''

  return JSON.stringify({
    schema_version: 2,
    application: 'Watermark Remover',
    version: capabilities.value.version,
    interface: 'web',
    max_upload_mb: Math.round(capabilities.value.max_upload_bytes / 1024 / 1024),
    formats: capabilities.value.formats.map((item) => ({
      id: item.id,
      status: item.status,
      strategies: item.strategies,
    })),
    ocr: {
      available: runtime.value.ocr.available,
      status: runtime.value.ocr.status,
      version: runtime.value.ocr.version,
      languages: runtime.value.ocr.languages,
    },
    xiaohongshu: {
      status: runtime.value.xiaohongshu.status,
      share_link_parsing: runtime.value.xiaohongshu.share_link_parsing,
      metadata_reading_enabled: runtime.value.xiaohongshu.metadata_reading_enabled,
      image_import_enabled: runtime.value.xiaohongshu.image_import_enabled,
      proxy_configured: runtime.value.xiaohongshu.proxy_configured,
    },
    vlm_localization: {
      enabled: runtime.value.vlm_localization.enabled,
      available: runtime.value.vlm_localization.available,
      status: runtime.value.vlm_localization.status,
      automatic_download: runtime.value.vlm_localization.automatic_download,
      requires_manual_review: runtime.value.vlm_localization.requires_manual_review,
    },
  }, null, 2)
})

async function loadDiagnostics() {
  loading.value = true
  diagnosticsError.value = ''
  copyMessage.value = ''
  capabilities.value = null
  runtime.value = null
  try {
    const [capabilityResult, runtimeResult] = await Promise.all([
      getCapabilities(),
      getRuntimeDiagnostics(),
    ])
    capabilities.value = capabilityResult
    runtime.value = runtimeResult
  } catch {
    diagnosticsError.value = '无法读取本地服务状态。请确认 Web 服务仍在运行后重试。'
  } finally {
    loading.value = false
  }
}

function ocrStatusLabel(status: RuntimeDiagnostics['ocr']['status']) {
  if (status === 'ready') return '已就绪'
  if (status === 'probe_failed') return '需要检查'
  return '未安装'
}

function xhsStatusLabel(status: RuntimeDiagnostics['xiaohongshu']['status']) {
  if (status === 'ready') return '可读取并导入'
  if (status === 'metadata_only') return '仅页面读取'
  if (status === 'configuration_invalid') return '配置需修正'
  return '仅链接解析'
}

function vlmStatusLabel(status: Capabilities['vlm_localization']['status']) {
  if (status === 'ready') return '已就绪'
  if (status === 'configuration_invalid') return '配置需修正'
  if (status === 'runtime_missing') return '缺少运行依赖'
  return '未启用'
}

function statusTone(status: string) {
  if (status === 'ready') return 'ready'
  if (['metadata_only', 'configuration_invalid', 'runtime_missing', 'probe_failed'].includes(status)) {
    return 'review'
  }
  return 'inactive'
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

  <section class="panel settings-panel runtime-panel">
    <div class="runtime-heading">
      <div>
        <p class="eyebrow">本机能力</p>
        <h2>运行环境诊断</h2>
        <p class="hint">这里只检查本机组件和功能开关，不发起小红书请求，也不加载 VLM 模型。</p>
      </div>
      <button class="secondary-button" type="button" :disabled="loading" @click="loadDiagnostics">
        {{ loading ? '正在检查…' : '重新检查' }}
      </button>
    </div>
    <p v-if="diagnosticsError" class="warning" role="alert">{{ diagnosticsError }}</p>
    <div v-else-if="runtime" class="runtime-grid">
      <article class="runtime-card">
        <div class="runtime-card-heading">
          <h3>PDF OCR</h3>
          <span :class="['runtime-status', statusTone(runtime.ocr.status)]">
            {{ ocrStatusLabel(runtime.ocr.status) }}
          </span>
        </div>
        <p>{{ runtime.ocr.message }}</p>
        <dl>
          <dt>版本</dt><dd>{{ runtime.ocr.version || '未读取' }}</dd>
          <dt>语言包</dt><dd>{{ ocrLanguageSummary }}</dd>
        </dl>
      </article>
      <article class="runtime-card">
        <div class="runtime-card-heading">
          <h3>小红书网络能力</h3>
          <span :class="['runtime-status', statusTone(runtime.xiaohongshu.status)]">
            {{ xhsStatusLabel(runtime.xiaohongshu.status) }}
          </span>
        </div>
        <p>{{ runtime.xiaohongshu.message }}</p>
        <dl>
          <dt>页面读取</dt><dd>{{ runtime.xiaohongshu.metadata_reading_enabled ? '已启用' : '已关闭' }}</dd>
          <dt>图片导入</dt><dd>{{ runtime.xiaohongshu.image_import_enabled ? '已启用' : '已关闭' }}</dd>
          <dt>受限代理</dt><dd>{{ runtime.xiaohongshu.proxy_configured ? '已配置' : '未配置' }}</dd>
        </dl>
      </article>
      <article class="runtime-card">
        <div class="runtime-card-heading">
          <h3>本地 VLM</h3>
          <span :class="['runtime-status', statusTone(runtime.vlm_localization.status)]">
            {{ vlmStatusLabel(runtime.vlm_localization.status) }}
          </span>
        </div>
        <p>{{ runtime.vlm_localization.message }}</p>
        <dl>
          <dt>自动下载</dt><dd>不会</dd>
          <dt>人工复核</dt><dd>始终需要</dd>
        </dl>
      </article>
    </div>
    <p v-else class="hint" aria-live="polite">正在检查本机运行环境…</p>
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
    <template v-if="diagnostics">
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
    <p v-else-if="!diagnosticsError" class="hint" aria-live="polite">正在读取本地服务状态…</p>
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
