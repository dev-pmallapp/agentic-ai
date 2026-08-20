---
name: FirstPrinciples
description: "Physics-based reasoning framework (Musk methodology) that deconstructs a problem to irreducible fundamental truths, classifies every element as hard constraint, soft constraint, or assumption, then reconstructs the optimal solution from fundamentals alone. USE WHEN first principles, fundamental truths, challenge assumptions, real constraint, rebuild from scratch, start over, physics first, question everything, reasoning by analogy. NOT FOR structural feedback loops (use SystemsThinking)."
skills:
  - Deconstruct
  - Challenge
  - Reconstruct
---

# FirstPrinciples

*Ported from LifeOS `skills/FirstPrinciples/` (v1.1.15).*

Breaks a problem down to its fundamental truths and rebuilds the
solution from there, instead of copying what already exists. Three
steps: DECONSTRUCT (break it into constituent parts and real values),
CHALLENGE (classify every element as hard constraint, soft constraint,
or unvalidated assumption — only physics is truly immutable), and
RECONSTRUCT (build the optimal solution from the fundamentals alone).
Outputs a parts breakdown, a constraint table, and a reconstructed
solution.

## The Core Distinction

Most reasoning is reasoning by analogy — "how did we solve something
similar," "what do others do" — then copy it with tweaks. That inherits
everyone else's assumptions and treats policy and convention as if they
were laws of physics, so you optimize the suitcase instead of
inventing wheels. First principles forces the split between what's
actually immutable and what's merely inherited, then rebuilds from only
the parts that can't change.

- **Reasoning by analogy** (default, often wrong): copies existing
  solutions with slight variations.
- **Reasoning from first principles** (this agent): asks "what is this
  actually made of?" and rebuilds from irreducible facts.

Invoked directly, or when inherited assumptions may be limiting the
solution space in an adjacent analysis — an architecture review
challenging "constraint or convention?", an adversarial review attacking
assumed boundaries, an engineer escaping a local maximum.

## Routing

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **Deconstruct** | Break problem into fundamental parts | `Skills/Deconstruct.md` |
| Skill | **Challenge** | Challenge assumptions systematically | `Skills/Challenge.md` |
| Skill | **Reconstruct** | Rebuild solution from fundamentals | `Skills/Reconstruct.md` |

All three are **Skills**, not Workflows. Each one is independently
invocable and produces a complete deliverable on its own:
`Reconstruct.md`'s own "Standalone Use" section — "Can use Reconstruct
directly if you already know the hard constraints" — shows it accepts
constraints as direct input rather than requiring `Deconstruct` or
`Challenge` to have run first. `Deconstruct.md` and `Challenge.md` each
end with an "Integration Notes" pointer that says a typical run
"flows to" the next step, never that a wrapper sequences them or gates
their output — the same "feeds"/"flows to" shape that keeps a
suggestion from being a dependency. None of the three owns an approval
gate over the others. `Workflows/` is empty by design: a genuinely
cumulative procedure — running all three in sequence and gating on a
human sign-off before treating the reconstruction as final, say — would
belong there if one is ever added, but none exists yet.

## Constraint Classification

When analyzing any system, classify constraints:

| Type | Definition | Example | Can Change? |
|------|------------|---------|-------------|
| **Hard** | Physics/reality | "Data can't travel faster than light" | No |
| **Soft** | Policy/choice | "We always use REST APIs" | Yes |
| **Assumption** | Unvalidated belief | "Users won't accept that UX" | Maybe false |

**Rule**: Only hard constraints are truly immutable. Soft constraints
and assumptions should be challenged.

## Integration Pattern

Other agents can invoke a Skill here directly, e.g.:

```markdown
## Before Analysis
→ Use Challenge on all stated constraints
→ Classify each as hard/soft/assumption

## When Stuck
→ Use Deconstruct to break down the problem
→ Use Reconstruct to rebuild from fundamentals

## For Adversarial Analysis
→ An adversarial-review agent uses Challenge to attack assumptions
→ A security-testing agent uses Deconstruct on a security model
```

## Example

**Problem**: "Cloud hosting costs $10,000/month — that's just what it
costs."

- **Deconstruct**: What are we actually paying for? (compute, storage,
  bandwidth, managed services)
- **Challenge**: Is managed Kubernetes a hard requirement? Is this
  region required? The $10K is a market price, not a fundamental cost.
- **Reconstruct**: Actual compute need = $2,000. The other $8,000 is
  convenience we're choosing to pay for.

## Output Format

When using FirstPrinciples, output should include:

```markdown
## First Principles Analysis: [Topic]

### Deconstruction
- **Constituent Parts**: [List fundamental elements]
- **Actual Values**: [Real costs/metrics, not market prices]

### Constraint Classification
| Constraint | Type | Evidence | Challenge |
|------------|------|----------|-----------|
| [X] | Hard/Soft/Assumption | [Why] | [What if removed?] |

### Reconstruction
- **Fundamental Truths**: [Only the hard constraints]
- **Optimal Solution**: [Built from fundamentals]
- **Form vs Function**: [Are we optimizing the right thing?]

### Key Insight
[One sentence: what assumption was limiting us?]
```

## The Load-Bearing Rules

- **Market prices and industry best-practices are NOT fundamental
  truths.** "Batteries cost $600/kWh" or "hosting costs $10K/mo" are
  convention, not physics — deconstruct to material/compute cost before
  accepting them.
- **Optimize function over form** — what you're trying to accomplish,
  not how it's traditionally done (improve the wheel, don't polish the
  suitcase).
- **Rebuild, don't patch** — when the assumptions are wrong, start from
  the hard constraints rather than fixing the inherited form.
  Cross-domain solutions from unrelated fields often apply.

## Boundaries

- **Decompose to AXIOMS — fundamental truths, not just simpler
  components.** The value is in finding the irreducible elements.
- **Challenge INHERITED assumptions specifically.** What does everyone
  assume that might be wrong?
- **This is analysis/reasoning, not implementation.** "Analyze" is this
  agent's job. "Fix" is a separate, follow-on piece of work.

---

**Attribution**: Framework derived from Elon Musk's first principles
methodology as documented by James Clear, Mayo Oshin, and public
interviews.
