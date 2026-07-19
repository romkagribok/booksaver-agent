---
version: v0.1.0-9808584
environment: production
deployed: 2026-07-19T01:03:44Z
deployed_by: Codex with product-owner approval
status: success
---

# Deployment History: Currency Alignment Recovery

## 2026-07-19 — `v0.1.0-9808584` → production

- **Host**: `booksaver-finland` (`root@135.181.91.254` via local SSH alias `booksaver`)
- **Service**: Docker Compose service `booksaver`
- **Release commit**: `9808584e64d2f61d333e84d3f26ac4ffee8a6cf2`
- **Previous commit**: `3a9a441e609b6270f740309f6044dd5f333d2638`
- **Started**: `2026-07-19T01:03:44.875941638Z`
- **Result**: healthy

### Changes

- Trusted search/property navigation requests the booking baseline currency.
- Rendered currency remains authoritative for offer selection.
- One deterministic-first, guarded-agent-optional alignment recovery is available.
- Persistent mismatches return an actionable `currency_mismatch` result without FX comparison.
- Scheduled and `/checknow` paths remain on the shared check coordinator.

### Preserved VPS State

The untracked `/opt/booksaver-agent/config.toml` and prior diagnostic screenshot were preserved.
No database, secret, config, or volume mutation was performed.

### Rollback

```bash
cd /opt/booksaver-agent
git checkout 3a9a441e609b6270f740309f6044dd5f333d2638
docker compose build booksaver
docker compose up -d --no-deps booksaver
```

After diagnosis, return to `phase-3-telegram-interface` and fast-forward before the next deployment.
