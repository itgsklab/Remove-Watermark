import type { components } from './generated'

type DeepRequired<T> = T extends readonly (infer Item)[]
  ? Array<DeepRequired<Item>>
  : T extends object
    ? { -readonly [Key in keyof T]-?: DeepRequired<T[Key]> }
    : T

type ResponseSchema<Name extends keyof components['schemas']> =
  DeepRequired<components['schemas'][Name]>

export type ApiErrorBody = ResponseSchema<'ErrorBody'>

export class ApiError extends Error {
  constructor(public readonly body: ApiErrorBody, public readonly status: number) {
    super(body.message)
  }
}

export type CapabilityItem = ResponseSchema<'CapabilityItem'>
export type Capabilities = ResponseSchema<'CapabilitiesResponse'>
export type RuntimeDiagnostics = ResponseSchema<'RuntimeDiagnosticsResponse'>
export type XiaohongshuPreview = ResponseSchema<'XiaohongshuPreviewResponse'>
export type Asset = ResponseSchema<'AssetResponse'>
export type SourceLocator = ResponseSchema<'SourceLocator'>
export type CandidateRegion = ResponseSchema<'CandidateRegion'>
export type PdfPageGeometry = ResponseSchema<'PdfPageGeometry'>
export type ImageMetadata = ResponseSchema<'ImageMetadataResponse'>
export type ProtectedContent = ResponseSchema<'ProtectedContentResponse'>
export type Candidate = ResponseSchema<'CandidateResponse'>
export type Analysis = ResponseSchema<'AnalysisResponse'>
export type RedactionRegion = ResponseSchema<'RedactionRegionRequest'>
export type RedactionPreview = ResponseSchema<'RedactionPreviewResponse'>
export type RedactionPlan = ResponseSchema<'RedactionPlanResponse'>
export type ImageMaskRegion = ResponseSchema<'ImageMaskRegion'>
export type VlmSuggestion = ResponseSchema<'VlmSuggestionResponse'>
export type ImageMaskPreview = ResponseSchema<'ImageMaskPreviewResponse'>
export type ImagePlan = ResponseSchema<'ImagePlanResponse'>
export type PlanWarning = ResponseSchema<'PlanWarning'>
export type Plan = ResponseSchema<'PlanResponse'>
export type Artifact = ResponseSchema<'ArtifactResponse'>
export type ComparisonPage = ResponseSchema<'ComparisonPage'>
export type Comparison = ResponseSchema<'ComparisonResponse'>
export type ProcessingTask = ResponseSchema<'TaskResponse'>

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>
  const payload = await response.json() as { error: ApiErrorBody }
  throw new ApiError(payload.error, response.status)
}

export async function getCapabilities(): Promise<Capabilities> {
  return parse<Capabilities>(await fetch('/api/v1/capabilities'))
}

export async function getRuntimeDiagnostics(): Promise<RuntimeDiagnostics> {
  return parse<RuntimeDiagnostics>(await fetch('/api/v1/diagnostics'))
}

export async function previewXiaohongshuLink(
  shareText: string,
  resolveMetadata: boolean,
): Promise<XiaohongshuPreview> {
  return parse<XiaohongshuPreview>(await fetch('/api/v1/xiaohongshu/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ share_text: shareText, resolve_metadata: resolveMetadata }),
  }))
}

export async function importXiaohongshuImage(
  shareText: string,
  candidateId: string,
  parserVersion: string,
): Promise<Asset> {
  return parse<Asset>(await fetch('/api/v1/xiaohongshu/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      share_text: shareText,
      candidate_id: candidateId,
      parser_version: parserVersion,
    }),
  }))
}

export async function uploadAsset(file: File): Promise<Asset> {
  const form = new FormData()
  form.append('file', file)
  return parse<Asset>(await fetch('/api/v1/assets', { method: 'POST', body: form }))
}

export async function getAsset(assetId: string): Promise<Asset> {
  return parse<Asset>(await fetch(`/api/v1/assets/${encodeURIComponent(assetId)}`))
}

export async function createAnalysis(
  assetId: string,
  watermarkText: string | null,
  preset: 'codecv' | 'general' | 'image' | null = null,
): Promise<Analysis> {
  return parse<Analysis>(await fetch('/api/v1/analyses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: assetId,
      watermark_text: watermarkText || null,
      preset,
    }),
  }))
}

export async function previewImageMasks(
  analysis: Analysis,
  regions: ImageMaskRegion[],
  protectedRegions: ImageMaskRegion[] = [],
): Promise<ImageMaskPreview> {
  return parse<ImageMaskPreview>(await fetch('/api/v1/image-masks/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      analysis_id: analysis.id,
      regions,
      protected_regions: protectedRegions,
    }),
  }))
}

export async function suggestImageMasks(analysis: Analysis): Promise<VlmSuggestion> {
  return parse<VlmSuggestion>(await fetch('/api/v1/image-suggestions/vlm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      analysis_id: analysis.id,
    }),
  }))
}

export async function validatePlan(
  analysis: Analysis,
  candidateIds: string[],
  acknowledgedWarnings: string[],
): Promise<Plan> {
  return parse<Plan>(await fetch('/api/v1/plans/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      asset_sha256: analysis.asset_sha256,
      analysis_id: analysis.id,
      operations: candidateIds.map(candidate_id => ({ candidate_id, strategy: 'object' })),
      acknowledged_warnings: acknowledgedWarnings,
    }),
  }))
}

export async function validateImagePlan(
  analysis: Analysis,
  regions: ImageMaskRegion[],
  protectedRegions: ImageMaskRegion[],
  radius: number,
  acknowledgedWarnings: string[],
): Promise<ImagePlan> {
  return parse<ImagePlan>(await fetch('/api/v1/image-plans/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      asset_sha256: analysis.asset_sha256,
      analysis_id: analysis.id,
      regions,
      protected_regions: protectedRegions,
      radius,
      acknowledged_warnings: acknowledgedWarnings,
    }),
  }))
}

export async function previewRedactions(
  analysis: Analysis,
  regions: RedactionRegion[],
  strategy: 'pymupdf_redaction' | 'raster_inpaint' = 'pymupdf_redaction',
): Promise<RedactionPreview> {
  return parse<RedactionPreview>(await fetch('/api/v1/redactions/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      analysis_id: analysis.id,
      regions,
      strategy,
    }),
  }))
}

export async function validateRedactionPlan(
  analysis: Analysis,
  regions: RedactionRegion[],
  acknowledgedWarnings: string[],
  options: {
    strategy: 'pymupdf_redaction' | 'raster_inpaint'
    dpi?: number
    radius?: number
    ocr_languages?: string | null
  } = { strategy: 'pymupdf_redaction' },
): Promise<RedactionPlan> {
  return parse<RedactionPlan>(await fetch('/api/v1/redaction-plans/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      asset_sha256: analysis.asset_sha256,
      analysis_id: analysis.id,
      regions,
      strategy: options.strategy,
      dpi: options.dpi,
      radius: options.radius,
      ocr_languages: options.ocr_languages,
      acknowledged_warnings: acknowledgedWarnings,
    }),
  }))
}

export async function createTask(planId: string): Promise<ProcessingTask> {
  return parse<ProcessingTask>(await fetch('/api/v1/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId }),
  }))
}

export async function getTask(taskId: string): Promise<ProcessingTask> {
  return parse<ProcessingTask>(await fetch(`/api/v1/tasks/${encodeURIComponent(taskId)}`))
}

export async function getTasks(): Promise<ProcessingTask[]> {
  return parse<ProcessingTask[]>(await fetch('/api/v1/tasks'))
}

export async function cancelTask(taskId: string): Promise<ProcessingTask> {
  return parse<ProcessingTask>(await fetch(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/cancel`,
    { method: 'POST' },
  ))
}
