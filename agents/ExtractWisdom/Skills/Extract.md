---
name: Extract
agent: ExtractWisdom
---

# Extract

Extract dynamic, content-adaptive wisdom from any content source.

Self-contained: everything needed to produce a correct extraction —
depth structure, voice, section rules, output format, and the quality
gate — is here. `AGENT.md` carries the persona, when to reach for each
depth level, and the agent's boundaries.

## Input Sources

| Source | Method |
|--------|--------|
| YouTube URL | `fabric -y "URL"` to get transcript |
| Article URL | Fetch the page content |
| File path | Read the file directly |
| Pasted text | Use directly |

For long content, save the transcript to a working file and chunk it —
don't extract from a 3-hour transcript in one pass.

## Depth Structure

Default is **Full** when no level is given. `AGENT.md` § Depth Levels
says which level to pick; this table says what each one produces.

| Level | Sections | Bullets/Section | Closing Sections |
|-------|----------|----------------|-----------------|
| **Instant** | 1 | 8 | None |
| **Fast** | 3 | 3 | None |
| **Basic** | 3 | 5 | One-Sentence Takeaway only |
| **Full** | 5-12 | 3-15 | All three |
| **Comprehensive** | 10-15 | 8-15 | All three + Themes & Connections |

**Comprehensive extras:**
- **Themes & Connections** closing section: identify 3-5 throughlines
  that connect multiple sections. Not summaries — the deeper patterns
  the speaker may not even realize they're revealing.
- Prioritize breadth. Every significant wisdom domain gets its own
  section.
- No merging sections to save space. If the content supports 15
  sections, use 15.

**All levels use the same voice, tone rules, and quality standards.**
The only thing that changes is structure. An Instant extraction should
hit just as hard per-bullet as a Comprehensive one.

## Tone Rules (CRITICAL)

The bullets should sound like the user telling a friend about it over
coffee. Not compressed info nuggets. Not clever one-liners. Actual
spoken observations.

**THREE LEVELS — we're aiming for Level 3:**

**Level 1 (BAD — documentation):**
- The speaker discussed the importance of self-modifying software in
  the context of agentic AI development
- It was noted that financial success has diminishing returns beyond a
  certain threshold
- The distinction between "vibe coding" and "agentic engineering" was
  emphasized as meaningful

**Level 2 (BETTER — but still "smart bullet points"):**
- He built self-modifying software basically by accident — just made
  the agent aware of its own source code
- Money has diminishing returns. A cheeseburger is a cheeseburger no
  matter how rich you are.
- "Vibe coding is a slur" — he calls it agentic engineering, and only
  does vibe coding after 3am

**Level 3 (YES — this is what we want — conversational, spoken voice):**
- He wasn't trying to build self-modifying software. He just let the
  agent see its own source code and it started fixing itself.
- Past a certain point, money stops mattering. A cheeseburger is a
  cheeseburger no matter how rich you are.
- He calls vibe coding a slur. What he does is agentic engineering. The
  vibe coding only happens after 3am, and he regrets it in the morning.

**The difference between Level 2 and 3:** Level 2 is compressed info
with em-dashes. Level 3 is how you'd actually SAY it. Varied sentence
lengths. Letting a thought breathe. Not trying to be clever — just
being clear and direct and a little bit personal.

**Key signals of Level 3:**
- Reads naturally when spoken aloud
- Varied sentence lengths — some short, some longer
- Understated — lets the content carry the weight
- Uses periods, not em-dashes, to let ideas land
- Feels opinionated ("Past a certain point, money stops mattering") not
  just informational
- The reader should think "I want to watch this" not "I got the
  summary"

## Bullets — the voice contract

The one-line target: sections specific to the content, bullets that
sound spoken, not summarized. The THREE LEVELS above are the standard —
every bullet lands at Level 3. A good bullet exhibits these properties:

- **Spoken, not summarized.** Reads like you telling a friend what you
  just watched, not a press release or a compressed tweet.
- **Specific over vague.** Carries the actual detail, quote, or number
  — "a cheeseburger is a cheeseburger no matter how rich you are," not
  "he talked about money." Use the speaker's own words when they're
  already perfect.
- **Insight over inventory.** "He picked a language he doesn't even
  like because the ecosystem fits agents" beats "he uses Go for CLIs."
  A contradiction or reversal is the wisdom.
- **8-16 words, varied length.** Mix short and medium; periods between
  thoughts, not em-dashes. Verbatim quotes are exempt.
- **Human moments count.** Burnout, doubt, something that moved the
  speaker — that's wisdom too, even when it isn't "technical."

**Contrarian takes are mandatory.** If the speaker has a genuinely hot
take ("screw MCPs", "X is dead", "Y is overhyped"), it MUST appear,
undiluted. Spicy takes are the most memorable and shareable material —
losing one is a failed extraction, including between drafts.

## Sections — adapt to the content

Sections are named for THIS content, not from a fixed list. A
programming interview gets "Programming Philosophy"; a business podcast
gets "Money Philosophy"; a security talk gets "Threat Model Insights."
Name them like a magazine editor — "The Death of 80% of Apps," not
"Technology Predictions." The name should make the reader curious.

- Section count follows the depth-structure table above.
- Every section needs at least 3 strong bullets (except Fast, where 3
  tight bullets IS the section). Can't find 3? Merge it into a related
  section.
- Include "Quotes That Hit Different" when the content has quotable
  moments; include "First-Time Revelations" when there are genuinely
  new ideas.
- No inventory sections — a bare list of facts isn't wisdom. Go deeper
  on why the choices matter, or merge into a philosophy section.
- Don't split what belongs together. Don't drop your best material
  between drafts — a spicy take or stunning moment found in an early
  pass MUST survive to the final.

## Closing Sections

Which closing sections appear depends on depth level:

| Level | Closing Sections |
|-------|-----------------|
| **Instant** | None |
| **Fast** | None |
| **Basic** | One-Sentence Takeaway only |
| **Full** | One-Sentence Takeaway + If You Only Have 2 Minutes + References & Rabbit Holes |
| **Comprehensive** | All three above + Themes & Connections |

**One-Sentence Takeaway** — the single most important thing from the
entire piece, in 15-20 words.

**If You Only Have 2 Minutes** — the 5-7 absolute must-know points. The
cream of the cream.

**References & Rabbit Holes** — people, projects, books, tools, and
ideas mentioned that are worth following up on, with brief context for
each.

**Themes & Connections** (Comprehensive only) — 3-5 throughlines that
connect multiple sections. The deeper patterns the speaker may not
realize they're revealing. Synthesis, not summary.

## Output Format

```markdown
# EXTRACT WISDOM: {Content Title}
> {One-line description of what this is and who's talking}

---

## {Dynamic Section 1 Name}

- {bullet}
- {bullet}
- {bullet}

## {Dynamic Section 2 Name}

- {bullet}
- {bullet}

[... more dynamic sections ...]

---

## One-Sentence Takeaway

{15-20 word sentence}

## If You Only Have 2 Minutes

- {essential point 1}
- {essential point 2}
- {essential point 3}
- {essential point 4}
- {essential point 5}

## References & Rabbit Holes

- **{Name/Project}** — {one-line context of why it's worth looking into}
- **{Name/Project}** — {context}
```

## Quality Check

Before delivering output, verify:
- [ ] Sections are specific to THIS content, not generic
- [ ] No bullet sounds like it was written by a committee
- [ ] Every bullet has a specific detail, quote, or insight — not vague
      summaries
- [ ] Section names are conversational and headline-worthy (not
      category labels)
- [ ] Section count matches depth level (Instant=1, Fast/Basic=3,
      Full=5-12, Comprehensive=10-15)
- [ ] Closing sections match depth level (see Closing Sections table)
- [ ] No bullet starts with "The speaker" or "It was noted that"
- [ ] No more than 3 bullets per section start with "He" or the
      speaker's name
- [ ] No bullet exceeds 25 words
- [ ] No inventory sections (just listing facts without insight)
- [ ] "If You Only Have 2 Minutes" bullets are each under 20 words
- [ ] Reading the output makes you want to consume the original content
