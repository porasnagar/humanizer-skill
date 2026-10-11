# Agent steps: Lema v2's LLM steps, done by you

Steps 1 and 2 follow the prompts in Lema's `v2/v2_engine.py` (`translate_to_chinese` and
`translate_chinese_to_japanese_with_history`). The guardrails are added so facts survive the Google
Translate hops that come after.

## Guardrails for both steps

- Keep these in their original Latin form, character for character, inside the Chinese and the Japanese:
  citations and author names (`Benigno et al. (2022)`, `(Ihrig et al., 2007)`), years, numbers, acronyms
  (`GSCPI`, `CPI`, `WPI`, `H1`), and proper names and named terms (`Baltic Dry Index`,
  `Reserve Bank of India`, `Suez Canal`). Google Translate passes Latin text through untouched, while
  translated names come back wrong (in testing, "Forbes" came back as "Fukubusu").
- Keep technical terms of art in English as well when a translation could come back as a different
  term (`local projections`, `sign restrictions`, `pass-through`, `output gap`, `input-output`).
- Keep every claim, number and caveat. Deconstruct the structure, not the content.
- Refer to cited authors in the third person (the authors, they). Never write "we/our" about someone
  else's study unless the original is in first person.
- In Japanese, give every sentence an explicit subject. Google fills a missing subject with "we", and
  that "we" then claims the cited authors' work. Vary the subject: author names, 彼ら, この論文,
  この研究, この指数. If every sentence opens with 著者たちは, the English comes back with "The authors"
  over and over; in one 210-sentence essay, 15 sentences started that way.
- One block per marker. Do not merge, split or reorder blocks, and keep the markers.

## Step 1: English to Chinese (zh.md)

From Lema's step 1 prompt:

1. Conceptual deconstruction: do not translate sentence by sentence. Extract the core ideas, discard the
   original structure, and write a completely new, asymmetrical text in Chinese.
2. Remove boilerplate: strip formulaic transitions and cliches ("Furthermore", "Moreover", "In today's
   digital landscape", "In conclusion", "delve into", "plethora"). Delete them; do not translate them.
3. Asymmetrical pacing: vary sentence lengths dramatically. Mix very short, punchy Chinese sentences
   with longer, detailed ones.

## Step 2: Chinese to Japanese (ja.md)

From Lema's step 2 prompt:

1. Translate your Chinese block into highly natural, asymmetrical Japanese.
2. Use the original English (originals.md) only as factual grounding, so nothing is invented or omitted.
   Do not copy its structure or formulaic transitions.
3. No cliches ("Furthermore", "In conclusion" and their equivalents).

## Step 3 onward is the script

`nmt` sends ja.md through Google Translate (Japanese > Finnish > English) and Lema's
`heuristic_cleanup()`: cliche swaps such as furthermore > also, em/en dashes to commas, and sentences over
38 words split. When you fix en.md afterwards, change only what a FLAGGED note lists. Polishing the
English puts back the patterns the pipeline exists to remove.

## Example (start of one block)

- Original: `Forbes (2019) likewise argues that models of domestic inflation need to account for global factors, ...`
- zh.md: `Forbes (2019) 也持类似看法。国内通胀模型，必须把全球因素算进去。...`
- ja.md: `Forbes (2019) も同じ立場だ。国内インフレのモデルには、グローバルな要因を組み込む必要がある。...`
