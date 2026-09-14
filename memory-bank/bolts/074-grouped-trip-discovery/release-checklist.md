# Unit 011 release checklist

The user authorized implementation, verification, merge and redeployment. This checklist records
required evidence; unchecked items are not completed or waived.

- [x] Final construction candidate passes the actual invited-caller inventory and price replay;
      explain coverage, unsupported facts and any terminal price outcome separately.
- [x] Final construction Ruff, mypy, pytest, AI-DLC validator tests and artifact validation pass.
- [x] Independent review findings are resolved with tests or evidence.
- [x] Construction artifacts and story index are consistent, then hand off to Operations.
- [ ] Commit only intended work; push a focused Conventional Commit and open/update the PR.
- [ ] Successful Cursor Bugbot check belongs to the exact final PR head, all Cursor threads
      resolved, and `python3 scripts/bugbot_merge_gate.py PR_NUMBER` passes before merge.
- [ ] Record merged source revision/tree, immutable production rollback image and protected
      SQLite/session/config backup. Never print secrets or credential-bearing browser output.
- [ ] Build the exact reviewed source. If reusing the immutable production dependency layer,
      prove dependency manifests unchanged, record base image/recipe hash, and verify installed
      package source bytes against the reviewed tree plus `pip check` and pinned dependencies.
- [ ] Dev: qualify installed package/CLI, Chromium startup and SQLite schema/FKs in isolation.
- [ ] Staging: run normal invited-caller inventory and price flow on cloned state using that exact
      installed image (no source overlay), no notifications and the sole browser lease. Verify
      shutdown within the 200-second grace and no orphan browser/display processes.
- [ ] Promote exactly the staged image. Stop only BookSaver; keep Caddy running. Roll back to the
      recorded immutable old image and protected state if health/integrity verification fails.
- [ ] Verify production image/revision, healthy process, restarts/OOM, logs, ports, dependencies,
      SQLite integrity/FKs and external health endpoint. Record Operations build/history evidence.
- [ ] Report independent replay separately from native Telegram interaction. Do not claim other
      users' expired sessions were tested or guarantee Booking.com will never change its pages.
