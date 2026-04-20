# Poetic synthesis reference

Fully self-contained framework for the `brand-philosopher`'s synthesis step. Text below is distilled from two upstream skills with credit retained:

- **Close reading + metaphor + image + sound analysis** — `majiayu000/claude-skill-registry/skills/data/poet-analyst-rysweet-azurehaymaker`
- **Poetic voice and Socratic cadence** — `majiayu000/claude-skill-registry/skills/data/greek-philosopher`

Consumed by `brand-philosopher` Step 2 (Synthesis) and Step 4 (Name the Movement), and by any agent translating abstract philosophy into concrete prompt-seed vocabulary.

---

## 1. Core premises *(from poet-analyst, verbatim)*

Poetic analysis rests on seven principles. A brand philosopher applies them to vault material, prior versions, and brand-identity.json:

- **Language carries more than literal meaning.** Words evoke, suggest, resonate. How something is said reveals as much as what is said. Read the vault for what's *around* the claims, not just the claims.
- **Metaphor structures thought.** We think in metaphors. Identifying the governing metaphor of a brand reveals hidden assumptions and emotional frames it hasn't named yet.
- **Form and content are inseparable.** The brand's typographic proportion, color temperature, and composition rhythm all carry meaning beyond what the copy says.
- **Ambiguity is generative.** Poetry embraces multiple meanings simultaneously. A brand that holds a genuine tension ("institutional + handmade") is richer than one that flattens into one.
- **Emotion is knowledge.** Feeling is a way of knowing. Emotional truth complements factual truth. "It lands heavy" is a valid analytical claim.
- **Particularity reveals universal.** Close attention to specific, concrete details illuminates larger truths. The philosophy names a particular chair in a particular room, not "warm seating".
- **Silence speaks.** What is unsaid, gaps, pauses, absences carry meaning. What the brand refuses to claim is often its strongest signal.

---

## 2. Close-reading method *(from poet-analyst, verbatim)*

Before naming the movement, read the vault like a close-reader:

1. Read multiple times, slowly.
2. Note every word choice, image, sound.
3. Identify patterns, repetitions, variations.
4. Analyze structure and form (how the vault is organized, what ordering it uses).
5. Consider ambiguities and tensions — hold them open.
6. Suspend judgment about meaning until the analysis is complete.

Every element contributes to the whole. Paradox and tension are valuable, not flaws.

**Source:** Cleanth Brooks, *The Well Wrought Urn* (1947).

---

## 3. Metaphor analysis — Lakoff & Johnson *(from poet-analyst)*

Every brand has a governing metaphor whether it has named it or not.

### Structure of a conceptual metaphor

- **Source domain** — concrete experience (e.g., "rammed earth", "workshop", "archive", "journey", "body", "architecture")
- **Target domain** — abstract concept (e.g., "trust", "expertise", "belonging", "transformation")
- **Mapping** — systematic correspondences between domains (rammed-earth walls → accreted expertise; each hand-packed layer → each project; the wall holds weight → the brand holds trust)

### Common governing metaphors (brand-adapted)

- Brand is an **institution** — implies durability, ceremony, ledgers, marble, gold leaf, restraint
- Brand is a **workshop** — implies craft, tools visible, wood grain, hand, mistakes preserved
- Brand is a **field guide** — implies observation, patience, taxonomy, plain paper, specimens
- Brand is a **concert hall** — implies performance, acoustic precision, audience, hushed waiting
- Brand is a **map** — implies orientation, scale, legend, edges, territory vs. territory
- Brand is a **garden** — implies seasonal change, patient attention, inevitable decay and renewal
- Brand is an **engine room** — implies function, pressure, tolerances, oil, heat, competence

### Process

1. Identify metaphors the vault already uses repeatedly (read for concrete nouns that recur — "stone", "column", "thread", "signal", "bridge").
2. For each: name source domain, target domain, and mapping.
3. Ask what the metaphor highlights and what it hides. ("Brand is a library" highlights durability; it hides motion.)
4. Consider alternative metaphors and their implications. The brand chose this metaphor, not those. Why?

**Key insight:** metaphors shape perception and action. Changing the governing metaphor changes the brand. Don't change it casually.

**Source:** Lakoff & Johnson, *Metaphors We Live By* (1980).

---

## 4. Image and symbol *(from poet-analyst)*

### Image

- **Definition:** concrete, sensory language appealing to sight, sound, touch, taste, smell.
- **Purpose:** makes the abstract concrete; engages senses; creates vivid experience.
- **Power:** images bypass intellect and speak directly to emotion and body. This is why brand-philosopher extracts *material words* (rammed earth, aged stone, linen, copper) rather than *adjectives* (warm, premium, institutional).

### Symbol

- **Definition:** object, image, or action carrying meaning beyond the literal.
- **Types:**
  - **Universal/archetypal** — cross-cultural (light/dark, water, the journey, the threshold)
  - **Cultural** — specific to culture (flag, crown, cross, monogram, ledger)
  - **Personal** — specific to this brand's vault and history (the founder's grandfather's workshop, the first customer's kitchen table)
- **Characteristics:** concrete yet suggestive; multiple meanings; emotional resonance.

### Analysis questions

- What images recur across the vault? Which senses do they engage?
- What do those images evoke emotionally?
- What symbols are present — archetypal, cultural, personal?
- What do the symbols suggest beyond the literal?
- What associations, connotations, cultural meanings do they carry?
- What patterns of imagery repeat across sections?

### Output for prompt seeds

The philosopher's job is to convert vault images and symbols into **material words** that the planner and cinematographer can embed in prompts:

| Vault mention | Material words for prompt seeds |
|---------------|----------------------------------|
| "our work feels like a library" | `rammed-earth walls`, `oak shelving`, `brass reading lamp`, `cream paper` |
| "we're a concert hall" | `velvet house curtain`, `warm wood proscenium`, `single spotlight`, `felt programme` |
| "we're a field guide" | `manila paper`, `hand-drawn specimen plates`, `faded ink`, `cotton thread binding` |

Never ship adjectives to the planner. Ship material words.

---

## 5. Sound and rhythm *(from poet-analyst)*

Brand voice has acoustic properties even when silent on the page.

### Sound devices

- **Alliteration** — repetition of consonant sounds
- **Assonance** — repetition of vowel sounds
- **Consonance** — repetition of consonants within or at the end of words
- **Onomatopoeia** — words that sound like what they mean
- **Rhyme** — repetition of end sounds (rarely used in modern brand voice, but notable when present)

### Rhythm and meter

- **Rhythm** — pattern of stressed and unstressed syllables
- **Meter** — regular rhythmic pattern
- **Free verse** — no regular meter but still rhythmic

### Effect of sound

- Creates musicality, pleasure
- Emphasizes key words and ideas
- Creates mood (harsh consonants feel cold; soft consonants feel warm)
- Aids memory (brand taglines with sound structure persist)
- Builds emotional intensity

### Analysis questions for the brand's existing voice

- Does the brand's writing use long or short sentences? Hard or soft consonants?
- Read the vault aloud. Does it move fast or slow? Does it stop or flow?
- What rhythm would match it on the page *and* in a video voiceover?

Output goes into `custom-scratchpad.md` Motion grammar (for video materials) and into the copy rubric for `brand-critic`.

---

## 6. Silence

What the brand does NOT say is often the strongest signal.

- What categories of language does the vault carefully avoid? (Marketing-speak? Technical jargon? Emotion?)
- What claims does the brand refuse to make even when competitors do?
- Where does the vault leave gaps? Are the gaps strategic or oversight?

In the philosophy, name the silences explicitly. "We do not use the word 'innovative.' We do not promise transformation. We do not claim to be first." These negations are as load-bearing as the affirmations.

---

## 7. Philosopher's voice directive *(from greek-philosopher)*

The `design-philosophy.md` document itself should read in a specific register:

- **Poetic and elevated**, but not purple. Language that stirs, but stays specific.
- **Questioning rather than declaring.** Guide by asking, not by pronouncing. "What would it look like for the brand to refuse this?" is stronger than "the brand refuses this."
- **Paradoxical and profound** when the brand's tensions are genuine. "Institutional gravity + intimate craft" is a real tension; name it, don't flatten it.
- **Timeless yet immediate.** Ancient concepts (restraint, proportion, witness) applied to a product launching next Tuesday.
- **Compassionate yet unflinching.** Truth with tenderness; the user is cultivating their brand, not being graded on it.

---

## 8. The metaphor → image bridge

This is where brand-philosopher connects to brand-planner. The philosophy gives metaphors; the planner needs images.

### Translation rules

1. **Name the governing metaphor in one sentence.** "This brand is a library" or "this brand is a concert hall".
2. **List 5–8 material words** that come from the metaphor's source domain (§4 examples above).
3. **List 3–5 composition rules** implied by the metaphor (a library has symmetrical shelving + hierarchy by height + warm light from discrete sources — not overhead fluorescent).
4. **List 2–3 quality boosters** that read the metaphor into the finish (meticulous spine alignment, hand-stamped gilt, paper thickness visible at edges).
5. **List 2–3 forbidden moves** — what the metaphor RULES OUT (no glossy plastic, no glassmorphism, no neon, no chrome).

These five lists become the prompt-seed vocabulary the planner embeds into plan-draft. They also populate `custom-scratchpad.md` Global style directives so every future run auto-applies them.

### Example translation (for a sample brand with governing metaphor "rammed-earth reading room")

- **Material words:** rammed earth, aged stone, oak shelving, cream parchment, brass reading lamp, cotton thread binding
- **Composition rules:** one dominant gesture + one support system; warm light from a single source; architectural rhythm (vertical columns, horizontal shelves); asymmetric framing never
- **Quality boosters:** meticulous alignment; labored-over proportion; master-level restraint; paper edges visible
- **Forbidden moves:** glossy plastic, gradient overlays, 3D glass, neon, chrome, purple/violet gradients (AI slop tell)

The cinematographer consumes the same lists plus the motion-grammar block from `seedance-shot-design.md`.

---

## 9. Anti-patterns

- **Listing adjectives instead of material words.** "Warm, premium, institutional" gives the planner nothing to embed in a prompt. "Rammed earth, brass reading lamp, cream parchment" does.
- **Flattening a real tension.** If the brand is genuinely "institutional + handmade", name both; do not pick one.
- **Inventing metaphors from nothing.** The philosophy cultivates what the vault already circled around. If no metaphor is present in the vault, that's a gap to fill through interview (`interview-protocol.md`), not invention.
- **Using abstract philosophy prose in prompts directly.** The planner builds prompts from the material words, not from the philosophy's full text. Excerpt, don't paste.
- **Skipping silence.** What the brand refuses to say shapes the output at least as much as what it affirms.
- **Treating the philosopher's voice as optional style.** A flat "this brand is about X" philosophy produces flat outputs. Voice is load-bearing.

---

## 10. Using this reference as a brand-gen agent

The `brand-philosopher` agent:

1. Loads this reference at Step 2 (Synthesis) of its workflow.
2. Applies §2 (close reading) to the vault.
3. Applies §3 (metaphor) to name the governing metaphor.
4. Applies §4 (image and symbol) to extract material words.
5. Applies §5 (sound and rhythm) to name the voice.
6. Applies §6 (silence) to name the brand's refusals.
7. Applies §7 (voice directive) to the prose of `design-philosophy.md`.
8. Applies §8 (metaphor → image bridge) to produce the five lists the planner and cinematographer consume.

Optional `brand-interviewer` agent (fresh-brand path): before any of the above, use `interview-protocol.md` to elicit the material that §2–§7 analyze.
