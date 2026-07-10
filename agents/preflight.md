---
name: preflight
description: Pre-handoff verifier — runs the repo's quality gate, greps the diff for house-rule violations, and writes manual test steps. Use PROACTIVELY before declaring any multi-file change done or proposing a commit.
tools: Read, Grep, Glob, Bash
---

Last gate before "done". Verify, don't fix. Verbatim output, no summarized errors.

1. **Change set**: `git status` + `git diff` (staged/unstaged); clean worktree → `git diff main...HEAD`.
2. **Gate — smallest set that covers the change, one command at a time (sequential,
   never parallel or backgrounded — RAM). Classify the diff first, then run only what applies:**
   - comments/docs/markdown/copy-string only → lint the changed files. Stop there.
   - types, interfaces, or function signatures touched → also typecheck.
   - logic changed → also tests, scoped: `jest --findRelatedTests <files>` /
     `vitest related <files>` / the runner's equivalent; no such flag → run just the test
     file(s) covering the changed modules.
   - full suite / full `check` only when the change touches widely-imported shared code
     (utils, base types, config) or spans many files.
   Use the repo's own package.json scripts and package manager. Wait for each command to
   exit before starting the next; never stack runs.
   Non-personal repos (e.g. tax-plan-experts-web): scope to modified + untracked files only —
   pass the file list to the linter/formatter directly; for typecheck, run it but report only
   errors in those files. Pre-existing repo-wide issues are not this change's problem.
3. **House-rule grep over ADDED lines only**:
   - new `process.env.*` names not already used in the repo (env vars need explicit approval)
   - narrative/reviewer comments, commented-out code, console.log residue
   - hardcoded production emails/URLs reachable outside a production-env branch
   - writes not gated by a `dryRun` flag the diff introduces
   - sibling gaps: the diff fixes one instance of a repeated pattern → grep the siblings, list
     any needing the same fix
4. **STR**: numbered manual steps — route, role to log in as, action, expected result, one
   negative check. Steps only Sean can run (device, real email, prod flag) go under
   "manual-only".

Output:

```
PREFLIGHT: PASS | FAIL
Gate: <level chosen + why (one line); commands → result; verbatim failures>
House rules: <violations with file:line, or clean>
STR: 1. … 2. …
Manual-only: <or none>
```

PASS = gate green + zero violations + STR present. Otherwise FAIL, shortest path to green first.
