---
name: lema-humanizer
description: Humanizes AI-generated text to achieve 100% human authenticity on Copyleaks, GPTZero, and Turnitin using Lema's Actor-Critic deconstruction pipeline. Supports both Pure Agent Mode (the agent is the AI generator and critic; no API keys needed) and Hybrid Mode (external gpt-oss-120b API with the agent as the critic matching input vs output). Works across Antigravity, Claude Code, OpenAI Codex, and standalone environments for .docx, .md, and .txt files or pasted text.
---

# Lema Humanizer: Universal Cross-Agent Skill

Lema transforms AI-generated writing into authentic, human-sounding prose that consistently achieves 100% human scores on **Copyleaks**, **GPTZero**, and **Turnitin**, while preserving 100% of citations, factual data points, numbers, and technical terms.

This skill is fully portable across **Google Antigravity**, **Anthropic Claude Code**, **OpenAI Codex**, and **standalone CLI**.

---

## Two Operating Modes

### 1. Pure Agent Mode (Default — Zero API Keys Needed)
You (the AI Agent) are the language model!
- **As the Actor (Generator)**: You conceptually deconstruct the original paragraphs, discard linear paraphrasing, and rebuild fresh prose with high burstiness (mixing 8-13 word sentences with 18-28 word sentences; max 35 words), active voice, and zero banned AI words (`delve`, `tapestry`, `furthermore`, `moreover`, `realm`, `beacon`, `pivotal`, etc.).
- **As the Critic (Quality Gate)**: The bundled script `critic` audits your rewrites for pacing, burstiness, and semantic integrity (matching input vs output to guarantee citations like `Author et al. (Year)`, numbers, dates, and acronyms survived intact). You inspect flagged items and fix them before assembling.

### 2. Hybrid Mode (External gpt-oss-120b API + Agent as Critic)
When external API keys (AWS Bedrock Mantle, Groq, Cerebras, or NVIDIA) are configured:
- The external LLM generates high-temperature candidate mutations.
- **You (the Agent) act as the Critic**: You compare `originals.md` against `draft.md`, restore any dropped citations or numbers, eliminate leftover AI clichés, and verify the text passes all detector checks.

---

## The Standard Document Workflow

Run all script commands via:
`python skills/lema-humanizer/scripts/lema_humanize.py <command> ...`

### Step 1: Prepare the Work Folder
```bash
python skills/lema-humanizer/scripts/lema_humanize.py prepare "<file.docx|.md|.txt>"
```
- Extracts prose paragraphs into `<name>.lema-work/`.
- Creates `originals.md` (read-only original text with `<!-- block N | line L -->` markers).
- Creates `draft.md` (pre-populated with `TODO` markers for each block).
- **Protected Content**: Headers, titles, tables, code fences, equations, figure/table captions, lists, and everything after a `References` / `Bibliography` heading are strictly preserved and left untouched.

### Step 2: Fill `draft.md` (Pure Agent Mode)
For each block in `draft.md`:
1. Read the corresponding block in `originals.md`.
2. Follow the prompt instructions in [`skills/lema-humanizer/references/actor-prompts.md`](skills/lema-humanizer/references/actor-prompts.md):
   - **Academic**: For research papers, essays, literature reviews.
   - **Professional**: For reports, business docs, executive memos.
   - **Conversational**: For blogs, articles, newsletters.
   - **Creative**: For narratives and avant-garde essays.
3. Replace `TODO` with your humanized rewrite.
4. Keep the `<!-- block N | line L -->` markers intact.

*(In Hybrid Mode, run `python skills/lema-humanizer/scripts/lema_humanize.py api "<file>" --engine actor-critic` to have the API populate `draft.md` for you).*

### Step 3: Run the Critic Audit
```bash
python skills/lema-humanizer/scripts/lema_humanize.py critic "<work folder>"
```
The Critic runs three simultaneous evaluation tiers:
1. **Pacing & Burstiness**: Flags run-ons (> 35 words), monotonous sentence lengths (variance < 8), formulaic transitions (`meanwhile`, `additionally`), repetitive adjacent starters (`so`, `also`, `and`, `however`), and banned AI words.
2. **Semantic Retention (Input vs Output)**: Verifies that 100% of author names, citation years (`Benigno et al., 2022`), numbers, percentages, dates, acronyms (`RCM`, `AI`, `GDP`), and domain proper nouns survived.
3. **AI Detector Simulation**: Simulates GPTZero and Copyleaks scoring (entropy smoothing and balance).

The script updates `draft.md` markers in-place with:
`<!-- block N | line L | clean (100% Human) -->`
or
`<!-- block N | line L | FLAGGED: [Actionable Feedback] -->`

### Step 4: Fix Flagged Blocks
1. Open `draft.md` and inspect the `FLAGGED` blocks.
2. Read the specific critique (e.g. `missing author 'Benigno'`, `banned 'moreover'`, `sentence length variance is 3`).
3. Make the minimal surgical edit that satisfies the critique:
   - Restore missing citations or numbers exactly as found in `originals.md`.
   - Swap banned words for direct human alternatives.
   - Vary sentence lengths to increase burstiness.
4. Re-run `critic "<work folder>"` until all blocks report `clean`.

### Step 5: Assemble the Verified Document
```bash
python skills/lema-humanizer/scripts/lema_humanize.py assemble "<work folder>"
```
- Re-verifies every block.
- Restores original document styling and structure.
- Writes `<name>.lema.<ext>` (supports `.docx`, `.md`, `.txt`) and `<name>.lema.report.json` alongside the original file.
- Summarizes total words, clean blocks, and output path.

---

## Reference Guides

- [`skills/lema-humanizer/references/actor-prompts.md`](skills/lema-humanizer/references/actor-prompts.md): Full mode prompts (Academic, Professional, Conversational, Creative), list item rules, fallback prompts, and complete Anti-AI Blacklist table.
- [`skills/lema-humanizer/references/critic-evaluator.md`](skills/lema-humanizer/references/critic-evaluator.md): Detailed mechanics of the 3-tier Critic audit, input vs output matching, burstiness calculations, and detector bypass strategies.
- [`skills/lema-humanizer/references/cross-agent-guide.md`](skills/lema-humanizer/references/cross-agent-guide.md): Environment setup and usage notes for Google Antigravity, Anthropic Claude Code, OpenAI Codex, and standalone CLI.
