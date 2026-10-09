export interface ApiErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
  request_id: string
}

export class ApiError extends Error {
  constructor(public readonly body: ApiErrorBody, public readonly status: number) {
    super(body.message)
  }
}

export interface CapabilityItem {
  id: string
  label: string
  status: 'available' | 'planned' | 'experimental'
  strategies: string[]
}

export interface Capabilities {
  version: string
  max_upload_bytes: number
  formats: CapabilityItem[]
}

export interface XiaohongshuPreview {
  kind: 'direct' | 'short'
  normalized_url: string
  canonical_url: string | null
  note_id: string | null
  metadata_status: 'not_requested' | 'disabled' | 'resolved' | 'unavailable'
  title: string | null
  description: string | null
  author: string | null
  thumbnail_present: boolean
  media_download_supported: boolean
  media_candidates: Array<{
    candidate_id: string
    position: number
    role: 'cover' | 'gallery'
  }>
  warnings: string[]
}

export interface Asset {
  id: string
  display_name: string
  kind: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export interface SourceLocator {
  part_name: string | null
  shape_index: number | null
  shape_id: string | null
  shape_type: string | null
  page_numbers: number[]
  resource_name: string | null
  object_number: number | null
  generation_number: number | null
  operation_index: number | null
  annotation_index: number | null
}

export interface CandidateRegion {
  coordinate_space: 'pdf_points'
  page_number: number
  x0: number
  y0: number
  x1: number
  y1: number
  page_width: number
  page_height: number
  rotation: number
  transform_id: string
  approximate: boolean
}

export interface PdfPageGeometry {
  page_number: number
  width: number
  height: number
  rotation: number
  crop_x: number
  crop_y: number
  transform_id: string
}

export interface ImageMetadata {
  width: number
  height: number
  display_width: number
  display_height: number
  format: 'PNG' | 'JPEG' | 'WEBP'
  mode: string
  frames: number
  animated: boolean
  has_alpha: boolean
  exif_orientation: number
  has_icc_profile: boolean
  transform_id: string
}

export interface ProtectedContent {
  content_id: string
  kind: 'text' | 'image' | 'form' | 'graphic' | 'link' | 'annotation'
  summary: string
  region: CandidateRegion
}

export interface Candidate {
  candidate_id: string
  classification: 'confirmed' | 'ambiguous' | 'content'
  kind: 'text' | 'image' | 'pattern' | 'other'
  content: string | null
  evidence: string
  source_locator: SourceLocator
  style: string | null
  allowed_strategies: string[]
  region: CandidateRegion | null
  overlaps_protected_content: boolean | null
}

export interface Analysis {
  id: string
  asset_id: string
  asset_sha256: string
  status: 'complete'
  candidates: Candidate[]
  inspected_parts: string[]
  warnings: string[]
  preset: 'codecv' | 'general' | 'image' | null
  match_status: 'matched' | 'needs_review' | 'not_found' | null
  pdf_pages: PdfPageGeometry[]
  protected_content: ProtectedContent[]
  image_metadata: ImageMetadata | null
}

export interface RedactionRegion {
  page_number: number
  x0: number
  y0: number
  x1: number
  y1: number
  transform_id: string
}

export interface RedactionPreview {
  asset_id: string
  analysis_id: string
  valid: boolean
  requires_acknowledgement: boolean
  executable: boolean
  regions: Array<{
    region: RedactionRegion
    overlaps: Array<{
      content_id: string
      kind: string
      summary: string
      intersection_area: number
    }>
  }>
  warnings: string[]
}

export interface RedactionPlan {
  id: string | null
  valid: boolean
  asset_id: string
  analysis_id: string
  strategy: 'pymupdf_redaction' | 'raster_inpaint'
  license_mode: 'agpl' | 'commercial'
  regions: RedactionRegion[]
  dpi: number | null
  radius: number | null
  ocr_languages: string | null
  warnings: PlanWarning[]
  output_kind: 'pdf'
}

export interface ImageMaskRegion {
  x0: number
  y0: number
  x1: number
  y1: number
  transform_id: string
}

export interface ImageMaskPreview {
  asset_id: string
  analysis_id: string
  valid: boolean
  executable: boolean
  regions: ImageMaskRegion[]
  covered_pixels: number
  coverage_ratio: number
  complexity: {
    level: 'low' | 'review' | 'high'
    regions: Array<{
      region_index: number
      risk: 'low' | 'review' | 'high'
      texture_score: number
      edge_density: number
      periodicity_score: number
      structure_score: number
      context_pixels: number
      reasons: string[]
    }>
  }
  selection_risk: {
    level: 'normal' | 'review'
    large_selection: boolean
    regions: Array<{
      region_index: number
      mean_luma_delta: number
      low_contrast: boolean
      reason: string
    }>
  }
  requires_acknowledgement: boolean
  warnings: string[]
}

export interface ImagePlan {
  id: string | null
  valid: boolean
  asset_id: string
  analysis_id: string
  strategy: 'opencv_telea'
  regions: ImageMaskRegion[]
  radius: number
  warnings: PlanWarning[]
  output_kind: 'png'
}

export interface PlanWarning {
  code: string
  candidate_id: string | null
  message: string
  requires_acknowledgement: boolean
}

export interface Plan {
  id: string | null
  valid: boolean
  asset_id: string
  analysis_id: string
  operations: Array<{ candidate_id: string; strategy: 'object' }>
  warnings: PlanWarning[]
  output_kind: 'docx' | 'pdf'
}

export interface Artifact {
  id: string
  display_name: string
  media_type: string
  size_bytes: number
  sha256: string
  download_url: string
  role: 'output' | 'source_preview' | 'result_preview'
  page_number: number | null
}

export interface ComparisonPage {
  page_number: number
  source_url: string | null
  result_url: string | null
}

export interface Comparison {
  available: boolean
  removed_count: number
  changed_parts: string[]
  source_page_count: number
  result_page_count: number
  pages: ComparisonPage[]
  warning: string | null
}

export interface ProcessingTask {
  id: string
  plan_id: string
  status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'succeeded' | 'failed'
  stage: string
  progress: number
  created_at: string
  updated_at: string
  error: ApiErrorBody | null
  artifacts: Artifact[]
  comparison: Comparison | null
}

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>
  const payload = await response.json() as { error: ApiErrorBody }
  throw new ApiError(payload.error, response.status)
}

export async function getCapabilities(): Promise<Capabilities> {
  return parse<Capabilities>(await fetch('/api/v1/capabilities'))
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
): Promise<Asset> {
  return parse<Asset>(await fetch('/api/v1/xiaohongshu/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ share_text: shareText, candidate_id: candidateId }),
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
): Promise<ImageMaskPreview> {
  return parse<ImageMaskPreview>(await fetch('/api/v1/image-masks/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      analysis_id: analysis.id,
      regions,
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
      radius,
      acknowledged_warnings: acknowledgedWarnings,
    }),
  }))
}

export async function previewRedactions(
  analysis: Analysis,
  region: RedactionRegion,
  strategy: 'pymupdf_redaction' | 'raster_inpaint' = 'pymupdf_redaction',
): Promise<RedactionPreview> {
  return parse<RedactionPreview>(await fetch('/api/v1/redactions/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asset_id: analysis.asset_id,
      analysis_id: analysis.id,
      regions: [region],
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
    ocr_languages?: string
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
