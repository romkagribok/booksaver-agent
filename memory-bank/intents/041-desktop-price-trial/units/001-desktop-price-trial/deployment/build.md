---
version: desktoptrial-34d89a8
commit: 34d89a8
built: "2026-11-13T03:25:01Z"
created: "2026-11-13T03:27:17Z"
status: success
---

## Build: desktoptrial-34d89a8

### Artifact
- **Type**: container
- **Tag**: `booksaver-agent:desktoptrial-34d89a8` (local to the VPS; no registry)
- **SHA**: `sha256:9a8ad2726df08f86dfeed4ace277eb18e130f516670e6d4055e3902a1d5a7fab`

### Build Environment
- Kit `/opt/booksaver-releases/desktoptrial-34d89a8`, `Dockerfile.kit` on base
  `booksaver-agent:legible-8fab90f`, source from the merge's `git archive`.

### Build Log Summary
- 118 modules installed, schema 25, `pip check` clean, production config valid in the image.

## Build: retiretrial-e6d1044

### Artifact
- **Type**: container
- **Tag**: `booksaver-agent:retiretrial-e6d1044` (local to the VPS; no registry)
- **SHA**: `sha256:73fe9d8f1e8c9e0517c2d4d96d761ad86fe657b807812fbd46fa8de28ac66f7c`
- **Built**: 2026-11-18T13:10:07Z, commit `e6d1044` (same source as the staged candidate `fd3fd69`)

### Build Environment
- Kit `/opt/booksaver-releases/retiretrial-20261118`, `Dockerfile.kit` on base
  `booksaver-agent:desktoptrial-34d89a8`, source from the candidate's `git archive`.

### Build Log Summary
- 117 modules installed, schema 26, `pip check` clean, no trial module left in the image.
