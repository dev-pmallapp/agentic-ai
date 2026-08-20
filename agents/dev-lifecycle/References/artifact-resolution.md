# Artifact Resolution

How this pipeline stores and re-finds the markdown artifacts it
produces — design docs, test plans, unit test plans, test results.
GitHub issues have no attachment API, so the durable store is the
repository itself, and the issue comment carries the content or a
permalink to it.

This one reference covers all four artifact kinds, parameterized by
sentinel heading and path, because the resolution chain is
structurally identical for each — Forge's own source material carries
this as three near-duplicate files for exactly that reason, which is
the kind of duplication `References/` exists to avoid (see `AGENT.md`'s
gh-dependency decision).

## The Two-Surface Model

| Surface | Role | Survives |
|---|---|---|
| **Issue comment**, sentinel-marked | source of truth for discovery | forever; searchable |
| **Committed file** under `docs/<kind>/` | durable store for full content | forever; versioned; diffable |

A sentinel comment always exists once an artifact is produced. It
holds either the **full artifact** (small) or a **summary plus a
permalink** (large). Resolution reads the comment first and follows
the permalink when present.

## Sentinels and Paths

| Artifact | Sentinel | Path | Producer |
|---|---|---|---|
| Design doc | `## dev-lifecycle-design-doc` | `docs/design/{issue}-design.md` | `story-design` |
| Test plan | `## dev-lifecycle-test-plan` | `docs/test-plans/{issue}-test-plan.md` | `story-test` (test-plan generation is not yet ported — see `AGENT.md`) |
| Unit test plan | `## dev-lifecycle-unit-tests` | `docs/test-plans/{issue}-unit-tests.md` | not yet ported — see `AGENT.md` |
| Test results | `## dev-lifecycle-test-results` | `docs/test-results/{issue}-{timestamp}.md` | `task-test`, `story-test` |

The sentinel is the comment body's **first line** — not indented, not
preceded by blank lines, not inside a code fence.

## Resolution Chain (reader side)

Steps are tried in order; first match wins. The issue is the source of
truth for Steps 1-2 — do not search the local filesystem during them,
and ignore any local file path written into an issue body (per-engineer
paths go stale).

**Step 1 — Issue comment (sentinel):**

```bash
gh issue view {issue} --repo {repo} --json comments,body,title
```

Scan comments whose body starts with the artifact's sentinel. Multiple
matches → use the most recent by `createdAt`. A `---` separator
followed by the full document means that content **is** the artifact;
no separator means the comment is a summary — follow its permalink to
Step 2.

**Step 2 — Committed file via permalink:**

```bash
# Prefer the local git object store when the SHA is available locally
git -C {repo_root} show {sha}:{path} > "{save_path}"
# otherwise
gh api "repos/{owner}/{name}/contents/{path}?ref={sha}" \
  --jq '.content' | base64 -d > "{save_path}"
```

Validate before trusting the result: exit 0, file non-empty, content
starts with markdown (`#` or `---`) rather than an HTML error page.
Any check failing → delete the partial file, continue to Step 3. Do
not retry against `raw.githubusercontent.com` — that path
authenticates differently and fails confusingly on private repos.

**Step 3 — Local artifact directory (fallback):**

Search the artifact's directory (`docs/design/`, `docs/test-plans/`,
`docs/test-results/`) for a file named or prefixed with `{issue}`. This
catches the producer having written the file locally before an upload
failure. If found, use it, then sync it upward (see below).

**Step 4 — Not found:**

Only when the caller treats the artifact as required. State plainly
what was checked and where, and name the Skill that produces it.
Callers that treat the artifact as optional stop at Step 3 and proceed
without it, noting the reduced grounding.

## Upload Procedure (writer side)

**1. Commit the file:**

```bash
mkdir -p "$(dirname "{artifact_path}")"
# ... write the file ...
git add "{artifact_path}"
git commit -m "#{issue}: Add {artifact_label}"
sha=$(git rev-parse HEAD)
```

Record `committed = true` and hold the permalink until the branch is
actually pushed — **a permalink to an unpushed SHA 404s**, so only
include it in the comment after the push. If the commit cannot happen
(not in a git repo, conflicted tree, no write access), record
`committed = false` and inline the content instead. Never run
`git init` to force it.

**2. Post the sentinel comment (always, regardless of step 1's
outcome):**

```bash
gh issue comment {issue} --repo {repo} --body-file {path}
```

Body shape — small artifact (under 60,000 characters), committed:

```markdown
## dev-lifecycle-design-doc

Design doc for #{issue} — {title}

- **File:** [`docs/design/{issue}-design.md`]({permalink})
- **Commit:** `{short_sha}` on `{branch}`
- **Sections:** {list of ## headings}

---

{full artifact content}
```

Large artifact (60,000+ characters) — post the metadata and a section
outline plus the permalink, without inlining the body; if it could not
be committed either, truncate at ~55,000 characters with an explicit
`TRUNCATED` marker and warn loudly, since that combination is the one
case where content genuinely only survives on the authoring machine.

**3. Verify the post landed (mandatory):**

```bash
gh issue view {issue} --repo {repo} --json comments \
  --jq '[.comments[] | select(.body | startswith("## dev-lifecycle-design-doc"))] | length'
```

Zero after a reported success → retry once. Zero after the retry →
warn and continue; do not block. This catches a run dying between
"post reported success" and the comment actually persisting.

## Error Handling

| Situation | Action |
|---|---|
| No sentinel comment | continue to Step 2 |
| Permalink fetch 404s | commit likely unpushed; warn, continue to Step 3 |
| Local file found, sync fails | warn, proceed — the local content is still usable |
| Nothing found anywhere, required | Step 4 — name what was checked, point at the producing Skill |
| Comment post 422 (too long) | recompute size, re-post as summary + permalink |
