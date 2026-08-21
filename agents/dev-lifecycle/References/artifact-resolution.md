# Artifact Resolution

How this pipeline stores and re-finds the markdown artifacts it
produces — design docs, test plans, unit test plans, test results,
effort estimates, checkpoints, and learning extractions. GitHub issues
have no attachment API, so the durable store is the repository itself,
and the issue comment carries the content or a permalink to it.

This one reference covers every artifact kind, parameterized by
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
| Design doc | `## dev-lifecycle-design-doc` | `docs/design/{issue}-design.md` | `story-design`, revised by `replan` |
| Root-cause analysis | `## dev-lifecycle-rca` | `docs/design/{issue}-rca.md` | `bug-analyze` |
| Test plan | `## dev-lifecycle-test-plan` | `docs/test-plans/{issue}-test-plan.md` | `story-test-plan`, regrounded by `story-test-replan` |
| Unit test plan | `## dev-lifecycle-unit-tests` | `docs/test-plans/{issue}-unit-tests.md` | `task-test-plan` |
| Test results | `## dev-lifecycle-test-results` | `docs/test-results/{issue}-{timestamp}.md` | `task-test`, `story-test` |
| Effort estimate | `## dev-lifecycle-effort-estimate` | comment only — no committed file | `size` |
| Checkpoint | `## dev-lifecycle-checkpoint` | comment only — `PROGRESS-{issue}.md` is a local counterpart, not the artifact | `checkpoint`, read by `resume` |
| Learning extraction | `## dev-lifecycle-kb-extraction` | `docs/knowledge/{subsystem}-{slug}.md` | `enhance-debugger` |

The sentinel is the comment body's **first line** — not indented, not
preceded by blank lines, not inside a code fence.

**Three of these are comment-only.** The effort estimate and the
checkpoint have no committed file, so the Resolution Chain below stops
at Step 1 for them: there is no permalink to follow and no local
fallback to find, and a reader that falls through to Step 3 for one of
them has a bug, not a missing artifact. `enhance-debugger`'s articles
are committed, but on a PR branch rather than the default branch, so
they resolve from the PR until it merges.

Every producer posts a **new** comment per run rather than editing the
previous one, so the progression stays readable; consumers take the
most recent by `createdAt` and the newest therefore wins with no
cleanup step.

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
failure. If found, use it, then sync it upward — see § Syncing a Local
Artifact Upward.

**Step 3b — Committed test files, unit test plans only:**

The unit test chain has one source the others do not: the test code
itself. When the plan is missing but the tests were written, the files
are still the thing `task-test` has to run.

```bash
# Commits for this task
git -C {repo_root} log --oneline --all --grep="^#{task}:"

# Test files those commits touched
git -C {repo_root} log --all --grep="^#{task}:" --name-only --format= \
  | sort -u | grep -Ei '(^|/)(tests?|spec)/|_test\.|test_|\.test\.|_spec\.'
```

The task's PR is the more reliable view once one exists:

```bash
pr=$(gh pr list --repo {repo} --head "task/{task}-*" --state all \
       --json number --jq '.[0].number')
gh pr diff "$pr" --repo {repo} --name-only | grep -Ei '(^|/)(tests?|spec)/|_test\.|test_'
```

Record what is found as `{unit_test_files}`. A caller that wanted the
*plan* and found only files must say so rather than reporting coverage
it cannot vouch for:

> "Found {n} committed test files for #{task} but no
> `## dev-lifecycle-unit-tests` plan. Running the files directly;
> coverage against the design doc is unverified."

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

## Narrowing to One Build Target

A caller usually wants one build target's slice of an artifact, not the
whole document. Given a task title of the form
`Implement {name} for #{story}`:

1. Extract `{name}`, stripping the wrapper. If the title does not match
   the pattern, use the full title.
2. Normalize: lowercase, spaces to hyphens, strip punctuation but
   **preserve dots** — build target names contain them (`libhft.lib`).
3. Find that target in the `## Build Targets` table.
4. Aggregate every `### Code Path:` section whose `**Build target:**`
   matches. One build target may have several code paths.
5. If the document has no `## Build Targets` table, fall back to
   matching a single `### Module:` or `### Code Path:` heading by the
   normalized name.

For a **test plan**, match test-case rows whose *Test Case* or
*Description* column names the target, or whose case file lists it
under `## Prerequisites`. If nothing matches, **use the whole plan**
rather than reporting no coverage — a plan written before task
decomposition often does not name targets at all, and reporting zero
cases would read as "untested" when it means "not yet sliced".

## Syncing a Local Artifact Upward

When Step 3 finds a local artifact that never reached the issue,
whether to upload it depends on who is asking.

| Context | Mode |
|---|---|
| A Workflow driving a worker role | **Auto-upload** |
| An interactively invoked Skill | **Warn and nudge** |

**Auto-upload.** Commit if needed, push, then post the sentinel comment
and verify it — the full writer-side procedure below.

```bash
cd "{repo_root}"
if ! git diff --quiet -- "{artifact_path}" || \
   ! git ls-files --error-unmatch "{artifact_path}" >/dev/null 2>&1; then
  git add "{artifact_path}"
  git commit -m "#{issue}: Add {artifact_label}"
fi
sha=$(git rev-parse HEAD)
git push 2>/dev/null || true
```

Record `committed = true` and the permalink **only if the push
succeeded**. If it failed — no upstream, no write access, offline —
set `committed = false` with the reason and inline the content instead.

On failure of both the commit and the comment, warn but never block:
> "Could not sync {artifact_label} to #{issue} (commit {reason},
> comment also failed). Using local content. Please upload manually."

**Warn and nudge.** Do not upload. Print the artifact's location, say
plainly that nothing downstream will find it, and give the commands:

> "Found {artifact_label} locally at `{artifact_path}` but it is NOT on
> issue #{issue}. Downstream Skills and other engineers will not find
> it until it is uploaded. Re-run the producing Skill, or upload by
> hand — prepend `{sentinel}` as the comment's first line."

Do not block on the answer. The Skill proceeds with the local content
either way.

## Error Handling

| Situation | Action |
|---|---|
| No sentinel comment | continue to Step 2 |
| Permalink fetch 404s | commit likely unpushed; warn, continue to Step 3 |
| Local file found, sync fails | warn, proceed — the local content is still usable |
| Nothing found anywhere, required | Step 4 — name what was checked, point at the producing Skill |
| Comment post 422 (too long) | recompute size, re-post as summary + permalink |
