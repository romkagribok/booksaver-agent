---
version: v0.1.0-9808584
commit: 9808584e64d2f61d333e84d3f26ac4ffee8a6cf2
built: 2026-07-19T01:02:20Z
status: success
---

# Build: Currency Alignment Recovery

## Artifact

- **Type**: Docker container image
- **Tag**: `booksaver-agent:latest`
- **Image ID**: `sha256:43d9b664f1f552751102a4df90e446023899273c62e5ce5764c67b71f8a91c91`
- **Size**: 549,157,788 bytes
- **Release commit**: `9808584e64d2f61d333e84d3f26ac4ffee8a6cf2`
- **Artifact location**: Local Docker image store on the production VPS; no external registry is
  configured for this owner-operated Compose deployment.

## Build Environment

- **Host**: owner-operated production VPS (provider and hostname redacted)
- **Builder**: Docker Compose / BuildKit
- **Base**: `python:3.12-slim`
- **Browser**: Playwright Chromium 149 (driver build 1228)

## Quality Gates

- 73 focused tests passed locally.
- 721 full repository tests passed locally.
- Ruff passed across source and tests.
- mypy passed across 77 source files.
- Docker dependency installation, package wheel build, Playwright browser installation, image export,
  and unpack completed successfully.

## Rollback Artifact

The prior source revision is `3a9a441e609b6270f740309f6044dd5f333d2638`. Rebuilding that
revision with the same Compose command recreates the previous release if rollback is required.
