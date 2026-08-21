# GitHub Error Handling

Standard error handling for every `gh` operation. A Skill cites this
document and adds only what is unique to itself.

There is no MCP layer here — every failure is a non-zero exit from `gh`
with a message on stderr. **Always capture stderr**; `gh` writes errors
there and prints nothing useful on stdout.

## Error Categories

### 1. `gh` Not Installed

**Trigger:** `command -v gh` fails.

**Action:** HARD STOP.
> "This agent requires the GitHub CLI. Install from
> https://cli.github.com then run `gh auth login`."

### 2. Not Authenticated

**Trigger:** `gh auth status` exits non-zero, or a command reports
`authentication required`.

**Action:** HARD STOP for writes. A read-only Skill (`status`) degrades
to local-only state with a warning.
> "Not authenticated to GitHub. Run `gh auth login`, then retry."

Do not attempt to authenticate on the user's behalf. Do not retry.

### 3. Repo Not Found / No Remote

**Trigger:** `gh repo view` fails with `Could not resolve to a
Repository`, or `git remote` is empty.

**Action:**
- No remote at all -> HARD STOP:
  > "No GitHub remote found. Add one with
  > `git remote add origin <url>`, or run from a cloned repo."
- Remote exists but resolution fails -> likely permissions or SSO.
  Suggest `gh auth refresh` and, for enterprise SSO, authorizing the
  token for the org.

### 4. Issue Not Found (404)

**Trigger:** `gh issue view {issue}` fails with `Could not resolve to
an Issue`.

**Action:**
- Validate the argument shape first: an issue reference must be
  `#?\d+`, `GH-\d+`, or a `github.com/{owner}/{repo}/issues/\d+` URL.
- Wrong shape -> suggest the correction.
- Right shape -> the issue does not exist **in this repo**. A common
  cause is running from the wrong clone in a multi-repo project, so
  report the repo that was actually searched:
  > "Issue #{issue} not found in {repo}. Verify the number, or check
  > whether it belongs to a different repository in this project."
- Do not proceed.

`gh issue view` also resolves **pull requests** by number — issues and
PRs share one numbering space. If the fetched object has a
`pull_request` field, the number is a PR; report that rather than
treating it as an issue.

### 5. Permission Denied (403)

**Trigger:** `HTTP 403` on a write, or `Resource not accessible by
integration`.

**Action:**
- Distinguish the causes: a missing token scope, a repo readable but
  not writable, or a lapsed org SSO authorization.
- Suggest `gh auth status` to inspect scopes, `gh auth refresh -s repo`
  to add them, and for SSO the "Authorize" link in `gh auth status`.
- Do not retry automatically.
- Read-only Skills continue with what they have; writing Skills stop.

### 6. Rate Limited

**Trigger:** `HTTP 403` with `rate limit exceeded`, or `HTTP 429`.

**Action:**

```bash
gh api rate_limit --jq '.resources.core.reset, .resources.graphql.reset'
```

Report the reset as a human-readable delta. **Do not sleep and retry in
a loop.** A batch operation that hits the limit stops, reports how far
it got, and lets the engineer resume.
> "GitHub rate limit hit after {n} of {m} operations. Resets in
> {minutes} minutes. Completed: {list}. Re-run to continue — these
> Skills are idempotent and skip what already exists."

### 7. Label Does Not Exist

**Trigger:** `gh issue edit --add-label` fails with `not found`.

**Action:** Create that single label with the standard colour from the
`init` Skill's table and retry once. If creation also fails, warn and
continue — the state transition is lost but the work is not:
> "Could not apply `{label}` to #{issue} — label missing and could not
> be created. State tracking for this issue will be inaccurate. Run
> `init` with write access to create the label set."

### 8. Sub-issue API Unavailable

**Trigger:** a GraphQL error naming `addSubIssue`, `subIssues`, or
`parent` as an unknown field — an older GitHub Enterprise Server.

**Action:** Switch to the `Parent: #N` body-link fallback for the rest
of the session (see `References/gh-operations.md` § Sub-issues). Say so
**once**, then proceed silently. This is a degraded mode, not an error.

### 9. Issue Creation Fails

**Trigger:** `gh issue create` exits non-zero.

**Action:**
- Log: "Failed to create issue: {stderr}."
- **Continue with the remaining operations** — creating 4 of 5 tasks
  beats creating none.
- Report partial results at the end:
  > "Created {n} of {m} task issues. Failed: {list with errors}."
- Suggest manual creation for the failures.

### 10. Branch / PR Failures

**Trigger:** `gh pr create` fails.

| Message | Cause | Action |
|---|---|---|
| `No commits between {base} and {head}` | Nothing implemented yet | Skip PR creation, warn, continue — it is created on the next run once commits exist |
| `a pull request for branch ... already exists` | Idempotent re-run | Fetch it with `gh pr list --head`, reuse it, do not error |
| `must be a collaborator` | Fork or insufficient rights | Report; suggest pushing a fork branch and opening the PR by hand |
| `Head ref must be a branch` | Branch not pushed | `git push -u origin {branch}` and retry once |

### 11. Milestone Not Found

**Trigger:** `gh api repos/{repo}/milestones/{n}` returns 404, or a
title match finds nothing.

**Action:**
> "Milestone '{arg}' not found in {repo}. Existing milestones:
> {list of number — title}. Create one with
> `gh api repos/{repo}/milestones -f title=...`, or pass an existing
> number."

**Do not create a milestone implicitly** — an Epic is a deliberate act.

### 12. Network Unreachable

**Trigger:** connection timeout, DNS failure.

**Action:**
- Switch to offline mode — save every artifact locally.
- Log: "GitHub unreachable — saving locally. Upload next session."
- Continue where the Skill can still make progress (writing a design
  doc, implementing code). A Skill whose entire purpose is a GitHub
  write (`story-create`, `task-create`) stops instead.
- On resume, the resolution chains and
  `References/artifact-resolution.md` push the local artifacts up.

## Verify, Don't Assume

`gh` sometimes exits 0 having done nothing useful — an empty list, a
no-op edit. After any operation whose result matters:

| Did | Verify by |
|---|---|
| Created an issue | The command printed a URL; parse the number from it. No URL means no issue. |
| Posted a comment | Re-fetch and scan for the sentinel (`References/gh-api.md` § Post-upload verification). |
| Changed labels | The next fetch shows the new label set — check it before reporting a transition. |
| Created a PR | `gh pr view {n} --json state` returns `OPEN`. |

This is the same discipline the orchestration Workflows apply to
subagent claims, for the same reason: a write that silently did nothing
corrupts pipeline state, and the only defence is re-reading the source
of truth.

## Usage in Skills

Each Skill cites this document for the standard errors:

```
## Error Handling

See `References/gh-error-handling.md` for standard GitHub errors
(auth, not found, permission denied, rate limits, label and PR
failures).

Skill-specific errors:
- [only what is unique to this Skill]
```
