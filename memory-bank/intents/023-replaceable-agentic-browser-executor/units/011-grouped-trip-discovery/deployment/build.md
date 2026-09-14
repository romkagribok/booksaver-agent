---
version: grouped-4a8582a
commit: 4a8582a502dc5d3d5ee9ec332aec5ef4791b3d87
built: 2026-09-14T19:24:41Z
status: success
---

# Build: grouped-4a8582a

- Image: `booksaver-agent:grouped-4a8582a`
- Immutable image: `sha256:c97023742f8c44ac469fb68caed0dfa66b9528fb5cdbcd4b4956c86dab4e3793`
- Size: 699,623,833 bytes. Runtime: Python 3.12, non-root BookSaver user.
- Base: immutable current PR50 production image `sha256:59740dfc836f97af145503c78f332b09cabaf54ac9fc9c684415d76ec861aa9c`.
- Source archive SHA256: `2c662b47aaead7aa363f916f9b33f2e635c3547ce14c70d0e0f88d381f3c0f94`.
- Build recipe SHA256: `ccafd2c412ed7849e3a065ef46ab186f469d5a619b4e8c026b899b8464f488bb`.

Dependency manifests and canonical Dockerfile are unchanged from PR50. To avoid duplicating the
large browser/dependency layers on the storage-constrained VPS, the build pins that exact base,
copies the committed source, reinstalls the local package with `--no-deps`, and runs `pip check`.
The release directory retains the archive, recipe and build log. No credentials are in the build.

```dockerfile
ARG QUALIFIED_BASE
FROM ${QUALIFIED_BASE}
USER root
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
COPY scripts/price_check_probe.py ./scripts/price_check_probe.py
RUN pip install --no-cache-dir --no-deps . && pip check
USER booksaver
```

Development verification compared all 122 installed Python module files byte-for-byte with the
committed image source; the import path is site-packages, not a source overlay. All eight pinned
browser/provider dependency versions matched, `pip check` passed, and CLI help loaded without
network access. The subsequent isolated Chromium/SQLite/daemon smoke passed in 2.87 seconds,
including integrity/FKs, heartbeat, actual SIGTERM handling and PID/heartbeat cleanup.
