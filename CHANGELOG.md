# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

### Added

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
  check, with protected-branch documentation synchronized to all six required checks.

### Changed

- Refresh the supported Vue build toolchain within its current major versions and regenerate the
  release dependency inventory and SPDX SBOM.
- Replace internal capability strategy labels on the home page with user-facing Chinese workflow
  descriptions, and distinguish supported formats from the CodeCV compatibility-validation status.

## [0.1.0] - 2026-10-13

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
