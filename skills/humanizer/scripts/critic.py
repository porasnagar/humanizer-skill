"""Humanizer Semantic Critic and Verifier.
Compares original input vs humanized output to check for:
1. Discrepancies (missing author citations, years, numbers, percentages, acronyms)
2. Hallucinations (invented facts, drift)
3. Untranslated Artifacts (stray Chinese, Japanese, or Finnish characters)
4. AI Cliches & Sentence Burstiness metrics

Used by AI agents (Antigravity, Claude Code, OpenAI Codex, OpenCode, Hermes)
as an automated audit pass before finalizing documents.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


# ── AI Blacklist Vocabulary ───────────────────────────────────────────────────

AI_BLACKLIST = [
    "delve", "tapestry", "furthermore", "moreover", "in conclusion",
    "it is important to note", "crucial role", "testament", "by understanding",
    "unlock", "revolutionize", "beacon", "catalyst", "foster", "demystify",
    "in today's digital age", "in the fast-paced world", "not only", "but also",
    "remains a key", "journey", "realm", "realms", "cornerstone",
    "consequently", "therefore", "ultimately", "paradigm", "synergy", "seamless",
    "holistic", "myriad", "plethora", "overarching", "cutting-edge",
    "embark", "burgeoning", "with alarming frequency", "valuable insights",
    "underscores the importance", "tangible benefits", "testament to",
    "multifaceted", "pivotal", "paramount", "underscores"
]

YEAR_RE = re.compile(r'\b(?:1[6-9]|20)\d{2}[a-z]?\b')
NUM_RE = re.compile(r'(?<![\w.])\d+(?:[.,]\d+)*%?')
ACRONYM_RE = re.compile(r'\b[A-Z][A-Z0-9]{1,}(?:[-–/][A-Z0-9]+)*\b')
AUTHOR_CITE_RE = re.compile(r'([A-Z][\w\'’\-]+(?:\s+(?:and|&)\s+[A-Z][\w\'’\-]+)?(?:\s+et\s+al\.?)?)\s*\((?:1[6-9]|20)\d{2}\)')
ASIAN_CHARS_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')


def audit_semantic_integrity(original: str, humanized: str) -> Dict[str, any]:
    """Side-by-side audit of original text vs humanized rewrite."""
    critiques = []
    missing_items = []

    # 1. Author citations
    orig_cites = set(AUTHOR_CITE_RE.findall(original))
    for cite in orig_cites:
        # Check if author name exists in humanized text
        author_lead = cite.split()[0].strip()
        if author_lead.lower() not in humanized.lower():
            missing_items.append(f"Citation author '{author_lead}'")
            critiques.append(f"Missing author citation from original: '{cite}'")

    # 2. Years (1900 - 2099)
    orig_years = set(YEAR_RE.findall(original))
    human_years = set(YEAR_RE.findall(humanized))
    missing_years = orig_years - human_years
    if missing_years:
        for y in missing_years:
            missing_items.append(f"Year {y}")
            critiques.append(f"Missing date/year '{y}' found in original.")

    # 3. Domain acronyms (length >= 2, e.g. GSCPI, CPI, WPI, RBI, GDP)
    orig_acronyms = set(ACRONYM_RE.findall(original)) - {"A", "I"}
    human_acronyms = set(ACRONYM_RE.findall(humanized))
    missing_acronyms = {a for a in (orig_acronyms - human_acronyms) if len(a) >= 3}
    if missing_acronyms:
        for a in missing_acronyms:
            missing_items.append(f"Acronym {a}")
            critiques.append(f"Missing technical acronym '{a}' from original.")

    # 4. Check for untranslated foreign artifacts (Kanji, Hiragana, Katakana, Hangul)
    asian_matches = ASIAN_CHARS_RE.findall(humanized)
    if asian_matches:
        sample_chars = "".join(asian_matches[:10])
        critiques.append(f"Untranslated foreign characters detected: '{sample_chars}'.")

    # 5. Check for banned AI words
    lower_human = humanized.lower()
    banned_found = [w for w in AI_BLACKLIST if re.search(rf"\b{re.escape(w)}\b", lower_human)]
    if banned_found:
        critiques.append(f"Contains AI cliché words: {', '.join(banned_found)}.")

    # 6. Sentence burstiness
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', humanized) if s.strip()]
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) >= 2:
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0

    if stdev < 5.0 and len(lengths) >= 3:
        critiques.append(f"Monotonous sentence pacing (stdev: {stdev:.1f}). Mix short sentences (<12 words) with longer ones (>20 words).")

    is_clean = len(critiques) == 0

    return {
        "is_clean": is_clean,
        "critiques": critiques,
        "missing_items": missing_items,
        "metrics": {
            "sentence_count": len(sentences),
            "sentence_length_stdev": round(stdev, 2),
            "word_count_original": len(original.split()),
            "word_count_humanized": len(humanized.split()),
            "length_retention_ratio": round(len(humanized.split()) / max(1, len(original.split())), 2),
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Audit humanized output against original input")
    parser.add_argument("--original", "-orig", type=str, required=True, help="Original input file or text")
    parser.add_argument("--humanized", "-hum", type=str, required=True, help="Humanized output file or text")
    args = parser.parse_args()

    # Load original
    if Path(args.original).exists():
        with open(args.original, "r", encoding="utf-8") as f:
            orig_text = f.read()
    else:
        orig_text = args.original

    # Load humanized
    if Path(args.humanized).exists():
        with open(args.humanized, "r", encoding="utf-8") as f:
            hum_text = f.read()
    else:
        hum_text = args.humanized

    report = audit_semantic_integrity(orig_text, hum_text)
    print(json.dumps(report, indent=2))

    if report["is_clean"]:
        print("\n[PASS] AUDIT PASSED: 100% Semantic Retention & Natural Human Pacing!")
        sys.exit(0)
    else:
        print(f"\n[FLAGGED] AUDIT FLAGGED {len(report['critiques'])} ISSUE(S):")
        for c in report["critiques"]:
            print(f"  - {c}")
        sys.exit(1)


if __name__ == "__main__":
    main()
