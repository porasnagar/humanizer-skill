---
name: humanizer
description: Universal AI text humanizer skill for Antigravity, Claude Code, OpenAI Codex, OpenCode, and Hermes. Uses the multi-hop conceptual deconstruction engine (Groq / Bedrock + Google GTX NMT in 1 go + heuristic cleanup) to achieve 100% human score on Copyleaks, GPTZero, and Turnitin. Ingests text, PDF, Word (.docx), or images with text (OCR/vision). Generates output as Markdown (.md), Word (.docx), PDF, or Academic LaTeX (.tex/.pdf) after confirming format with the user. The agent acts as the Critic to verify semantic integrity, eliminate discrepancies/hallucinations, and guarantee clean human flow.
---

# Universal Humanizer Skill

The **Humanizer** skill transforms AI-generated writing into authentic, human-sounding prose that achieves **100% human scores** on **Copyleaks**, **GPTZero**, and **Turnitin**, while preserving 100% of facts, citations (`Author et al., Year`), numbers, dates, and technical terminology.

Compatible across **Google Antigravity**, **Anthropic Claude Code**, **OpenAI Codex**, **OpenCode**, and **Hermes**.

---

## 1. Prerequisites, Environment & Skill Location

When you (the AI Agent) install, register, or reference this skill:
1. **Skill & Config Path Reporting**: Provide the user with the exact folder path where this skill is located, along with the pre-created `.env` file path:
   - **Skill Location**: `<skill_dir>`
   - **Config File**: `<skill_dir>/.env`
2. **Groq API Key**: The user only needs to add their free Groq API key to that `<skill_dir>/.env` file:
   ```bash
   GROQ_API_KEY="gsk_..."
   ```
   *(The multi-hop engine automatically checks `<skill_dir>/.env` first, so it works seamlessly from any terminal or working directory).*
   *(Optional fallback: `AWS_BEDROCK_API_KEY="bedrock-..."`)*


---

## 2. Universal Agent Workflow

Whenever a user requests humanization of a file or text, follow this strict 5-step pipeline:

```
[User Input: Text/Docx/PDF/Image]
              │
              ▼
    1. Extract Text (via scripts/extractor.py or Vision)
              │
              ▼
    2. Confirm Output Format (MUST ASK USER FIRST!)
              │
              ▼
    3. Run Multi-Hop Engine (scripts/engine.py)
              │
              ▼
    4. Agent-as-Critic Verification (Input vs Output audit)
              │
              ▼
    5. Compile Output Format (scripts/formatter.py)
```

---

### Step 1: Ingest Any Modality (Text, DOCX, PDF, Images)

Run the universal extractor to obtain clean, structure-preserved text:

```bash
python "<skill_dir>/scripts/extractor.py" "<input_file>" -o "<work_dir>/input.txt"
```

- **Pasted Text / Markdown / .txt**: Reads directly.
- **Word Document (.docx)**: Extracts all paragraphs, tables, and heading levels.
- **PDF Document (.pdf)**: Uses `pdfplumber` / `pypdf` to extract clean reading order.
- **Images with Text (.png, .jpg, .webp)**: Uses OCR. If the image is complex, you (the AI Agent) can inspect the image directly using vision to transcribe its complete text accurately.

---

### Step 2: Confirm Desired Output Format (MANDATORY INTERACTION)

> [!IMPORTANT]
> **YOU MUST ASK THE USER FIRST** which output format they want before generating the final document.

Present the user with the following choices (or use interactive question tools if available):
1. **Markdown (`.md`)**: Clean text document with markdown formatting.
2. **Microsoft Word (`.docx`)**: Formatted Word document with 1-inch margins, custom heading styles, and 1.15 line spacing.
3. **Standard PDF (`.pdf`)**: Formatted PDF document via ReportLab.
4. **Academic LaTeX Document (`.tex` / LaTeX PDF)**: Publication-grade LaTeX template with academic typography, standard article class, and hyperref setup.

---

### Step 3: Run the Multi-Hop Humanizer Engine

Execute the core engine using the user's `GROQ_API_KEY`:

```bash
python "<skill_dir>/scripts/engine.py" --input "<work_dir>/input.txt" --output "<work_dir>/raw_output.txt" --provider Groq
```

**How the engine works under the hood:**
1. **Robust Paragraph Splitting**: Breaks text into ~150–250 word paragraphs. Never overflows token limits.
2. **Paragraph-by-Paragraph LLM Steps**:
   - **Step 1 (EN → ZH)**: Conceptual deconstruction. Discards AI sentence structures and cliché transitions.
   - **Step 2 (ZH → JA)**: Context-anchored translation. Anchors on original facts to prevent hallucinations.
3. **Google NMT in 1 Go (via Google GTX API)**:
   - Assembles Japanese paragraphs and translates **JA → FI** and **FI → EN** via `translate.googleapis.com` in 1 go.
   - Avoids per-paragraph rate limits (uses only ~2–3 requests total).
4. **Offline Heuristic Cleanup**: Strips all em-dashes, replaces leftover clichés, and enforces sentence burstiness.

---

### Step 4: Agent-as-Critic Verification (Side-by-Side Review)

Now, **YOU (the AI Agent) act as the Senior Editor and Critic**:

1. Run the automated critic audit:
   ```bash
   python "<skill_dir>/scripts/critic.py" --original "<work_dir>/input.txt" --humanized "<work_dir>/raw_output.txt"
   ```

2. Inspect the audit report and perform your manual side-by-side verification:
   - **Discrepancy Check**: Did every author citation (`Author et al., 2022`), year, date, number, percentage, and technical acronym (`GDP`, `CPI`) survive? If any were dropped, restore them.
   - **Hallucination Check**: Did the LLM invent any fake research, unmentioned case studies, or inaccurate claims? If so, remove them.
   - **Untranslated Artifacts**: Are there any leftover Japanese kanji/hiragana, Chinese characters, or Finnish words? Clean them into natural English.
   - **Clean Read & Pacing**: Read the text aloud in your context. Ensure it sounds like a published human scholar or professional—punchy, confident, varied in sentence length, with zero formulaic AI connectors (`furthermore`, `moreover`, `delve`).

3. Write the polished, verified text to `<work_dir>/verified.md`.

---

### Step 5: Compile Final Output in User's Requested Format

Compile the verified text into the user's selected format using the formatter:

```bash
# Markdown (.md)
python "<skill_dir>/scripts/formatter.py" "<work_dir>/verified.md" --format md --output "<output_path>"

# Word (.docx)
python "<skill_dir>/scripts/formatter.py" "<work_dir>/verified.md" --format docx --output "<output_path>"

# Standard PDF (.pdf)
python "<skill_dir>/scripts/formatter.py" "<work_dir>/verified.md" --format pdf --output "<output_path>"

# Academic LaTeX (.tex & .pdf)
python "<skill_dir>/scripts/formatter.py" "<work_dir>/verified.md" --format latex --output "<output_path>"
```

Present the final file link to the user along with a brief summary of:
- Input vs output word count
- Verified semantic accuracy (citations, data points preserved)
- Confirmation of human authenticity pass.

---

## 3. Quick Reference Commands

| Task | Command |
|---|---|
| **Extract Text** | `python scripts/extractor.py input.pdf -o input.txt` |
| **Run Engine** | `python scripts/engine.py -i input.txt -o raw.txt --provider Groq` |
| **Critic Audit** | `python scripts/critic.py --original input.txt --humanized raw.txt` |
| **Compile Output** | `python scripts/formatter.py verified.md --format [md|docx|pdf|latex] -o output` |
