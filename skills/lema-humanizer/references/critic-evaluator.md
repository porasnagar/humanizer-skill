# Lema Critic Evaluator: The Agent as Critic (Quality & AI Detector Gate)

When operating in **Agent-as-Critic Mode** (either evaluating your own rewrites or evaluating external LLM output from AWS Bedrock / Groq / Cerebras / NVIDIA), you serve as the final quality and authenticity gate.

Your objective is twofold:
1. **Factual & Semantic Matching (Input vs Output)**: Ensure zero hallucinations, no dropped citations, no missing numbers/dates, and no meaning distortions.
2. **AI Detector Hallmarks Elimination**: Ensure the text completely avoids the statistical fingerprints flagged by Copyleaks, GPTZero, and Turnitin.

---

## The 3-Tier Critic Audit

Every paragraph must pass all three audit tiers before it is marked `clean` (100% Human):

```
                   ┌───────────────────────────────────────┐
                   │          ORIGINAL INPUT BLOCK         │
                   └──────────────────┬────────────────────┘
                                      │
                   ┌──────────────────▼────────────────────┐
                   │         REWRITTEN DRAFT BLOCK         │
                   └──────────────────┬────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
     ┌────────▼────────┐    ┌─────────▼─────────┐   ┌─────────▼─────────┐
     │ TIER 1: PACING  │    │ TIER 2: INTEGRITY │   │ TIER 3: DETECTOR  │
     │  & BURSTINESS   │    │  (INPUT VS OUTPUT)│   │    SIMULATION     │
     └────────┬────────┘    └─────────┬─────────┘   └─────────┬─────────┘
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │ All Passed?               │
                        │   YES -> clean            │
                        │   NO  -> FLAGGED (Revise) │
                        └───────────────────────────┘
```

---

### Tier 1: Programmatic Pacing & Burstiness (`check_sentence_pacing`)

| Audit Check | Failure Trigger | How to Resolve |
|---|---|---|
| **Banned AI Words** | Any presence of `delve`, `tapestry`, `realm`, `beacon`, `furthermore`, `moreover`, `pivotal`, `testament`, `revolutionize`, etc. | Replace immediately with direct human alternatives (see Blacklist table). |
| **Run-on Sentences** | Any individual sentence exceeding 35 words. | Split into two distinct sentences separated by a period. |
| **Single-Sentence Block** | Paragraph of 28+ words written as a single continuous sentence. | Break down into at least 2-3 distinct, shorter sentences. |
| **Monotonous Pacing** | Paragraph of 4+ sentences where max length - min length < 8 words, and no sentence < 16 words. | Insert at least one short, punchy sentence (8-13 words) to create high variance. |
| **Adjacent Starters** | Consecutive sentences starting with the same transition word (`so`, `also`, `and`, `but`, `however`, `this`, `it`). | Change grammatical opening of the second sentence (e.g., start with a prepositional phrase or gerund). |
| **Formulaic Starters** | Sentences opening with `meanwhile`, `additionally`, `furthermore`, `moreover`, `consequently`. | Delete the connector and start the sentence directly with the subject or verb. |

---

### Tier 2: Factual & Semantic Integrity Matcher (`check_integrity`)

The Critic extracts protected tokens from the original input block and cross-checks them against the rewritten draft:

1. **Citations (Hard Failure if Missing)**:
   - Narrative citations: `Benigno et al. (2022)`, `Smith and Jones (2019)`
   - Parenthetical citations: `(Benigno et al., 2022)`, `(IMF, 2023)`
   - Author names: Must match Latin spelling character-for-character.
2. **Numbers, Dates & Metrics (Hard Failure if Missing)**:
   - Years: `2020`, `2024`, `1998`
   - Numeric figures: `14.2%`, `$3.8B`, `450`, `0.05`
   - Quantities and sample sizes: Must never be omitted or altered.
3. **Acronyms (Hard Failure if Missing)**:
   - Capitalized acronyms: `RCM`, `AI`, `GDP`, `CPI`, `WPI`, `API`, `LLM`
4. **Proper Nouns & Domain Terms (Hard Failure if Missing)**:
   - Named indices and entities: `Baltic Dry Index`, `Reserve Bank of India`, `Suez Canal`, `Ayushman Bharat`
5. **Length Ratio Checks**:
   - Word count ratio < 65%: Flagged for **Excessive Compression / Omission**.
   - Word count ratio > 160%: Flagged for **Fluff / Artificial Expansion**.
6. **Perspective Shift (Soft Failure)**:
   - If original is written in third person, do NOT introduce "we" or "our" claiming other researchers' work.

---

### Tier 3: AI Detector Simulation (`simulate_ai_detector`)

Modern AI detectors evaluate statistical text distributions:
- **Perplexity**: How predictable the word choice is (AI chooses high-probability tokens; humans choose varied, idiomatic, pragmatic tokens).
- **Burstiness**: How much sentence length and syntactic complexity vary across the paragraph (AI is smooth and uniform; humans are irregular and spikey).
- **Entropy Smoothing**: AI paraphrasers often maintain a standard linear subject-verb-object skeleton while replacing words with synonyms.
- **Clinical Symmetry**: Neatly balanced clauses joined by polite semicolons or colons.

#### How to Shatter Detector Signatures:
- Inject an em-dash (`—`) for an abrupt parenthetical observation.
- Place a 7-word fragment directly following a 25-word analytical sentence.
- Eliminate smooth transitions and juxtapose thoughts directly.

---

## Actionable Resolution Playbook

When `critic <workdir>` marks a block as `FLAGGED`:

1. **Read the FLAGGED note**:
   ```markdown
   <!-- block 3 | line 14 | FLAGGED: author 'Benigno'; banned 'moreover'; length variance is 3 -->
   ```
2. **Locate the original text in `originals.md`**:
   Compare the draft with the original to see where the author name was dropped.
3. **Make the minimal targeted fix**:
   - Put back the author name: `Benigno et al. (2022)`.
   - Remove `moreover`: replace with `also` or start sentence directly.
   - Break a 24-word sentence into a 9-word punchy sentence and a 15-word explanation.
4. **Re-run the Critic**:
   ```bash
   python lema_humanize.py critic "<workdir>"
   ```
5. **Confirm `clean (100% Human)` status**.
