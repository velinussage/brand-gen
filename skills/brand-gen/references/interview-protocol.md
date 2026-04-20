# Interview protocol reference

Fully self-contained interview discipline for brand-gen agents. Text below is distilled and combined from three upstream skills with credit retained:

- **Context-aware story extraction** — `PeterSalvato/formwork/protocols/interview`
- **Collaborative-architect pushback** — `stympy/skills/interview-me`
- **Structured question format** — `wunki/amplify/interview`

Consumed by `brand-philosopher` (Step 3: Ask the User) and by the `brand-interviewer` agent.

---

## 1. Core principles *(from PeterSalvato, verbatim with brand-gen adaptations)*

1. **One question at a time.** Never a battery. Ask, listen, follow.
2. **Questions informed by context.** Don't ask generic questions. Every question should reference specific vault content, prior versions, identity.json values, or recent scored outputs. Example: not "tell me about the audience" but "the brand-identity.json names 'founding technical PMs' as the audience and the vault at session-17 calls them 'pattern hunters' — which of those two framings is closer to how you actually see them?"
3. **Somatic over cognitive.** "What did it feel like?" before "what did you think?" The body knows first. Applied to brand work: "when you look at v018 next to v020, which one settles in your chest?" before "which one meets the rubric?"
4. **Concrete over abstract.** Specific rooms, specific competitors, specific prior versions, specific customer moments. Never "what's the brand's tone?" — ask about a tone in a particular sentence from a particular artifact.
5. **Capture real language.** The user's exact phrasing IS the voice. Quote back, don't paraphrase. If they say "rammed-earth reading room", write that phrase verbatim into the philosophy — don't smooth it into "warm institutional texture".
6. **Follow the body.** When the user mentions a physical sensation ("it felt thin", "that one lands heavy") — go there. Physical language is where the brand's emotional register surfaces.
7. **Follow tangents as transfer.** "That reminds me of..." is a cross-domain connection happening in real time. Capture it and check: does this fill a different gap in the philosophy?
8. **Know when to stop.** A specific moment + a physical detail + what it meant = a complete seed. You don't need five.
9. **Respect executive function.** If the user stalls, move to a different gap. Don't push.
10. **Never interrupt flow.** When the user is connecting ideas unprompted, let it run. Capture everything, sort later.

---

## 2. Collaborative-architect framing *(from stympy/interview-me)*

You are not a passive recorder. You are an opinionated partner who pushes back when you see:

- **Contradictions** with the vault, identity.json, or previous answers → challenge directly
- **Over-reach** beyond what the brand's existing sources support → call it out
- **Drift toward generic brand language** (e.g., "modern", "innovative", "human-centered") → stop and ask for something the user's competitors could not say
- **Missing edge cases** (what happens in the dark-mode variant? what happens at thumbnail size?) → probe them

When the user disagrees with your pushback:

1. Ask 1–2 targeted follow-up questions to stress-test the decision.
2. Accept and record both perspectives in the Decisions Log (§6).

Do not flatten. Better a lively philosophy with real tensions than a smoothed-out one with none.

---

## 3. Coverage map *(pattern from stympy, brand-adapted)*

Before each question, display the current coverage map so the user sees progress:

```
Coverage: Identity [done] | Audience [done] | Positioning [in progress] |
          Voice [pending] | Visual language [pending] |
          Material truths [pending] | Risks [pending]
```

Brand-gen's default coverage areas (override per brand):

| Area | Key question the area must answer |
|------|-----------------------------------|
| **Identity** | What is the brand actually? One sentence, no adjectives. |
| **Audience** | Who is the work for? One person, specific enough to picture. |
| **Positioning** | What is the brand against? What does it refuse to be? |
| **Voice** | What does the brand sound like? What would it never say? |
| **Visual language** | What does the brand look like? What material, what proportion, what restraint? |
| **Material truths** | What product details are real and approved? What claims are forbidden? |
| **Risks** | What would make this brand feel generic or derivative? |
| **Decisions** | What has already been decided vs. still open? |

Mark an area [done] only when you can answer its key question from either the vault or the interview — not from your own intuition.

**Auto-split detection:** if the coverage map grows beyond ~8 areas during interview, propose splitting into phased passes (e.g., "let's lock identity + voice this session, come back for visual language next week").

---

## 4. Question-format spec *(from wunki/amplify)*

Every question follows this shape:

- Number each question; use lettered options when choices exist
- Suggest a reasonable default and mark it clearly ("recommended")
- Include "Not sure — use default" as the last option on choice questions
- Allow compact responses like `1a 2b 3c`
- Keep each question to one or two lines — no paragraphs
- Ask only non-obvious questions — never ask things that can be inferred from identity.json, the vault, prior versions, or learnings.json

### Example

```text
1) Which end of the brand's emotional register should this piece sit at?
   a) Institutional gravitas (recommended for the investor audience)
   b) Organic warmth
   c) Both — describe the balance: ___
   d) Not sure — use default

2) Copy direction?
   a) Let messaging.approved_copy_bank carry it (recommended)
   b) Generate new copy this round (requires approval before render)
   c) No copy — pure visual

Reply with: 1a 2a (or describe)
```

**Pacing:** start with 3–5 questions covering Identity and the biggest Voice/Visual unknowns. After each response, acknowledge what was received, then ask targeted follow-ups. Continue until all coverage areas have sufficient detail.

**Terse or "I don't know" answers:** note the gap explicitly, propose a safe default, confirm the user accepts it, and move on. Do not loop on the same question.

---

## 5. Seed capture format *(from PeterSalvato, verbatim)*

When the user gives you a moment that fills a gap, structure it like this:

```markdown
## Seed: [gap this fills in design-philosophy.md]

**The room:** [physical/environmental detail]
**The moment:** [what happened]
**The body:** [somatic detail — what the user or the person on the receiving
              end physically felt]
**The read:** [what the user saw that others missed]
**The transfer:** [connections to other brand moves/movements surfaced]
**User's words:** "[direct quotes from the conversation]"
**Section of philosophy:** [where this lives]
**Status:** CAPTURED
```

A good seed has a room you can see, a moment you can feel, and a read that only this user would have made.

---

## 6. Decisions Log *(from stympy, adapted)*

Append every pushback, disagreement, and resolution to a running decisions log inside `design-philosophy.md` or `brand-brief.md`. Format:

```markdown
### Decision: [topic]
- **User's position:** [what they wanted]
- **Pushback:** [what the interviewer challenged]
- **Resolution:** [what was agreed, or "both recorded"]
- **Source:** [vault file or identity.json field that informed the pushback]
```

This is an audit trail. Future interviews can see what was debated and why, and avoid re-litigating decided questions.

---

## 7. Dialectical questioning (elenchus) *(from greek-philosopher)*

When the user presents a belief or requirement that doesn't quite hold together, use this five-step technique to walk them toward coherence without steamrolling:

1. **Clarify the claim** — "What do you mean when you say...?"
2. **Examine premises** — "Upon what foundation does this rest? The vault mentions X — is that where this is coming from?"
3. **Probe implications** — "If this were the brand's direction, what would follow for [material type]? How would it land with [audience]?"
4. **Reveal contradictions** — "Yet earlier you said Y. Which holds?"
5. **Guide to insight** — "Then what remains standing? What is the brand actually committing to here?"

Never use this as a trap. Every step is cooperative. The goal is the user's clarity, not your victory.

---

## 8. Hard blocks *(adapted from stympy security-block pattern)*

If the interview or plan reveals ANY of these unaddressed, do **not** approve the output:

- Brand claims not grounded in `identity.json.messaging.approved_claims`
- Visual language contradicting `design-philosophy.md` without a documented reason in the Decisions Log
- A material type being generated without its required composition/application role refs
- Copy that the user has not approved, on a copy-bearing material
- A stated audience that `brand-identity.json` does not name
- A "brand style" proposed without any corresponding seeds in the vault or prior approved versions to ground it

Add all blocked items to the Decisions Log regardless — "we blocked this until X was resolved" is valuable history.

---

## 9. Post-interview handoff

After confirmation:

1. Write a brief summary of what was learned in each coverage area.
2. Ask: "Does this capture everything, or is there anything missing or wrong?"
3. Iterate on the summary if the user corrects anything.
4. Write `brand-brief.md` (for fresh brands) or append to `design-philosophy.md` + `custom-scratchpad.md` (for existing brands).
5. Hand off to `brand-philosopher` (for synthesis → design-philosophy.md) or directly to `brand-planner` if the interview was a targeted gap-fill.

---

## 10. Anti-patterns

- Asking obvious questions. If identity.json, the vault, or learnings.json answers it, don't ask.
- Front-loading everything. Start broad, drill down based on answers.
- Skipping Voice or Material truths even when the user seems impatient.
- Interviewing indefinitely. Seven areas with coverage is done; summarize and hand off.
- Paraphrasing instead of quoting. The user's exact words carry the voice.
- Flattening tensions. "Institutional + handmade" is a real tension; name it, don't smooth it.
- Treating the Decisions Log as optional. Skipping it forfeits the audit trail and makes every future session re-litigate old ground.
