# lema-humanizer

An [Agent Skill](https://code.claude.com/docs/en/skills) that rewrites AI-sounding prose by running a
multi-language translation chain over it — **using the coding agent itself as the language model**, not
an external API. Works in Claude Code, Codex and Antigravity.

It also checks its own output: after every rewrite it verifies that citations, author names, years,
numbers, acronyms and named terms survived, and flags the paragraphs that lost something. That part
matters more than it sounds — see [What it costs you](#what-it-costs-you).

```
                    you run: prepare
                            │
  original.md ──────────────┴──────────▶  originals.md   (prose blocks, one per marker)
                                                │
  ┌─────────────────────────── the agent writes these ───┴──────────────────┐
  │  zh.md   English ▸ Chinese   "conceptual deconstruction", structure discarded │
  │  ja.md   Chinese ▸ Japanese  grounded against the original so nothing is lost │
  └──────────────────────────────────┬────────────────────────────────────────┘
                            │ you run: nmt
                            ▼
      Google Translate  Japanese ▸ Finnish ▸ English      (keyless, deterministic)
                            │
      heuristic cleanup: cliché swaps, no em-dashes, long sentences split
                            │
      integrity checks  ───▶ en.md with `clean` or `FLAGGED: ...` per block
                            │ the agent fixes what is flagged
                            │ you run: assemble
                            ▼
                    original.lema.md + original.lema.report.json
```

Grammar is rebuilt by passing through languages with different sentence structure, instead of asking a
model to "write like a human" — which produces polished, uniform text that detectors flag easily.

## Why the agent is the model

Most humanizers are a wrapper around an LLM API, so you need keys, you pay per call, and you are
limited to whatever model the service picked. Here the agent that loaded the skill does the two
language steps itself. The script only does the parts that are not language work: the Google Translate
hops, the regex cleanup, parsing and reassembling documents, and the integrity checks.

**No API keys. No per-word cost. No word limit.**

## Install

```bash
git clone https://github.com/porasnagar/humanizer-skill
cd humanizer-skill
pip install -r requirements.txt
python install.py
```

That copies the skill into every tool it finds:

| Tool | Path |
|---|---|
| Claude Code | `~/.claude/skills/lema-humanizer/` |
| Codex | `~/.agents/skills/lema-humanizer/` |
| Antigravity | `~/.gemini/config/skills/lema-humanizer/` |

`python install.py --only claude` installs for one tool, `--uninstall` removes it, `--list` prints the
paths. Then check it:

```bash
python ~/.claude/skills/lema-humanizer/scripts/lema_humanize.py check-setup
```

```
Bundled pipeline: imported (Google Translate hops and heuristic cleanup)
  cleanup check: also, the findings shows a key shift, a proof to the model.
Google Translate: reachable (fi 'Hei maailma' -> 'Hello world')
.docx support: python-docx installed
API mode (optional): no Lema engine repo found, so agent mode only
```

(The cleanup check is deliberately a worst case: it shows the word swaps and the em-dash removal
working, and also that blunt substitution can leave clumsy grammar for you to fix.)

Needs Python 3.9+ and outbound network to `translate.googleapis.com`. In a sandboxed agent such as
Codex, the `nmt` step needs network access or approval to run outside the sandbox.

## Use it

Just ask the agent. The skill's description triggers on requests like *"humanize this file"* or
*"make this sound less AI-generated"*, and the agent then follows the steps in
[`SKILL.md`](skills/lema-humanizer/SKILL.md). In Claude Code you can also invoke it directly:

```
/lema-humanizer path/to/essay.md
```

### Or drive it yourself

```bash
S=~/.claude/skills/lema-humanizer/scripts/lema_humanize.py

python "$S" preview  essay.md             # which paragraphs would be rewritten
python "$S" prepare  essay.md             # creates essay.lema-work/
#   ... fill in zh.md, then ja.md ...
python "$S" nmt      essay.lema-work      # translate, clean up, check
#   ... fix the FLAGGED blocks in en.md ...
python "$S" assemble essay.lema-work      # writes essay.lema.md
python "$S" verify   essay.lema.md essay.md
```

Handy flags: `nmt --only 3,7` redoes single blocks and keeps your edits to the rest;
`nmt --hops ja,fi,en` changes the language chain (try `ja,fi,de,en`); `prepare --force` starts over.

### What is left alone

Only prose paragraphs are rewritten. Headings, tables, list items, block quotes, code fences, figure
captions, "Keywords" lines, anything with a URL, short fragments, and **everything after a References
heading** are copied through byte-for-byte. In `.docx` files the same applies by paragraph style, and
tables are never touched.

## The integrity checks

This is the part most humanizers do not have. Translation chains quietly destroy exactly the things
academic writing cannot afford to lose, so every block is compared against its original.

**Hard problems** (retried automatically in api mode, flagged in agent mode):

| Check | Example it catches |
|---|---|
| Author name from a citation missing | `Forbes` came back as `Fukubusu` |
| Year or number missing | `(2023)` dropped |
| Acronym missing | `GSCPI`, `CPI`, `H1` gone |
| Capitalised name or term missing | `Baltic Dry Index` → `Baltic Sea dry index` |
| Foreign-language text left in | a Finnish sentence survived into the output |
| Paragraph shrank below 65% | content silently omitted |

**Soft problems** (reported, not retried):

| Check | Why it matters |
|---|---|
| Citation wording changed | `Benigno et al. (2022) built...` → `In 2022, Benigno's team published...` |
| First person appeared | `we used...` now claims someone else's study as your own |
| Paragraph grew past 160% | padding, or invented content |

`verify OUTPUT ORIGINAL` re-runs all of it on an edited file, with no network calls.

## What it costs you

Measured on a 2,861-word, 28-paragraph literature review (academic prose, dense with citations):

- **Speed.** The `nmt` step took **24 seconds** for all 28 paragraphs.
- **First pass.** 21 blocks clean, **7 flagged**: two mangled author names, a scrambled citation, a
  dropped `United States` and `CPI`, and three paragraphs where "we" had taken credit for other
  authors' work.
- **What the checks missed.** Reading all 28 against the originals turned up more: one paragraph's
  central claim was **reversed** ("the gap is *not* a lack of evidence" → "there *is* a lack of
  evidence"), and terms had drifted — `pricing-to-market` → `mark-to-market`, `moderates` →
  `mediates`, `local projections` → `local forecasts`, `a simple ranking` → `simple investments`.

**`clean` means no protected token was lost. It does not mean the meaning survived.** Read every
block against the original. That review step is not optional, and it is why the pipeline is built as
staged files you inspect rather than one command that hands you a finished document.

## Does it beat AI detectors?

Sometimes, partly, unpredictably. Honest numbers from the same document, same month:

| Version | GPTZero | Copyleaks |
|---|---|---|
| Human-edited rewrite (no pipeline) | 100% AI | — |
| This pipeline (agent ▸ zh ▸ ja ▸ fi ▸ en) | 100% AI | **47% AI** |
| Lema v1 actor-critic, 3 paragraphs | 100% AI | 100% AI |
| …plus heuristic cleanup | 100% AI | 100% AI |
| …plus an en▸fi▸en round trip | 100% AI | 100% AI |

So: one real improvement on Copyleaks, nothing on GPTZero. **If you need a guaranteed detector score,
this tool will not give you one, and neither will any other.** The published research agrees that
results swing wildly by detector and by month:

- Perkins et al. (2024) found the detectors they tested averaged **39.5% accuracy** on unmodified AI
  text, that simple manipulations cut accuracy a further **17.4%**, and that **33% of human-written
  controls were misclassified**.
  ([paper](https://educationaltechnologyjournal.springeropen.com/articles/10.1186/s41239-024-00487-w))
- Jabarian & Imas (2025) found commercial humanizers pushed GPTZero's miss rate to **~50%+**, while
  Pangram still caught nearly everything — and warn their own numbers will not hold over time.
  ([paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5407424))
- Liang et al. (2023) found detectors flagged writing by **non-native English speakers** as AI at a
  **61.3%** false-positive rate. ([paper](https://arxiv.org/abs/2304.02819))

Treat detector scores as noise, in both directions.

## Appropriate use

This is a text-transformation tool with a verification harness, and it is published as one. Reasonable
uses: studying how transformations affect detector output and content accuracy, rewriting your own
drafts, de-robotifying text you wrote with AI assistance where that is permitted and disclosed.

It will not make AI-written work into your own work, and it is not a way around an academic integrity
policy — where AI use is restricted, the honest move is to write it yourself or disclose the
assistance. Detectors being unreliable cuts both ways: it is also why a flagged score should never be
treated as proof of anything about a person.

## Optional: api mode

If you have the Lema engine repo (not included — it holds the provider calls and prompts), `api` mode
runs the whole pipeline through an LLM provider instead of the agent:

```bash
python install.py --lema-home /path/to/lema
python "$S" api essay.md --engine v2            # translation chain, same as agent mode
python "$S" api essay.md --engine v1 --mode Academic   # actor-critic rewrite, up to 6 rounds
python "$S" api --text "One paragraph."
```

It reads keys from `<lema-home>/.env` (`AWS_BEDROCK_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`,
`CEREBRAS_API_KEY`), never from `.env.example`, and falls back across providers on errors. Details in
[`references/engines.md`](skills/lema-humanizer/references/engines.md).

## Layout

```
install.py                               installs into all three tools
requirements.txt
skills/lema-humanizer/
├── SKILL.md                             what the agent reads and follows
├── agents/openai.yaml                   Codex display metadata
├── references/
│   ├── agent-steps.md                   the two LLM steps, prompts and guardrails
│   └── engines.md                       pipeline internals, checks, block rules
└── scripts/
    ├── lema_humanize.py                 the CLI
    └── pipeline.py                      Google Translate hops + heuristic cleanup (keyless)
```

`pipeline.py` is ported from `v2/v2_engine.py` in the Lema project so this skill runs standalone; its
cleanup output is byte-identical to the original on test documents.

## Credits

The pipeline comes from [Lema](https://trylema.in), an AI text humanizer, whose v2 engine took the
translation-chain approach from Lynote-AI (MIT). This repo packages the keyless half of that engine
as an agent skill and adds the integrity checks and the document handling.

MIT licensed.
