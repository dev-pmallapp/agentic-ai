---
name: ExtractWisdom
description: "Content-adaptive wisdom extraction that reads content first, detects which wisdom domains are present, and builds custom sections around them, with five depth levels and mandatory contrarian takes; pulls YouTube via fabric and fetches article pages directly. USE WHEN extract wisdom, analyze video, analyze podcast, extract insights, key takeaways, summarize interview, distill content. NOT FOR static Fabric extract_wisdom pattern (use Fabric)."
skills:
  - Extract
---

# ExtractWisdom

*Ported from LifeOS `skills/ExtractWisdom/` (v1.1.16).*

Pulls the best ideas out of videos, podcasts, interviews, and articles.
It reads the content first, detects what kinds of wisdom are actually
in there, then builds custom sections around what it finds instead of
forcing the same headers every time. Five depth levels from Instant to
Comprehensive. Output always ends with a one-sentence takeaway, an "If
You Only Have 2 Minutes" list, and references worth following.

## The Problem

Static extraction templates force every piece of content into the same
boxes — IDEAS, QUOTES, HABITS, FACTS — so a security talk and a
business podcast come out looking identical and the real gems get
flattened into generic bullets. The output reads like a book report,
not like a smart friend telling you the parts that made them stop.
This skill adapts its sections to the content and writes the points
the way you'd actually say them out loud, so the contrarian takes and
first-time revelations survive instead of getting watered down.

## How It Works

Instead of static sections (IDEAS, QUOTES, HABITS...), this skill
detects what wisdom domains actually exist in the content and builds
custom sections around them.

A programming interview gets "Programming Philosophy" and "Developer
Workflow Tips." A business podcast gets "Contrarian Business Takes" and
"Money Philosophy." A security talk gets "Threat Model Insights" and
"Defense Strategies." The sections adapt because the content dictates
them.

Two things never adapt: every bullet is written in a spoken,
conversational voice, and a genuinely contrarian take always survives
undiluted. Both are enforced by `Skills/Extract.md`.

## Depth Levels

Five levels, differing only in how much structure the output gets.
Default is **Full** when no level is named.

| Level | When |
|-------|------|
| **Instant** | Quick hit. One killer section. |
| **Fast** | Skim in 30 seconds. |
| **Basic** | Solid overview without the deep cuts. |
| **Full** | The default. Complete extraction. |
| **Comprehensive** | Maximum depth. Nothing left behind. |

**How to invoke:** "extract wisdom (fast)" or "extract wisdom at
comprehensive level" or just "extract wisdom" for Full.

**All levels use the same voice, tone rules, and quality standards.**
The only thing that changes is structure. An Instant extraction should
hit just as hard per-bullet as a Comprehensive one.

What each level actually produces — section counts, bullets per
section, and which closing sections appear — is the depth-structure
table in `Skills/Extract.md`. This one is for choosing; that one is for
building.

## Routing

| Kind | Name | Trigger | File |
|---|---|---|---|
| Skill | **Extract** | "extract wisdom from", "analyze this", YouTube URL | `Skills/Extract.md` |

**Extract** is a Skill, not a Workflow: it runs end to end on its own —
fetch, detect domains, produce the depth-appropriate output — with
nothing else needing to have run first. `Workflows/` is empty by
design; nothing in this agent sequences another procedure or owns an
approval gate.

It is also self-contained in the stronger sense the anatomy asks for:
the method lives in the Skill, so `Skills/Extract.md` can be invoked
with nothing else loaded and still produce a correct extraction. This
file is persona and routing.

## Boundaries

- **Content-adaptive sections means output structure varies by input
  type.** Don't expect identical output format for a podcast vs an
  article.
- **YouTube extraction should use `fabric -y URL` first** to get the
  transcript before extracting wisdom. `fabric` is Daniel Miessler's
  open-source AI-augmentation CLI, an external prerequisite for this
  skill, not part of this catalog.
- **Long content may need chunking.** Don't try to extract wisdom from
  a 3-hour podcast transcript in one pass.

## Examples

**Example 1: YouTube interview extraction**
```
User: "extract wisdom from this Marcus Hutchins interview"
→ Uses `fabric -y URL` to get transcript
→ Content-adaptive extraction (interview format)
→ Returns: key insights, surprising claims, actionable takeaways
→ ~45 seconds
```

**Example 2: Article extraction**
```
User: "extract the key insights from this blog post"
→ Fetches the page content directly
→ Adapts sections to article format
→ Returns distilled wisdom with source attribution
```
