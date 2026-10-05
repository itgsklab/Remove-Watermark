import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Asset, Capabilities } from '@/api/client'

export const useWorkspaceStore = defineStore('workspace', () => {
  const capabilities = ref<Capabilities | null>(null)
  const currentAsset = ref<Asset | null>(null)
  return { capabilities, currentAsset }
})
