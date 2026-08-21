# checkpoint

Captures local workflow state, git state, and PR state, and posts it to
an issue as a structured comment so another engineer — or a later
session — can pick the work up. Paired with `resume`.

## Purpose

Record what git cannot reconstruct. Someone with no context should be
able to read one comment and continue: what you were about to do, what
you already tried that failed, and what you know that the code does not
say.

## Preconditions

- An issue to checkpoint against. With no issue given, look for
  `PROGRESS-*.md` in the working directory — exactly one identifies the
  issue; several means ask which; none means ask for a number.
- `gh` authenticated with write access.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` Steps
1-2. Needs `{repo}`, `{repo_root}`, `{default_branch}`.

**2. Read the progress file.** `PROGRESS-{issue}.md` if it exists,
otherwise `PROGRESS.md` when its `issue` field matches. Take
`active_skill`, `current_phase`, `story_branch`, and the body summary
(schema in `Skills/story-design.md` step 6).

No progress file is **not an error** — checkpoint what is observable.

**3. Capture git state.**

```bash
git -C {repo_root} branch --show-current
git -C {repo_root} status --short
git -C {repo_root} log --oneline "origin/{default_branch}..HEAD" | head -20
git -C {repo_root} log --oneline -5
git -C {repo_root} stash list
```

Record the branch, uncommitted files, unpushed commits, recent commits,
and **stashes** — stashes are the single most-forgotten piece of state
in a handoff, and they are invisible to everyone but their author.

**4. Deal with unreachable work.** Unpushed commits or uncommitted
changes are a handoff hazard: a checkpoint can record that they exist,
but it cannot make them reachable by anyone else.

> "{n} unpushed commits and {m} uncommitted files. A checkpoint records
> that they exist, but nobody else can access them until they are
> pushed."

Offer to commit and push (as `#{issue}: WIP — checkpoint`), to push the
committed work only and leave the working tree alone, or to checkpoint
as-is and push nothing. In an autonomous run, push — an agent's
uncommitted work is lost when it exits, which makes "as-is" the one
option that is never right there.

Never `git reset`, `git clean`, or force-switch to tidy the tree first
(`AGENT.md` § Boundaries).

**5. Capture PR and artifact state.**

```bash
gh pr list --repo {repo} --head "{current_branch}" --state all \
  --json number,state,isDraft,reviewDecision,url,statusCheckRollup

ls -la docs/design/{issue}-* docs/test-plans/{issue}-* \
       docs/test-results/{issue}-* 2>/dev/null
```

Record the environment only where it affects reproducibility — the
working directory, the toolchain versions the project's commands
depend on, and any environment variable those commands reference. Do
not dump the whole environment, and **never** record anything that
looks like a credential.

**6. Capture intent.** This is the part git cannot reconstruct, and the
reason this Skill exists. Ask:

1. What were you about to do next?
2. Anything in flight or half-finished a reader should know about?
3. Anything you tried that did **not** work? (Saves the next person
   from repeating it.)
4. Any blockers or open questions?

Record "not provided" for anything skipped — never invent content here.
A fabricated "next step" is worse than a blank one, because the reader
acts on it. In an autonomous run, fill these from the run's own state
rather than asking.

**7. Determine the pipeline position.** Fetch the issue
(`number,title,state,labels,assignees,milestone,comments`) and read
which sentinels are present — design doc, test plan, unit tests,
results — so the reader gets the stage without deriving it.

**8. Post the checkpoint** via `References/artifact-resolution.md`
§ Upload Procedure, sentinel `## dev-lifecycle-checkpoint`, written via
`--body-file`. Sections, in order:

- **Pipeline position** — a stage/state table (design doc, test plan,
  tasks resolved over total, implementation, validation).
- **Git** — branch, head SHA and subject, unpushed commits, uncommitted
  files, stashes, and whether it is pushed.
- **Pull request** — number, state, draft or ready, review decision, CI
  status; or none.
- **Local artifacts** — each path, and whether it is synced to the
  issue or local only.
- **Next step**, **In flight**, **Tried and rejected**, **Blockers /
  open questions** — from step 6.
- **Resume** — that `resume {issue}` restores this.

Where work is unreachable, end with it stated plainly rather than
buried in the git table:

> "{n} commits are unpushed and {m} files uncommitted on `{branch}`.
> They exist only on {hostname}. Another engineer resuming from this
> checkpoint will not have them."

Verify the comment landed, per that same section — an operation that
exits 0 having done nothing is the failure mode this pipeline guards
against everywhere.

**9. Update the progress file.** Add or update:

```yaml
checkpointed: true
checkpointed_at: {timestamp}
checkpoint_comment: {comment_url}
```

Create `PROGRESS-{issue}.md` if absent — with a checkpoint posted there
is now state worth tracking locally. Commit it if it is inside the repo
and the branch is not protected.

**10. Report** the branch and head SHA and whether it is pushed, the
unpushed and uncommitted counts, the PR, and the comment URL. Where
anything is unpushed, say so again at the end:

> "Push before handing off — the checkpoint records that this work
> exists but cannot make it reachable."

## Outputs

- A `## dev-lifecycle-checkpoint` sentinel comment on the issue.
- A created or updated `PROGRESS-{issue}.md`.
- Optionally a `WIP` commit and a push, with consent.

## State Transitions

None. Checkpointing records state; it does not advance it.

## Errors

- **No progress file:** not an error — checkpoint observable state.
- **Not in a git repo:** checkpoint the issue state and the interview
  answers, and skip the git section with a note saying why.
- **Comment post fails:** write the checkpoint to
  `docs/test-results/{issue}-checkpoint-{timestamp}.md` so the content
  survives, and report both the failure and the local path. Losing a
  handoff to a transient API error is the one outcome this Skill cannot
  afford.
- **Detached HEAD:** record the SHA and say so explicitly — a resume
  from a detached HEAD needs the SHA, not a branch name.
- **Standard `gh` failures:** `References/gh-error-handling.md`.
