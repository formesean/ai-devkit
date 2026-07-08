# House rules (all repos)

- Never add an env var, dependency, or DB migration without asking first.
- No narrative comments in diffs; no commented-out code; no console.log residue.
- Never push/publish by any means (including `gh ... --push`). Hand me the command to run via `!`.
- Before publishing anything new (repo public, gist, deploy), scan content AND git history for
  secret values (gitleaks; the pre-push hook enforces this on pushes). If a secret ever hit
  history: rotate the key first — history rewrite without rotation is theater.
- Branches/commits: work repo (tax-plan-experts-web) = `tm/<type>/<kebab>`; personal repos =
  `<type>/<kebab>` + commitizen-style Conventional Commits. When unsure, copy `git branch -a`.
- A change is done only after the repo's own gate passes (`check`/`typecheck`/`lint`/`test`
  from package.json; on non-personal repos scope it to modified + untracked files only) — then
  give me the ship-it handoff (branch + commit message) unprompted, plus numbered manual test steps.
- Bug fixes: grep all callers, fix at the shared choke point, check sibling instances of the
  same pattern.
- When I ask "A or B?": one recommendation, one sentence why.
- When I paste a screenshot saying something looks off: redesign the presentation, not one property.
