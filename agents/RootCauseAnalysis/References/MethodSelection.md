# RootCauseAnalysis — Method Selection Guide

When to use which method. Using FiveWhys on a safety-critical problem
or FaultTree on a simple defect both produce bad outcomes.

## Decision Flow

```
Is this an incident or a defect?
│
├─ Incident (production outage, security event, data loss)
│    │
│    └─ Use Postmortem as wrapper
│         ├─ Single thread, clear mechanism → FiveWhys inside
│         ├─ Multiple suspected categories → Fishbone inside
│         ├─ "Works here not there" subtle → KepnerTregoe inside
│         └─ Safety/security-critical → FaultTree inside
│
└─ Defect (recurring bug, quality drift, process failure)
     │
     ├─ Simple, single-thread → FiveWhys
     ├─ Multi-category or brainstorm needed → Fishbone + Pareto
     ├─ Deviation from known-good → KepnerTregoe IS/IS-NOT
     ├─ Novel, never-happened-before → Apollo/RealityCharting (see Foundation.md)
     └─ Complex interacting failures → FaultTree
```

## Quick Decision Table

| Criterion | FiveWhys | Fishbone | FaultTree | Apollo | KepnerTregoe |
|-----------|--------|----------|-----|--------|-----|
| Problem complexity | Simple-moderate | Moderate-complex | Complex-very complex | Moderate-complex | Moderate |
| Causal structure | Linear (single chain) | Multi-category, parallel | Branching, probabilistic | Branching, evidence-based | IS/IS-NOT deviation |
| Team involvement | Solo or small team | Group brainstorm | Engineers + analysts | Formal panel | Solo or small team |
| Time available | Minutes-hours | Hours | Days-weeks | Hours-days | Hours |
| Safety-critical | No | No | Yes | Yes | No |
| Quantitative probability needed | No | No | Yes | No | No |
| Good for novel failures | Moderate | Yes | Yes | Yes | Moderate |
| Defensible for regulatory | No | Partial | Yes | Yes | Partial |
| Outputs | Causal chain + fix | Category map + Pareto | Cut sets + probabilities | Causal graph + evidence | Distinction + change |

*Apollo/RealityCharting is discussed as related theory (see
`Foundation.md` §5) — this agent does not carry a dedicated Apollo
Skill file.*

## Combining Methods

RCA methods nest and combine — they are not mutually exclusive.

### The standard software-ops combination

**Postmortem** (wrapper) → **FiveWhys** (per thread) → **Swiss Cheese**
(defensive layers review, see `Foundation.md` §8) → **Action item
strength ranking**

### The quality-investigation combination

**Fishbone** (breadth) → **Pareto** (prioritize vital few, see
`Foundation.md` §3) → **FiveWhys** (depth on top causes) →
**Verification**

### The subtle-defect combination

**KepnerTregoe** (IS/IS-NOT identifies the change) → **FiveWhys** (go
deeper into *why* the change wasn't caught) → **Corrective action**

### The safety-critical combination

**FaultTree** (top-down deductive map) → **FMEA** (failure modes
ranked by RPN/AP, see `Foundation.md` §6) → **Postmortem** (if
incident occurred) → **Action items at multiple layers**

## Anti-Patterns

**Using FiveWhys when Fishbone is right.**
- Signal: you keep getting stuck because the answer to "why?" has three valid parallel answers
- Switch to Fishbone so you can explore all branches

**Using Fishbone when FiveWhys is right.**
- Signal: you already know the category; you need depth, not breadth
- Use FiveWhys directly

**Using FaultTree when you have no probability data.**
- Signal: the quantitative benefit is lost; you're just drawing a tree
- Use Fishbone + FiveWhys instead

**Using KepnerTregoe when there's no baseline.**
- Signal: no "worked before" state exists; nothing to deviate from
- Use Apollo or Fishbone

**Skipping the Postmortem wrapper for "small" incidents.**
- Signal: you're making exceptions for "it wasn't a big one"
- Run the postmortem anyway — the discipline compounds; the exception never recovers the learning

## Method-to-Domain Map

| Domain | Primary method | Secondary |
|--------|----------------|-----------|
| Production software outage | Postmortem + FiveWhys | Swiss Cheese, Fishbone |
| Distributed systems failure | Postmortem + Apollo | FaultTree |
| Security incident | Postmortem + Swiss Cheese | KepnerTregoe for subtle defects |
| Manufacturing defect | Fishbone + Pareto | FiveWhys |
| Intermittent / environment-specific | KepnerTregoe | FiveWhys |
| Safety-critical engineering | FaultTree | FMEA, Apollo |
| Pre-launch risk analysis | FMEA (proactive) | FaultTree |
| Process/org failure | Fishbone (4 P's) | FiveWhys |
| Regulatory investigation | Apollo / RealityCharting | FaultTree |

## Speed vs. Thoroughness Tradeoff

| Situation | Method |
|-----------|--------|
| Time pressure — 10 minutes | Quick FiveWhys |
| 1 hour | FiveWhys + Fishbone |
| Half day | Postmortem + multiple methods |
| Days | Postmortem + FaultTree + FMEA |
| Regulatory deadline | Apollo with full evidence |

## Integration With Other Agents

- **SystemsThinking** — When multiple postmortems reveal the same
  structural cause, escalate to structure-level analysis. RCA stops at
  contributing factors; SystemsThinking continues to structure and
  mental models.
- **FirstPrinciples** — Decompose a contributing factor to its
  fundamental truths before designing a fix.
- **Adversarial review** — "How would we cause this again?" is
  adversarial RCA. Stress-test remediations.
- **Hypothesis-driven investigation** — RCA *is* the scientific method
  applied to failures. Use it for hypothesis generation during
  investigation.
