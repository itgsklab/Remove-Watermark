import { computed, ref, type Ref } from 'vue'
import {
  ApiError,
  createTask,
  type Analysis,
  type PlanWarning,
  type ProcessingTask,
  validatePlan,
} from '@/api/client'

interface ObjectCandidateWorkflowOptions {
  analysis: Ref<Analysis | null>
  busy: Ref<boolean>
  message: Ref<string>
  confirmedSignatureInvalidation: Ref<boolean>
  canProcess: () => boolean
  runTask: (task: ProcessingTask) => Promise<void>
}

export function useObjectCandidateWorkflow(options: ObjectCandidateWorkflowOptions) {
  const selectedCandidates = ref<string[]>([])
  const confirmedAmbiguous = ref<string[]>([])
  const planWarnings = ref<PlanWarning[]>([])

  const canProcess = computed(() => options.canProcess())
  const hasObjectCandidates = computed(() => options.analysis.value?.candidates.some(
    candidate => candidate.allowed_strategies.includes('object'),
  ) ?? false)

  function resetObjectCandidates(nextAnalysis: Analysis | null = null) {
    selectedCandidates.value = nextAnalysis?.candidates
      .filter(candidate => candidate.classification === 'confirmed')
      .map(candidate => candidate.candidate_id) ?? []
    confirmedAmbiguous.value = []
    planWarnings.value = []
  }

  async function processSelection() {
    if (!options.analysis.value || selectedCandidates.value.length === 0) return
    options.busy.value = true
    options.message.value = ''
    planWarnings.value = []
    try {
      const acknowledgements = confirmedAmbiguous.value.map(
        candidateId => `AMBIGUOUS_CANDIDATE:${candidateId}`,
      )
      if (options.confirmedSignatureInvalidation.value) {
        acknowledgements.push('PDF_DIGITAL_SIGNATURE_INVALIDATION')
      }
      const plan = await validatePlan(
        options.analysis.value,
        selectedCandidates.value,
        acknowledgements,
      )
      planWarnings.value = plan.warnings
      if (!plan.valid || !plan.id) {
        options.message.value = '请确认所有需要复核的候选后再执行。'
        return
      }
      await options.runTask(await createTask(plan.id))
    } catch (error) {
      options.message.value = error instanceof ApiError ? error.message : '创建处理任务失败。'
    } finally {
      options.busy.value = false
    }
  }

  return {
    selectedCandidates,
    confirmedAmbiguous,
    planWarnings,
    canProcess,
    hasObjectCandidates,
    resetObjectCandidates,
    processSelection,
  }
}
