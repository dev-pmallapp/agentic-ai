# enhance-debugger

Scans a completed milestone's development history — issues, comments,
commits, PRs, test results — extracts what the team learned the hard
way, raises PRs for knowledge-base articles and knowledge-file updates,
and closes the milestone. The pipeline's close-out step.

## Purpose

Most of what a team learns during a milestone evaporates. It lives in a
comment thread nobody reads again, or in the head of whoever spent the
afternoon on it; six months later someone hits the same failure and
spends the same afternoon.

The value is in the things that cost hours and are written nowhere: the
failure that looked like one thing and was another, the flag that has
to be set first, the error message that means something other than what
it says.

## Preconditions

- A milestone with all its Stories closed. With no milestone given,
  list the ones whose Stories are all closed and ask which.
- `gh` authenticated with write access.

Optional external KB targets are declared by the project in `README.md`
under a `## Knowledge Base` heading, as a target/repo table. Absent →
articles are written into this repo's `docs/knowledge/` and no external
PR is raised. **That is a complete outcome, not a degraded one.**

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` in full.
Needs `{repo}`, `{repo_root}`, `{default_branch}`, and the knowledge
file locations.

**2. Check readiness.** Fetch the milestone and its Stories.

Any Story still open → say which, explain that extraction works on
completed milestones because the interesting failures happen during
implementation and validation, and ask whether to continue anyway. If
the engineer continues, extract — but do **not** close the milestone
(step 9).

Scan the epic tracker for a prior `## dev-lifecycle-kb-extraction`.
Found → ask whether to re-extract incrementally, covering only what is
new, or stop.

Then count what will be scanned — Stories, tasks, bugs, comments,
commits, PRs — and say so. Above a few hundred comments, scan in
Story-sized batches and report progress; this step is where the context
goes, and running out of it mid-extraction loses the work.

**3. Collect the data**, per Story and its tasks:

- **Issue comments** — the richest source. Debugging narrative lives in
  comments, not commit messages.
- **PR review threads** — where "this looks wrong because…" lives:

  ```bash
  gh pr view {pr} --repo {repo} --json comments,reviews,title,body
  gh api repos/{repo}/pulls/{pr}/comments --paginate \
    --jq '.[] | {path, line, user: .user.login, body}'
  ```

- **Commit messages**, especially fixes. A run of `#61: fix …` commits
  is a debugging session with the narrative stripped out — the diffs
  say what changed, the surrounding comments say why.
- **Test results** — `docs/test-results/*.md` for these issues.
  Regressions and flaky tests are learnings in themselves.
- **CI failures** on the story branches, where reachable
  (`gh run list --repo {repo} --branch "story/{n}-*"`).

**4. Extract five kinds of learning.**

- **Failure signatures** — a symptom paired with its actual cause. The
  *pairing* is the value; the symptom alone is what the next person
  already has. Capture the observable (error text, log line, stack
  frame, test name), what it actually meant, how it was distinguished
  from what it looked like, and the fix.
- **Caveats and quirks** — ordering requirements, a flag that must be
  set first, an API that returns success while doing nothing, a timeout
  that is really a retry limit.
- **Architecture insights** — things learned about the system that the
  design doc did not say, often discovered by breaking something.
- **Debugging techniques** — the command, query, or instrumentation
  that made an opaque failure legible. The highest-value entries, and
  the least often written down.
- **Knowledge file deltas** — where `ARCHITECTURE.md`, a conventions
  file, or a `docs/*.md` is now wrong or incomplete.

Four disciplines, each of which is what separates a useful knowledge
base from an ignored one:

- **Quote the source.** Every learning cites the issue, comment, PR, or
  commit it came from. An unattributed claim cannot be verified later.
- **Extract what happened, not what should have happened.** "The buffer
  overflowed because the flush interval was longer than the fill rate"
  is a learning. "Buffers should be flushed promptly" is a platitude.
- **Skip the generic.** If it could have been written before the
  milestone started, it is not a learning from the milestone.
- **Preserve exact strings** — error text, command invocations, config
  keys. They are what a future search matches on, and paraphrasing
  destroys their value.

**5. Categorize and deduplicate.** Group by subsystem and build target.
The same failure hit in three tasks is **one** learning with three
citations, not three learnings. Search the existing knowledge files and
any configured KB repo for each learning (`grep -ril "{key phrase}"`)
and drop what is already documented, or note it as reinforcement where
the existing text is thin.

Rate confidence: **high** (root-caused, fixed, verified by a test),
**medium** (consistent evidence, no definitive confirmation), or **low**
(a plausible pattern observed once). Low-confidence learnings are still
worth recording, labelled as such — a hypothesis someone can confirm
later beats a lost observation.

**6. Engineer review gate.** Present the scan counts, the learnings
table (type, learning, source, confidence), the proposed knowledge-file
updates, and where the KB articles will go. Ask the engineer to approve
all, select individually, edit the text, or stop.

**Do not skip this gate, in any mode.** Knowledge-base content outlives
the code it describes: a wrong entry misleads people for years and
nobody re-derives it to check. This is the one gate in this pipeline
that an autonomous run does **not** resolve as approve-and-note.

**7. Generate the files.** One article per learning, named
`{subsystem}-{slug}.md`, into the configured KB repo if declared and
`{repo_root}/docs/knowledge/` otherwise. Knowledge-file updates edit
the affected sections in place, **additively** — append to the relevant
section, do not restructure someone's document.

**8. Raise the PRs.** Knowledge-file updates in this repo go on one
branch, as one PR:

```bash
git switch --create "docs/{milestone_slug}-learnings" "origin/{default_branch}"
git add {edited files}
git commit -m "docs: capture learnings from milestone '{title}'"
git push -u origin "docs/{milestone_slug}-learnings"
gh pr create --repo {repo} --base "{default_branch}" \
  --title "docs: learnings from milestone '{title}'" --body-file {file}
```

For an external KB repo, clone shallow, write the articles, and open a
PR there. Clone or PR fails for lack of access → write the articles
into `{repo_root}/docs/knowledge/` instead, fold them into the PR
above, and report that the external PR could not be raised. **Do not
lose the content over an access problem.**

Report every PR with its URL. This pipeline does not merge them
(`AGENT.md` § Boundaries).

**9. Close the milestone.** Verify every Story is closed first — any
still open and the milestone is **not** closed; report and stop at the
summary.

Post the extraction record to the epic tracker (creating it if needed)
via `References/artifact-resolution.md` § Upload Procedure, sentinel
`## dev-lifecycle-kb-extraction`, carrying the scan counts, the
learning counts before and after deduplication, the KB article count
and PR, the knowledge-file PR, and the learnings table. Then:

```bash
gh api -X PATCH repos/{repo}/milestones/{n} -f state=closed
```

Label the tracker `status:resolved` and close it, per
`References/workflow-states.md` § Epic Lifecycle.

**10. Report** the milestone as closed, the Story count, the learnings
extracted and their sources, the KB articles and their PR, and the
knowledge-file PR — noting that both PRs are open for review and this
pipeline does not merge them. Where any learning was low-confidence,
say how many and that they are recorded as hypotheses worth confirming
next time the area is touched.

## Outputs

- KB articles, in the configured repo or `docs/knowledge/`.
- Additive edits to the repo's knowledge files.
- One PR in this repo, and optionally one in the KB repo. Neither
  merged.
- A `## dev-lifecycle-kb-extraction` record on the epic tracker.
- The milestone closed, and its tracker resolved and closed.

## State Transitions

Epic: In Progress → Closed — the milestone itself and its tracker
issue. **This is the only Skill in this port that closes a milestone**;
see `AGENT.md` § Boundaries.

## Errors

- **Milestone has open Stories:** warn, allow continuing for the
  extraction, but do **not** close the milestone.
- **No learnings found:** a legitimate outcome, not a failure — the
  milestone may simply have gone smoothly. Offer to close it without
  raising PRs.
- **KB repo inaccessible:** fall back to `docs/knowledge/` and report.
- **Volume too large for one pass:** batch by Story, report progress,
  and run `checkpoint` between batches so exhausting the context does
  not lose the extraction.
- **Prior extraction exists:** offer incremental or full re-extraction.
- **Milestone close fails:** report the PRs raised and the failure. The
  extraction is the valuable part; closing the milestone is bookkeeping
  and can be done by hand.
- **Standard `gh` failures:** `References/gh-error-handling.md`.

**Root-cause documents are the highest-signal source available** —
already-structured root causes, each with a classification, a trigger
condition, and a stated confidence. Collect them for every bug in the
milestone, via `## dev-lifecycle-rca` sentinels and
`docs/design/*-rca.md`, and read them before the raw comment threads: a
learning that an RCA already states precisely does not need
re-deriving from the conversation that produced it.

An RCA marked `confidence: hypothesis` maps to a **low-confidence**
learning in step 5, not a high one, however well-written it reads.

## Templates

`Templates/kb-article.md` gives KB articles their fixed shape and is
**present**. Generate every article from it.

Its frontmatter is what makes an article findable later, so fill it
even where a value looks obvious from the body — `error_patterns` and
`related_commands` especially. Error strings are matched verbatim by a
future search, so paraphrasing one destroys its value.

The `confidence` field in the frontmatter and the `## Confidence`
section must agree; the rule in this Skill decides both, and an RCA
marked as a hypothesis is **low** however well-written it reads.
