# planner

The planning role: takes a milestone or a Story from "requirements
written down" to "designed, sized, test-planned, and broken into
tasks." Composed by `autodev`; independently invocable on its own.

## Purpose

One of three worker roles — `planner`, `coder`, `validator` — that an
orchestrator runs. Each is an ordinary Workflow, which is what makes
the roles portable: see `## Running This Role` below.

This one owns everything upstream of code being written.

## Preconditions

- A milestone with requirements, or a Story number to plan just that
  Story.
- `gh` authenticated with write access.
- Everything the invoked Skills require. This Workflow inherits their
  preconditions rather than restating them.

## Running This Role

A role is content, not a harness feature. The orchestrator decides how
to run it, and the choice changes nothing about the steps below:

- **Harness with a subagent primitive:** run this Workflow in a
  separate worker with its own context. Preferred — planning a
  milestone reads a lot of GitHub, and isolating it keeps the
  orchestrator's own context free.
- **Harness without one:** run this Workflow inline, in the main
  session. Identical steps, identical gates, identical output
  contract; the only difference is a shared context, so the
  orchestrator should say so up front and `checkpoint` between
  Stories on a long run.

Nothing in this file spawns anything. That decision belongs to the
orchestrator (`Workflows/autodev.md` § Running the Workers).

## Procedure

**1. Preflight — validate the whole chain before doing any of it.**
Run `References/context-discovery.md` in full; record `{repo}`,
`{repo_root}`, `{design_doc_path}`, `{test_plan_path}`,
`{build_targets}`, `{default_branch}`.

Not a git repo, no GitHub remote, or no `README.md` → **abort** naming
the specific gap. Validating up front matters here: this role can spend
a long design session before reaching `task-create`, and discovering a
missing precondition then wastes all of it.

Then, per Story in scope, check what already exists — a
`## dev-lifecycle-design-doc` sentinel, a local design file, a
`status:` label — so the steps below can skip rather than redo.

**2. Break the milestone into Stories.** Given a milestone, run
`story-create`. Always run it, even when Stories exist: the Skill
deduplicates internally, querying existing Stories and creating only
net-new ones, which is what makes a partial breakdown or a later
requirement addition resolve correctly.

Capture every Story number, existing and created.

**Verify:** re-list the milestone's `type:story` issues from GitHub.
Zero → hard failure; report and stop. Given a Story number directly,
skip this step.

**3. Per Story, design it.** Three cases, checked in order:

- **Sentinel already on the issue:** skip `story-design`. Ensure the
  Story carries `status:in-progress` (already at or beyond that → no
  error, no action), and ensure a local copy exists for downstream
  Skills, extracting it from the comment or its permalink.
- **A local design file but no sentinel:** the content is valid, it
  was just never posted. Sync it upward per
  `References/artifact-resolution.md` § Syncing a Local Artifact
  Upward, sentinel `## dev-lifecycle-design-doc`, then skip the Skill.
- **Neither:** run `story-design`. Its section-by-section prompts and
  its final approval gate are expected interaction, not a stall.

**Verify:** re-read the issue and confirm the
`## dev-lifecycle-design-doc` sentinel is present. Absent → hard
failure for this Story; report and stop rather than proceeding to
`task-create` with nothing to derive tasks from.

**4. Size it.** Run `size` against the Story while the design is
fresh. **Post the estimate** — this is the one context where `size`'s
display-only default is overridden, because the orchestrator's design
gate presents it and a gate with no number is a worse gate.

Informational only: sizing failing is a **warning, never a failure**.
Record "—" and continue.

**5. Generate the test plan.** Run `story-test-plan` against the
Story. It derives cases from the design doc, which is why it runs here
rather than after implementation — a plan written from the design says
what *should* be true, and that is the thing worth agreeing before code
exists.

Regrounding it on the code actually written is `validator`'s job, via
`story-test-replan`.

**Verify** the `## dev-lifecycle-test-plan` sentinel landed. Absent →
warning, not a failure: `story-test` can run without a plan at reduced
grounding, and it says so itself.

**6. Create the tasks.** Run `task-create` once the design doc is
committed. One task per build target, per
`AGENT.md` § The GitHub Hierarchy.

**Verify** the sub-issues exist and each carries `type:task`. Zero →
hard failure for this Story.

**7. Return the plan** in the output contract below.

## Output Contract

Returned to the orchestrator. Keep the shape:

```
Planned {Milestone|Story} {ref}:

· Story #{n}: {title}
  Design:    docs/design/{n}-design.md ({permalink})
  Effort:    {S|M|L|XL} (or "—" when sizing was skipped)
  Test plan: docs/test-plans/{n}-test-plan.md ({n} cases, {n} P0)
  Tasks:     #{n}, #{n}, #{n} ({n} build targets)
  Branch:    story/{n}-{slug}

Total: {n} Stories planned.
Ready for design review.
```

On a hard failure, return instead:

```
HARD FAILURE in step {n} ({skill}): {reason}
Planned so far: {list, or "nothing"}
```

## Idempotency

Every step checks before acting, so re-running this role on a
part-planned milestone resumes rather than duplicating:

| Already present | Behaviour |
|---|---|
| Stories exist | `story-create` dedupes internally — run it anyway |
| Design sentinel on the issue | Skip `story-design`; ensure the label and a local copy |
| Local design, no sentinel | Sync upward, then skip the Skill |
| Effort estimate exists | Post a new one — the progression is the point (`References/sizing-criteria.md` § Re-Sizing) |
| Test plan sentinel exists | Skip `story-test-plan`; a regrounding pass is `validator`'s |
| Tasks exist | `task-create` dedupes per build target |

## Outputs

Whatever the invoked Skills produce: Story issues, design docs and
their sentinels, effort estimates, test plans and case files, task
sub-issues, and story branches. This Workflow writes nothing itself.

## Errors

- **No Stories after `story-create`:** hard failure — nothing to plan.
- **No design sentinel after `story-design`:** hard failure for that
  Story. Do not continue to `task-create`.
- **`size` fails:** warning. Record "—" and continue.
- **No test plan sentinel:** warning. `story-test` degrades explicitly.
- **No tasks after `task-create`:** hard failure for that Story.
- **A design gate is rejected:** stop that Story, report, and let the
  orchestrator continue with the others. If the rejection is because
  requirements changed, `replan` is the right Skill, not another pass
  of `story-design`.

Anything a called Skill treats as a hard stop is a hard stop here too.
This Workflow does not override a Skill's own error handling, and it
never merges, deletes, or force-pushes — see `AGENT.md` § Boundaries.
