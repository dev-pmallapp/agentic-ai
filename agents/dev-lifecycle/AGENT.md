---
name: dev-lifecycle
description: Reserved for a GitHub-native, issue/PR-driven development lifecycle (milestone -> story -> task -> PR). Not yet implemented.
---

# dev-lifecycle

**Reservation, not an implementation.** This directory holds a name, a
pointer, and the empty anatomy directories it will be filled into.
`Skills/`, `Workflows/`, `References/`, and `Tools/` all exist and are
all empty.

Most agents in this catalog will be ported from LifeOS's skill
catalog. A GitHub-native development lifecycle — issues, sub-issues,
milestones, pull requests, and the traceability between them — is the
one domain LifeOS has no equivalent for, so it is the one place this
project draws on a second source.

That source is the Forge plugin at `/home/pmallapp/tmp/gh-workflow`,
a self-contained Claude Code plugin for exactly this lifecycle. Its
agent split (`forge-planner` / `forge-coder` / `forge-validator`) and
its skills set are the reference to draw from when this gets built out
for real: planning and decomposition, implementation, and validation as
three separable roles over one issue hierarchy.

The port has a decided shape. Forge's 20 atomic skills become `Skills/`
— each individually invocable, as they already are as `/` commands.
Forge's orchestration (`autodev`, `bug-fix`) becomes `Workflows/`,
composing those Skills and owning the human gates. Forge's 13 shared
references become `References/`. The direction is one-way: Forge bends
to this catalog's anatomy, never the reverse.

Nothing has been ported. Forge remains untouched and independent; a
real port — deciding which parts become workflows here, and how its
`gh`-only dependency model maps onto this catalog's harness-neutral
content — is future work.
