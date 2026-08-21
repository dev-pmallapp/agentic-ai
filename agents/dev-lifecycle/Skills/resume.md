# resume

Pulls the most recent checkpoint from an issue, reconciles it against
the current state of the repo and the issue, restores local progress
state, and presents what is needed to continue. Paired with
`checkpoint`.

## Purpose

The reconciliation matters more than the restore. A checkpoint is a
snapshot of a moment, and the repo may have moved since — work may have
continued without you. This Skill reports what changed rather than
presenting a stale snapshot as current.

## Preconditions

- An issue with at least one `## dev-lifecycle-checkpoint` comment.
- `gh` authenticated. Read access is enough.

## Procedure

**1. Resolve context.** Run `References/context-discovery.md` Steps
1-2. Needs `{repo}`, `{repo_root}`, `{default_branch}`,
`{current_user}`.

**2. Fetch the checkpoint.** Fetch the issue
(`number,title,body,state,labels,assignees,milestone,comments`) and
scan for comments whose body starts with
`## dev-lifecycle-checkpoint`. Use the **most recent** by `createdAt`.

None found → report what *is* available rather than failing: the issue
title, state and labels; which sentinels are present; the local
progress file, branches, and artifacts; and the pipeline's next step.
Route to `status` for the fuller picture.

Parse the sections: pipeline position, git state, PR, artifacts, next
step, in-flight work, tried-and-rejected, blockers.

Note **who** wrote it and **when**, and say which case this is — a
checkpoint from someone else is a handoff; one of your own from this
morning is a resume. The reader treats them differently.

**3. Reconcile against reality.** The checkpoint describes a past
moment; check what still holds.

*Branch:*

```bash
git -C {repo_root} fetch origin
git -C {repo_root} rev-parse --verify "{checkpoint_branch}" 2>/dev/null
git ls-remote --heads origin "{checkpoint_branch}"
```

| Finding | Report |
|---|---|
| Local and remote both present | Available |
| Remote only | Exists on the remote but not locally — `git switch {branch}` will create it |
| Local only | The checkpoint's commits were never pushed. If this is a handoff from someone else, their work is not here |
| Neither | Branch no longer exists — it may have been merged and deleted |

*Head commit:* does the checkpoint's SHA still exist, and is the branch
still at it?

```bash
git -C {repo_root} cat-file -e {checkpoint_sha} 2>/dev/null
git -C {repo_root} rev-parse "{checkpoint_branch}"
```

Moved → report how far and in which direction.

*Issue state:* compare the checkpoint's pipeline position against the
issue now — "since the checkpoint: the test plan was posted, #62 was
resolved, PR #105 was merged." **This is the highest-value part of the
reconcile**, and the reason resuming blind is dangerous.

*PR state:* fetch it (`state,isDraft,reviewDecision,mergedAt,
statusCheckRollup`). Merged since the checkpoint → say so; the branch
may be gone for a good reason rather than a bad one.

*Unreachable work:* if the checkpoint recorded uncommitted files or
stashes, those exist only on the authoring machine:

> "The checkpoint recorded {n} uncommitted files and {m} stashes on
> {hostname}. They are not in this clone and cannot be recovered from
> here. If you are not on that machine, treat that work as unavailable
> and ask its author."

**4. Restore local state.** Write `PROGRESS-{issue}.md` from the
checkpoint using the schema in `Skills/story-design.md` step 6, with
`checkpointed: false` (this session is now live), plus
`restored_from: {checkpoint_comment_url}` and `restored_at`. Use the
**reconciled** values, not the stale ones. Below the frontmatter, carry
the checkpoint's narrative sections: next step, in flight, tried and
rejected, blockers.

An existing progress file **newer** than the checkpoint is not
overwritten silently — report both timestamps and ask whether to
overwrite, keep, or diff.

**5. Offer the branch, do not take it.** Check the tree first
(`git -C {repo_root} status --porcelain`). Clean and the branch exists
→ offer to check it out. Dirty → report it and let the engineer decide.
**Never** force-switch, reset, or clean (`AGENT.md` § Boundaries) —
the working tree may hold unrelated work, and it is not this Skill's to
discard.

**6. Fetch missing artifacts.** For each artifact the checkpoint
references that is not on disk, resolve it through
`References/artifact-resolution.md` § Resolution Chain so the local
copy is restored.

**7. Present.** Lead with whose checkpoint it is and how old, then:
where things stood (the pipeline table), **what changed since** (the
reconciliation findings, or "nothing"), current state (branch, head, PR,
issue labels, tasks resolved over total), the next step per the
checkpoint, in-flight work, what was already tried and rejected, and
blockers.

The suggested next command comes from the **reconciled** state, not
from the checkpoint's `active_skill` — if the pipeline moved on, the
next step moved with it.

**8. Stop.** Do **not** execute the suggested next step. Presenting a
suggestion is not authorization to run it: the engineer decides after
reading what changed. Resuming into an action its author intended three
days ago, without confirmation, is how work gets duplicated or undone.

## Multiple Checkpoints

An issue accumulates checkpoints. Only the most recent is restored, but
list the others with author and date so the history stays visible.

## Outputs

- A restored or updated `PROGRESS-{issue}.md`.
- Locally restored artifacts that the checkpoint referenced.
- A presented reconciliation. No GitHub writes.

## State Transitions

None.

## Errors

- **No checkpoint:** report available state and the pipeline's next
  step (step 2). Not a failure.
- **Checkpoint references a deleted branch:** report it — the work may
  have merged. Check the PR state before concluding anything was lost.
- **Checkpoint references unpushed work:** flag it as unavailable and
  name the author to ask.
- **Local progress file is newer:** ask before overwriting.
- **Working tree is dirty:** report and let the engineer resolve it.
  Never force-switch.
- **Checkpoint is malformed** (missing sections): restore what parses,
  list what did not, and continue.
- **Standard `gh` failures:** `References/gh-error-handling.md`.
