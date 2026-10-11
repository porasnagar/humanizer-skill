"""Lema Humanizer Core Pipeline.
Implements the keyless Actor-Critic deconstruction checks, heuristic cleanups,
burstiness & pacing validation, semantic integrity checks, and fallback Google Translate.
Compatible with all AI agents (Antigravity, Claude Code, OpenAI Codex, etc.).
"""
from __future__ import annotations

import math
import re
import time
import unicodedata
from typing import Dict, List, Set, Tuple, Optional

import requests as http_requests

# ── Blacklisted AI words/phrases that detectors scan for ────────────────────────
AI_BLACKLIST = [
    "delve", "tapestry", "furthermore", "moreover", "in conclusion", 
    "it is important to note", "crucial role", "testament", "by understanding", 
    "unlock", "revolutionize", "beacon", "catalyst", "foster", "demystify",
    "in today's digital age", "in the fast-paced world", "not only", "but also",
    "remains a key", "journey", "realm", "realms", "cornerstone",
    "consequently", "therefore", "ultimately", "paradigm", "synergy", "seamless",
    "holistic", "myriad", "plethora", "overarching", "cutting-edge",
    "embark", "confluence", "burgeoning", "with alarming frequency",
    "wealth of", "valuable insights", "underscores the importance",
    "tangible outcomes", "tangible benefits", "tangible impact", "testament to",
    "digital age", "beacon of", "shifting dynamics", "multifaceted", "pivotal",
    "paramount", "underscores", "byzantine", "hampered", "entrenched", "proliferate"
]

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
}

DASHES = ("—", "–", "‒", "‑", "‐", " -- ", "--")
CONJUNCTIONS = (", and ", ", but ", ", yet ", ", so ", ", or ", ", because ")


# ── Sentence Pacing, Burstiness & Heuristic Critic ────────────────────────────

def check_sentence_pacing(text: str, is_list_item: bool = False) -> Tuple[bool, str]:
    """
    Programmatically validates text pacing, burstiness, and anti-AI structure.
    Exact implementation from Lema's production Critic engine.
    """
    if not text or not text.strip():
        return True, ""

    lower_text = text.lower()
    found_banned = []
    for item in AI_BLACKLIST:
        pattern = rf"\b{re.escape(item)}\b"
        if re.search(pattern, lower_text):
            found_banned.append(item)

    if found_banned:
        banned_str = ", ".join([f"'{w}'" for w in found_banned])
        return False, (
            f"CRITICAL FAULT: Contains banned AI words/phrases: {banned_str}. "
            f"Modern detectors scan for these vocabulary hotspots. Replace them "
            f"with natural, direct human alternatives (e.g., replace 'moreover' with 'also' or start sentence directly; "
            f"replace 'landscape' with 'environment' or 'domain'; replace 'underscores' with 'shows' or 'reveals')."
        )

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        return True, ""

    total_words = len(text.split())

    if is_list_item:
        if len(sentences) > 2:
            return False, (
                f"CRITICAL FAULT: The list item was expanded into {len(sentences)} sentences. "
                f"A list item MUST remain a single concise, direct sentence or phrase."
            )
        if total_words > 35:
            return False, (
                f"CRITICAL FAULT: The list item is too wordy ({total_words} words). "
                f"Keep it under 30 words."
            )
        first_word = text.strip().split()[0] if text.strip().split() else ""
        if first_word in ["-", "*", "•", "o", "+"] or re.match(r'^\d+\.$', first_word):
            return False, (
                f"CRITICAL FAULT: Contains a manual list prefix/symbol '{first_word}'. "
                f"Do NOT generate bullet symbols or numbers; output only the clean text."
            )
        return True, ""

    if len(sentences) == 1 and total_words > 28:
        return False, (
            f"CRITICAL FAULT: Entire paragraph of {total_words} words is a single continuous sentence. "
            f"Break this paragraph down into at least 2 or 3 distinct sentences ending in periods."
        )

    for idx, sentence in enumerate(sentences):
        words = sentence.split()
        if len(words) > 36:
            snippet = " ".join(words[:5]) + "..."
            return False, (
                f"CRITICAL FAULT: Sentence {idx+1} ('{snippet}') is a run-on with {len(words)} words. "
                f"Modern AI detectors flag sentences exceeding 35 words. Split into shorter thoughts under 30 words."
            )

    starters = []
    for s in sentences:
        words = s.split()
        if words:
            word = re.sub(r'[^\w]', '', words[0]).lower()
            starters.append(word)

    monitored_starters = {"so", "also", "and", "but", "rather", "however", "this", "it", "then", "indeed"}
    for i in range(len(starters) - 1):
        if starters[i] == starters[i+1] and starters[i] in monitored_starters:
            return False, (
                f"CRITICAL FAULT: Adjacent sentences both start with the transition word '{sentences[i+1].split()[0]}'. "
                f"Vary adjacent sentence starters and avoid repetitive transitions."
            )

    if len(sentences) >= 4:
        lengths = [len(s.split()) for s in sentences]
        has_short = any(l < 16 for l in lengths)
        has_variance = (max(lengths) - min(lengths)) >= 8
        if not (has_short or has_variance):
            return False, (
                f"CRITICAL FAULT: Monotonous sentence flow ({lengths} words). "
                f"Detectors flag this uniform pacing as 'Low Burstiness'. "
                f"Insert at least one short, punchy sentence (8-13 words) and vary sentence lengths."
            )

    for idx, sentence in enumerate(sentences):
        words = sentence.split()
        if words:
            first_word_cleaned = re.sub(r'[^\w]', '', words[0]).lower()
            banned_starters = {"meanwhile", "additionally", "furthermore", "moreover", "consequently"}
            if first_word_cleaned in banned_starters:
                return False, (
                    f"CRITICAL FAULT: Sentence {idx+1} starts with formulaic transition '{words[0]}'. "
                    f"Start naturally without heavy transitional signposts."
                )

    return True, ""


def simulate_ai_detector(text: str, original_text: Optional[str] = None) -> Tuple[int, bool, List[str]]:
    """
    Simulates state-of-the-art AI detection engines (GPTZero, Copyleaks).
    Returns (human_score_0_to_100, is_human, list_of_critiques).
    """
    critiques: List[str] = []
    score = 100

    ok, critique = check_sentence_pacing(text)
    if not ok:
        critiques.append(critique)
        score -= 40

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        if len(lengths) >= 3:
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            std_dev = math.sqrt(variance)
            if std_dev < 3.0:
                critiques.append(f"Low burstiness detected (std dev: {std_dev:.1f}). Sentence lengths are too uniform.")
                score -= 25

        # Check for clinical symmetry / balance
        has_em_dash = any("—" in s or "--" in s for s in sentences)
        if not has_em_dash and len(sentences) >= 4 and all(15 <= l <= 25 for l in lengths):
            critiques.append("Clinical grammatical balance detected. Inject asymmetrical thoughts or em-dash parentheticals.")
            score -= 15

    score = max(0, min(100, score))
    is_human = score >= 80 and len(critiques) == 0
    return score, is_human, critiques


# ── Text Cleanups & Normalization ─────────────────────────────────────────────

def strip_em_dashes(text: str) -> str:
    """Replace em/en dashes with commas and clean up punctuation artifacts."""
    for dash in DASHES:
        text = text.replace(dash, ", ")
    text = re.sub(r",\s*,", ", ", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_pacing_punctuation(text: str) -> str:
    """Clean up pacing punctuation, double commas, and spacing artifacts."""
    if not text:
        return text
    for dash in ["\u2014", "—", "\u2013", "–", "--"]:
        text = text.replace(dash, ", ")
    text = re.sub(r',\s*,', ', ', text)
    text = re.sub(r'\s+,\s+', ', ', text)
    text = re.sub(r'\s+,', ', ', text)
    text = re.sub(r',\s*\.', '.', text)
    text = re.sub(r'\.\s*,', '.', text)
    return re.sub(r' +', ' ', text).strip()


def replace_ai_cliches(text: str) -> str:
    for pattern, replacement in AI_CLICHE_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def enforce_sentence_length(text: str, max_words: int = 38) -> str:
    """Split sentences longer than max_words at a conjunction near midpoint."""
    result: List[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
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
    """Lema offline cleanup: cliche swaps, dash normalization, long sentence splitting."""
    return enforce_sentence_length(strip_em_dashes(replace_ai_cliches(text))).strip()


# ── Keyless Google Translate Chain (Fallback / Multilingual) ──────────────────

_COOLDOWN_SECONDS = 300
_blocked_until: Dict[str, float] = {}

def _chunk_text(text: str, limit: int = 4500) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?。！？])\s+", text):
        if len(current) + len(sentence) + 1 > limit:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def _gtx(text: str, source: str, target: str) -> str:
    resp = http_requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t"},
        data={"q": text},
        timeout=20,
    )
    resp.raise_for_status()
    translated = "".join(seg[0] for seg in resp.json()[0] if seg and seg[0])
    if not translated.strip():
        raise ValueError("empty translation from gtx endpoint")
    return translated


def _scraper(text: str, source: str, target: str) -> str:
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source=source, target=target).translate(text)


def _translate_chunk(text: str, source: str, target: str) -> str:
    errors = []
    for name, fn in (("google-gtx", _gtx), ("google-scraper", _scraper)):
        if time.time() < _blocked_until.get(name, 0):
            continue
        try:
            return fn(text, source, target)
        except Exception as e:
            errors.append(f"{name}: {e}")
            if any(s in str(e).lower() for s in ("429", "too many requests")):
                _blocked_until[name] = time.time() + _COOLDOWN_SECONDS
    raise RuntimeError("Google Translate unavailable: " + "; ".join(errors or ["cooling down"]))


def translate(text: str, source: str, target: str) -> str:
    return " ".join(_translate_chunk(c, source, target) for c in _chunk_text(text))


def translate_chain(text: str, hops: List[str]) -> str:
    for source, target in zip(hops, hops[1:]):
        text = translate(text, source, target)
    return text
