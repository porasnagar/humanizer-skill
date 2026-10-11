"""The keyless half of Lema's v2 humanizer pipeline: Google Translate hops and heuristic cleanup.

Ported from `v2/v2_engine.py` in the Lema project (the engine behind the Lema site) so this skill
runs without that repository. Only the steps that need no API key live here; the two LLM steps are
done by the agent using the skill, and the optional `api` mode imports Lema's own engines instead.

Nothing here calls an LLM. `translate_en_chain` is a plain Google Translate round trip, and
`heuristic_cleanup` is offline regex work.
"""
from __future__ import annotations

import re
import time

import requests as http_requests

# ── Cliche replacements (Lema's AI_CLICHE_REPLACEMENTS) ───────────────────────
# Stripping these words outright leaves broken sentences, so each maps to a plain alternative.
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


# ── Heuristic cleanup ─────────────────────────────────────────────────────────

def strip_em_dashes(text: str) -> str:
    """Replace em/en dashes with commas and clean up the artefacts that leaves."""
    for dash in DASHES:
        text = text.replace(dash, ", ")
    text = re.sub(r",\s*,", ", ", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def replace_ai_cliches(text: str) -> str:
    for pattern, replacement in AI_CLICHE_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def enforce_sentence_length(text: str, max_words: int = 38) -> str:
    """Split sentences longer than max_words at a conjunction near the midpoint."""
    result: list[str] = []
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
            found = joined.lower().find(conj, len(head) - 40 if len(head) > 40 else 0)
            if found != -1:
                split_at = (found + 1, len(conj) - 1)
                break
        if split_at:
            pos, skip = split_at
            first, second = joined[:pos].strip().rstrip(","), joined[pos + skip:].strip()
        else:  # no conjunction to break on: hard-split at the midpoint
            first, second = head.rstrip(","), tail
        if not first or not second:
            result.append(sentence)
            continue
        if not first.endswith((".", "!", "?")):
            first += "."
        if second[0].islower():
            second = second[0].upper() + second[1:]
        result += [first, second]
    return " ".join(result)


def heuristic_cleanup(text: str) -> str:
    """Lema's offline cleanup: cliche swaps, no em-dashes, long sentences split."""
    return enforce_sentence_length(strip_em_dashes(replace_ai_cliches(text))).strip()


# ── Google Translate (keyless) ────────────────────────────────────────────────
# Both backends are rate-limited per IP, so a backend that errors is skipped for a cooldown
# rather than hammered.
_COOLDOWN_SECONDS = 300
_blocked_until: dict[str, float] = {}


def _chunk_text(text: str, limit: int = 4500) -> list[str]:
    """Split on sentence boundaries into chunks under Google's ~5000 character limit."""
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
    """translate.googleapis.com gtx endpoint (its own rate limit)."""
    resp = http_requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": source, "tl": target, "dt": "t"},
        data={"q": text},
        timeout=20,
    )
    resp.raise_for_status()
    translated = "".join(seg[0] for seg in resp.json()[0] if seg and seg[0])
    if not translated.strip():
        raise ValueError("empty translation from the gtx endpoint")
    return translated


def _scraper(text: str, source: str, target: str) -> str:
    """deep-translator, which scrapes translate.google.com."""
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
    raise RuntimeError("Google Translate unavailable: " + "; ".join(errors or ["all backends cooling down"]))


def translate(text: str, source: str, target: str) -> str:
    """Translate text between two language codes, chunking long input."""
    return " ".join(_translate_chunk(c, source, target) for c in _chunk_text(text))


def translate_chain(text: str, hops: list[str]) -> str:
    """Translate through a chain of language codes, e.g. ['ja', 'fi', 'en']."""
    for source, target in zip(hops, hops[1:]):
        text = translate(text, source, target)
    return text
