import { onScopeDispose, watch, type Ref } from 'vue'

import {
  ApiError,
  getAsset,
  getCapabilities,
} from '@/api/client'
import type { useWorkspaceStore } from '@/stores/workspace'

interface WorkspaceBootstrapOptions {
  assetId: Ref<string>
  message: Ref<string>
  store: ReturnType<typeof useWorkspaceStore>
  loadPdfDiagnostics: () => Promise<void>
  resetWorkspace: () => void
}

export function useWorkspaceBootstrap(options: WorkspaceBootstrapOptions) {
  let requestGeneration = 0
  let activeAssetId: string | null = null

  async function initializeWorkspace(assetId: string) {
    const generation = ++requestGeneration
    if (activeAssetId !== assetId) {
      activeAssetId = assetId
      options.resetWorkspace()
    }
    options.message.value = ''
    if (options.store.currentAsset?.id !== assetId) {
      options.store.currentAsset = null
    }

    try {
      if (!options.store.capabilities) {
        const capabilities = await getCapabilities()
        if (generation !== requestGeneration) return
        options.store.capabilities = capabilities
      }
      if (generation !== requestGeneration) return

      if (options.store.currentAsset?.id !== assetId) {
        const asset = await getAsset(assetId)
        if (generation !== requestGeneration) return
        options.store.currentAsset = asset
      }
      if (options.store.currentAsset?.kind === 'pdf') {
        await options.loadPdfDiagnostics()
      }
    } catch (error) {
      if (generation !== requestGeneration) return
      options.message.value = error instanceof ApiError ? error.message : '无法读取文件信息。'
    }
  }

  watch(
    options.assetId,
    assetId => void initializeWorkspace(assetId),
    { immediate: true },
  )

  onScopeDispose(() => {
    requestGeneration += 1
  })
}
