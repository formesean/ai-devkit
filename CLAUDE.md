# House rules (all repos)

- Never add an env var, dependency, or DB migration without asking first.
- No narrative comments in diffs; no commented-out code; no console.log residue.
- Never push/publish by any means (including `gh ... --push`). Hand me the command to run via `!`.
- Before publishing anything new (repo public, gist, deploy), scan content AND git history for
  secret values (gitleaks; the pre-push hook enforces this on pushes). If a secret ever hit
  history: rotate the key first — history rewrite without rotation is theater.
- Branches/commits: identify the repo from the changed files' directory first
  (`git rev-parse --show-toplevel` + remote) — work repo (tax-plan-experts-web) =
  `tm/<type>/<kebab>`; personal repos = `<type>/<kebab>` + commitizen-style Conventional
  Commits. When unsure, copy `git branch -a`.
- A change is done only after the smallest quality gate that covers it passes, using the
  repo's own package.json scripts: docs/comments/copy-only → lint the changed files;
  types/signatures touched → also typecheck; logic changed → also tests scoped to affected
  files (`--findRelatedTests`/`vitest related` or the covering test file); full suite only
  for widely-imported shared code or many-file changes. Run gate commands one at a time,
  sequentially — never parallel or backgrounded (RAM). On non-personal repos scope everything
  to modified + untracked files only. Then give me the ship-it handoff (branch + commit
  message) unprompted, plus numbered manual test steps.
- Bug fixes: grep all callers, fix at the shared choke point, check sibling instances of the
  same pattern.
- When I ask "A or B?": one recommendation, one sentence why.
- When I paste a screenshot saying something looks off: redesign the presentation, not one property.
