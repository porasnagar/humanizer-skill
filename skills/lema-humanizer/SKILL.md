---
name: lema-humanizer
description: Humanizes AI-sounding writing with the Lema v2 translation-chain pipeline, using the agent itself as the language model - the agent rewrites each paragraph into Chinese and then Japanese, and a bundled script runs Google Translate (Japanese to Finnish to English), a heuristic cleanup, and checks that citations, numbers, acronyms and named terms survived. No API keys needed. Use when the user asks to humanize text, run Lema on a file or pasted text, make writing sound less AI-generated, or lower an AI-detector score for a .md, .txt or .docx file.
---

# Lema Humanizer

You are the language model for this pipeline. You do its two language steps;
[scripts/lema_humanize.py](./scripts/lema_humanize.py) (in this skill's folder) does the rest, with no
API keys.

Per paragraph: English > Chinese (you) > Japanese (you) > Finnish > English (Google Translate) >
heuristic cleanup > integrity checks.

Run the script as `python "<this skill's folder>/scripts/lema_humanize.py" <command> ...`.

## Steps

1. `prepare "<file>"` creates `<name>.lema-work/` next to the file: `originals.md` (the paragraphs to
   rewrite) plus `zh.md` and `ja.md` templates with one `<!-- block N -->` marker per paragraph.
   Headings, tables, lists, captions and everything after a References heading are not included and
   stay unchanged. For pasted text, save it to a .md file first.
2. Fill `zh.md`: replace each TODO with a Chinese rewrite of that block, following step 1 and the
   guardrails in [references/agent-steps.md](./references/agent-steps.md). Read that file first.
   For long documents, write the blocks in batches.
3. Fill `ja.md`: translate each Chinese block into Japanese (step 2 in the same file).
4. `nmt "<work folder>"` runs Google Translate JA > FI > EN and the heuristic cleanup on every block
   and writes `en.md`. Each marker then says `clean` or lists what was lost (FLAGGED).
5. Fix `en.md` block by block, using the smallest edit that restores the original's facts.
   - FLAGGED blocks: put back the author name, year, number, acronym or named term exactly as
     `originals.md` has it; restore the citation format; replace a "we" that claims someone else's
     work with "the authors"; turn leftover foreign words into English.
   - Then read every block, clean or flagged, against `originals.md`. "clean" only means no protected
     token was lost; the meaning can still have flipped ("the gap is not a lack of evidence" came back
     as "there is a lack of evidence"). Swap back technical terms that changed meaning ("local
     projections" > "local forecasts", "pricing-to-market" > "mark-to-market") and qualifiers that
     dropped out ("freight prices" became "prices").
   - Change nothing else. Polishing the English puts back the patterns the pipeline removes.
   - A block that came back partly untranslated is usually a transient Google glitch: re-run
     `nmt "<work folder>" --only N` as it is. Otherwise Google returns the same English for the same
     Japanese, so to redo a garbled block, rewrite its Japanese first, then re-run it.
6. `assemble "<work folder>"` re-checks every block and writes `<name>.lema.<ext>` plus a
   `.report.json` next to the original. It will not overwrite an existing output (`--force` or `-o`).
7. Tell the user the output path, how many blocks were flagged, and what you fixed.

## Other commands

- `preview "<file>"`: list the paragraphs that would be rewritten.
- `verify "<output>" "<original>"`: re-check an output file after manual edits.
- `check-setup`: confirm the bundled pipeline imports, Google Translate is reachable, and whether the
  optional api mode is available.
- `api "<file>"`: only if a separate Lema engine repo is installed (`check-setup` says so). It runs the
  LLM steps through that repo's provider instead of you. Use it only when the user asks, or the
  document is too long to rewrite by hand. Options: `--engine v2|v3|v1`, `--mode`, `--provider`,
  `--workers`, `--retries`; details in [references/engines.md](./references/engines.md).

## Notes

- Needs outbound network to translate.googleapis.com. In a sandboxed agent such as Codex, ask for
  network access or approval to run outside the sandbox.
- The text goes to Google Translate (and to the provider in api mode). Confirm before sending anything
  confidential.
- No detector result is guaranteed, and results vary between runs and between detectors. Do not
  promise the user a score. If they are submitting the text somewhere AI use is restricted, say that
  this does not make AI-written work their own.
- `nmt --hops ja,fi,en` changes the language chain if the user wants to try a different one.
