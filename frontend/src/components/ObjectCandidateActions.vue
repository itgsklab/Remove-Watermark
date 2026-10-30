<script setup lang="ts">
defineProps<{
  busy: boolean
  selectedCount: number
  isPdf: boolean
  pdfHasDigitalSignatures: boolean
}>()

const emit = defineEmits<{
  process: []
}>()

const confirmedSignature = defineModel<boolean>('confirmedSignature', { required: true })
</script>

<template>
  <div class="process-actions">
    <label v-if="pdfHasDigitalSignatures" class="risk-confirm signature-confirm">
      <input v-model="confirmedSignature" type="checkbox" :disabled="busy" />
      我知道原 PDF 的现有数字签名将在 CodeCV 清理副本中失效，并确认继续处理
    </label>
    <button
      :disabled="busy || selectedCount === 0 || (pdfHasDigitalSignatures && !confirmedSignature)"
      @click="emit('process')"
    >
      {{ busy ? '正在处理…' : `生成无水印${isPdf ? ' PDF' : ''}副本（已选 ${selectedCount} 项）` }}
    </button>
    <p>仅生成新文件，上传的原始文件不会被覆盖。</p>
  </div>
</template>
