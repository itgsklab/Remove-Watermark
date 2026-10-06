# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

### Added

- Local-first Vue and FastAPI application for inspecting and removing supported watermarks.
- DOCX VML watermark selection, validation, removal, and optional rendered comparison.
- CodeCV PDF signature detection and targeted content-stream cleanup.
- General PDF region redaction with overlap warnings and before/after previews.
- Static PNG, JPEG, and WebP mask editing with OpenCV Telea inpainting.
- Xiaohongshu share-link parsing with an optional metadata-only preview boundary.
- Supervised background workers, cancellation, recovery, retention, and downloadable artifacts.
- Reproducible desktop packaging inputs and macOS Apple Silicon bundle verification.
- Deterministic third-party dependency inventory and SPDX 2.3 release-input SBOM.
- Clean-environment backend wheel build, installation, dependency, and import checks.

### Security

- Local services bind to loopback interfaces and reject cross-origin state-changing requests.
- Uploads use signature checks, size limits, archive safety limits, and isolated processing.

[Unreleased]: https://github.com/itgsklab/Remove-Watermark/commits/main
