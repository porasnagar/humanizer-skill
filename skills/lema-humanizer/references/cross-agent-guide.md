# Lema Humanizer: Cross-Agent Compatibility Guide

The Lema Humanizer skill is built to run natively across all major agentic AI coding assistants and environments:
- **Google Antigravity** (Antigravity IDE & CLI)
- **Anthropic Claude Code**
- **OpenAI Codex & ChatGPT Agent Environments**
- **Cursor, Windsurf, Aider & Custom Agent Scripts**

---

## 1. Google Antigravity

Antigravity automatically discovers skills from:
1. Workspace root: `.agents/skills/lema-humanizer/`
2. Global root: `~/.gemini/config/skills/lema-humanizer/`

### Activation in Antigravity:
Simply ask Antigravity:
> *"Humanize document.docx using Lema"*
> *"Act as Lema and humanize this paragraph"*
> *"Run Lema in Hybrid mode with Bedrock on literature-review.md"*

Antigravity reads `SKILL.md`, prepares the work folder, executes the Actor rewrites, audits with `critic`, and reassembles the final output.

---

## 2. Anthropic Claude Code

Claude Code discovers personal user skills located in:
`~/.claude/skills/lema-humanizer/` (or `.claude/skills/lema-humanizer/` in the project root).

### Installation:
Run the bundled installer:
```bash
python skills/install_skills.py --only claude
```

### Usage in Claude Code:
Ask Claude:
> `/lema-humanizer prepare paper.md`
> or
> *"Use the lema-humanizer skill to humanize draft.md and fix all flagged blocks"*

Claude Code will:
1. Execute `python ~/.claude/skills/lema-humanizer/scripts/lema_humanize.py prepare paper.md`
2. Read `draft.md` and `originals.md`
3. Write the conceptual deconstructions block-by-block following `references/actor-prompts.md`
4. Run `python ~/.claude/skills/lema-humanizer/scripts/lema_humanize.py critic paper.lema-work`
5. Inspect any `FLAGGED` markers, apply surgical corrections, and re-run until all blocks are `clean`
6. Run `assemble` and present the output path.

---

## 3. OpenAI Codex & ChatGPT Agents

Codex and OpenAI agent environments read user skills from:
`~/.agents/skills/lema-humanizer/` (with `agents/openai.yaml`).

### Installation:
```bash
python skills/install_skills.py --only codex
```

### Usage in Codex / Terminal:
Tell Codex:
> *"Run Lema humanizer on test.docx in Agent mode. Prepare the blocks, rewrite them in draft.md using high burstiness, run critic, and assemble."*

Because the script is standard Python with zero required external dependencies (uses standard library; optional `python-docx` for `.docx`), it runs smoothly inside Codex sandboxes and terminal shells.

---

## 4. Standalone CLI (Direct Terminal Usage)

Any developer or automated CI/CD pipeline can use Lema directly from the terminal without an agent:

```bash
# 1. Prepare workdir
python scripts/lema_humanize.py prepare manuscript.docx

# 2. In Hybrid mode with AWS Bedrock Mantle (gpt-oss-120b)
python scripts/lema_humanize.py api manuscript.docx --engine actor-critic --provider Bedrock

# 3. Evaluate workdir with the Critic
python scripts/lema_humanize.py critic manuscript.lema-work

# 4. Assemble final document
python scripts/lema_humanize.py assemble manuscript.lema-work -o manuscript_human.docx
```

---

## Provider API Keys Configuration (Optional for Hybrid Mode)

If you wish to use external LLM providers (AWS Bedrock, Groq, Cerebras, NVIDIA) in Hybrid mode:

Place your keys in your `.env` file or environment variables:
```bash
# AWS Bedrock Mantle
AWS_BEDROCK_API_KEY="ABSK..."

# Groq
GROQ_API_KEY="gsk_..."

# Cerebras
CEREBRAS_API_KEY="csk-..."

# NVIDIA
NVIDIA_API_KEY="nvapi-..."
```
If no keys are present, the skill automatically defaults to **Pure Agent Mode**, where the AI Agent itself performs the generation with zero API costs!
