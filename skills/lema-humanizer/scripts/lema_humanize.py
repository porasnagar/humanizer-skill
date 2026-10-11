#!/usr/bin/env python3
"""Lema Humanizer Runner.
Universal AI agent skill for Antigravity, Claude Code, OpenAI Codex, and standalone CLI.

Two primary pipelines:
1. Actor-Critic Deconstruction (Recommended, Default):
   - Agent Mode (Zero API keys): The agent is the AI generator (conceptual deconstruction,
     varying burstiness, removing AI blacklist vocabulary) and the agent/critic validates input vs output.
   - Hybrid Mode: External gpt-oss-120b API generates drafts, and the Agent acts as the Critic
     matching input vs output (citations, numbers, acronyms, detector fingerprints).
   Commands:
     prepare FILE [--pipeline actor-critic]   creates originals.md and draft.md template
     critic WORKDIR                           runs programmatic pacing + semantic integrity + detector simulation
     critic --text "..." [--original "..."]   runs one-shot critic on a single paragraph
     assemble WORKDIR                         re-checks draft.md and writes <name>.lema.<ext>

2. Translation Chain (Lema v2 fallback):
   - English > Chinese (agent) > Japanese (agent) > Finnish > English (Google NMT) > cleanup.
   Commands:
     prepare FILE --pipeline translation     creates originals.md, zh.md, ja.md
     nmt WORKDIR                              Google Translate JA > FI > EN + cleanup
     assemble WORKDIR                         re-checks en.md and writes <name>.lema.<ext>

Other Commands:
  api FILE [--engine actor-critic|v2|v3|v1 ...]  calls external LLM provider
  preview FILE                                   lists prose paragraphs to rewrite
  verify OUTPUT ORIGINAL                         checks output document against original
  check-setup                                    verifies environment, imports, and provider keys
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sys
import threading
import time
import unicodedata
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Try importing from local pipeline.py in same directory or sys.path
try:
    from pipeline import (
        check_sentence_pacing,
        simulate_ai_detector,
        AI_BLACKLIST,
        heuristic_cleanup,
        strip_em_dashes,
        replace_ai_cliches,
        translate_chain,
    )
except ImportError:
    # Look next to this script
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    from pipeline import (
        check_sentence_pacing,
        simulate_ai_detector,
        AI_BLACKLIST,
        heuristic_cleanup,
        strip_em_dashes,
        replace_ai_cliches,
        translate_chain,
    )

PROVIDER_KEYS = {
    "Bedrock": "AWS_BEDROCK_API_KEY",
    "Groq": "GROQ_API_KEY",
    "NVIDIA": "NVIDIA_API_KEY",
    "Cerebras": "CEREBRAS_API_KEY",
}
PROVIDER_ORDER = ["Bedrock", "Groq", "NVIDIA", "Cerebras"]

REF_HEADINGS = {
    "references", "reference list", "bibliography", "works cited",
    "sources", "literature cited", "citations",
}
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
SETEXT_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
LIST_RE = re.compile(r"^\s{0,3}(?:[-*+•]|\d{1,3}[.)]|\(?[a-zA-Z0-9]{1,3}\))\s+")
HR_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
CAPTION_RE = re.compile(r"^(?:table|figure|fig\.?|chart|exhibit)\s*[\dIVX]", re.I)
LINK_RE = re.compile(r"https?://")
XML_BAD_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

YEAR = r"(?:1[6-9]|20)\d{2}[a-z]?"
YEAR_RE = re.compile(r"\b" + YEAR + r"\b")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]*[A-Z0-9](?:[-–/][A-Z0-9]+)*\b")
NAME = r"[A-Z][\w'’\-]+"
NARRATIVE_CITE_RE = re.compile(
    r"(" + NAME + r"(?:\s+(?:and|&)\s+" + NAME + r")?(?:\s+et\s+al\.?)?)(?:['’]s)?"
    r"\s+\((" + YEAR + r"(?:,\s*" + YEAR + r")*)\)"
)
PAREN_CITE_RE = re.compile(r"\(([^()]*?\b" + YEAR + r"\b[^()]*)\)")
AUTHOR_SPLIT_RE = re.compile(r"\s*(?:,|&|\band\b|\bet\s+al\.?)\s*")
CAP_WORD = r"[A-Z][\w'’\-]*"
PROPER_PHRASE_RE = re.compile(CAP_WORD + r"(?:\s+(?:of|for|and|the|de|on)?\s*" + CAP_WORD + r")+")
PHRASE_STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "their", "its", "our", "in", "on", "at", "for",
    "when", "where", "while", "both", "neither", "each", "such", "by", "with", "from", "as", "after",
}
FOREIGN_CHAR_RE = re.compile(r"[äöåÄÖÅЀ-ӿ぀-ヿ㐀-鿿가-힯]")
FINNISH_WORDS = {"ja", "että", "sekä", "jotka", "joka", "tämä", "mutta", "myös",
                 "ovat", "eivät", "kuin", "tai"}
FIRST_PERSON_RE = re.compile(r"\b(?:we|our|ours|ourselves)\b", re.I)
KANA_RE = re.compile(r"[぀-ヿ]")
HAN_RE = re.compile(r"[一-鿿]")

MARKER_RE = re.compile(r"<!--\s*block\s+(\d+)\b.*?-->", re.S)
PLACEHOLDER = "TODO"
INVISIBLE_RE = re.compile(r"[­​‌‍⁠﻿]")
LOWERED_START_RE = re.compile(r"(^|[.!?]\s+)(so|also|as a result|in the end)\b")

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, file=sys.__stderr__, flush=True)


def tidy_output(text: str) -> str:
    """Drop invisible characters, turn non-breaking hyphens into plain ones,
    and re-capitalise sentence starts that lowercase replacements created."""
    if not text:
        return ""
    text = INVISIBLE_RE.sub("", text).replace("‑", "-").replace("‐", "-")
    text = LOWERED_START_RE.sub(lambda m: m.group(1) + m.group(2)[0].upper() + m.group(2)[1:], text)
    text = re.sub(r"[ \t]+([,.;:])", r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


# ── Locating Lema Repo & Configuration ────────────────────────────────────────

def find_lema_home(explicit: str | None = None) -> Path:
    here = Path(__file__).resolve()
    candidates = [explicit, os.environ.get("LEMA_HOME")]
    pointer = here.parent.parent / "lema_home.txt"
    if pointer.exists():
        candidates.append(pointer.read_text(encoding="utf-8").strip())
    if len(here.parents) > 3:
        candidates.append(str(here.parents[3]))
    for c in candidates:
        if c and ((Path(c) / "v2" / "v2_engine.py").exists() or (Path(c) / "humanizer.py").exists()):
            return Path(c)
    # Default fallback to standard known path
    fallback = Path.home() / "Documents" / "antigravity projects" / "Lema"
    if fallback.exists():
        return fallback
    sys.exit(
        "Could not find the Lema repo. "
        "Pass --lema-home <path> or set LEMA_HOME."
    )


def load_keys(lema_home: Path, env_files: list[str]) -> list[str]:
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        for f in env_files:
            if Path(f).exists():
                load_dotenv(f, override=False)
        for f in (lema_home / ".env", lema_home / "backend" / ".env"):
            if f.exists():
                load_dotenv(f, override=False)
    return [p for p in PROVIDER_ORDER if os.environ.get(PROVIDER_KEYS[p])]


def provider_chain(preferred: str, available: list[str], fallback: bool) -> list[str]:
    if preferred not in available:
        sys.exit(
            f"No key for {preferred}: set {PROVIDER_KEYS[preferred]} in the environment or in "
            f"<LEMA_HOME>/.env. Providers with keys: {', '.join(available) or 'none'}."
        )
    if not fallback:
        return [preferred]
    return [preferred] + [p for p in available if p != preferred]


# ── Semantic & Factual Integrity Checks (Input vs Output) ─────────────────────

def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'")
    for dash in ("‐", "‑", "–", "-"):
        s = s.replace(dash, " ")
    return re.sub(r"\s+", " ", s).lower()


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def capitalised_mid_sentence(word: str, text: str) -> bool:
    for m in re.finditer(r"\b" + re.escape(word) + r"\b", text):
        before = text[: m.start()].rstrip()
        if before and before[-1] not in ".!?:":
            return True
    return False


def protected_items(text: str) -> dict:
    names: set[str] = set()
    exact: set[str] = set()
    for m in NARRATIVE_CITE_RE.finditer(text):
        exact.add(squash(m.group(0)))
        for part in AUTHOR_SPLIT_RE.split(m.group(1)):
            if part[:1].isupper():
                names.add(re.sub(r"['’]s$", "", part))
    for m in PAREN_CITE_RE.finditer(text):
        found_cite = False
        for chunk in m.group(1).split(";"):
            cm = re.match(r"\s*(?:e\.g\.,?\s*|see\s+|cf\.\s*)?(.+?),\s*" + YEAR, chunk)
            if not cm:
                continue
            authors = [a for a in AUTHOR_SPLIT_RE.split(cm.group(1)) if a[:1].isupper()]
            if authors:
                found_cite = True
                names.update(authors)
        if found_cite:
            exact.add(squash(m.group(0)))
    phrases: set[str] = set()
    for m in PROPER_PHRASE_RE.finditer(text):
        words = m.group(0).split()
        sentence_start = not text[: m.start()].strip() or text[: m.start()].rstrip()[-1] in ".!?:"
        if sentence_start and words and not capitalised_mid_sentence(words[0], text):
            words = words[1:]
        while words and (words[0].lower() in PHRASE_STOPWORDS or re.search(r"['’]s$", words[0])):
            words = words[1:]
        while words and words[-1].lower() in {"of", "for", "and", "the", "de", "on"}:
            words = words[:-1]
        if words:
            words[-1] = re.sub(r"['’]s$", "", words[-1])
        caps = [w for w in words if w[:1].isupper()]
        if len(caps) >= 2 and not all(w.isupper() or w in names for w in caps):
            phrases.add(" ".join(words))
    return {
        "names": names,
        "numbers": set(NUM_RE.findall(text)) | set(YEAR_RE.findall(text)),
        "acronyms": set(ACRONYM_RE.findall(text)),
        "phrases": phrases,
        "citations": exact,
    }


def lost_items(items: dict, text: str) -> list[str]:
    """Protected items from the original that text no longer contains."""
    folded = fold(text)
    lost = [f"author '{n}'" for n in sorted(items["names"]) if fold(n) not in folded]
    lost += [f"number '{n}'" for n in sorted(items["numbers"])
             if not re.search(r"(?<![\d.,])" + re.escape(n) + r"(?!\d)", text)]
    lost += [f"acronym '{a}'" for a in sorted(items["acronyms"])
             if not re.search(r"(?<![A-Za-z0-9])" + re.escape(a) + r"(?![A-Za-z0-9])", text)]
    lost += [f"name/term '{p}'" for p in sorted(items["phrases"]) if fold(p) not in folded]
    return lost


def untranslated_words(original: str, rewritten: str) -> list[str]:
    before = set(re.findall(r"\S+", original))
    odd = [w for w in re.findall(r"\S+", rewritten) if FOREIGN_CHAR_RE.search(w) and w not in before]
    fi_hits = [w for w in re.findall(r"\b\w+\b", rewritten.lower()) if w in FINNISH_WORDS]
    if len(fi_hits) >= 2:
        odd += fi_hits
    return odd


def check_integrity(original: str, rewritten: str) -> tuple[list[str], list[str]]:
    """Return (hard, soft) problems comparing original input to rewritten output."""
    items = protected_items(original)
    hard: list[str] = []
    soft: list[str] = []
    foreign = untranslated_words(original, rewritten)
    if foreign:
        hard.append("untranslated text: '" + " ".join(foreign[:5]) + "'")
    hard += lost_items(items, rewritten)
    out_squash = squash(rewritten)
    soft += [f"citation wording '{c}'" for c in sorted(items["citations"]) if c not in out_squash]
    if FIRST_PERSON_RE.search(rewritten) and not FIRST_PERSON_RE.search(original):
        soft.append("switched to first person ('we/our')")
    words_in, words_out = len(original.split()), len(rewritten.split())
    if words_in:
        ratio = words_out / words_in
        if ratio < 0.65:
            hard.append(f"length dropped to {ratio:.0%} of original (excessive compression/omission)")
        elif ratio > 1.6:
            soft.append(f"length grew to {ratio:.0%} of original (potential AI fluff)")
    return hard, soft


# ── Document Parsing & Reconstruction ─────────────────────────────────────────

def strip_inline_md(s: str) -> str:
    s = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", r"\1", s)
    return s


def ends_with_sentence_punct(s: str) -> bool:
    s = s.strip().rstrip("\"'”’)*_")
    return bool(s) and s[-1] in ".?!:;"


def heading_text(line: str) -> str:
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
    t = re.sub(r"[*_#`]", "", t)
    t = re.sub(r"^[\dIVX]+[.)]?\s+", "", t.strip())
    return t.strip().rstrip(".:").lower()


def split_markdown(text: str) -> list[dict]:
    lines = text.split("\n")
    segs: list[dict] = []
    i, n = 0, len(lines)
    if lines and lines[0].strip() == "---":
        for j in range(1, n):
            if lines[j].strip() in ("---", "..."):
                segs.append({"kind": "frontmatter", "lines": lines[: j + 1], "line": 1})
                i = j + 1
                break
    while i < n:
        line = lines[i]
        if not line.strip():
            segs.append({"kind": "blank", "lines": [line], "line": i + 1})
            i += 1
            continue
        m = FENCE_RE.match(line)
        if m:
            j = i + 1
            while j < n and not lines[j].lstrip().startswith(m.group(1)):
                j += 1
            segs.append({"kind": "code", "lines": lines[i : j + 1], "line": i + 1})
            i = j + 1
            continue
        if HEADING_RE.match(line):
            segs.append({"kind": "block", "lines": [line], "line": i + 1})
            i += 1
            continue
        j = i + 1
        while j < n and lines[j].strip() and not FENCE_RE.match(lines[j]) and not HEADING_RE.match(lines[j]):
            j += 1
        segs.append({"kind": "block", "lines": lines[i:j], "line": i + 1})
        i = j
    return segs


def classify_markdown(segs: list[dict]) -> None:
    in_refs = False
    for seg in segs:
        if seg["kind"] != "block":
            continue
        lines = seg["lines"]
        first = lines[0].lstrip()
        joined = " ".join(l.strip() for l in lines)
        plain = strip_inline_md(joined)
        is_heading = bool(HEADING_RE.match(lines[0])) or (len(lines) == 2 and SETEXT_RE.match(lines[1]))
        if is_heading:
            in_refs = in_refs or heading_text(lines[0]) in REF_HEADINGS
            seg["kind"] = "heading"
        elif in_refs:
            seg["kind"] = "references"
        elif any(l.lstrip().startswith("|") for l in lines):
            seg["kind"] = "table"
        elif LIST_RE.match(lines[0]):
            seg["kind"] = "list"
        elif first.startswith(">"):
            seg["kind"] = "quote"
        elif first.startswith("<"):
            seg["kind"] = "html"
        elif len(lines) == 1 and HR_RE.match(lines[0]):
            seg["kind"] = "rule"
        elif plain.strip().rstrip(".:").lower() in REF_HEADINGS:
            in_refs = True
            seg["kind"] = "heading"
        elif LINK_RE.search(joined):
            seg["kind"] = "has-link"
        elif re.fullmatch(r"(\*\*|__|\*|_).+\1", joined.strip()):
            seg["kind"] = "emphasised-line"
        elif CAPTION_RE.match(plain) or plain.lower().startswith(("keywords", "key words")):
            seg["kind"] = "caption"
        elif len(plain.split()) < 5 or (not ends_with_sentence_punct(plain) and len(plain.split()) < 12):
            seg["kind"] = "fragment"
        else:
            seg["kind"] = "prose"
            seg["text"] = plain
            seg["had_formatting"] = plain != joined


def docx_targets(doc) -> list[dict]:
    targets = []
    in_refs = False
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if not t:
            continue
        low = t.lower().rstrip(".:")
        style = (p.style.name if p.style is not None else "").lower()
        kind = "prose"
        if low in REF_HEADINGS:
            in_refs, kind = True, "heading"
        elif in_refs:
            kind = "references"
        elif any(h in style for h in ("heading", "title", "subtitle", "caption", "header", "footer", "toc")):
            kind = "heading"
        elif any(h in style for h in ("list", "bullet", "number")) or LIST_RE.match(t):
            kind = "list"
        elif CAPTION_RE.match(t) or low.startswith(("keywords", "key words")):
            kind = "caption"
        elif getattr(p, "hyperlinks", None) or LINK_RE.search(t):
            kind = "has-link"
        elif len(t.split()) < 5 or (not ends_with_sentence_punct(t) and len(t.split()) < 12):
            kind = "fragment"
        targets.append({"kind": kind, "para": i, "line": i + 1, "text": t})
    return targets


def load_source(src: Path) -> dict:
    if not src.exists():
        sys.exit(f"Input file not found: {src}")
    if src.suffix.lower() == ".docx":
        import docx
        doc = docx.Document(str(src))
        items = docx_targets(doc)
        blocks = [t for t in items if t["kind"] == "prose"]
        kept, kinds_source = len(items) - len(blocks), items
        container = {"kind": "docx", "doc": doc}
    else:
        raw = src.read_bytes().decode("utf-8-sig")
        segs = split_markdown(raw.replace("\r\n", "\n"))
        classify_markdown(segs)
        blocks = [s for s in segs if s["kind"] == "prose"]
        kinds_source = [s for s in segs if s["kind"] != "blank"]
        kept = len(kinds_source) - len(blocks)
        container = {"kind": "text", "segs": segs, "newline": "\r\n" if "\r\n" in raw else "\n"}
    for i, b in enumerate(blocks, 1):
        b["id"] = i
    kinds: dict[str, int] = {}
    for s in kinds_source:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    return {"container": container, "blocks": blocks, "kept": kept, "kinds": kinds}


def write_document(container: dict, out: Path, blocks: list[dict]) -> None:
    usable = {b["id"] for b in blocks if b.get("result") and b.get("status") != "error"}
    if container["kind"] == "docx":
        doc = container["doc"]
        for b in blocks:
            if b["id"] not in usable:
                continue
            p = doc.paragraphs[b["para"]]
            text = XML_BAD_RE.sub("", b["result"])
            if p.runs:
                p.runs[0].text = text
                for r in p.runs[1:]:
                    r.text = ""
            else:
                p.text = text
        doc.save(str(out))
    else:
        parts = []
        for s in container["segs"]:
            if s["kind"] == "prose" and s["id"] in usable:
                parts.append(s["result"])
            else:
                parts.extend(s["lines"])
        out.write_text(container["newline"].join(parts), encoding="utf-8", newline="")


def default_output(path: Path) -> Path:
    return path.with_name(f"{path.stem}.lema{path.suffix}")


def write_report(path: Path, meta: dict, blocks: list[dict]) -> None:
    rows = []
    for b in blocks:
        rows.append({
            "block": b["id"], "line": b["line"], "status": b.get("status"), "attempts": b.get("attempts", 1),
            "provider": b.get("provider", "agent"), "missing_hard": b.get("missing_hard", []),
            "missing_soft": b.get("missing_soft", []), "errors": b.get("errors", []),
            "formatting_removed": b.get("had_formatting", False),
            "words_in": len(b["text"].split()), "words_out": len((b.get("result") or "").split()),
            "original": b["text"], "humanized": b.get("result"),
        })
    path.write_text(json.dumps({**meta, "blocks": rows}, indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(meta: dict, blocks: list[dict], kept: int) -> None:
    clean = [b for b in blocks if b.get("status") == "clean"]
    flagged = [b for b in blocks if b.get("status") == "flagged"]
    errors = [b for b in blocks if b.get("status") == "error"]
    w_in = sum(len(b["text"].split()) for b in blocks)
    w_out = sum(len((b.get("result") or "").split()) for b in blocks if b.get("status") != "error")
    print(f"Lema humanizer: {meta['engine']}")
    print(f"Input:   {meta['input']} ({len(blocks)} paragraphs rewritten, {kept} blocks left as-is)")
    print(f"Output:  {meta['output']}")
    print(f"Report:  {meta['report']}")
    took = f"  ({meta['seconds']:.0f}s)" if meta.get("seconds") else ""
    print(f"Words in rewritten paragraphs: {w_in} -> {w_out}{took}")
    print(f"Clean (100% Human): {len(clean)}   Flagged: {len(flagged)}   Errors: {len(errors)}")
    for b in sorted(flagged, key=lambda b: b["line"]):
        issues = b.get("missing_hard", []) + b.get("missing_soft", [])
        print(f"  block {b['id']} (line {b['line']}): " + "; ".join(issues))
    for b in sorted(errors, key=lambda b: b["line"]):
        print(f"  block {b['id']} (line {b['line']}): ERROR {(b.get('errors') or ['unknown'])[-1]}")


# ── Stage Reading & Work Folder Management ────────────────────────────────────

def read_stage(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    parts = MARKER_RE.split(path.read_text(encoding="utf-8-sig"))
    out: dict[int, str] = {}
    for k in range(1, len(parts) - 1, 2):
        body = re.sub(r"<!--.*?-->", "", parts[k + 1], flags=re.S).strip()
        if body and body != PLACEHOLDER:
            out[int(parts[k])] = " ".join(body.split())
    return out


def note_safe(s: str) -> str:
    return s.replace("--", "-").replace(">", "›")


def load_work(workdir: str) -> tuple[Path, dict]:
    work = Path(workdir).resolve()
    meta_path = work / "work.json"
    if not meta_path.exists():
        sys.exit(f"{work} is not a Lema work folder (no work.json). Run 'prepare' first.")
    return work, json.loads(meta_path.read_text(encoding="utf-8"))


def parse_ids(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    return {int(x) for x in re.split(r"[,\s]+", spec.strip()) if x}


# ── Core Commands ─────────────────────────────────────────────────────────────

def cmd_prepare(args) -> int:
    src = Path(args.file).resolve()
    parsed = load_source(src)
    blocks = parsed["blocks"]
    if not blocks:
        sys.exit("No prose paragraphs found to rewrite.")
    work = Path(args.workdir).resolve() if args.workdir else src.with_name(src.stem + ".lema-work")
    if work.exists():
        if not (work / "work.json").exists():
            sys.exit(f"{work} exists and is not a Lema work folder; choose another --workdir.")
        if not args.force:
            sys.exit(f"{work} already exists (it may hold drafts). Use --force to start over.")
        shutil.rmtree(work)
    work.mkdir(parents=True)
    meta = {
        "source": str(src),
        "pipeline": args.pipeline,
        "created": datetime.now().isoformat(timespec="seconds"),
        "blocks": [{"id": b["id"], "line": b["line"], "original": b["text"],
                    "formatting_removed": b.get("had_formatting", False)} for b in blocks],
    }
    (work / "work.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # originals.md is common to all pipelines
    orig_lines = [
        f"# Original prose paragraphs extracted from {src.name} (read-only)",
        "# Citations, numbers, acronyms, and facts in these blocks must be retained 100%.",
        ""
    ]
    for b in blocks:
        orig_lines += [f"<!-- block {b['id']} | line {b['line']} -->", b["text"], ""]
    (work / "originals.md").write_text("\n".join(orig_lines), encoding="utf-8")

    if args.pipeline == "actor-critic":
        draft_lines = [
            f"# Lema Actor-Critic: English Humanized Rewrites for {src.name}",
            "# Instructions for the Agent (Actor):",
            "# 1. Rewrite each block using Lema deconstruction principles (Academic, Professional, etc.).",
            "# 2. Ensure high burstiness (mix 8-13 word sentences with 18-28 word sentences; max 35 words).",
            "# 3. Never use banned AI words (delve, tapestry, furthermore, moreover, realm, etc.).",
            "# 4. Preserve 100% of all citations (Author et al., Year), numbers, acronyms, and key terms.",
            "# 5. Keep every <!-- block N --> marker exactly as it is.",
            "# 6. When all blocks are filled, run: python lema_humanize.py critic \"" + str(work) + "\"",
            ""
        ]
        for b in blocks:
            draft_lines += [f"<!-- block {b['id']} | line {b['line']} -->", PLACEHOLDER, ""]
        (work / "draft.md").write_text("\n".join(draft_lines), encoding="utf-8")
        print(f"Prepared {len(blocks)} paragraphs ({sum(len(b['text'].split()) for b in blocks)} words) in '{work.name}'")
        print(f"Pipeline: Actor-Critic (Agent-as-Generator & Agent-as-Critic)")
        print(f"Work folder: {work}")
        print("Next: Fill draft.md with your humanized rewrites, then run: critic \"%s\"" % work)
    else: # translation pipeline
        for name, header in [
            ("zh.md", "Step 1: replace each TODO with a Chinese rewrite (references/agent-steps.md)."),
            ("ja.md", "Step 2: replace each TODO with a Japanese translation (references/agent-steps.md).")
        ]:
            lines = [f"# {header}", "# Keep every <!-- block N --> marker exactly as it is.", ""]
            for b in blocks:
                lines += [f"<!-- block {b['id']} | line {b['line']} -->", PLACEHOLDER, ""]
            (work / name).write_text("\n".join(lines), encoding="utf-8")
        print(f"Prepared {len(blocks)} paragraphs in '{work.name}' (Translation Chain)")
        print("Next: Fill zh.md, then ja.md, then run: nmt \"%s\"" % work)

    return 0


def cmd_critic(args) -> int:
    """Evaluates text or an entire workdir using Lema's complete Critic engine:
    1. Programmatic pacing & burstiness (check_sentence_pacing)
    2. Semantic & factual integrity audit (check_integrity)
    3. AI detector simulation (simulate_ai_detector)
    """
    if args.text:
        original = args.original or ""
        text = tidy_output(args.text)
        pacing_ok, pacing_critique = check_sentence_pacing(text)
        hard, soft = check_integrity(original, text) if original else ([], [])
        score, is_human, detector_critiques = simulate_ai_detector(text, original)
        
        print("\n=== LEMA CRITIC AUDIT REPORT ===")
        print(f"Simulated Human Authenticity Score: {score}/100")
        print(f"Verdict: {'100% HUMAN PASS' if (pacing_ok and not hard and is_human) else 'FLAGGED AS AI'}")
        
        all_issues = []
        if not pacing_ok:
            all_issues.append(f"[PACING] {pacing_critique}")
        if hard:
            all_issues.append(f"[LOST DATA / HARD] {'; '.join(hard)}")
        if soft:
            all_issues.append(f"[DRIFT / SOFT] {'; '.join(soft)}")
        if detector_critiques:
            all_issues.extend([f"[DETECTOR] {c}" for c in detector_critiques])
            
        if all_issues:
            print("\nActionable Critic Feedback:")
            for issue in all_issues:
                print(f"  • {issue}")
            return 1
        else:
            print("\nAll checks passed! Text shows natural asymmetry, high burstiness, and zero AI fingerprints.")
            return 0

    work, meta = load_work(args.workdir)
    blocks = meta["blocks"]
    only = parse_ids(args.only)
    targets = [b for b in blocks if only is None or b["id"] in only]

    target_file = work / "draft.md"
    if not target_file.exists():
        target_file = work / "en.md"
    if not target_file.exists():
        sys.exit(f"Neither draft.md nor en.md found in {work}. Run 'prepare' and fill draft.md first.")

    drafts = read_stage(target_file)
    originals = {b["id"]: b["original"] for b in blocks}

    counts = {"clean": 0, "flagged": 0, "todo": 0}
    report_rows = []
    updated_lines = [
        f"# Lema Critic Audit: {target_file.name}",
        "# Review the FLAGGED blocks below and fix only what the critique specifies.",
        "# When all blocks say 'clean', run: assemble \"" + str(work) + "\"",
        ""
    ]

    for b in blocks:
        bid = b["id"]
        orig = originals[bid]
        rewritten = drafts.get(bid)

        if not rewritten or rewritten == PLACEHOLDER:
            counts["todo"] += 1
            status = "TODO"
            note = "TODO: Not written yet"
            body = PLACEHOLDER
            report_rows.append(f"  block {bid} (line {b['line']}): NOT WRITTEN YET")
        else:
            rewritten_tidy = tidy_output(rewritten)
            pacing_ok, pacing_critique = check_sentence_pacing(rewritten_tidy)
            hard, soft = check_integrity(orig, rewritten_tidy)
            score, is_human, det_critiques = simulate_ai_detector(rewritten_tidy, orig)

            issues = []
            if hard:
                issues.extend(hard)
            if not pacing_ok:
                issues.append(pacing_critique)
            if det_critiques:
                issues.extend(det_critiques)
            if soft:
                issues.extend(soft)

            if not issues and pacing_ok and not hard and is_human:
                counts["clean"] += 1
                status = "clean"
                note = "clean (100% Human)"
            else:
                counts["flagged"] += 1
                status = "flagged"
                note = f"FLAGGED: {'; '.join(issues)}"
                report_rows.append(f"  block {bid} (line {b['line']}): FLAGGED - " + "; ".join(issues))

            body = rewritten_tidy

        updated_lines += [f"<!-- block {bid} | line {b['line']} | {note_safe(note)} -->", body, ""]

    target_file.write_text("\n".join(updated_lines), encoding="utf-8")

    print(f"\nLema Critic evaluated {len(blocks)} blocks:")
    print(f"  Clean (100% Human): {counts['clean']}")
    print(f"  Flagged (Needs revision): {counts['flagged']}")
    print(f"  Pending (TODO): {counts['todo']}")
    print(f"\nUpdated: {target_file}")

    if report_rows:
        print("\nActionable Critic Feedback:")
        for r in report_rows[:20]:
            print(r)
        if len(report_rows) > 20:
            print(f"  ... and {len(report_rows) - 20} more (see {target_file.name} for full inline notes)")
        print("\nNext step for Agent:")
        print("  1. Inspect FLAGGED blocks in draft.md.")
        print("  2. Apply targeted edits: restore lost citations/numbers, replace banned words, vary sentence lengths.")
        print("  3. Re-run: critic \"%s\" until all blocks pass!" % work)
        return 1
    else:
        print("\nSUCCESS: All paragraphs passed Lema Critic validation!")
        print("Next: assemble \"%s\"" % work)
        return 0


def cmd_assemble(args) -> int:
    work, meta = load_work(args.workdir)
    src = Path(meta["source"])
    parsed = load_source(src)
    blocks = parsed["blocks"]
    if [b["text"] for b in blocks] != [m["original"] for m in meta["blocks"]]:
        sys.exit(f"{src.name} changed since prepare; run prepare again.")

    target_file = work / "draft.md"
    if not target_file.exists():
        target_file = work / "en.md"
    if not target_file.exists():
        sys.exit(f"Neither draft.md nor en.md found in {work}.")

    drafts = read_stage(target_file)
    missing = [b["id"] for b in blocks if b["id"] not in drafts]
    if missing:
        sys.exit(f"{target_file.name} has no text for block(s) {', '.join(map(str, missing))}.")

    for b in blocks:
        b["result"] = tidy_output(drafts[b["id"]])
        hard, soft = check_integrity(b["text"], b["result"])
        pacing_ok, pacing_critique = check_sentence_pacing(b["result"])
        if not pacing_ok:
            hard.append(pacing_critique)
        b.update(
            status="flagged" if (hard or soft) else "clean",
            missing_hard=hard,
            missing_soft=soft,
            attempts=1,
            provider="agent" if meta.get("pipeline") == "actor-critic" else "agent+google"
        )

    out = Path(args.output).resolve() if args.output else default_output(src)
    if out.exists() and not args.force:
        sys.exit(f"{out} already exists. Use --force to overwrite it or -o to specify a new path.")

    write_document(parsed["container"], out, blocks)
    report = out.with_name(out.stem + ".report.json")
    info = {
        "engine": f"Lema Humanizer ({meta.get('pipeline', 'actor-critic')} pipeline)",
        "pipeline": meta.get("pipeline", "actor-critic"),
        "input": str(src),
        "output": str(out),
        "report": str(report),
        "work": str(work),
        "finished": datetime.now().isoformat(timespec="seconds")
    }
    write_report(report, info, blocks)
    print_summary(info, blocks, parsed["kept"])
    return 0


# ── Translation Chain (Lema v2 fallback) ──────────────────────────────────────

def cmd_nmt(args) -> int:
    work, meta = load_work(args.workdir)
    blocks = meta["blocks"]
    only = parse_ids(args.only)
    targets = [b for b in blocks if only is None or b["id"] in only]
    en_path = work / "en.md"
    if en_path.exists() and only is None and not args.force:
        sys.exit("en.md already exists. Use --only N,M to redo specific blocks, or --force to redo all.")
    zh, ja = read_stage(work / "zh.md"), read_stage(work / "ja.md")
    problems = []
    for b in targets:
        i = b["id"]
        if i not in zh or not HAN_RE.search(zh[i]):
            problems.append(f"block {i}: zh.md has no Chinese text yet")
        if i not in ja:
            problems.append(f"block {i}: ja.md has no text yet")
        elif not KANA_RE.search(ja[i]):
            problems.append(f"block {i}: ja.md text has no kana (not Japanese)")
    if problems:
        print("Not ready for translation:\n  " + "\n  ".join(problems))
        return 1

    def one(b: dict) -> str:
        chain = translate_chain(ja[b["id"]], ["ja", "fi", "en"])
        return tidy_output(heuristic_cleanup(chain))

    results: dict[int, dict] = {}
    log(f"Translating JA > FI > EN on {len(targets)} blocks...")
    sink = sys.__stderr__ if args.verbose else open(os.devnull, "w", encoding="utf-8")
    with contextlib.redirect_stdout(sink):
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(one, b): b for b in targets}
            for fut in as_completed(futures):
                b = futures[fut]
                try:
                    results[b["id"]] = {"text": fut.result()}
                except Exception as e:
                    results[b["id"]] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    if not args.verbose:
        sink.close()

    existing = read_stage(en_path) if only is not None else {}
    lines = [
        "# Step 3 output: English after Google Translate (JA > FI > EN) and Lema cleanup.",
        "# Fix only what a FLAGGED note lists, keep the markers, then run assemble.",
        ""
    ]
    counts = {"clean": 0, "flagged": 0, "error": 0}
    report = []
    for b in blocks:
        r = results.get(b["id"]) or ({"text": existing[b["id"]]} if b["id"] in existing else
                                     {"error": "not translated yet"})
        if "error" in r:
            status, issues, body = "error", [r["error"]], PLACEHOLDER
        else:
            hard, soft = check_integrity(b["original"], r["text"])
            pacing_ok, pacing_critique = check_sentence_pacing(r["text"])
            if not pacing_ok:
                hard.append(pacing_critique)
            issues, body = hard + soft, r["text"]
            status = "flagged" if issues else "clean"
        counts[status] += 1
        note = "clean" if status == "clean" else f"{status.upper()}: " + "; ".join(issues)
        lines += [f"<!-- block {b['id']} | line {b['line']} | {note_safe(note)} -->", body, ""]
        if status != "clean":
            report.append(f"  block {b['id']} (line {b['line']}): {status} - " + "; ".join(issues))
    en_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(blocks)} blocks in en.md: {counts['clean']} clean, {counts['flagged']} flagged, {counts['error']} errors")
    for row in report[:20]:
        print(row)
    print(f"Next: fix flagged blocks in en.md, then run: assemble \"{work}\"")
    return 0


# ── API Mode (External LLM Generator) ─────────────────────────────────────────

def cmd_api(args) -> int:
    """Invokes external LLM (AWS Bedrock, Groq, Cerebras, NVIDIA) for high-temp mutations."""
    lema_home = find_lema_home(args.lema_home)
    available_keys = load_keys(lema_home, args.env_file)
    providers = provider_chain(args.provider, available_keys, not args.no_fallback)

    sys.path.insert(0, str(lema_home))
    if args.engine in ("actor-critic", "v1"):
        try:
            from humanizer import process_text, humanize_paragraph
        except ImportError as e:
            sys.exit(f"Could not import humanizer.py from {lema_home}: {e}")

        def run_fn(text: str, prov: str, mod: str | None) -> str:
            out, _ = process_text(
                input_text=text,
                api_key="",
                mode=args.mode,
                intensity=args.intensity,
                provider=prov,
                model=mod,
                use_sabotage=False,
                remove_ehm=args.strip_dashes
            )
            return out
    elif args.engine == "v2":
        try:
            from v2.v2_engine import humanize_v2
            run_fn = lambda t, p, m: humanize_v2(text=t, provider=p, api_key=None, model=m)["humanized"]
        except ImportError as e:
            sys.exit(f"Could not import v2 engine: {e}")
    else: # v3
        try:
            from v3.v3_engine import humanize_v3
            run_fn = lambda t, p, m: humanize_v3(text=t, provider=p, api_key=None, model=m)["humanized"]
        except ImportError as e:
            sys.exit(f"Could not import v3 engine: {e}")

    if args.text:
        print(f"Generating rewrite with {args.engine} ({args.provider})...")
        out = tidy_output(run_fn(args.text, args.provider, args.model))
        print("\n--- REWRITTEN OUTPUT ---")
        print(out)
        print("\n--- RUNNING CRITIC ON OUTPUT ---")
        pacing_ok, pacing_critique = check_sentence_pacing(out)
        hard, soft = check_integrity(args.text, out)
        score, is_human, det = simulate_ai_detector(out, args.text)
        print(f"Human Authenticity Score: {score}/100")
        if pacing_ok and not hard and is_human:
            print("Verdict: 100% HUMAN PASS")
        else:
            print(f"Verdict: FLAGGED ({'; '.join(hard + ([pacing_critique] if not pacing_ok else []) + det)})")
        return 0

    if not args.file:
        sys.exit("api: Specify a file or --text")

    src = Path(args.file).resolve()
    parsed = load_source(src)
    blocks = parsed["blocks"]
    if not blocks:
        sys.exit("No prose paragraphs found to rewrite.")

    # In Hybrid Mode, we prepare the work folder and fill draft.md with candidates,
    # then run the Critic so the Agent can act as the Critic!
    work = src.with_name(src.stem + ".lema-work")
    if not work.exists() or args.force:
        args_prep = argparse.Namespace(file=str(src), pipeline="actor-critic", workdir=str(work), force=True)
        cmd_prepare(args_prep)

    print(f"Calling {args.provider} ({args.model or 'default model'}) on {len(blocks)} blocks...")
    drafts: dict[int, str] = {}
    for b in blocks:
        log(f"Generating candidate for block {b['id']}/{len(blocks)}...")
        try:
            drafts[b["id"]] = tidy_output(run_fn(b["text"], args.provider, args.model))
        except Exception as e:
            log(f"Error on block {b['id']}: {e}")
            drafts[b["id"]] = b["text"]

    draft_lines = [
        f"# Lema Hybrid Mode: Candidates generated by {args.provider} ({args.engine})",
        "# The Agent acts as the Critic! Review FLAGGED blocks against originals.md.",
        ""
    ]
    for b in blocks:
        draft_lines += [f"<!-- block {b['id']} | line {b['line']} -->", drafts.get(b["id"], PLACEHOLDER), ""]
    (work / "draft.md").write_text("\n".join(draft_lines), encoding="utf-8")

    # Run Critic immediately
    args_critic = argparse.Namespace(workdir=str(work), only=None, text=None, original=None)
    cmd_critic(args_critic)

    print("\nHybrid API generation complete! The Agent should now review draft.md, match input vs output, and fix any FLAGGED blocks.")
    return 0


# ── Other Utilities ───────────────────────────────────────────────────────────

def cmd_preview(args) -> int:
    parsed = load_source(Path(args.file).resolve())
    blocks = parsed["blocks"]
    print(f"{len(blocks)} paragraphs would be rewritten; left as-is: " +
          ", ".join(f"{k} {v}" for k, v in sorted(parsed["kinds"].items()) if k != "prose"))
    for b in blocks:
        words = b["text"].split()
        print(f"  block {b['id']} (line {b['line']}, {len(words)} words): {' '.join(words[:10])} ...")
    return 0


def cmd_verify(args) -> int:
    new, old = Path(args.output).resolve(), Path(args.original).resolve()
    pairs = []
    if new.suffix.lower() == ".docx":
        import docx
        old_doc, new_doc = docx.Document(str(old)), docx.Document(str(new))
        if len(old_doc.paragraphs) != len(new_doc.paragraphs):
            sys.exit("Paragraph count differs between the files.")
        for t in docx_targets(old_doc):
            if t["kind"] == "prose":
                pairs.append((t["line"], t["text"], new_doc.paragraphs[t["para"]].text))
    else:
        old_segs = split_markdown(old.read_bytes().decode("utf-8-sig").replace("\r\n", "\n"))
        new_segs = split_markdown(new.read_bytes().decode("utf-8-sig").replace("\r\n", "\n"))
        classify_markdown(old_segs)
        old_blocks = [s for s in old_segs if s["kind"] != "blank"]
        new_blocks = [s for s in new_segs if s["kind"] != "blank"]
        for o, n in zip(old_blocks, new_blocks):
            if o["kind"] == "prose":
                pairs.append((n["line"], o["text"], strip_inline_md(" ".join(l.strip() for l in n["lines"]))))
    bad = 0
    for line, orig, rewritten in pairs:
        hard, soft = check_integrity(orig, rewritten)
        pacing_ok, pacing_critique = check_sentence_pacing(rewritten)
        if hard or soft or not pacing_ok:
            bad += 1
            issues = hard + soft + ([pacing_critique] if not pacing_ok else [])
            print(f"  line {line}: " + "; ".join(issues))
    print(f"Checked {len(pairs)} paragraphs: {len(pairs) - bad} clean, {bad} with issues.")
    return 0


def cmd_check_setup(args) -> int:
    lema_home = find_lema_home(args.lema_home)
    print(f"Lema repository: {lema_home}")
    available = load_keys(lema_home, args.env_file)
    print(f"Active Provider Keys: {', '.join(available) or 'None (Agent mode does not need any)'}")
    try:
        import docx
        print("python-docx: Installed (Full .docx parsing and reassembly enabled)")
    except ImportError:
        print("python-docx: Not installed (Plain text and markdown supported; run 'pip install python-docx' for .docx)")
    print("Pipeline modules: Loaded (Actor-Critic, check_sentence_pacing, simulate_ai_detector, heuristic_cleanup)")
    return 0


# ── Main Entrypoint ───────────────────────────────────────────────────────────

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lema-home", help="path to Lema repository")
    common.add_argument("--verbose", action="store_true", help="verbose engine progress output")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # prepare
    p = sub.add_parser("prepare", parents=[common], help="split a file into prose blocks and generate work folder")
    p.add_argument("file", help="input file (.docx, .md, .txt)")
    p.add_argument("--pipeline", choices=["actor-critic", "translation"], default="actor-critic",
                   help="actor-critic = direct deconstruction with draft.md (default); translation = zh.md/ja.md")
    p.add_argument("--workdir", help="custom work folder path")
    p.add_argument("--force", action="store_true", help="overwrite existing work folder")
    p.set_defaults(func=cmd_prepare)

    # critic
    p = sub.add_parser("critic", parents=[common], help="run pacing, burstiness, integrity, and detector check")
    p.add_argument("workdir", nargs="?", help="work folder containing draft.md and originals.md")
    p.add_argument("--text", help="evaluate a single text paragraph")
    p.add_argument("--original", help="original input paragraph (for factual/citation diff matching)")
    p.add_argument("--only", help="comma-separated block IDs to evaluate")
    p.set_defaults(func=cmd_critic)

    # assemble
    p = sub.add_parser("assemble", parents=[common], help="verify draft blocks and assemble final document")
    p.add_argument("workdir", help="work folder")
    p.add_argument("-o", "--output", help="custom output path")
    p.add_argument("--force", action="store_true", help="overwrite existing output file")
    p.set_defaults(func=cmd_assemble)

    # nmt (translation fallback)
    p = sub.add_parser("nmt", parents=[common], help="run translation chain JA > FI > EN (v2 fallback)")
    p.add_argument("workdir", help="work folder")
    p.add_argument("--only", help="comma-separated block numbers to redo")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_nmt)

    # api
    p = sub.add_parser("api", parents=[common], help="generate mutations using external LLM provider")
    p.add_argument("file", nargs="?", help="file to process")
    p.add_argument("--text", help="rewrite a single string")
    p.add_argument("-o", "--output", help="output path")
    p.add_argument("--engine", choices=["actor-critic", "v1", "v2", "v3"], default="actor-critic")
    p.add_argument("--mode", default="Academic", choices=["Academic", "Professional", "Conversational", "Creative"])
    p.add_argument("--intensity", default="Enhanced", choices=["Standard", "Enhanced"])
    p.add_argument("--strip-dashes", action="store_true")
    p.add_argument("--provider", default="Bedrock", choices=PROVIDER_ORDER)
    p.add_argument("--no-fallback", action="store_true")
    p.add_argument("--model", help="override model name (e.g. openai.gpt-oss-120b)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--env-file", action="append", default=[])
    p.set_defaults(func=cmd_api)

    # preview, verify, check-setup
    p = sub.add_parser("preview", parents=[common], help="list prose paragraphs")
    p.add_argument("file")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("verify", parents=[common], help="compare output vs original")
    p.add_argument("output")
    p.add_argument("original")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("check-setup", parents=[common], help="verify environment and keys")
    p.add_argument("--env-file", action="append", default=[])
    p.set_defaults(func=cmd_check_setup)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
