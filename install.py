#!/usr/bin/env python3
"""Install the lema-humanizer skill for Claude Code, Codex and Antigravity.

Copies skills/lema-humanizer into each tool's user-level skills folder. Re-run after editing the
skill to update every copy.

  python install.py                                 # all three tools
  python install.py --only codex                    # one tool
  python install.py --lema-home /path/to/lema       # also enable the optional api mode
  python install.py --uninstall
  python install.py --list                          # show the target paths
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL = "lema-humanizer"
TARGETS = {
    # Claude Code personal skills
    "claude": Path.home() / ".claude" / "skills",
    # Codex user skills ($HOME/.agents/skills)
    "codex": Path.home() / ".agents" / "skills",
    # Antigravity global customizations
    "antigravity": Path.home() / ".gemini" / "config" / "skills",
}


def is_ours(dest: Path) -> bool:
    skill_md = dest / "SKILL.md"
    return skill_md.exists() and f"name: {SKILL}" in skill_md.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(TARGETS))
    ap.add_argument("--lema-home", help="path to the Lema engine repo, to enable the optional api mode")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the install paths and exit")
    args = ap.parse_args()

    if args.list:
        for name, path in TARGETS.items():
            print(f"{name:12} {path / SKILL}")
        return 0

    src = Path(__file__).resolve().parent / "skills" / SKILL
    if not (src / "SKILL.md").exists():
        sys.exit(f"Could not find the skill at {src}")

    chosen = [c.strip() for c in args.only.split(",")] if args.only else list(TARGETS)
    unknown = [c for c in chosen if c not in TARGETS]
    if unknown:
        ap.error(f"unknown target(s): {', '.join(unknown)}")

    lema_home = None
    if args.lema_home:
        lema_home = Path(args.lema_home).expanduser().resolve()
        if not (lema_home / "v2" / "v2_engine.py").exists():
            sys.exit(f"{lema_home} does not look like the Lema engine repo (no v2/v2_engine.py)")

    for name in chosen:
        dest = TARGETS[name] / SKILL
        if dest.exists() and not is_ours(dest):
            print(f"{name:12} skipped: {dest} exists and is not this skill")
            continue
        if dest.exists():
            shutil.rmtree(dest)
        if args.uninstall:
            print(f"{name:12} removed {dest}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "lema_home.txt"))
        if lema_home:
            (dest / "lema_home.txt").write_text(str(lema_home), encoding="utf-8")
        print(f"{name:12} installed {dest}")

    if not args.uninstall:
        print("\nCheck it works:  python \"%s\" check-setup" % (TARGETS[chosen[0]] / SKILL / "scripts" / "lema_humanize.py"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
