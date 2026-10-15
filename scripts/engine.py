"""Humanizer Multi-Hop Engine.
Core engine for the universal Humanizer skill across all AI agents:
Antigravity, Claude Code, OpenAI Codex, OpenCode, and Hermes.

Pipeline:
  1. Paragraph-by-paragraph Conceptual Deconstruction: English -> Chinese (Groq / Bedrock)
  2. Context-Anchored Conceptual Translation: Chinese -> Japanese (Groq / Bedrock)
  3. Machine Translation in 1 Go: Japanese -> Finnish (Google GTX API)
  4. Machine Translation in 1 Go: Finnish -> English (Google GTX API)
  5. Heuristic Cleanup: Offline regex (em-dashes, AI cliches, sentence burstiness)

Requires:
  GROQ_API_KEY in .env or environment (or AWS_BEDROCK_API_KEY).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests as http_requests

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json

try:
    from dotenv import load_dotenv
    # Automatically search for .env in:
    # 1. Skill root directory (where install.py saves .env)
    # 2. scripts/ directory
    # 3. Current working directory
    _script_path = Path(__file__).resolve()
    _possible_env_paths = [
        _script_path.parent.parent / ".env",
        _script_path.parent / ".env",
        Path.cwd() / ".env",
    ]
    for _p in _possible_env_paths:
        if _p.is_file():
            load_dotenv(_p, override=False)
    load_dotenv(override=False)
except ImportError:
    pass


try:
    import groq
except ImportError:
    groq = None

try:
    import openai
except ImportError:
    openai = None


# ── AI Cliches and Replacements ───────────────────────────────────────────────

AI_CLICHE_REPLACEMENTS = {
    r"\bfurthermore\b": "also",
    r"\bmoreover\b": "also",
    r"\badditionally\b": "also",
    r"\bconsequently\b": "as a result",
    r"\btherefore\b": "so",
    r"\bultimately\b": "in the end",
    r"\bparamount\b": "critical",
    r"\bpivotal\b": "key",
    r"\bdelve\b": "dig into",
    r"\btapestry\b": "mix",
    r"\brealm\b": "area",
    r"\bbeacon\b": "example",
    r"\bcatalyst\b": "trigger",
    r"\bfoster\b": "build",
    r"\bunlock\b": "open up",
    r"\brevolutionize\b": "reshape",
    r"\bdemystify\b": "explain",
    r"\bembark\b": "start",
    r"\bjourney\b": "process",
    r"\bcornerstone\b": "foundation",
    r"\btestament\b": "proof",
    r"\bunderscores\b": "shows",
    r"\bsynergy\b": "cooperation",
    r"\bseamless\b": "smooth",
    r"\bholistic\b": "full",
    r"\bmyriad\b": "many",
    r"\bplethora\b": "large number of",
    r"\boverarching\b": "broad",
    r"\bcutting-edge\b": "advanced",
    r"\bmultifaceted\b": "complex",
    r"\bburgeoning\b": "growing",
    r"\bparadigm\b": "model",
    r"it is important to note(?: that)?": "",
    r"it is worth noting(?: that)?": "",
    r"in today's (?:digital age|world|fast-paced world)": "today",
}

DASHES = ("\u2014", "—", "\u2013", "–", " -- ", "--")
CONJUNCTIONS = (", and ", ", but ", ", yet ", ", so ", ", or ", ", because ")


# ── Heuristic Cleanup ────────────────────────────────────────────────────────

def strip_em_dashes(text: str) -> str:
    """Strictly replace em/en dashes with commas, preserving natural phrasing."""
    for dash in DASHES:
        text = text.replace(dash, ", ")
    text = text.replace("\u2011", "-").replace("\u2010", "-")
    text = re.sub(r',\s*,', ', ', text)
    text = re.sub(r'\s+,\s+', ', ', text)
    text = re.sub(r'\s+,', ', ', text)
    text = re.sub(r',\s*\.', '.', text)
    return text.strip()


def replace_ai_cliches(text: str) -> str:
    """Replace typical machine-learning transition words with direct human equivalents."""
    for pattern, replacement in AI_CLICHE_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def enforce_sentence_length(text: str, max_words: int = 38) -> str:
    """Split sentences longer than max_words at a conjunction to maximize burstiness."""
    result: List[str] = []
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        words = sentence.split()
        if len(words) <= max_words:
            result.append(sentence)
            continue
        midpoint = len(words) // 2
        head, tail = " ".join(words[:midpoint]), " ".join(words[midpoint:])
        joined = f"{head} {tail}"
        split_at = None
        for conj in CONJUNCTIONS:
            found = joined.lower().find(conj, max(0, len(head) - 40))
            if found != -1:
                split_at = (found + 1, len(conj) - 1)
                break
        if split_at:
            pos, skip = split_at
            first, second = joined[:pos].strip().rstrip(","), joined[pos + skip:].strip()
        else:
            first, second = head.rstrip(","), tail
        if not first or not second:
            result.append(sentence)
            continue
        if not first.endswith((".", "!", "?")):
            first += "."
        if second and second[0].islower():
            second = second[0].upper() + second[1:]
        result += [first, second]
    return " ".join(result)


def clean_mt_artifacts(text: str) -> str:
    """
    Cleans Google NMT artifacts that trigger GPTZero detection:
    - Redundant year prefixes: 'In 2022, Benigno et al. (2022)' -> 'Benigno et al. (2022)'
    - Repetitive sentence-initial 'as a result, ', 'so, ', 'also, '
    - Truncated MT idioms: 'This is important.' / 'It is insufficient.'
    - Unicode non-breaking hyphens (\u2011, \u2010)
    """
    if not text:
        return text

    # Normalize hyphens
    text = text.replace('\u2011', '-').replace('\u2010', '-')
    
    # Clean redundant year citations like 'In 2022, Benigno et al. (2022)'
    text = re.sub(
        r'\bIn\s+(\d{4}),\s+([A-Z][a-zA-Z\u00C0-\u024F\s\.-]+(?:\s+et\s+al\.)?\s*\(\1\))',
        r'\2',
        text
    )

    # Clean repetitive 'as a result, '
    text = re.sub(r'(?<=[.!?]\s)[Aa]s a result,\s*', 'Consequently, ', text)
    text = re.sub(r'\b,\s*and as a result\b', ', directly allowing', text)
    text = re.sub(r'\b[Aa]s a result,\s*', '', text)

    # Clean repetitive sentence-initial 'so, ' and 'also, '
    text = re.sub(r'(?<=[.!?]\s)[Ss]o,\s*', 'Hence, ', text)
    text = re.sub(r'(?<=[.!?]\s)[Aa]lso,\s*', 'In addition, ', text)
    text = re.sub(r'\n[Ss]o,\s*', '\nHence, ', text)
    text = re.sub(r'\n[Aa]lso,\s*', '\nIn addition, ', text)

    # Clean formulaic MT fragments
    text = re.sub(r'\s+This is important\.', ' This distinction is critical for empirical identification.', text)
    text = re.sub(r'\s+This point is important\.', ' This divergent response provides key structural insight.', text)
    text = re.sub(r'\s+It is insufficient\.', ' This metric alone remains insufficient.', text)

    # Ensure proper sentence capitalization
    lines = []
    for line in text.splitlines():
        if line.strip() and not line.startswith('#'):
            line = re.sub(r'(^[a-z])', lambda m: m.group(1).upper(), line)
            line = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), line)
        lines.append(line)
    return "\n".join(lines).strip()


def stdev_sentences(text: str) -> float:
    """Calculate standard deviation of sentence lengths in words."""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.split()) > 2]
    if len(sents) < 2:
        return 0.0
    lengths = [len(s.split()) for s in sents]
    mean = sum(lengths) / len(lengths)
    return round((sum((l - mean) ** 2 for l in lengths) / len(lengths)) ** 0.5, 1)


def sentence_lengths(text: str) -> List[int]:
    """Return lengths of all sentences with > 2 words."""
    return [len(s.split()) for s in re.split(r'(?<=[.!?])\s+', text) if len(s.split()) > 2]


BRAIN_PROMPT = """You are an academic editor. The paragraph below ALREADY PASSES Copyleaks at 0% AI. Your ONLY goal is to fix machine translation artifacts, resolve broken syntax, and increase sentence-length variance so GPTZero stops flagging it as AI.

STRICT CONSTRAINTS (breaking these destroys the Copyleaks score):
- Change AT MOST 15% of the words
- NEVER change citations (e.g. Benigno et al. (2022), Carrière-Swallow et al. (2023))
- NEVER change acronyms (GSCPI, CPI, WPI, RBI, BDI, GVC, SVAR, NEER)
- NEVER change any number, year, or named index
- NEVER add transitional phrases (Furthermore, Moreover, Notably)
- NEVER use em-dashes or double hyphens

ALLOWED MICRO-EDITS (pick 2-3 maximum, not all):
A) SPLIT one long sentence (>22 words) at a natural conjunction or comma into a punchy 6-10 word statement plus the remainder.
B) JOIN two consecutive similar-length sentences with a semicolon.
C) Clean formulaic MT phrases and fix any broken translation fragments.

Output ONLY the edited paragraph. No explanation, no markdown, no quotes.

Paragraph:
{para}"""


def pass2_brain_burstiness(paragraph: str, provider: str = "Groq", api_key: Optional[str] = None, model: Optional[str] = None) -> str:
    """
    Pass 2: Surgical micro-edit injection to eliminate GPTZero AI detection.
    Only runs if paragraph has low sentence variance (stdev < 6.0 or span < 12).
    Enforces a strict 35% word change safety ceiling: if exceeded, reverts to Pass 1.
    """
    if len(paragraph.split()) < 15:
        return paragraph

    sd_init = stdev_sentences(paragraph)
    lens_init = sentence_lengths(paragraph)
    
    # If already high variance (stdev >= 6.0 and span >= 12), keep Copyleaks-perfect text
    if sd_init >= 6.0 and lens_init and (max(lens_init) - min(lens_init) >= 12):
        return paragraph

    prompt = BRAIN_PROMPT.format(para=paragraph)
    try:
        raw = call_llm(prompt, provider=provider, api_key=api_key, model=model, temperature=1.05)
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        if "<think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        result = " ".join(l.strip() for l in raw.splitlines() if l.strip())
        
        # Normalize non-breaking hyphens
        result = result.replace('\u2011', '-').replace('\u2010', '-')

        # Safety: revert if > 35% word change (would break Copyleaks)
        orig_w = set(paragraph.lower().split())
        new_w = set(result.lower().split())
        changed = len(orig_w.symmetric_difference(new_w))
        total = max(len(orig_w), len(new_w), 1)
        pct = changed / total
        if pct > 0.35:
            print(f"[Pass 2 Brain] Reverted: {pct:.0%} word change exceeded safety ceiling (preserves Copyleaks 0% AI).", flush=True)
            return paragraph
        return result
    except Exception as e:
        print(f"[Pass 2 Brain] Warning: LLM pass 2 failed ({e}). Keeping Pass 1 text.", flush=True)
        return paragraph


def heuristic_cleanup(text: str) -> str:
    """Full offline heuristic cleanup pipeline."""
    text = replace_ai_cliches(text)
    text = strip_em_dashes(text)
    text = enforce_sentence_length(text)
    text = clean_mt_artifacts(text)
    return text.strip()


# ── LLM Caller (Groq default, Bedrock fallback) ──────────────────────────────

def call_llm(prompt: str, provider: str = "Groq", api_key: Optional[str] = None,
             model: Optional[str] = None, temperature: float = 1.1) -> str:
    """Calls Groq (default) or Bedrock with automatic think-tag stripping and retry."""
    max_retries = 6
    for attempt in range(max_retries):
        try:
            if provider.lower() == "groq":
                if not groq:
                    raise ImportError("groq package not installed. Run: pip install groq")
                key = api_key or os.getenv("GROQ_API_KEY")
                if not key:
                    # Check if Bedrock is available as automatic fallback
                    if os.getenv("AWS_BEDROCK_API_KEY"):
                        return call_llm(prompt, provider="Bedrock", temperature=temperature)
                    raise ValueError("GROQ_API_KEY not found in environment or .env. Please set GROQ_API_KEY.")
                
                client = groq.Groq(api_key=key, timeout=45.0)
                model_name = model or "openai/gpt-oss-120b"
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    top_p=0.95
                )
                msg = resp.choices[0].message
                raw = msg.content or ""
                if not raw and hasattr(msg, "reasoning") and msg.reasoning:
                    raw = msg.reasoning
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                if "<think>" in raw:
                    raw = raw.split("</think>")[-1].strip()
                time.sleep(0.5)
                return raw

            elif provider.lower() == "bedrock":
                if not openai:
                    raise ImportError("openai package not installed. Run: pip install openai")
                key = api_key or os.getenv("AWS_BEDROCK_API_KEY")
                if not key:
                    raise ValueError("AWS_BEDROCK_API_KEY not found in environment or .env.")
                
                client = openai.OpenAI(
                    api_key=key,
                    base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
                    timeout=45.0
                )
                model_name = model or "openai.gpt-oss-120b"
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=4096,
                    top_p=1.0
                )
                msg = resp.choices[0].message
                raw = msg.content or ""
                if not raw and hasattr(msg, "reasoning") and msg.reasoning:
                    raw = msg.reasoning
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                if "<think>" in raw:
                    raw = raw.split("</think>")[-1].strip()
                time.sleep(0.5)
                return raw

            else:
                raise ValueError(f"Unsupported provider: {provider}")

        except Exception as e:
            err = str(e).lower()
            if ("429" in err or "quota" in err or "rate" in err) and os.getenv("AWS_BEDROCK_API_KEY") and provider.lower() == "groq":
                print(f"[Engine] Groq rate limited. Seamlessly switching to Bedrock fallback...", flush=True)
                return call_llm(prompt, provider="Bedrock", temperature=temperature)
            if "429" in err or "quota" in err or "rate" in err:
                wait = min(60, 15 * (attempt + 1))
                print(f"[Engine] Rate limit hit. Sleeping {wait}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            if attempt < max_retries - 1:
                print(f"[Engine] Error: {e}. Retrying in 5s...")
                time.sleep(5)
                continue
            raise e

    raise RuntimeError(f"[Engine] All {max_retries} LLM attempts failed for {provider}.")


# ── Translation Steps ────────────────────────────────────────────────────────

def translate_to_chinese(text: str, provider: str = "Groq", api_key: Optional[str] = None,
                         model: Optional[str] = None) -> str:
    """Step 1: Translate English to Chinese using Conceptual Deconstruction."""
    prompt = (
        "You are an elite, highly authentic human writer. Your goal is to translate the following English text to Chinese, "
        "but you MUST follow these critical rules to destroy any AI fingerprints:\n"
        "1. CONCEPTUAL DECONSTRUCTION: Do NOT perform a sentence-by-sentence translation. Extract the core ideas, discard "
        "the original structure, and write a completely new, asymmetrical text in Chinese.\n"
        "2. REMOVE BOILERPLATE: Strip out formulaic AI transitions and clichés (e.g., 'Furthermore', 'Moreover', 'In today's "
        "digital landscape', 'In conclusion', 'delve into', 'plethora'). Do not translate these concepts; delete them entirely.\n"
        "3. ASYMMETRICAL PACING: Vary sentence lengths dramatically. Mix short, punchy Chinese sentences with longer, detailed ones.\n"
        "4. OUTPUT ONLY THE CHINESE TRANSLATION RESULT.\n\n"
        f"English Text to Deconstruct and Translate:\n\"\"\"\n{text}\n\"\"\""
    )
    return call_llm(prompt, provider=provider, api_key=api_key, model=model, temperature=1.15)


def translate_chinese_to_japanese_with_history(chinese_text: str, original_english: str,
                                              provider: str = "Groq", api_key: Optional[str] = None,
                                              model: Optional[str] = None) -> str:
    """Step 2: Translate Chinese to Japanese with factual context anchoring."""
    prompt = (
        "You are translating Chinese text to Japanese.\n"
        "I am providing the original English text ONLY for factual context (to ensure you don't hallucinate fake research or omit details).\n"
        "DO NOT copy the structure or formulaic transitions of the English text.\n"
        "1. Translate the Chinese text to highly natural, asymmetrical Japanese.\n"
        "2. Ensure there are absolutely NO AI clichés (like 'Furthermore', 'In conclusion').\n"
        "3. Retain all citations, years, numbers, and technical terms accurately.\n"
        "4. Output ONLY the Japanese translation.\n\n"
        f"【Original English Reference (FOR FACTUAL GROUNDING ONLY)】\n{original_english}\n\n"
        f"【Chinese Text to Translate to Japanese】\n{chinese_text}"
    )
    return call_llm(prompt, provider=provider, api_key=api_key, model=model, temperature=1.15)


# ── Google NMT in 1 Go (via Google's GTX Endpoint with LLM Fallback) ──────────

_GOOGLE_AVAILABLE = False  # Set to False by default if public endpoints rate-limit datacenter IPs


def _google_gtx_translate(text: str, source: str, target: str) -> str:
    """Google Translate via translate.googleapis.com gtx endpoint."""
    resp = http_requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t"},
        data={"q": text},
        timeout=3,
    )
    resp.raise_for_status()
    translated = "".join(seg[0] for seg in resp.json()[0] if seg and seg[0])
    if not translated.strip():
        raise ValueError("Empty translation from gtx endpoint")
    return translated


def _llm_translate(text: str, source_lang: str, target_lang: str) -> str:
    lang_names = {'ja': 'Japanese', 'fi': 'Finnish', 'en': 'English'}
    s_name = lang_names.get(source_lang, source_lang)
    t_name = lang_names.get(target_lang, target_lang)
    prompt = (
        f"You are a professional academic translator. Translate the following {s_name} text into natural, precise {t_name}. "
        "Strictly preserve all author citations (e.g. 'Author et al., Year'), data numbers, years, percentages, and technical acronyms. "
        f"Output ONLY the direct {t_name} translation without commentary:\n\n{text}"
    )
    provider = "Bedrock" if os.getenv("AWS_BEDROCK_API_KEY") else "Groq"
    return call_llm(prompt, provider=provider, temperature=0.3)


def translate_with_google(text: str, source: str, target: str) -> str:
    """Translate using Google Translate API or LLM fallback in 1 go."""
    global _GOOGLE_AVAILABLE
    if not text or not text.strip():
        return ""

    def _call_chunk(chunk: str) -> str:
        global _GOOGLE_AVAILABLE
        if _GOOGLE_AVAILABLE:
            try:
                res = _google_gtx_translate(chunk, source, target)
                if res and res.strip():
                    return res
            except Exception:
                _GOOGLE_AVAILABLE = False

        # Direct LLM translation
        try:
            res = _llm_translate(chunk, source, target)
            if res and res.strip():
                return res.strip()
        except Exception as e_llm:
            print(f"[NMT] Translation error: {e_llm}", flush=True)

        return chunk

    # For texts <= 4000 chars, send in 1 call
    if len(text) <= 4000:
        return _call_chunk(text)

    # For longer texts, chunk into ~4000-char pieces at paragraph / sentence boundaries
    parts = [p.strip() for p in re.split(r'(?<=[.!?。！？\n])\s*', text) if p.strip()]
    chunks = []
    current = ""
    for p in parts:
        if len(current) + len(p) + 2 > 4000:
            if current:
                chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)

    results = []
    for i, chunk in enumerate(chunks):
        print(f"[NMT] Translating chunk {i+1}/{len(chunks)} ({source}->{target})...", flush=True)
        res = _call_chunk(chunk)
        results.append(res if res else chunk)
    return "\n\n".join(results)


# ── Main Humanize Entry Point ────────────────────────────────────────────────

def humanize_text(text: str, provider: str = "Groq", api_key: Optional[str] = None,
                  model: Optional[str] = None, cache_path: Optional[Path | str] = None) -> Dict[str, any]:
    """
    Main humanization pipeline:
      1. Robust Paragraph Splitting (splits chunks > 350 words)
      2. Step 1 (EN -> ZH) & Step 2 (ZH -> JA) paragraph-by-paragraph via Groq/Bedrock
      3. Step 3 (JA -> FI) in 1 go via Google GTX NMT
      4. Step 4 (FI -> EN) in 1 go via Google GTX NMT
      5. Step 5 Heuristic Cleanup
    """
    if not text or not text.strip():
        return {"original": text, "humanized": text, "word_count": 0}

    total_words = len(text.split())
    print(f"[Humanizer] Starting Humanizer pipeline on {total_words} words (Provider: {provider})...")

    # Normalize carriage returns
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')

    # Split by paragraph breaks (double newlines first)
    raw_paras = [p.strip() for p in re.split(r'\n\s*\n+', normalized) if p.strip()]
    paragraphs: List[str] = []
    for p in raw_paras:
        # If a block is large (>350 words), split by single newlines or sentence boundaries
        if len(p.split()) > 350:
            sub = [s.strip() for s in p.split('\n') if s.strip()]
            if len(sub) > 1:
                paragraphs.extend(sub)
            else:
                sents = re.split(r'(?<=[.!?])\s+', p)
                cur, cur_wc = [], 0
                for s in sents:
                    cur.append(s)
                    cur_wc += len(s.split())
                    if cur_wc >= 200:
                        paragraphs.append(" ".join(cur))
                        cur, cur_wc = [], 0
                if cur:
                    paragraphs.append(" ".join(cur))
        else:
            paragraphs.append(p)

    print(f"[Humanizer] Document split into {len(paragraphs)} paragraph(s)...")

    # Step 1 & 2: Paragraph by paragraph through LLM
    ja_paragraphs: List[str] = []
    cached_map: Dict[int, str] = {}
    c_path = Path(cache_path) if cache_path else None
    if c_path and c_path.exists():
        try:
            with open(c_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if isinstance(cached_data, dict):
                    cached_map = {int(k): v for k, v in cached_data.items()}
                elif isinstance(cached_data, list):
                    cached_map = {i: v for i, v in enumerate(cached_data)}
            print(f"[Humanizer] Loaded {len(cached_map)} cached paragraph(s) from {c_path}")
        except Exception as e_cache:
            print(f"[Humanizer] Warning loading cache: {e_cache}")

    for i, para in enumerate(paragraphs):
        # Preserve structural elements: headings, markdown formatting, bullet points
        if len(para.split()) <= 6 or para.startswith(('#', '-', '*', '•', '1.', '2.', '3.')):
            ja_paragraphs.append(para)
            continue

        if i in cached_map:
            print(f"[Humanizer] Para {i+1}/{len(paragraphs)} (cached): Using existing translation")
            ja_paragraphs.append(cached_map[i])
            continue

        print(f"[Humanizer] Para {i+1}/{len(paragraphs)} ({len(para.split())}w): Step 1 (ZH) & Step 2 (JA)...")
        zh = translate_to_chinese(para, provider=provider, api_key=api_key, model=model)
        if not zh or not zh.strip():
            zh = para
        ja = translate_chinese_to_japanese_with_history(zh, para, provider=provider, api_key=api_key, model=model)
        if not ja or not ja.strip():
            ja = zh
        ja_paragraphs.append(ja)
        cached_map[i] = ja
        if c_path:
            try:
                c_path.parent.mkdir(parents=True, exist_ok=True)
                with open(c_path, "w", encoding="utf-8") as f:
                    json.dump(cached_map, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    combined_japanese = "\n\n".join(ja_paragraphs)

    # Step 3: Google NMT in 1 go (Japanese to Finnish)
    print(f"[Humanizer] Step 3/4: Translating Japanese to Finnish (Google NMT in 1 go)...")
    finnish = translate_with_google(combined_japanese, source='ja', target='fi')

    # Step 4: Google NMT in 1 go (Finnish back to English)
    print(f"[Humanizer] Step 4/4: Translating Finnish back to English (Google NMT in 1 go)...")
    english = translate_with_google(finnish, source='fi', target='en')

    # Step 5: Heuristic cleanup
    print(f"[Humanizer] Step 5/6: Running heuristic cleanup and MT artifact removal...")
    cleaned = heuristic_cleanup(english)

    # Step 6: Pass 2 Burstiness Injection (GPTZero evasion)
    print(f"[Humanizer] Step 6/6: Running Pass 2 Burstiness Injection (GPTZero evasion)...")
    blocks = [b.strip() for b in cleaned.split('\n\n') if b.strip()]
    p2_blocks = []
    for bi, block in enumerate(blocks):
        if block.startswith(('#', '-', '*', '•', '1.', '2.', '3.')) or len(block.split()) <= 10:
            p2_blocks.append(block)
            continue
        p2_para = pass2_brain_burstiness(block, provider=provider, api_key=api_key, model=model)
        p2_blocks.append(p2_para)
    final_output = "\n\n".join(p2_blocks)

    out_words = len(final_output.split())
    print(f"[Humanizer] Done. Output: {out_words} words.")
    return {
        "original": text,
        "humanized": final_output,
        "word_count": out_words,
    }


def main():
    parser = argparse.ArgumentParser(description="Humanizer Multi-Hop CLI")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input text or markdown file")
    parser.add_argument("--output", "-o", type=str, help="Output destination file")
    parser.add_argument("--provider", "-p", type=str, default="Groq", choices=["Groq", "Bedrock"], help="LLM Provider (default: Groq)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file {args.input} does not exist.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    cache_file = Path(args.output).with_suffix(".ja_cache.json") if args.output else None
    result = humanize_text(text, provider=args.provider, cache_path=cache_file)
    out_text = result["humanized"]

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"[Humanizer] Saved humanized document to: {out_path}")
    else:
        print("\n--- HUMANIZED OUTPUT ---\n")
        print(out_text)


if __name__ == "__main__":
    main()
