# Agent-as-Critic Verification & Surgical Fact-Check Guide

When operating in **Agent-as-Critic Mode**, you serve as the final truth and factual verification gate.

> [!CAUTION]
> **GOLDEN RULE: NEVER REWRITE OR PARAPHRASE SENTENCES!**
> The engine output (`raw_output.txt`) has already passed through multi-hop conceptual deconstruction (EN ➔ ZH ➔ JA ➔ FI ➔ EN). Its syntactic structure, n-grams, and perplexity have been humanized to beat Copyleaks, GPTZero, and Turnitin.
> 
> If YOU (the AI Agent) rewrite whole sentences or elevate vocabulary to sound "academic", you will inject standard LLM probability distributions, immediately turning the document into **100% AI**.
> 
> **Your sole responsibility is surgical in-place correction.**

---

## The 4-Step Surgical Correction Checklist

### 1. Author Name & Citation Restoration
Phonetic translation through Chinese and Japanese sometimes alters foreign names. Check the original vs humanized text and surgically restore the exact English spelling:
- `Celasu et al.` ➔ `Celasun et al.`
- `Kareil-Swolo et al.` / `Carrire-Swallow` ➔ `Carrière-Swallow et al.`
- `Fukufusi (2019)` ➔ `Forbes (2019)`
- `Bahnke` ➔ `Bernanke`
- Never drop an author name, co-author (`et al.`), or publication year (`2022`).

### 2. Numbers, Statistics & Acronyms
Scan `scripts/critic.py` output to confirm all quantitative data survived:
- Exact percentages (e.g. `15.4%`), sample dates (e.g. `2020–2022`), and sample counts (e.g. `4,783 words`).
- Domain acronyms: `GSCPI`, `CPI`, `WPI`, `RBI`, `SVAR`, `NEER`, `BDI`.
- If `Global Supply Power Index` appeared, surgically change `Power` to `Chain Pressure`.

### 3. Untranslated Artifacts & Encodings
- Remove any stray Chinese characters (`[\u4e00-\u9fff]`) or Japanese kana.
- Fix any broken UTF-8 accent marks (e.g. `Carrire` ➔ `Carrière`).
- Replace foreign ideographic punctuation (`。`, `、`, `【】`) with standard ASCII.

### 4. Strip Any Leftover Robotic Starters
- If a sentence starts with `So, ` or `Also, `, strip it:
  - `"So, supply chain fluctuations..."` ➔ `"Supply chain fluctuations..."`
  - `"Also, we use a natural experiment..."` ➔ `"We also use a natural experiment..."`

---

## Final Assembly
Take `<work_dir>/raw_output.txt`, apply ONLY the surgical fixes above, and write the verified text to `<work_dir>/verified.md`. Do not perform any stylistic rewriting.
