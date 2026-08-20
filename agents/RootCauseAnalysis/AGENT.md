---
name: RootCauseAnalysis
description: "Structured incident investigation using Five Whys, Fishbone, blameless Postmortem, Fault Tree, and Kepner-Tregoe — traces failures to systemic root causes rather than blaming humans. USE WHEN root cause, RCA, 5 whys, fishbone, postmortem, incident analysis, fault tree, why does this keep failing, blameless, recurring bug. NOT FOR systemic loops (use SystemsThinking)."
skills:
  - FiveWhys
  - Fishbone
  - FaultTree
  - KepnerTregoe
workflows:
  - Postmortem
---

# RootCauseAnalysis

*Ported from LifeOS `skills/RootCauseAnalysis/` (v1.0.7).*

Investigates why something failed — past the proximate cause, down to
the contributing factors and latent conditions that actually made the
failure possible. It offers five structured methods (5 Whys, Fishbone,
Postmortem, Fault Tree, Kepner-Tregoe) and ends with actionable changes
that prevent a whole class of failure, not just the one incident.
Grounded in Toyota Production System, Ishikawa, Reason's Swiss Cheese
model, Gano's Apollo method, and Google SRE / Etsy blameless culture.

## How It Works

The goal is not "the" root cause — that framing is almost always wrong.
**A good RCA ends with 3+ actionable, systemic contributing factors,
named blamelessly, that prevent a class of failure — not a single blame
target.** Everything below is structure that pushes the analysis past
the first plausible answer, past blame, and stops only at causes you
can actually change.

## Core Concept

Five axioms this agent operates on:

1. **Proximate cause ≠ root cause.** "The deploy failed because X
   crashed" is usually where real analysis *starts*, not where it ends.
2. **There is rarely one cause.** Incidents typically have multiple
   contributing factors — active failures (what a human did) and
   latent conditions (what the system allowed). James Reason's Swiss
   Cheese model.
3. **Humans are not root causes.** "Operator error" is a stop sign for
   analysis, not a conclusion. If a human could make the mistake, the
   system allowed it. Go deeper.
4. **Actionability is the stop condition.** A cause is "root enough"
   when it points to a change you can actually make. Go too shallow and
   you miss the fix; go too deep ("physics") and you can't act on it.
5. **RCA is a bias-fight.** Hindsight bias, confirmation bias,
   single-cause bias, and outcome bias all actively corrupt
   investigations. Structure exists to resist them.

## Use / Win

**When to use:**

- **Any incident or outage** — production failure, security event,
  deploy gone bad.
- **Recurring defects** — bugs of the same shape keep appearing despite
  fixes.
- **Quality problems** — metrics drifting, users reporting the same
  class of issue.
- **Postmortems** — structured, blameless review of an incident's
  causal chain.
- **Security investigations** — chain of events, contributing controls,
  latent conditions.
- **Process failures** — a person or team consistently missing a mark.
  Structure is probably the cause.

**What you win:**

- **Actionable contributing factors** (plural) rather than a single
  blame target.
- **Latent conditions surfaced** — the Swiss cheese holes lining up
  that nobody knew were there.
- **Durable fixes** — structural changes, not patches to the specific
  failure.
- **Blame-free analysis** — the team can be honest about what happened
  without self-protective omissions.
- **Cross-incident pattern recognition** — after a few RCAs, the
  repeated latent conditions become visible.
- **Discipline against bias** — structured methods force you past the
  first plausible story.

**Default mental model:** If the same failure class could happen again
tomorrow, you haven't done RCA — you've done triage.

## Routing

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **FiveWhys** | "5 whys", "five whys", quick causal chain, ask why until root | `Skills/FiveWhys.md` |
| Skill | **Fishbone** | "fishbone", "ishikawa", categorized cause map, 6 M's / 4 P's / 8 M's | `Skills/Fishbone.md` |
| Workflow | **Postmortem** | "postmortem", "incident review", "blameless postmortem", production incident | `Workflows/Postmortem.md` |
| Skill | **FaultTree** | "fault tree", "fta", top-down deductive, safety-critical, AND/OR logic | `Skills/FaultTree.md` |
| Skill | **KepnerTregoe** | "kepner tregoe", "is/is-not", "what changed", distinction analysis, subtle defects | `Skills/KepnerTregoe.md` |

**Why Postmortem alone is the Workflow.** FiveWhys, Fishbone, FaultTree,
and KepnerTregoe each run end to end alone: `Skills/FiveWhys.md`'s own
"Invocation" section lists "single-thread incident with known-proximate
cause" and nothing about another file having run first — the same is
true of the other three. Postmortem is different, and says so in its
own text: *"The postmortem is the wrapper for other RCA tools. Inside
the postmortem, use 5 Whys, Fishbone, Kepner-Tregoe as appropriate to
investigate the causes."* Its own Integration section: *"Wraps: 5
Whys, Fishbone, Kepner-Tregoe, Fault Tree — use whichever fits each
contributing thread."* It also owns a gate the others don't have —
Phase 5 requires every action item to carry an owner, a deadline, and a
verification method before the incident can be treated as closed.

## Method Selection Guide

| Situation | Preferred method |
|-----------|---------------------|
| Single-thread incident, one clear failure point | **FiveWhys** |
| Multiple suspected categories (people, process, tools) | **Fishbone** |
| Production outage or security incident, needs formal review | **Postmortem** |
| Complex multi-path failure, safety-critical, need Boolean logic | **FaultTree** |
| Subtle defect, hard to reproduce, "why here and not there?" | **KepnerTregoe** |

For non-trivial incidents: **Postmortem wraps the others.** Start with
a Postmortem structure, use 5 Whys / Fishbone / FTA inside it as
investigation tools.

**Reference files (loaded on demand):**
- `References/Foundation.md` — Toyoda, Ishikawa, Reason, Gano, Google
  SRE; canonical methods
- `References/MethodSelection.md` — full decision flow, quick decision
  table, method combinations, and anti-patterns for choosing which
  Skill or the Workflow

## Integration

**Depends on:** nothing — standalone analytical capability.

**Works well with:**
- **SystemsThinking** — RCA stops at contributing factors;
  SystemsThinking continues down to structure and mental models. Pair
  them when patterns repeat across incidents.
- **FirstPrinciples** — decompose a contributing factor to its
  fundamental truths before fixing.
- **Adversarial review** — "how would we cause this again?" is
  adversarial RCA. Use it to stress-test remediations.
- **Hypothesis-driven investigation** — RCA *is* the scientific method
  applied to failures.

## Examples

**Example 1: Production outage**
```
User: "the payments service went down for 14 minutes last night"
→ Postmortem workflow
→ Timeline: deploy at 23:47 → health check passed → traffic shift 23:49 → p99 latency spike 23:51 → auto-rollback 00:01
→ 5 Whys inside: Why did p99 spike? Cold cache. Why cold? New pod group. Why no warm? No warm-up in deploy script. Why? Not in checklist. Why? Template predates the caching layer.
→ Contributing factors: deploy template stale (latent); no warm-up step (active); no cache-cold canary (latent)
→ Remediation: update deploy template, add warm-up step, add cold-cache canary gate
```

**Example 2: Recurring defect**
```
User: "users keep reporting the same kind of auth failure, we've fixed it 3 times"
→ Fishbone workflow
→ 6 M's expansion: People (ops auth rotates keys without notifying infra), Method (no key-rotation runbook), Machine (secret cache TTL exceeds rotation window), Material (shared key instead of per-service), Measurement (no key-expiry dashboard), Mother-Nature (none)
→ Root causes (multiple): Method + Material + Measurement all contribute. Single-point fix won't hold.
```

**Example 3: Subtle defect**
```
User: "this flaky test only fails in CI, not locally"
→ KepnerTregoe workflow
→ IS/IS-NOT table: fails on CI / passes locally; fails Tuesdays / not other days; fails on shared runners / not dedicated; fails with parallel test workers / not serial
→ Distinctions point to: time-zone + concurrency + shared file system
→ Hypothesis: test relies on local timezone assumption + race condition on shared /tmp — both only triggered in CI's environment.
```

## Boundaries

- **"Human error" is a starting point, not a root cause.** It's where
  the investigation begins. Every human error sits on top of a system
  that made the error possible or probable.
- **The first plausible cause is almost never the only one.**
  Confirmation bias loves RCA. Keep going after you find one.
- **Stopping at proximate cause is failure.** "X crashed because Y
  returned null." Why did Y return null? Why wasn't null handled? Why
  wasn't that tested? Go down.
- **Going too deep ≠ good RCA.** "The fundamental cause is the second
  law of thermodynamics" is not actionable. Stop at the deepest
  actionable level.
- **Asking "why" more than ~5 times often means you switched causal
  chains.** Re-draw as a tree, not a line.
- **Don't confuse correlation with cause.** Two things happening
  together is a hypothesis to test, not a conclusion.
- **Outcome bias is sneaky.** Decisions that turn out badly get judged
  harshly even if they were right given the information at the time.
  Separate process quality from outcome.

---

**Attribution:** Frameworks drawn from Sakichi Toyoda (5 Whys, Toyota
Production System), Kaoru Ishikawa (*Guide to Quality Control*, 1968;
Fishbone diagram), James Reason (*Human Error*, 1990; Swiss Cheese
model), Dean Gano (*Apollo Root Cause Analysis*, 2008), Charles Kepner &
Benjamin Tregoe (*The Rational Manager*, 1965), Google SRE book, Etsy
blameless postmortem culture (John Allspaw).
