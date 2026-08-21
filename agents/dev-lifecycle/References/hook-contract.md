# Hook Contract

Lifecycle automation stated as **guarantees**, not scripts. Six hooks,
each with the event it keys on, the promise it makes, and a named
degradation for when it cannot fire.

The source material implements these as six shell scripts registered
in one Claude-Code-specific `hooks.json`. That registration file does
not survive the port: the four harnesses this catalog targets do not
share a hook mechanism, and some have none at all. What is ported is
the contract each script was enforcing, so a harness can honor it by
whatever means it has — or be honest that it cannot. Per-harness
expression lives in `harness-adapters/*/README.md` § Hooks.

Counted as seven in task #30's requirements: six scripts plus their
registration file. There is no seventh hook.

## Invariants

Two properties hold across the whole contract. A harness expression
that breaks either is not honoring it.

**Advisory, never blocking.** Every hook succeeds whatever it finds.
A hook that cannot parse its input, or that finds a violation, prints
and yields. There is exactly one deliberate exception, named under
`check-commit-prefix` below: the git `commit-msg` expression *does*
reject, because rejecting is the entire reason to prefer it.

**The catalog runs without any of them.** No Skill or Workflow
requires a hook to have fired. Each hook re-derives, earlier and
automatically, something a Skill already establishes on its own — it
buys timing, not capability. This is what makes a harness with no hook
mechanism merely worse to use rather than broken, and it is the
property to preserve if this contract ever grows.

## The Six Hooks

| Hook | Guarantee | Keys on | Git hook? |
|---|---|---|---|
| `check-commit-prefix` | A commit message carries an issue prefix before it is written | A commit is about to run | **yes** — `commit-msg` |
| `issue-link-commit` | A commit that will not appear in any issue timeline is called out at the moment it is made | A commit has completed | **yes** — `post-commit` |
| `session-start` | A session opens knowing whether `gh` is usable and whether work is already in flight | A session begins | no |
| `detect-workflow-prompt` | A request that names an issue and describes a lifecycle step is pointed at the Skill that does it | A user prompt is submitted | no |
| `auto-save-progress` | A session does not end with an uncommitted progress file | A session or turn ends | no |
| `pre-compact` | Workflow state survives a context compaction | Context is about to be compacted | no |

Three of the six — `session-start`, `auto-save-progress`,
`pre-compact` — read `PROGRESS-{issue}.md`, whose schema is in
`Skills/story-design.md` step 6. That file is a real part of this port
(`checkpoint`, `resume`, and `status` all read or write it), so these
guarantees translate without restatement.

### check-commit-prefix

**Guarantee.** A commit message that does not start with `#{issue}: `
— or `owner/repo#{issue}: ` for a cross-repo reference — is flagged
before the commit lands.

**Event.** A commit is about to run. An amend carrying no new message
is out of scope: there is nothing to validate.

**Degradation.** Commits land without a prefix, and nothing announces
it. The consequence is not cosmetic: an unprefixed commit never
appears in its issue's timeline, so the traceability the whole
lifecycle rests on is silently missing for that commit. Detection
moves to review time, where `task-test` and `story-test` read the
commit log against the issue.

**Delivery.** Prefer the git `commit-msg` hook, which is **shipped**:
`Templates/git-commit-msg-hook.sh`, with install instructions in
`Templates/CONTRIBUTING.md` § Commits. This is the one place the
contract's advisory invariant is deliberately relaxed: a `commit-msg`
hook can exit non-zero and *reject* the commit, which is strictly
better than printing advice after the fact, and it works on every
harness and on plain command-line git alike. Merge, `fixup!`/`squash!`,
and `Revert` commits are exempt. Where a harness expresses this as its
own pre-commit hook instead, it stays advisory — a harness hook that
blocks a tool call is a worse failure mode than an unprefixed commit.
State which of the two a given harness is doing; they are not
interchangeable.

### issue-link-commit

**Guarantee.** After a commit completes, its issue reference is
confirmed, or its absence is reported. No API call is involved:
GitHub cross-links a commit to an issue on its own once the message
contains `#N` and the commit lands in the same repo. The hook confirms
the link will form; it does not create it.

**Event.** A commit has completed successfully.

**Degradation.** The link still forms — GitHub does that regardless.
What is lost is the immediate notice that a *particular* commit will
not appear in any issue timeline. Overlaps with
`check-commit-prefix`, deliberately: one catches the message before it
is written, the other catches what actually got written.

**Delivery.** Deliverable as a git `post-commit` hook, which reads the
commit that just landed rather than a tool call's transcript, and so
is both simpler and more accurate than the harness expression. **No
script is shipped for this one** — unlike `check-commit-prefix`, it
has no counterpart in `Templates/`. It is a specification here and
nothing more, which is the honest reading of "deliverable as".

### session-start

**Guarantee.** By the first turn of a session, three things are known:
whether `gh` is installed and authenticated; whether the repo root has
the docs this agent discovers project context from; and whether a
`PROGRESS-*.md` shows work already in flight, including whether it was
checkpointed.

**Event.** A session begins.

**Degradation.** All three are recoverable, just later and more
expensively. `gh` trouble surfaces as the first failing command
instead, handled by `References/gh-error-handling.md` §§ 1–2 — the
same message, one wasted call later. Missing root docs surface when
`References/context-discovery.md` cannot resolve build targets, which
routes to `init`. In-flight work is found by invoking `status`, which
reads the same progress files plus GitHub state, and reads more of
them than this hook does. So the loss here is one prompt of
convenience, not a capability: **`status` is the manual equivalent of
this hook**, and is the thing to tell a user to run where it cannot
fire.

**Delivery.** Not a git hook — git has no notion of a session. Where a
harness has no session event, the fallback is to run `status` at the
start of a session by convention.

### detect-workflow-prompt

**Guarantee.** A prompt that both names an issue (`#123`, `GH-123`, or
an issue URL) and describes a lifecycle step gets a pointer to the
Skill that performs it. Both conditions must hold — an issue number
with no intent produces nothing, which is what keeps this from firing
on ordinary conversation.

**Event.** A user prompt is submitted, before it is acted on.

**Degradation.** This is the most redundant hook in the set, and the
least costly to lose. `AGENT.md` § Routing is the same mapping in
durable form, and the agent consults it anyway; the hook only makes
the match happen a turn earlier. Nothing is unreachable without it.

**Delivery.** Not a git hook. No fallback is needed beyond the routing
table already in `AGENT.md`.

### auto-save-progress

**Guarantee.** A session does not end leaving `PROGRESS-{issue}.md`
modified but uncommitted.

**Event.** A session or turn ends.

**Degradation.** Progress-file edits stay uncommitted and invisible to
everyone else. Nothing is destroyed — the file is on disk — but a
handoff made from that state is missing whatever the last session
learned. `checkpoint` is the manual equivalent and does strictly more,
since it captures git state, PR state, and stashes as well as the
progress file; the hook is a reminder to run it, not a substitute.

**Delivery.** Not a git hook: the trigger is a session ending, and git
has no such event. Where a harness has no session-end event, the
fallback is `checkpoint` invoked deliberately.

### pre-compact

**Guarantee.** Before context is compacted, the active issue, repo,
milestone, Skill, phase, and story branch are re-emitted, so the
workflow survives the compaction.

**Event.** Context is about to be compacted.

**Degradation.** Post-compaction the session may not know which issue
it is on. Recovery is reading `PROGRESS-{issue}.md`, which is the same
file this hook was quoting from and is still on disk — so the state is
never lost, only unloaded. This is the hook whose absence is felt most
often on a long-running `autodev` run, and the reason every Skill in
this port is resumable from GitHub state alone: that design decision
is what makes losing this hook survivable.

**Delivery.** Not a git hook. Where a harness has no compaction event
— or does not compact at all — the fallback is that resumability
already covers it; re-read the progress file.

## The Git-Hook Subset

Two of the six are deliverable as plain git hooks:
`check-commit-prefix` as `commit-msg`, `issue-link-commit` as
`post-commit`. **Prefer these.** A git hook runs for every commit in
the repo regardless of which harness — or no harness — made it, which
is a stronger guarantee than any per-harness expression can offer, and
it is the only expression available on a harness with no hook
mechanism at all.

The remaining four key on session start, prompt submission, session
end, and context compaction. None has a git equivalent, because git
has no concept of a session or a conversation. They are harness
features or they are nothing, and where a harness lacks them the
fallbacks named above — `status`, `checkpoint`, `AGENT.md` § Routing,
and progress-file resumability — are the whole of the recovery.

Of the two, only `check-commit-prefix` has a script in this catalog:
`Templates/git-commit-msg-hook.sh`. `issue-link-commit` is specified
here and not implemented anywhere.

Git hooks are **not installed by this catalog**, shipped script
included. `.git/hooks/` is local, untracked, and per-clone; writing
into it is a mutation of a user's repository outside anything this
agent was asked to do. The user installs it — either by copying into
`.git/hooks/commit-msg`, or by committing it to a tracked directory
and pointing `core.hooksPath` at that directory, which is how a
project makes it reviewable and gets it to every contributor. Both
forms are written out in `Templates/CONTRIBUTING.md` § Commits.

## Delivery Status

This document is the contract, and it is mostly still only that.

**One executable exists**: `Templates/git-commit-msg-hook.sh`, the git
expression of `check-commit-prefix`, added by task #32. It ships as a
template for a user to install, not as something this catalog turns
on.

Everything else here is a specification. The other five hooks have no
script in this catalog, on any harness; the harness expressions are
described in `harness-adapters/*/README.md` § Hooks but are not
generated, and `install.generate_harness_adapters` writes agent
pointers only. Do not read a guarantee in this document as something
currently firing.
