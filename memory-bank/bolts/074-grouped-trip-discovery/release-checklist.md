# Unit 011 release checklist

The user authorized implementation, verification, merge and redeployment. This checklist records
required evidence; unchecked items are not completed or waived.

- [x] Final construction candidate passes the actual invited-caller inventory and price replay;
      explain coverage, unsupported facts and any terminal price outcome separately.
- [x] Final construction Ruff, mypy, pytest, AI-DLC validator tests and artifact validation pass.
- [x] Independent review findings are resolved with tests or evidence.
- [x] Construction artifacts and story index are consistent, then hand off to Operations.
- [x] Commit only intended work; push a focused Conventional Commit and open/update the PR.
- [x] Successful Cursor Bugbot check belongs to the exact final PR head, all Cursor threads
      resolved, and `python3 scripts/bugbot_merge_gate.py PR_NUMBER` passes before merge.
- [x] Record merged source revision/tree, immutable production rollback image and protected
      SQLite/session/config backup. Never print secrets or credential-bearing browser output.
- [x] Build the exact reviewed source. If reusing the immutable production dependency layer,
      prove dependency manifests unchanged, record base image/recipe hash, and verify installed
      package source bytes against the reviewed tree plus `pip check` and pinned dependencies.
- [x] Dev: qualify installed package/CLI, Chromium startup and SQLite schema/FKs in isolation.
- [x] Staging: run normal invited-caller inventory and price flow on cloned state using that exact
      installed image (no source overlay), no notifications and the sole browser lease. Verify
      shutdown within the 200-second grace and no orphan browser/display processes.
- [x] Promote exactly the staged image. Stop only BookSaver; keep Caddy running. Roll back to the
      recorded immutable old image and protected state if health/integrity verification fails.
- [x] Verify production image/revision, healthy process, restarts/OOM, logs, ports, dependencies,
      SQLite integrity/FKs and external health endpoint. Record Operations build/history evidence.
- [x] Report independent replay separately from native Telegram interaction. Do not claim other
      users' expired sessions were tested or guarantee Booking.com will never change its pages.

Release evidence: `deployment/verification-grouped-6c94033.md` under Unit011. PR51 merged;
exact staged image deployed and normal production inventory refreshed. Native Telegram
interaction and other users with expired sessions remain explicitly untested.
