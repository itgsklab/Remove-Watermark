<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Analysis } from '@/api/client'

const props = defineProps<{
  analysis: Analysis
}>()

const diagnosticCopyState = ref('')
const diagnosticPayload = computed(() => {
  if (!props.analysis.codecv_diagnostics || props.analysis.preset !== 'codecv') return ''
  return JSON.stringify({
    schema_version: 1,
    match_status: props.analysis.match_status,
    ...props.analysis.codecv_diagnostics,
  }, null, 2)
})

watch(() => props.analysis, () => {
  diagnosticCopyState.value = ''
})

async function copyCodeCvDiagnostics() {
  if (!diagnosticPayload.value) return
  try {
    await navigator.clipboard.writeText(diagnosticPayload.value)
    diagnosticCopyState.value = '已复制脱敏诊断。'
  } catch {
    diagnosticCopyState.value = '浏览器未允许复制，请手动记录下方统计。'
  }
}
</script>

<template>
  <div class="section-heading">
    <div>
      <p class="eyebrow">{{ analysis.preset === 'image' ? '图片检查结果' : '扫描结果' }}</p>
      <h2>{{ analysis.preset === 'image' ? '图片与蒙版' : '候选对象' }}</h2>
    </div>
    <span>{{ analysis.inspected_parts.length }} 个已检查位置</span>
  </div>

  <section
    v-if="analysis.preset === 'codecv' && analysis.codecv_diagnostics"
    class="panel codecv-diagnostics"
    aria-labelledby="codecv-diagnostics-title"
  >
    <div class="codecv-diagnostics-heading">
      <div>
        <p class="eyebrow">脱敏兼容诊断</p>
        <h3 id="codecv-diagnostics-title">CodeCV 结构匹配统计</h3>
        <p>只包含规则版本和聚合数量，不包含简历正文、文件名、路径、资源名或 PDF 对象内容。</p>
      </div>
      <button class="secondary-button" type="button" @click="copyCodeCvDiagnostics">复制诊断</button>
    </div>
    <dl class="codecv-diagnostics-grid">
      <div><dt>扫描页数</dt><dd>{{ analysis.codecv_diagnostics.pages_scanned }}</dd></div>
      <div><dt>含 Pattern 的页面</dt><dd>{{ analysis.codecv_diagnostics.pages_with_pattern_resources }}</dd></div>
      <div><dt>Pattern 资源</dt><dd>{{ analysis.codecv_diagnostics.pattern_resource_count }}</dd></div>
      <div><dt>Tiling Pattern</dt><dd>{{ analysis.codecv_diagnostics.tiling_pattern_resource_count }}</dd></div>
      <div><dt>完整操作签名</dt><dd>{{ analysis.codecv_diagnostics.complete_signature_count }}</dd></div>
      <div><dt>已确认 / 待复核</dt><dd>{{ analysis.codecv_diagnostics.confirmed_signature_count }} / {{ analysis.codecv_diagnostics.ambiguous_signature_count }}</dd></div>
    </dl>
    <p class="codecv-rule-version">规则 {{ analysis.codecv_diagnostics.rule_version }}</p>
    <p v-if="diagnosticCopyState" class="hint" role="status">{{ diagnosticCopyState }}</p>
  </section>
</template>
