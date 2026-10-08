<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ApiError,
  getCapabilities,
  previewXiaohongshuLink,
  uploadAsset,
  type XiaohongshuPreview,
} from '@/api/client'
import { useWorkspaceStore } from '@/stores/workspace'

const store = useWorkspaceStore()
const router = useRouter()
const selectedFile = ref<File | null>(null)
const busy = ref(false)
const message = ref('')
const shareText = ref('')
const resolveMetadata = ref(false)
const linkBusy = ref(false)
const linkMessage = ref('')
const linkPreview = ref<XiaohongshuPreview | null>(null)
const maxSize = computed(() => store.capabilities?.max_upload_bytes ?? 0)

onMounted(async () => {
  try {
    store.capabilities = await getCapabilities()
  } catch {
    message.value = '无法连接本地后端，请先启动 Python 服务。'
  }
})

function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  message.value = ''
}

async function submit() {
  if (!selectedFile.value) return
  busy.value = true
  message.value = ''
  try {
    store.currentAsset = await uploadAsset(selectedFile.value)
    await router.push(`/workspace/${store.currentAsset.id}`)
  } catch (error) {
    message.value = error instanceof ApiError ? error.message : '上传失败。'
  } finally {
    busy.value = false
  }
}

async function inspectShareLink() {
  if (!shareText.value.trim()) return
  linkBusy.value = true
  linkMessage.value = ''
  linkPreview.value = null
  try {
    linkPreview.value = await previewXiaohongshuLink(shareText.value, resolveMetadata.value)
  } catch (error) {
    linkMessage.value = error instanceof ApiError ? error.message : '分享链接解析失败。'
  } finally {
    linkBusy.value = false
  }
}

function metadataStatusLabel(status: XiaohongshuPreview['metadata_status']) {
  return {
    not_requested: '仅解析链接',
    disabled: '元数据读取未启用',
    resolved: '元数据已读取',
    unavailable: '元数据暂不可用',
  }[status]
}
</script>

<template>
  <section class="hero">
    <p class="eyebrow">本地优先 · 0.1.0 发布候选</p>
    <h1>看清改动，再处理水印</h1>
    <p class="intro">支持 DOCX、PDF、CodeCV 简历和本地图片。原件默认保留，处理前确认候选与影响范围。</p>
  </section>

  <section class="panel upload-panel">
    <h2>选择本地文件</h2>
      <p>DOCX、CodeCV PDF、通用 PDF 区域删除和静态图片已支持处理闭环。</p>
    <input type="file" accept=".docx,.pdf,.png,.jpg,.jpeg,.webp" @change="onFile" />
    <div v-if="selectedFile" class="file-row">
      <span>{{ selectedFile.name }}</span>
      <span>{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</span>
    </div>
    <button :disabled="!selectedFile || busy" @click="submit">
      {{ busy ? '正在上传…' : '上传并检查' }}
    </button>
    <p v-if="maxSize" class="hint">单文件上限 {{ Math.round(maxSize / 1024 / 1024) }} MB</p>
    <p v-if="message" class="message" role="status">{{ message }}</p>
  </section>

  <section class="panel xhs-link-panel">
    <div class="xhs-panel-heading">
      <div>
        <p class="eyebrow">小红书 · 分享链接</p>
        <h2>先确认笔记地址</h2>
      </div>
      <span class="boundary-badge">仅元数据</span>
    </div>
    <p class="hint">粘贴分享文案或 HTTPS 链接。当前功能只识别笔记地址和可选页面标题，不下载图片或视频。</p>
    <label class="share-input-label" for="xhs-share-text">分享内容</label>
    <textarea
      id="xhs-share-text"
      v-model="shareText"
      rows="4"
      maxlength="4096"
      placeholder="例如：发现一篇笔记 https://www.xiaohongshu.com/explore/..."
      @input="linkPreview = null; linkMessage = ''"
    />
    <div class="xhs-actions">
      <label class="metadata-option">
        <input v-model="resolveMetadata" type="checkbox" />
        <span>尝试读取页面标题和描述（需后端显式启用）</span>
      </label>
      <button :disabled="!shareText.trim() || linkBusy" @click="inspectShareLink">
        {{ linkBusy ? '正在解析…' : '解析分享链接' }}
      </button>
    </div>
    <p v-if="linkMessage" class="message warning" role="alert">{{ linkMessage }}</p>
    <article v-if="linkPreview" class="link-preview" aria-live="polite">
      <div class="link-preview-heading">
        <div>
          <span class="candidate-state confirmed">{{ linkPreview.kind === 'direct' ? '笔记直链' : '分享短链' }}</span>
          <h3>{{ linkPreview.title || '链接格式有效' }}</h3>
        </div>
        <span class="metadata-state">{{ metadataStatusLabel(linkPreview.metadata_status) }}</span>
      </div>
      <p v-if="linkPreview.description" class="link-description">{{ linkPreview.description }}</p>
      <dl class="link-details">
        <div>
          <dt>规范地址</dt>
          <dd>{{ linkPreview.canonical_url || linkPreview.normalized_url }}</dd>
        </div>
        <div>
          <dt>笔记 ID</dt>
          <dd>{{ linkPreview.note_id || '解析短链后确定' }}</dd>
        </div>
        <div v-if="linkPreview.author">
          <dt>作者</dt>
          <dd>{{ linkPreview.author }}</dd>
        </div>
        <div>
          <dt>媒体边界</dt>
          <dd>不返回图片或视频地址</dd>
        </div>
      </dl>
      <p v-for="warning in linkPreview.warnings" :key="warning" class="warning">{{ warning }}</p>
    </article>
  </section>

  <section v-if="store.capabilities" class="capabilities">
    <article v-for="item in store.capabilities.formats" :key="item.id" class="panel">
      <span class="status">{{ item.status === 'planned' ? '规划中' : item.status === 'experimental' ? '实验性' : '可用' }}</span>
      <h2>{{ item.label }}</h2>
      <p>{{ item.strategies.join(' · ') }}</p>
    </article>
  </section>
</template>
