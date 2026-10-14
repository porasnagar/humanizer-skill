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

try:
    from dotenv import load_dotenv
    # 1. Standard search (current working directory and upward)
    load_dotenv()
    # 2. User home directory (~/.env)
    home_env = Path.home() / ".env"
    if home_env.exists():
        load_dotenv(home_env)
    # 3. Skill installation root
    skill_root_env = Path(__file__).resolve().parent.parent / ".env"
    if skill_root_env.exists():
        load_dotenv(skill_root_env)
    # 4. Global project locations
    lema_env = Path.home() / "Documents" / "antigravity projects" / "Lema" / ".env"
    if lema_env.exists():
        load_dotenv(lema_env)
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


def heuristic_cleanup(text: str) -> str:
    """Full offline heuristic cleanup pipeline."""
    text = replace_ai_cliches(text)
    text = strip_em_dashes(text)
    text = enforce_sentence_length(text)
    return text.strip()


# ── LLM Caller (Groq default, Bedrock fallback) ──────────────────────────────

def call_llm(prompt: str, provider: str = "Groq", api_key: Optional[str] = None,
             model: Optional[str] = None, temperature: float = 1.1) -> str:
    """Calls Groq (default) or Bedrock with automatic think-tag stripping and retry."""
    max_retries = 3
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
                raw = resp.choices[0].message.content or ""
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                if "<think>" in raw:
                    raw = raw.split("</think>")[-1].strip()
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
                raw = resp.choices[0].message.content or ""
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                if "<think>" in raw:
                    raw = raw.split("</think>")[-1].strip()
                return raw

            else:
                raise ValueError(f"Unsupported provider: {provider}")

        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err:
                wait = 20 * (attempt + 1)
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


# ── Google NMT in 1 Go (via Google's GTX Endpoint) ───────────────────────────

def _google_gtx_translate(text: str, source: str, target: str) -> str:
    """Google Translate via translate.googleapis.com gtx endpoint (reliable from datacenter IPs)."""
    resp = http_requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t"},
        data={"q": text},
        timeout=20,
    )
    resp.raise_for_status()
    translated = "".join(seg[0] for seg in resp.json()[0] if seg and seg[0])
    if not translated.strip():
        raise ValueError("Empty translation from gtx endpoint")
    return translated


def _google_scrape_translate(text: str, source: str, target: str) -> str:
    """Secondary fallback: deep_translator scraper."""
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        raise RuntimeError(f"Scraper fallback failed: {e}")


def translate_with_google(text: str, source: str, target: str) -> str:
    """Step 3 & 4: Translate using Google Translate API (traditional NMT) in 1 go."""
    if not text or not text.strip():
        return ""

    def _call_chunk(chunk: str, retries: int = 3) -> str:
        for attempt in range(retries):
            # Try official gtx endpoint first
            try:
                res = _google_gtx_translate(chunk, source, target)
                if res and res.strip():
                    return res
            except Exception as e_gtx:
                pass

            # Try scraper fallback
            try:
                res = _google_scrape_translate(chunk, source, target)
                if res and res.strip():
                    return res
            except Exception as e_scrape:
                pass

            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))

        print(f"[NMT] Warning: all translation backends failed for chunk. Returning original.")
        return chunk

    # If text fits in 1 call (<3500 chars), send in 1 go!
    if len(text) <= 3500:
        return _call_chunk(text)

    # For longer texts, chunk into ~3500-char pieces at paragraph / sentence boundaries
    parts = [p.strip() for p in re.split(r'(?<=[.!?。！？\n])\s*', text) if p.strip()]
    chunks = []
    current = ""
    for p in parts:
        if len(current) + len(p) + 2 > 3500:
            if current:
                chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)

    results = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.5)  # Spacing between chunks
        res = _call_chunk(chunk)
        results.append(res if res else chunk)
    return "\n\n".join(results)


# ── Main Humanize Entry Point ────────────────────────────────────────────────

def humanize_text(text: str, provider: str = "Groq", api_key: Optional[str] = None,
                  model: Optional[str] = None) -> Dict[str, any]:
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
    for i, para in enumerate(paragraphs):
        # Preserve structural elements: headings, markdown formatting, bullet points
        if len(para.split()) <= 6 or para.startswith(('#', '-', '*', '•', '1.', '2.', '3.')):
            ja_paragraphs.append(para)
            continue

        print(f"[Humanizer] Para {i+1}/{len(paragraphs)} ({len(para.split())}w): Step 1 (ZH) & Step 2 (JA)...")
        zh = translate_to_chinese(para, provider=provider, api_key=api_key, model=model)
        if not zh or not zh.strip():
            zh = para
        ja = translate_chinese_to_japanese_with_history(zh, para, provider=provider, api_key=api_key, model=model)
        if not ja or not ja.strip():
            ja = zh
        ja_paragraphs.append(ja)

    combined_japanese = "\n\n".join(ja_paragraphs)

    # Step 3: Google NMT in 1 go (Japanese to Finnish)
    print(f"[Humanizer] Step 3/4: Translating Japanese to Finnish (Google NMT in 1 go)...")
    finnish = translate_with_google(combined_japanese, source='ja', target='fi')

    # Step 4: Google NMT in 1 go (Finnish back to English)
    print(f"[Humanizer] Step 4/4: Translating Finnish back to English (Google NMT in 1 go)...")
    english = translate_with_google(finnish, source='fi', target='en')

    # Step 5: Heuristic cleanup
    print(f"[Humanizer] Step 5/5: Running heuristic cleanup...")
    cleaned = heuristic_cleanup(english)

    out_words = len(cleaned.split())
    print(f"[Humanizer] Done. Output: {out_words} words.")
    return {
        "original": text,
        "humanized": cleaned,
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

    result = humanize_text(text, provider=args.provider)
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
