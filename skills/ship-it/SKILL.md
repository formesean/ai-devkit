---
name: ship-it
description: End-of-change handoff — branch name, Conventional Commit message, and optional non-technical ticket description. Use when a change is complete or when asked for a branch name / commit message / ticket description.
---

# ship-it

## Derive, don't assume

Identify the repo first — conventions are per-repo, and the conversation may span several:

```bash
basename "$(git rev-parse --show-toplevel)"; git remote get-url origin  # which repo this cwd is
git branch -a | grep -v HEAD | tail -15   # the real prefix in use
git log --oneline -10                      # the real commit style in use
```

Run these in the directory of the files just changed, not wherever the shell happens to sit.

- tax-plan-experts-web: prefix is always `tm/` (never Sean's initials). Ticket ID in branch
  when known: `tm/feat/tmi-2970-<kebab>`.
- taxmaverick-lms-web: prefix is always `lms/`. Ticket ID in branch when known:
  `lms/feat/tmi-2675-<kebab>` (type is `feat`/`fix`/etc., ticket id is lowercase `tmi-<n>`).
- Personal repos: `<type>/<kebab>` branches, commitizen-style Conventional Commits.
- Existing branches contradict the above → the repo wins.

## Gate first

Run the smallest gate that covers the change (see house rules): docs/copy-only → lint changed
files; types/signatures → also typecheck; logic → also scoped tests. One command at a time,
sequentially — never parallel. Non-personal repos: scope to modified + untracked files only
(lint those files directly; filter typecheck output to them). Red gate = no handoff; paste
the failure verbatim instead.

## Handoff block

```
Branch:  tm/fix/rc-module-block-column-drag
Commit:  fix: keep dragged blocks in the target column on RC module sections
         <body only if the why isn't in the subject; wrap at 72>
```

- Subject: imperative, ≤72 chars, honest type (data/tooling scripts = `chore`, not `feat`).
- Unrelated changes in the worktree → propose split commits with per-commit `git add <paths>`.
- Never run push yourself, by any vehicle.
- PM-visible work: append a 2–4 sentence ticket description in product language — no function,
  variable, or file names.

Emit this unprompted when a change is done; being asked for it means it fired late.
