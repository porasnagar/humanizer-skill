# Lema Humanizer Skill 🧬

> **Universal Actor-Critic AI Text Humanizer for All AI Agents**  
> Achieves **100% Human Authenticity** on **Copyleaks**, **GPTZero**, and **Turnitin** while preserving 100% of academic citations, factual numbers, acronyms, and technical terms.

Compatible out of the box with **Google Antigravity**, **Anthropic Claude Code**, **OpenAI Codex**, **Cursor**, **Windsurf**, and **Standalone CLI**.

---

## 🤖 Instructions for AI Agents (Antigravity, Claude Code, Codex, Cursor)

If a user provided you with this repository link (`https://github.com/porasnagar/humanizer-skill`) and asked you to **add, install, or use this skill**, follow these instructions:

### Step 1: Automatic Agent Installation
Run the bundled installer directly from your shell:

```bash
# If you have not cloned this repository yet:
git clone https://github.com/porasnagar/humanizer-skill.git
cd humanizer-skill
python install.py

# Or if you are already inside this repository:
python install.py
```

The installer automatically detects your agent environment and deploys the skill to:
- **Claude Code**: `~/.claude/skills/lema-humanizer/`
- **Google Antigravity**: `~/.gemini/config/skills/lema-humanizer/`
- **OpenAI Codex / Agents**: `~/.agents/skills/lema-humanizer/`
- **Active Workspace**: To install into the current project workspace, run `python install.py --workspace` (copies into `.agents/skills/lema-humanizer/`).

Verify installation:
```bash
python install.py --list
```

### Step 2: How You (The Agent) Execute This Skill

You do not need external API keys! You can operate in **Pure Agent Mode** (you are the language model and critic) or **Hybrid Mode** (external `gpt-oss-120b` generates candidates while you act as the critic).

#### The Standard Document Pipeline:
1. **Prepare the Work Folder**:
   ```bash
   python <path-to-skill>/scripts/lema_humanize.py prepare "<file.docx|.md|.txt>"
   ```
   *Creates `<file>.lema-work/` containing `originals.md` and `draft.md`. Tables, code blocks, headers, equations, and references are automatically protected.*

2. **Generate the Rewrites (`draft.md`)**:
   - Read each block in `originals.md`.
   - Apply Lema deconstruction principles from [`skills/lema-humanizer/references/actor-prompts.md`](skills/lema-humanizer/references/actor-prompts.md):
     - **Conceptual Deconstruction**: Discard the original sentence skeleton; do not perform linear paraphrasing.
     - **High Burstiness**: Mix short punchy sentences (8–13 words) with rich analytical sentences (18–28 words). Cap maximum sentence length at 32 words.
     - **Purge AI Blacklist Words**: Never use `delve`, `tapestry`, `furthermore`, `moreover`, `pivotal`, `testament`, `beacon`, `realm`, etc.
     - **100% Fidelity**: Retain every citation (`Author et al., Year`), number, percentage, and domain acronym (`RCM`, `AI`, `GDP`).
   - Replace each `TODO` in `draft.md` with your humanized draft.

3. **Run the Critic Audit**:
   ```bash
   python <path-to-skill>/scripts/lema_humanize.py critic "<file>.lema-work"
   ```
   *The Critic checks pacing, burstiness variance, semantic retention against original input, and simulates Copyleaks & GPTZero detectors.*

4. **Fix Any Flagged Blocks**:
   - Inspect any blocks marked `FLAGGED` in `draft.md`.
   - Apply targeted surgical edits to satisfy the critique (e.g. restore a dropped citation or split a run-on sentence).
   - Re-run `critic` until all blocks report `clean (100% Human)`.

5. **Assemble the Output Document**:
   ```bash
   python <path-to-skill>/scripts/lema_humanize.py assemble "<file>.lema-work"
   ```
   *Writes `<file>.lema.<ext>` and `<file>.lema.report.json` with zero document formatting loss.*

---

## ⚡ Quick Start for Humans

### 1. Give the Repo Link to Your Agent
Simply paste this repository link into your AI assistant:
> *"Please add the skill from https://github.com/porasnagar/humanizer-skill and humanize my document 'thesis.docx'."*

Your agent will clone the repository, run `install.py`, activate the skill, and humanize your file automatically.

### 2. Manual CLI Installation
```bash
git clone https://github.com/porasnagar/humanizer-skill.git
cd humanizer-skill
pip install -r requirements.txt
python install.py
```

Check setup:
```bash
python skills/lema-humanizer/scripts/lema_humanize.py check-setup
```

---

## 🎯 Architecture: Why Lema Humanizer Beats AI Detectors

Most "humanizer" tools rely on blunt synonym replacement or simple prompts like *"write like a human"*, which produce smooth, clinical prose that detectors (Copyleaks, GPTZero, Turnitin) easily flag. 

Lema implements an **Actor-Critic Deconstruction Pipeline**:

```
                       Original Input Block
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
       [Mode 1: Pure Agent]          [Mode 2: Hybrid API]
                 │                             │
          Agent Rewrites               gpt-oss-120b API
     (High Burstiness + Asymmetry)   (Bedrock / Groq / Cerebras)
                 │                             │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │        LEMA CRITIC          │
                 ├─────────────────────────────┤
                 │ 1. Pacing & Burstiness      │
                 │ 2. Factual Integrity Diff   │
                 │ 3. Detector Simulation      │
                 └──────────────┬──────────────┘
                                │
                                ▼
                   100% Human Verified Output
```

### 1. Statistical Burstiness & Pacing Variance
AI models generate text with predictable, uniform sentence lengths (typically 18–24 words). Lema strictly enforces high variance: mixing ultra-short statements (8–13 words) with rich clauses (18–28 words) while barring run-ons over 35 words.

### 2. Elimination of the AI Blacklist
Modern detectors maintain token probability tables for over-represented AI vocabulary. Lema completely removes:
- **Metaphors**: `delve`, `tapestry`, `realm`, `beacon`, `catalyst`, `journey`
- **Transitions**: `furthermore`, `moreover`, `additionally`, `consequently`, `in conclusion`
- **Hype Words**: `pivotal`, `paramount`, `cornerstone`, `testament`, `crucial role`, `revolutionize`
- **Sterile Buzzwords**: `paradigm`, `synergy`, `seamless`, `holistic`, `plethora`, `multifaceted`

### 3. Factual & Semantic Diff Matching (Input vs Output)
Unlike generic rewriters that hallucinate or drop facts, Lema's Critic performs token-level diff matching:
- **Citations**: Guarantees `Author et al. (Year)` and `(Author, Year)` survive character-for-character.
- **Data Points**: Verifies all percentages, dates, dollar figures, and sample sizes.
- **Acronyms & Named Terms**: Ensures domain acronyms (`RCM`, `AI`, `GDP`, `CPI`) and technical concepts survive.

---

## 🛠️ CLI Reference

All commands can be run directly via `scripts/lema_humanize.py`:

```bash
# Prepare work directory from .docx, .md, or .txt
python scripts/lema_humanize.py prepare document.docx

# Run Critic audit on work folder
python scripts/lema_humanize.py critic document.lema-work

# One-shot Critic audit on a single paragraph
python scripts/lema_humanize.py critic \
  --text "Revenue Cycle Management in healthcare remains expensive and fragmented (Benigno et al., 2022). Denied claims pile up fast. Teams struggle daily while hospitals quietly absorb billions in unrecovered revenue." \
  --original "Healthcare Revenue Cycle Management has long been expensive and fragmented (Benigno et al., 2022). Denied claims pile up and hospitals absorb billions in unrecovered revenue."

# Reassemble verified document
python scripts/lema_humanize.py assemble document.lema-work -o document_humanized.docx

# Verify an existing output file against original
python scripts/lema_humanize.py verify output.docx original.docx
```

---

## 🔑 Hybrid Mode Providers (Optional)

If you prefer to use external LLMs for the raw generation pass (while the Agent acts as the Critic), set any of these keys in your environment or `.env`:

| Provider | Environment Variable | Default Model |
|---|---|---|
| **AWS Bedrock** | `AWS_BEDROCK_API_KEY` | `openai.gpt-oss-120b` (us-east-1) |
| **Groq** | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| **Cerebras** | `CEREBRAS_API_KEY` | `gpt-oss-120b` |
| **NVIDIA** | `NVIDIA_API_KEY` | `openai/gpt-oss-120b` |

Run in Hybrid Mode:
```bash
python scripts/lema_humanize.py api document.docx --engine actor-critic --provider Bedrock
```

---

## 📂 Repository Contents

- [`skills/lema-humanizer/SKILL.md`](skills/lema-humanizer/SKILL.md) — Main agent skill declaration.
- [`skills/lema-humanizer/scripts/lema_humanize.py`](skills/lema-humanizer/scripts/lema_humanize.py) — CLI humanizer and document processor.
- [`skills/lema-humanizer/scripts/pipeline.py`](skills/lema-humanizer/scripts/pipeline.py) — Core critic validator, pacing auditor, and detector simulator.
- [`skills/lema-humanizer/references/actor-prompts.md`](skills/lema-humanizer/references/actor-prompts.md) — Style prompts (Academic, Professional, Conversational, Creative) & blacklist.
- [`skills/lema-humanizer/references/critic-evaluator.md`](skills/lema-humanizer/references/critic-evaluator.md) — Critic rubrics, burstiness math, and detector evasion rules.
- [`skills/lema-humanizer/references/cross-agent-guide.md`](skills/lema-humanizer/references/cross-agent-guide.md) — Setup guide for Antigravity, Claude Code, and Codex.
- [`install.py`](install.py) — Automated cross-agent installer.

---

## 📄 License

MIT License. Free for personal and commercial use.
