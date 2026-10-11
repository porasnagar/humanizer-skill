#!/usr/bin/env python3
"""Install the lema-humanizer skill for Claude Code, OpenAI Codex, Antigravity, and active workspaces.

Copies skills/lema-humanizer into each agent tool's skill folder.

Usage:
  python install.py                                 # Installs for all detected AI agents (Claude, Codex, Antigravity)
  python install.py --only claude                   # Install for Claude Code only
  python install.py --only codex                    # Install for OpenAI Codex only
  python install.py --only antigravity              # Install for Google Antigravity only
  python install.py --workspace                     # Install into current project root (.agents/skills/lema-humanizer)
  python install.py --lema-home /path/to/lema       # Enable optional external API mode
  python install.py --uninstall                     # Remove skill from all tools
  python install.py --list                          # Show target paths
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
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(TARGETS) + ", workspace")
    ap.add_argument("--workspace", action="store_true", help="install into current working directory's .agents/skills")
    ap.add_argument("--lema-home", help="path to the Lema engine repo, to enable the optional api mode")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the install paths and exit")
    args = ap.parse_args()

    targets_map = dict(TARGETS)
    if args.workspace:
        targets_map["workspace"] = Path.cwd() / ".agents" / "skills"

    if args.list:
        for name, path in targets_map.items():
            print(f"{name:15} {path / SKILL}")
        return 0

    src = Path(__file__).resolve().parent / "skills" / SKILL
    if not (src / "SKILL.md").exists():
        sys.exit(f"Could not find the skill at {src}")

    chosen = [c.strip() for c in args.only.split(",")] if args.only else list(targets_map)
    unknown = [c for c in chosen if c not in targets_map]
    if unknown:
        ap.error(f"unknown target(s): {', '.join(unknown)}")

    lema_home = None
    if args.lema_home:
        lema_home = Path(args.lema_home).expanduser().resolve()
        if not (lema_home / "v2" / "v2_engine.py").exists() and not (lema_home / "humanizer.py").exists():
            sys.exit(f"{lema_home} does not look like the Lema engine repo")

    for name in chosen:
        dest = targets_map[name] / SKILL
        if dest.exists() and not is_ours(dest):
            print(f"{name:15} skipped: {dest} exists and is not this skill")
            continue
        if dest.exists():
            shutil.rmtree(dest)
        if args.uninstall:
            print(f"{name:15} removed {dest}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "lema_home.txt"))
        if lema_home:
            (dest / "lema_home.txt").write_text(str(lema_home), encoding="utf-8")
        print(f"{name:15} installed -> {dest}")

    if not args.uninstall and chosen:
        sample_path = targets_map[chosen[0]] / SKILL / "scripts" / "lema_humanize.py"
        print(f"\nVerification command: python \"{sample_path}\" check-setup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
