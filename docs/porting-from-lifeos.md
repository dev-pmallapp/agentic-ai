# Porting a skill from LifeOS

`ARCHITECTURE.md` calls this "close to mechanical — copy the directory,
strip what doesn't apply, done." This doc is the checklist that makes
that true: what maps where, what gets deleted, what survives untouched,
and how to prove the port didn't break anything.

Source catalog: `/home/pmallapp/tmp/LifeOS/LifeOS/install/skills/`
(read-only reference, never edited from here).

## 1. The structural mapping

| LifeOS | ai-agents |
|---|---|
| `skills/<Name>/SKILL.md` | `agents/<Name>/AGENT.md` |
| `skills/<Name>/Workflows/*.md` | `Skills/` or `Workflows/` — **decide per file** |
| loose `*.md` at the skill root (`Foundation.md`, `BiasTaxonomy.md`, `MethodSelection.md`, `Archetypes.md`, `LeveragePoints.md`) | `References/*.md` |
| `Tools/*.ts` | `Tools/*.py` — rewrite, do not transliterate |

The first three rows are close to copy-paste. The second row is not,
and it is the part of the port that actually requires judgment.

### Workflows/ does not map onto Workflows/

LifeOS has no Skill/Workflow distinction — every procedure under a
LifeOS skill's `Workflows/` directory is just called a "workflow,"
whether it runs alone or sequences other files. This catalog's split
is real (`ARCHITECTURE.md`, "Skills and Workflows"): a Skill is atomic
and individually invocable; a Workflow is cumulative, sequences Skills,
and owns the gates between them. Most LifeOS workflow files turn out to
be atomic once you check what they actually depend on, so **most of
them become Skills here, not Workflows.**

`RootCauseAnalysis/` is the clean worked example, because it contains
one genuine case of each:

- `Workflows/FiveWhys.md`, `Fishbone.md`, `FaultTree.md`,
  `KepnerTregoe.md` each run end to end alone. `FiveWhys.md`'s own
  "Invocation" section lists "single-thread incident with known-proximate
  cause" and nothing about another file having run first. These four
  become **Skills**.
- `Workflows/Postmortem.md` is different. Its own text says so
  directly: *"The postmortem is the wrapper for other RCA tools. Inside
  the postmortem, use 5 Whys, Fishbone, Kepner-Tregoe as appropriate to
  investigate the causes."* Its `Integration` section: *"Wraps: 5 Whys,
  Fishbone, Kepner-Tregoe, Fault Tree — use whichever fits each
  contributing thread."* It also owns a gate the others don't have —
  Phase 5's action-item sign-off before the incident can close. This one
  becomes the agent's single **Workflow**.

`SystemsThinking/` is the trap case, and the reason "decide per file"
is in the table instead of a rule you could automate. Its five
workflow files (`Iceberg.md`, `CausalLoop.md`, `FindArchetype.md`,
`FindLeverage.md`, `ConceptMap.md`) constantly reference each other —
`CausalLoop.md`'s Integration section: *"Feeds **FindLeverage** — once
the CLD is drawn, Meadows' leverage points apply."* `Iceberg.md`:
*"Feeds **CausalLoop** when Layer 3 structure is a feedback loop that
deserves explicit diagramming."* Read quickly, that looks exactly like
Postmortem wrapping the RCA methods. It isn't. Every one of these is
phrased as "feeds" or "runs after" or "entry point from" — a suggested
next step a human can take or skip — not a wrapper that sequences the
others and owns a gate. Each file is independently invocable: you can
run `Iceberg` on its own and get a complete answer; nothing requires
`CausalLoop` to have executed first. All five stay **Skills**. Nothing
under `SystemsThinking/` becomes a Workflow.

The check that separates the two cases: does the file say another file
must have already run, or does it own an approval gate over a sequence?
If it only says "consider running X next," that's a Skill pointing at
a sibling Skill, not a Workflow.

## 2. What gets stripped

### Voice notification blocks

Most LifeOS skills open with a mandatory `curl` to a local voice
daemon. From `BiasCheck/SKILL.md`:

````
## Voice Notification

**When executing a workflow, do BOTH:**

1. **Send voice notification**:
   ```bash
   curl -s -X POST http://localhost:31337/notify \
     -H "Content-Type: application/json" \
     -d '{"message": "Running the Check workflow in the BiasCheck skill to audit the source"}' \
     > /dev/null 2>&1 &
   ```
````

`RootCauseAnalysis/SKILL.md` makes it stronger still: `## MANDATORY:
Voice Notification (REQUIRED BEFORE ANY ACTION)` ... `**This is not
optional. Execute this curl command immediately upon skill
invocation.**` Delete the whole section — heading, curl, and the text
notification line under it — on every file that has one.

**Not universal — check anyway.** `ExtractWisdom/SKILL.md` has no
Voice Notification section at all (`grep -c 31337` on it returns 0).
Across the whole LifeOS catalog, 43 of 57 skills have the block and 14
don't. Don't assume every ported file needs this strip; grep for it.

### Customization-path lookups

Every skill in this batch opens (or nearly opens) with a pointer into
the user's LifeOS install. From `ExtractWisdom/SKILL.md`:

```
## Customization

**Before executing, check for user customizations at:**
`~/.claude/LIFEOS/USER/CUSTOMIZATIONS/SKILLS/ExtractWisdom/`

If this directory exists, load and apply any PREFERENCES.md,
configurations, or resources found there. These override default
behavior. If the directory does not exist, proceed with skill defaults.
```

This is LifeOS's own override mechanism and has no counterpart here —
this catalog's override mechanism is the tier cascade in
`ARCHITECTURE.md` ("Multi-level Install"), which already lets a project
pin an edited copy of an agent. Delete the section. Same 43-of-57 count
as the voice block — the two travel together in practice.

### LifeOS runtime references

Mentions of Pulse, Cortex, the Algorithm, TELOS, ISA, Synapse, Atlas,
Ledger, Hermes, or the DA turn up across the four skills read for this
guide. Most are incidental — a passing mention of how LifeOS's own
routing engine happens to invoke the skill, safe to delete without
touching the substance. A couple are load-bearing enough that deleting
them naively would delete real content along with the LifeOS-specific
wrapper around it.

**Incidental (delete outright):**

`SystemsThinking/Workflows/Iceberg.md`, "Invocation":
```
2. **By the Algorithm** when OBSERVE capability scan selects
   SystemsThinking with a recurring-problem signal
```
This just describes LifeOS's own dispatcher. The line right after it —
*"By the RootCauseAnalysis skill — its Postmortem workflow hands off to
Iceberg when patterns repeat across incidents"* — is a real cross-agent
integration point worth keeping if both agents get ported.

Every skill read for this guide ends with an `## Execution Log` block
appending a JSONL line to `~/.claude/LIFEOS/MEMORY/SKILLS/execution.jsonl`
— LifeOS's own telemetry sink. This catalog has no equivalent logging
path. Delete the section.

**Load-bearing (rewrite, don't just delete):**

`BiasCheck/Workflows/Check.md`:
```
## Step 0 — Sufficiency Check (Algorithm v6.7.0)
```
The three-item gate underneath this heading (is there a source, is
this the right tool, is the input ambiguous) is genuinely valuable —
keep it. Only the `(Algorithm v6.7.0)` parenthetical, which cites
LifeOS's own versioned routing engine, needs to go. Retitle the
heading, keep the gate.

`SecurityMarketData/SKILL.md`, "Setup and Diagnostics":
```
Prefer Streamable HTTP MCP. For Hermes:

hermes mcp add signal-mcp --url https://mcp.returnonsecurity.com/mcp
hermes mcp list
```
A ported agent that needs an MCP server still needs setup
instructions — that content doesn't disappear. But `hermes` is LifeOS's
own CLI; the commands have to be re-derived per harness (or left as a
documented external prerequisite) rather than copied verbatim, since
`ARCHITECTURE.md` requires agent content to stay harness-neutral.

`ConceptMap.md`'s own worked example is titled "Worked Example — LifeOS
Algorithm Subsystems" and walks through the Algorithm's own Claims
Loop, ISC Quality System, and ISA as the example concept map. The
*method* (Novak-style concept mapping) ports cleanly; this particular
worked example does not — it needs a domain-neutral replacement, which
is an editorial call per file, not something a strip rule catches.

### Frontmatter fields

`catalog.py`'s `read_agent` reads exactly four frontmatter keys:
`name`, `description`, `skills`, `workflows` (everything else in the
block is parsed and silently ignored — `parse_frontmatter` keeps
unknown keys in the dict but nothing downstream reads them). Across the
57 LifeOS `SKILL.md` files, frontmatter keys break down as:

| Field | Count | Survives the port? |
|---|---|---|
| `name` | 58 | Yes — same key, same meaning |
| `description` | 57 | Yes — keep the `USE WHEN ... NOT FOR ...` convention inside it |
| `version` | 56 | No equivalent field; the version number is worth one line in the source-credit note (§5), not frontmatter |
| `background` | 7 | No — Claude Code loader hint (`context: fork`, `background: false`), meaningless outside it |
| `context` | 7 | No — same as above |
| `disable-model-invocation` | 5 | No — Claude Code loader hint |
| `disallowed-tools` | 1 | No — Claude Code tool-permission hint |
| `allowed-tools` | 1 | No — same |
| `argument-hint` | 1 | No — Claude Code slash-command hint |
| `license` | 1 | No — not read by `catalog.py`; drop unless the content genuinely needs a license note in the body |
| `skills:` / `workflows:` | 0 in LifeOS | New — LifeOS has neither; write these fresh, listing what actually ended up under `Skills/` and `Workflows/` per §1 |

Net effect: an `AGENT.md` frontmatter block ported from LifeOS keeps
`name` and `description` nearly as-is and drops everything else,
replacing it with the `skills:`/`workflows:` lists this catalog
actually uses.

### TypeScript

None of the four skills read in depth for this guide (`ExtractWisdom`,
`BiasCheck`, `RootCauseAnalysis`, `SystemsThinking`) ships a `Tools/`
directory, but plenty of others do —
`ThreatModel/Tools/RiskRegister.ts`, for one. Its header:

```typescript
#!/usr/bin/env bun
/**
 * RiskRegister.ts — deterministic risk register CLI for the ThreatModel skill.
 *
 * Code is public; data is private. The register lives OUTSIDE the skill tree:
 *   default  ~/.claude/LIFEOS/USER/SECURITY/THREATMODEL/
 *   override THREATMODEL_DATA_DIR
 */
```

This is why "rewrite, do not transliterate" is the instruction rather
than "convert." The `bun` shebang, the `node:fs`/`node:os` imports, and
the hardcoded `~/.claude/LIFEOS/USER/...` default data path are all
LifeOS-runtime assumptions baked into the tool, not incidental syntax.
A faithful Python port needs a new default data location appropriate to
this catalog's tiers, not a line-by-line TypeScript-to-Python
translation of a path that no longer makes sense.

## 3. What gets kept

### The `USE WHEN ... NOT FOR ...` description convention

This is LifeOS's convention, already adopted here. Compare
`agents/stock-screening/AGENT.md`:

```
description: Identify candidate securities matching a set of screening
criteria. USE WHEN screening stocks, building a watchlist, or
shortlisting trade candidates for a horizon. NOT FOR order execution,
position sizing, portfolio accounting, or investment advice.
```

against `RootCauseAnalysis/SKILL.md`:

```
description: "Structured incident investigation using Five Whys,
Fishbone, blameless Postmortem, Fault Tree, Kepner-Tregoe, and FMEA —
traces failures to systemic root causes rather than blaming humans.
USE WHEN root cause, RCA, 5 whys, fishbone, postmortem, incident
analysis, fault tree, why does this keep failing, blameless, recurring
bug. NOT FOR systemic loops (use SystemsThinking)."
```

Keep this shape verbatim on every port: what it does, `USE WHEN`
followed by trigger phrases, `NOT FOR` followed by the adjacent agent
it isn't. The `NOT FOR` clause is what keeps two similar agents
(`RootCauseAnalysis` vs. `SystemsThinking`) from both claiming the same
request.

### Boundaries and Gotchas

These sections carry the operational knowledge that took real incidents
to learn — they are the most valuable content in a LifeOS skill and
should port close to verbatim. From `RootCauseAnalysis/SKILL.md`:

```
## Gotchas

- **"Human error" is a starting point, not a root cause.** It's where
  the investigation begins. Every human error sits on top of a system
  that made the error possible or probable.
- **Going too deep ≠ good RCA.** "The fundamental cause is the second
  law of thermodynamics" is not actionable. Stop at the deepest
  actionable level.
```

From `BiasCheck/SKILL.md`:

```
## Gotchas

- **Always try to find the primary source.** The single biggest failure
  mode is analyzing an article without ever reaching the underlying
  study.
- **Don't conflate Layer 1 and Layer 3.** A bad headline doesn't make
  the underlying data bad. A flawed study doesn't make the journalism
  dishonest. Keep them separate even when both have problems.
```

Neither of these needs editing to be true here. `agents/stock-screening/
AGENT.md` already has the ai-agents-side equivalent under `## Boundaries`
— keep that heading name for anything sourced this way, since it's
this repo's established name for the section (LifeOS itself uses
`Gotchas` for the same kind of content; either heading is fine, but
don't drop the section).

### The routing table

LifeOS's `## Workflow Routing` table (Workflow / Trigger / File) is
exactly the shape `AGENT.md`'s `## Routing` table already uses (Kind /
Name / Trigger / File — see `agents/stock-screening/AGENT.md`). Port it
directly, adding only the Skill/Workflow `Kind` column decided in §1.

## 4. Verification checklist

Run in order. Every command should be run from the `ai-agents` repo
root.

1. **Frontmatter and files agree.** `catalog.py` reads the repo tree
   directly (this is what `tests/test_catalog.py` does too, not
   `ai-agents list`, which reads `~/.ai-agents` and won't see a newly
   ported agent until re-initialized):
   ```bash
   python -c "
   from pathlib import Path
   from ai_agents import catalog
   agent = {a['name']: a for a in catalog.list_agents(Path('.'))}['<Name>']
   print(agent)
   print('dangling refs:', catalog.find_dangling_skill_refs(agent))
   "
   ```
   `skills` and `workflows` in the output should match what's on disk;
   `find_dangling_skill_refs` should return `[]`.

2. **Nothing LifeOS-specific survived.** Each of these must return
   nothing:
   ```bash
   grep -rn "31337" agents/<Name>/
   grep -rn "LIFEOS/USER" agents/<Name>/
   grep -rniE "Pulse|Cortex|TELOS|Algorithm" agents/<Name>/
   grep -rn "\.ts\b" agents/<Name>/
   find agents/<Name>/ -name "*.ts"
   ```
   A hit on the `Algorithm` grep is not automatically wrong — check
   whether it's a load-bearing case like `Check.md`'s sufficiency gate
   (§2) before deleting the surrounding content, but the citation
   itself should still be gone.

3. **Every `Workflows/*.md` file is actually cumulative.** For each
   file under `agents/<Name>/Workflows/`, confirm it explicitly wraps
   or sequences at least one Skill and owns a gate — if it doesn't,
   move it to `Skills/` instead. This is the check that catches the
   `SystemsThinking` trap from §1: a file that only says "consider
   running X next" belongs in `Skills/`.

4. **Tests still pass.**
   ```bash
   pytest -q
   ```

5. **`ai-agents list` picks it up**, after refreshing the user tier
   (`init` refuses to overwrite an existing `~/.ai-agents`, so a repo
   check that already ran `init` won't see new agents without this):
   ```bash
   rm -rf ~/.ai-agents   # only if it's safe to discard on this machine
   pip install -e .
   ai-agents init
   ai-agents list
   ```
   The new agent should appear with its skills and workflows listed.

## 5. Source-crediting convention

Every ported agent credits its LifeOS source, one italic line right
after the `AGENT.md` title, before the persona paragraph — in the body,
not the frontmatter, so it never interferes with what `catalog.py`
parses:

```markdown
# RootCauseAnalysis

*Ported from LifeOS `skills/RootCauseAnalysis/` (v1.0.7).*

Investigates why something failed — past the proximate cause, down to
the contributing factors and latent conditions that actually made the
failure possible.
```

The version number is the LifeOS `SKILL.md`'s own `version:`
frontmatter field at the time of the port — it has no home in the
ported frontmatter (§2), so it lives here instead, giving anyone who
reads the agent later something to diff against if LifeOS's original
gets updated. Same line, same place, same format on every port —
`grep -rn "Ported from LifeOS" agents/*/AGENT.md` should return exactly
one hit per ported agent.
