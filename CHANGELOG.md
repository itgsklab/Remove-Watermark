# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

### Added

- A reusable workspace-bootstrap workflow for capability discovery, asset loading, PDF diagnostics
  initialization and stale-response protection when route parameters change.
- A reusable workspace-analysis workflow for file-kind routing, scan requests, outcome messages and
  analysis cleanup across DOCX, CodeCV/general PDF and image inputs.
- A reusable task-execution workflow for polling, timeout feedback, cancellation and terminal status
  messages, including safe invalidation when a workspace analysis is replaced or cleared.
- A reusable object-candidate workflow and action panel for DOCX and CodeCV selection, ambiguous
  candidate acknowledgements, digital-signature confirmation, plan validation and task creation.
- A reusable analysis-summary panel that centralizes result headings, inspected-location counts and
  privacy-safe CodeCV compatibility diagnostics with clipboard feedback.
- A reusable workspace inspection panel that centralizes file metadata, source previews and
  format-specific scan controls while preserving the existing DOCX, PDF and image workflows.
- A reusable image-workflow panel that centralizes mask editing, local-model suggestions, risk
  evidence, repair guidance, radius previews and required warning acknowledgements.
- A reusable general-PDF strategy panel that centralizes object removal, Deep raster repair, OCR
  language selection, multi-page region drafts, overlap review and destructive-change confirmations.
- A reusable candidate-list component for DOCX and PDF analyses, centralizing preview, evidence,
  source location, selection and acknowledgement behavior while preserving read-only candidates.
- A reusable workspace task outcome panel with accessible progress, duration, warning count,
  centralized cancellation, terminal failure/cancellation reporting, result downloads and visual
  comparisons shared by DOCX, CodeCV, general-PDF and image workflows.
- End-to-end PDF digital-signature safeguards for CodeCV cleanup, general region removal and Deep
  repair, including structured detection, required Web/CLI/API acknowledgement and task-report
  evidence that the generated copy invalidates existing signature verification.
- Privacy-safe CodeCV compatibility diagnostics in the Web analysis response and interface,
  covering aggregate Pattern resources and complete, confirmed and ambiguous signature counts
  without exposing resume text, file paths, resource names or PDF object contents.
- A machine-checked public release-status contract and generated support/limitations matrix that
  separates the packaged `v0.1.0` surface from unreleased `main`, experimental capabilities and
  evaluation-only work.
- A deterministic OpenAPI 3.1 compatibility baseline for all versioned Web endpoints, enforced in
  continuous integration and local release checks to expose accidental breaking API changes.
- Generated Vue TypeScript API definitions sourced from the frozen OpenAPI contract, with the client
  response types migrated from handwritten duplicates and a CI freshness check.
- A generated v1 error-code contract covering Web response/task delivery, HTTP status mappings and
  CLI exit-code mappings, enforced in local and three-platform release checks.
- A model-independent box-guided mask-refinement Protocol and reproducible pixel benchmark covering
  IoU, leakage, correction workload, runtime metadata and human workflow timing gates.
- An evaluation-only SAM2 Hiera-T supply-chain manifest and audit gate pinning official revisions,
  Apache-2.0 evidence, Safetensors file digests and an isolated runtime while rejecting Pickle
  checkpoints, automatic downloads, release bundling and product integration.
- An evaluation-only SAM2 box-refinement adapter and reproducible prediction command, with public
  CPU/MPS benchmark reports showing strong recall but failed precision and human-timing gates.
- A provenance-audited 32-sample real-photo refinement corpus built from 16 independent NASA and
  Wikimedia sources, with paired clean negatives, exact pixel-difference masks and CPU/MPS reports.
- A reproducible Florence-2 candidate-confirmation gate that rejects all 16 paired clean negatives
  before SAM2 refinement and passes the CPU/MPS pixel metric gates on the fixed development corpus.
- A source-disjoint eight-photo holdout corpus and frozen real-model reports showing zero clean
  candidate acceptances but failed CPU/MPS pixel gates, preventing premature timing and Web claims.
- An evaluation-only SAM2 multimask policy that chooses each box's highest model-predicted IoU mask
  without consulting ground truth, with reproducible CPU/MPS development reports and no Web wiring.
- A second eight-source confirmation corpus frozen before multimask inference, with source-group and
  digest disjointness enforced against both development data and the first holdout corpus; its
  fixed CPU/MPS run failed the pixel gate and therefore blocks timing and Web integration.
- An evaluation-only local RGB-contrast augmentation for text-shaped candidate boxes, with fixed
  thresholds and CPU/MPS development reports; it remains disabled pending a new unseen confirmation.
- A third eight-source confirmation corpus frozen before text-contrast inference and disjoint by
  source group and digest from all 32 sources used by earlier stages; its fixed CPU/MPS run failed
  the pixel gate, so timing and Web integration remain blocked.
- An evaluation-only candidate match strategy that accepts a substantial Florence-2 detection fully
  contained by the proposed region, restoring 16/16 development recall without accepting clean pairs.
- A fourth eight-source confirmation corpus frozen before contained-detection inference, with source
  groups and digests disjoint from all 40 sources used by earlier stages; its fixed CPU/MPS run
  passed the candidate, pixel and evidence gates, allowing blind human timing to begin next.
- A frozen human-timing protocol for manual, candidate-box and model-refined masks, with anonymous
  session generation, counterbalanced task order, tamper checks, failure evidence and fixed gates.
- A loopback-only blind timing interface that loads the frozen image, candidate box or MPS mask,
  starts each task only after an explicit participant-ready action, measures server total time and
  active edits, and atomically saves each anonymous trial.
- A local timing-collection coordinator that creates permission-restricted anonymous sessions,
  reports completion without trial details and refuses to audit partially completed collections.
- Versioned Xiaohongshu HTML parsing diagnostics and privacy-safe candidate dimensions, including
  explicit page-structure states and stale-parser rejection before image import.
- Image-editor brush, eraser, independent mask/protection visibility and protected-area strokes,
  with shared undo/redo history and backend-enforced subtraction from the effective repair mask.
- Per-page PDF Deep task-report evidence for OCR execution status, searchable word counts and
  privacy-safe reasons when a selected page remains unsearchable.
- Installed-language selection for PDF Deep OCR, including multi-language combinations, an explicit
  OCR-off path and backend rejection of unavailable or duplicated Tesseract language packs.
- Privacy-safe Web settings diagnostics for Tesseract version and language packs, Xiaohongshu
  network feature gates and local VLM readiness, backed by a read-only diagnostics endpoint.
- Undoable image-mask editing for manual rectangles, removals, clearing and local-model suggestions,
  with redo support, a 50-step history and an explicit 100-region draft limit.
- DOCX DrawingML image candidate detection with relationship evidence, browser-safe embedded
  previews and explicitly confirmed selective removal that preserves shared media and relationships;
  unsupported formats and external relationships remain read-only or rejected.
- Multi-page, multi-region PDF plan drafts with per-page overlays, removable regions, aggregate
  overlap review and one-task execution for up to 100 rectangles.
- Playwright Chromium end-to-end coverage for the complete DOCX, general-PDF and image Web
  workflows, including result and privacy-safe task-report downloads in a dedicated CI gate.
- Downloadable task report schema v1 with duration, input and processing summaries, warning codes,
  result digests and privacy-safe failure codes.
- Structured GitHub forms for reproducible bug, document-compatibility and feature reports, with
  explicit privacy checks for user files, credentials, share links and local paths.
- Contribution, security-disclosure and `0.1.x` maintenance guidance, including patch severity and
  release-gate requirements.
- In-product links for structured issue intake, existing reports and private vulnerability
  disclosure, with a visible warning against sharing private user files or credentials.
- A preview-before-copy diagnostics summary containing only release version, supported formats,
  processing strategies and feature flags, with user files, paths and task history excluded.
- Weekly Dependabot checks for Python, npm and GitHub Actions dependencies, backed by repository
  vulnerability alerts and automated security-update Pull Requests.
- Pull Request dependency review that rejects newly introduced high/critical vulnerabilities, plus
  default exclusion of unplanned major-version Dependabot updates.
- Push and Pull Request continuous integration for Python linting, the full backend test suite,
  Vue type checking, production builds and high-severity npm vulnerability auditing.
- Protected `main` branch requiring synchronized backend, frontend, dependency-review and aggregate
  release-evidence checks, resolved review conversations, and no force pushes or branch deletion.
- CodeQL scanning for Python and JavaScript/TypeScript on Pull Requests, `main` pushes and a weekly
  schedule, with results uploaded to GitHub code scanning.
- Immutable commit pinning for every third-party GitHub Action, enforced by the required backend
  check, with protected-branch documentation synchronized to all seven required checks.

### Changed

- Move general-PDF region drafts, OCR diagnostics, risk previews and processing-plan orchestration
  into a reusable Vue composable while keeping shared task polling in the workspace view.
- Move image-mask drafts and their bounded undo/redo history into a reusable Vue composable, and
  isolate image preview, suggestion and processing API orchestration from the workspace view.
- Refresh the supported Vue build toolchain within its current major versions and regenerate the
  release dependency inventory and SPDX SBOM.
- Replace internal capability strategy labels on the home page with user-facing Chinese workflow
  descriptions, and distinguish supported formats from the CodeCV compatibility-validation status.

## [0.1.0] - 2026-10-13

The packaged release scope and current limitations are recorded in the
[public release status](docs/release/RELEASE_STATUS.md).

### Added

- Local-first Vue and FastAPI application for inspecting and removing supported watermarks.
- Production `wmrm-web` entry point for serving the built Vue interface and FastAPI API from one
  loopback-only origin.
- Reproducible Web release bundles containing compiled Vue assets, audited Python artifacts,
  startup instructions, the project license and internal SHA-256 checksums.
- DOCX VML watermark selection, validation, removal, and optional rendered comparison.
- CodeCV PDF signature detection and targeted content-stream cleanup.
- General PDF region redaction with overlap warnings and before/after previews.
- Static PNG, JPEG, and WebP mask editing with OpenCV Telea inpainting.
- Xiaohongshu share-link parsing with optional metadata preview and guarded public cover/gallery
  import into the existing local image workflow.
- Supervised background workers, cancellation, recovery, retention, and downloadable artifacts.
- Deterministic third-party dependency inventory and SPDX 2.3 release-input SBOM.
- Clean-environment backend wheel build, installation, dependency, and import checks.
- Installable CLI commands for PDF region removal, PDF Deep repair, reviewable image plans, DOCX
  candidate removal, and CodeCV candidate removal.
- Machine-checked v1 CLI/JSON compatibility contract targeting the first public `0.1.0` release.
- Isolated-wheel execution checks for every CLI command on the release-readiness path.
- Per-platform release-readiness reports with source, contract and wheel digests.
- A three-platform evidence gate that rejects missing, duplicate, dirty or mismatched release
  reports before release-candidate preparation.
- A dry-run-first release-candidate preparation tool that revalidates raw evidence, updates every
  version source, regenerates release metadata and rolls back failed updates.
- AGPL-3.0 license text embedded in Python wheel and source-distribution artifacts, with a
  release-readiness check that rejects missing or changed license payloads.
- A model-independent watermark-localization Protocol, reviewed positive/negative corpus and IoU/
  precision/recall benchmark contract for evaluating optional VLM adapters without bundling weights.
- An opt-in Florence-2 localizer, pinned model downloader and real-prediction command that verify
  Safetensors files and keep model dependencies and weights outside the default Web installation.
- Conservative rejection of Florence-2 boxes covering over 30% of an image, corrected visible-glyph
  truth for translucent text, a text-heavy UI negative sample, and separate metric/evidence gates
  requiring at least 20 reviewed samples with 10 negatives before any release claim.
- A reproducible 48-image Florence-2 corpus with 21 clean/watermarked scene pairs, 24 negatives,
  per-scene metrics and pair diagnostics; expanded evidence includes sixteen independent photo sources
  and shows that the candidate still fails the overall quality gate.
- An opt-in pixel-only photo-scene gate that prevents Florence-2 inference on UI, document and
  typography images, with color-diversity, continuous-tone and distributed-detail evidence routes
  plus reproducible classification, pair-stability and independent-source reports. The scene gate
  passes its fixed corpus, while Florence-2 photo precision remains below the release threshold.
- An explicit local Web opt-in for photo-gated Florence-2 mask suggestions. It verifies the pinned
  local model, loads it only after the gate passes, never downloads weights, and keeps every model
  box inside the existing editable preview and manual-confirmation workflow.

### Security

- Local services bind to loopback interfaces and reject cross-origin state-changing requests.
- Uploads use signature checks, size limits, archive safety limits, and isolated processing.
- Xiaohongshu imports keep token-bearing CDN URLs on the backend and require HTTPS, approved CDN
  hosts, public DNS results, pinned connections, bounded redirects, image types and size limits.
- Page-declared HTTP image metadata is accepted only for the approved Xiaohongshu CDN and upgraded
  to HTTPS before any network request; redirects and media downloads remain HTTPS-only.
- Optional Xiaohongshu proxy mode accepts only an explicit loopback HTTP CONNECT endpoint, keeps
  target allowlists and TLS validation, and avoids fake-IP DNS without inheriting system proxies.

[Unreleased]: https://github.com/itgsklab/Remove-Watermark/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/itgsklab/Remove-Watermark/releases/tag/v0.1.0
