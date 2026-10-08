# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

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
- Xiaohongshu share-link parsing with an optional metadata-only preview boundary.
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

### Security

- Local services bind to loopback interfaces and reject cross-origin state-changing requests.
- Uploads use signature checks, size limits, archive safety limits, and isolated processing.

[Unreleased]: https://github.com/itgsklab/Remove-Watermark/commits/main
