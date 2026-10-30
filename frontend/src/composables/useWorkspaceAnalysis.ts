import { computed, ref, type Ref } from 'vue'

import {
  ApiError,
  createAnalysis,
  type Analysis,
  type Asset,
} from '@/api/client'

interface WorkspaceAnalysisOptions {
  assetId: Ref<string>
  busy: Ref<boolean>
  message: Ref<string>
  assetKind: () => Asset['kind'] | null
}

export function useWorkspaceAnalysis(options: WorkspaceAnalysisOptions) {
  const analysis = ref<Analysis | null>(null)
  const watermarkText = ref('')
  const pdfPreset = ref<'codecv' | 'general'>('codecv')

  const isDocx = computed(() => options.assetKind() === 'docx')
  const isCodeCvPdf = computed(() => options.assetKind() === 'pdf')
  const isImage = computed(() => ['png', 'jpeg', 'webp'].includes(options.assetKind() || ''))
  const canInspect = computed(() => isDocx.value || isCodeCvPdf.value || isImage.value)

  function inspectionMessage(result: Analysis) {
    if (result.preset === 'image' && result.image_metadata) {
      return `图片检查完成：${result.image_metadata.display_width} × ${result.image_metadata.display_height} 像素。`
    }
    if (result.candidates.length) {
      return `发现 ${result.candidates.length} 个候选。扫描不会修改原文件。`
    }
    if (isCodeCvPdf.value && pdfPreset.value === 'codecv') {
      return '没有匹配 CodeCV 平铺水印的完整操作签名。'
    }
    if (isCodeCvPdf.value) {
      return '没有发现需要复核的通用 PDF 水印结构。'
    }
    return '没有识别到受支持的页眉或页脚 VML 文字、DrawingML 图片候选。'
  }

  async function inspect() {
    if (!canInspect.value) return
    options.busy.value = true
    options.message.value = ''
    try {
      const result = await createAnalysis(
        options.assetId.value,
        watermarkText.value.trim() || null,
        isCodeCvPdf.value ? pdfPreset.value : isImage.value ? 'image' : null,
      )
      analysis.value = result
      options.message.value = inspectionMessage(result)
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '扫描失败。'
    } finally {
      options.busy.value = false
    }
  }

  function clearAnalysis() {
    analysis.value = null
    options.message.value = ''
  }

  return {
    analysis,
    watermarkText,
    pdfPreset,
    isDocx,
    isCodeCvPdf,
    isImage,
    canInspect,
    inspect,
    clearAnalysis,
  }
}
