# Pipeline internals and checks

## Agent mode (default)

`prepare` / `nmt` / `assemble`. The agent running the skill does the two language steps (see
agent-steps.md), and `nmt` uses the bundled `scripts/pipeline.py`: `translate_chain()` and
`heuristic_cleanup()`, both ported from `v2/v2_engine.py` in the Lema project and needing no API key.

Google Translate is tried on the gtx endpoint first, then the deep-translator scraper; a backend that
returns 429 is skipped for five minutes. There is no LLM fallback, so blocks that fail are marked as
errors in `en.md` and you re-run them with `--only`.

`heuristic_cleanup()` output is byte-identical to Lema's original on test documents. `tidy_output()`
in `lema_humanize.py` then removes zero-width characters, normalises non-breaking hyphens, fixes the
" ," spacing that dash stripping leaves, and re-capitalises sentences that the cliche swap lowercased
("Therefore" > "so").

## API mode (optional): `api "<file>" --engine v2|v3|v1`

Needs the separate Lema engine repo, which holds the provider calls and prompts and is not part of
this skill. Point at it with `--lema-home`, `LEMA_HOME`, or `install.py --lema-home`. That repo's
provider runs the whole engine; the agent only runs the command and fixes flagged blocks.

### v2 (default, live site)

`v2/v2_engine.py` `humanize_v2()`: the same function `/api/humanize/text` calls.

1. English to Chinese with an LLM ("conceptual deconstruction", temperature 1.2).
2. Chinese to Japanese with an LLM, given the original English for grounding.
3. Japanese to Finnish, then Finnish to English, with Google Translate (gtx endpoint, then the
   deep-translator scraper, then a literal LLM translation if Google rate-limits).
4. `heuristic_cleanup()`: swaps cliche words (furthermore > also, delve > dig into, ...), turns em/en
   dashes into commas, and splits sentences over 38 words.

Seen in testing on academic text: author names transliterated ("Forbes" > "Fukubusu"), named terms
renamed ("Baltic Dry Index" > "Baltic Sea dry index"), "we" inserted for other authors' work, and a
sentence left in Finnish. The checks below catch these; fixing them is a manual step.

### v3 (experimental)

`v3/v3_engine.py` `humanize_v3()`: same as v2, but the Finnish to English hop is an LLM told to write with
"extreme burstiness". Output reads more casual and drifts further from the original register.

### v1 (actor-critic)

`humanizer.py` `process_text()`: per paragraph, an LLM rewrite using the mode prompt (Academic,
Professional, Conversational, Creative) and intensity, then `check_sentence_pacing()` plus an LLM
"detector" critic; up to 6 rounds with falling temperature (1.35 > 0.95). The skill always passes
`use_sabotage=False`, so Lema's deliberate-typo option is never applied. `--strip-dashes` maps to
`remove_ehm=True`.

### Providers and keys (API mode only)

Read from the environment, then `--env-file`, then `<Lema repo>/.env`, then `<Lema repo>/backend/.env`.
`.env.example` is never read.

| Provider | Key | Default model |
|---|---|---|
| Bedrock | `AWS_BEDROCK_API_KEY` | `openai.gpt-oss-120b` (bedrock-mantle, us-east-1) |
| Groq | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| NVIDIA | `NVIDIA_API_KEY` | `openai/gpt-oss-120b` |
| Cerebras | `CEREBRAS_API_KEY` | `gpt-oss-120b` |

## Integrity checks

The same checks run in both modes. In API mode, hard problems trigger a retry (`--retries`, default 2)
and the attempt with the fewest problems is kept. In agent mode they are reported as FLAGGED notes in
en.md for the agent to fix. Before translating, `nmt` also warns when ja.md is missing an item that
should have stayed in Latin script.

- Hard: an author name from a citation is missing (accent- and hyphen-insensitive); a year or number
  is missing; an acronym (`GSCPI`, `CPI`, `H1`) is missing; a capitalised name or term
  (`Baltic Dry Index`, `Reserve Bank of India`) is missing; foreign-language text appears; the
  paragraph shrinks below 65% of its original length.
- Soft (reported only): the exact citation wording changed (`Benigno et al. (2022) built...` became
  `In 2022, Benigno's team published...`); "we/our" appears where the original had none; the paragraph
  grew past 160%.

## Which blocks are rewritten

Markdown and text: blocks separated by blank lines. Left unchanged: front matter, fenced code, headings,
tables, list items, block quotes, HTML, horizontal rules, blocks containing a URL, lines that are
entirely bold or italic, figure/table captions, "Keywords" lines, blocks under 5 words, blocks under
12 words without closing punctuation, and everything after a References/Bibliography heading. Inline
bold and italics inside rewritten paragraphs are removed.

.docx: the same rules by paragraph, plus heading/title/list styles and paragraphs with hyperlinks. The
new text goes into the paragraph's first run, so run-level formatting inside rewritten paragraphs is
lost; tables are never touched.
