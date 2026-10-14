# Agent-as-Critic Verification & Polish Guide

When operating in **Agent-as-Critic Mode**, you serve as the final quality, truth, and authenticity gate before the user receives their document.

---

## The 4-Tier Critic Review Checklist

### 1. Discrepancy Audit (Factual & Citation Alignment)
Compare the original passage with the raw engine output:
- **Author Citations**: If the original contains `Benigno et al. (2022)`, verify that the humanized version cites `Benigno et al. (2022)` or `Benigno and co-authors (2022)`. Never drop author names or citation years.
- **Numbers and Statistics**: If original contains `2,572 words`, `15%`, `4500`, or `October 2026`, ensure exact numerical fidelity.
- **Domain Acronyms**: Acronyms like `GSCPI`, `CPI`, `WPI`, `RBI`, `GDP`, `SVAR`, `NEER` must be preserved.

### 2. Hallucination Check
- Ensure the model didn't invent external citations, authors, or empirical claims not present in the original text.
- If the model added speculative examples not mentioned in the source, prune them back to the original factual bounds.

### 3. Untranslated Foreign Artifacts
Because the engine routes through Chinese, Japanese, and Finnish:
- Scan for stray CJK characters (`[\u4e00-\u9fff]`), Japanese kana (`[\u3040-\u30ff]`), or Finnish grammatical artifacts (e.g., `-ssa`, `-lle` endings attached to English proper nouns).
- Replace any foreign punctuation artifacts (e.g. Japanese brackets `【】`, ideographic commas `、`, or full-width periods `。`) with standard ASCII punctuation.

### 4. Clean Read, Flow & Burstiness Polish
- **Sentence Variance**: Mix short punchy statements (6–12 words) with compound analytical sentences (18–28 words). Max sentence length is 35 words.
- **Zero Em-Dashes**: Strictly avoid em-dashes (`—`) or double hyphens (`--`). Use commas, parentheses, or separate sentences.
- **Ban AI Connectors**: Remove words like `Furthermore`, `Moreover`, `Additionally`, `In conclusion`, `It is crucial to note`, `delve into`, `testament`.
- **Active Voice**: Prefer active, direct academic voice (`"The data show..."` rather than `"It is demonstrated by the data that..."`).
