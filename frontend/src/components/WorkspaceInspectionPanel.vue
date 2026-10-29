<script setup lang="ts">
import { computed } from 'vue'
import type { Asset } from '@/api/client'

const props = defineProps<{
  asset: Asset
  assetId: string
  busy: boolean
}>()

const emit = defineEmits<{
  inspect: []
  clearAnalysis: []
}>()

const watermarkText = defineModel<string>('watermarkText', { required: true })
const pdfPreset = defineModel<'codecv' | 'general'>('pdfPreset', { required: true })

const isDocx = computed(() => props.asset.kind === 'docx')
const isPdf = computed(() => props.asset.kind === 'pdf')
const isImage = computed(() => ['png', 'jpeg', 'webp'].includes(props.asset.kind))
</script>

<template>
  <section class="workspace-head">
    <p class="eyebrow">文件工作区</p>
    <h1>{{ asset.display_name }}</h1>
    <div class="meta-row">
      <span>{{ asset.kind.toUpperCase() }}</span>
      <span>{{ (asset.size_bytes / 1024).toFixed(1) }} KB</span>
      <span>SHA-256 {{ asset.sha256.slice(0, 12) }}…</span>
    </div>
  </section>

  <section class="workspace-grid">
    <article class="panel preview-placeholder">
      <template v-if="isImage">
        <p class="eyebrow">原始图片</p>
        <img
          class="workspace-image-preview"
          :src="`/api/v1/assets/${encodeURIComponent(assetId)}/content`"
          alt="上传的原始图片"
        />
        <p>图片仅在本地服务中预览；检查和框选不会修改原文件。</p>
      </template>
      <template v-else>
        <p class="eyebrow">页面对比</p>
        <h2>处理完成后显示原件与副本</h2>
        <p>页面由本机 LibreOffice 和 Poppler 渲染，用于人工检查水印是否移除及正文布局是否保持。</p>
      </template>
    </article>

    <aside class="panel inspector-panel">
      <h2>扫描水印候选</h2>
      <template v-if="isDocx">
        <label for="watermark-text">目标文字（可选）</label>
        <input
          id="watermark-text"
          v-model="watermarkText"
          type="text"
          maxlength="200"
          placeholder="例如 DRAFT、草稿"
        />
        <p class="hint">同时扫描 DrawingML 嵌入图片；可安全预览的内部图片经人工确认后可从输出副本删除。</p>
        <button :disabled="busy" @click="emit('inspect')">{{ busy ? '正在扫描…' : '开始扫描' }}</button>
      </template>
      <template v-else-if="isPdf">
        <label for="pdf-preset">扫描模式</label>
        <select id="pdf-preset" v-model="pdfPreset" :disabled="busy" @change="emit('clearAnalysis')">
          <option value="codecv">CodeCV 简历预设</option>
          <option value="general">通用 PDF 候选</option>
        </select>
        <template v-if="pdfPreset === 'general'">
          <label for="pdf-watermark-text">目标文字（可选）</label>
          <input
            id="pdf-watermark-text"
            v-model="watermarkText"
            type="text"
            maxlength="200"
            placeholder="例如 DRAFT、草稿"
          />
          <p>扫描重复文字、图片、Form、Pattern、注释和可选内容组。</p>
          <p class="hint">扫描后可框选区域，选择对象级删除或 Deep 栅格修复并生成新 PDF。</p>
        </template>
        <template v-else>
          <p>检查 CodeCV 平铺图案操作签名和对应资源对象。</p>
          <p class="hint">扫描后可选择完整匹配的候选生成新 PDF，原文件不会被覆盖。</p>
        </template>
        <button :disabled="busy" @click="emit('inspect')">
          {{ busy ? '正在扫描…' : pdfPreset === 'codecv' ? '扫描 CodeCV 结构' : '扫描通用 PDF' }}
        </button>
      </template>
      <template v-else-if="isImage">
        <p>读取图片尺寸、格式、色彩模式、透明通道、方向、色彩配置和动画帧数。</p>
        <p class="hint">检查完成后可框选多个水印区域并验证蒙版覆盖范围。</p>
        <button :disabled="busy" @click="emit('inspect')">
          {{ busy ? '正在检查…' : '检查图片并编辑蒙版' }}
        </button>
      </template>
      <p v-else class="message">该格式已安全保存，候选扫描仍在开发中。</p>
    </aside>
  </section>
</template>
