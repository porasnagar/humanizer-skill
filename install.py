#!/usr/bin/env python3
"""Universal Installer for the Humanizer Skill.

Installs the humanizer skill for Google Antigravity, Anthropic Claude Code,
OpenAI Codex, OpenCode, Hermes, or any current project workspace.

Usage:
  python install.py                   # Auto-detects and installs for all AI agents & workspace
  python install.py --workspace       # Installs into current project's .agents/skills/humanizer
  python install.py --only claude     # Installs for Claude Code only (~/.claude/skills/humanizer)
  python install.py --only antigravity# Installs for Google Antigravity (~/.gemini/config/skills/humanizer)
  python install.py --only codex      # Installs for OpenAI Codex (~/.agents/skills/humanizer)
  python install.py --deps            # Also installs required Python dependencies via pip
  python install.py --list            # Show installation paths
  python install.py --uninstall       # Remove skill from all targets
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_NAME = "humanizer"

TARGETS = {
    # Antigravity global customizations
    "antigravity": Path.home() / ".gemini" / "config" / "skills",
    # Claude Code personal skills
    "claude": Path.home() / ".claude" / "skills",
    # OpenAI Codex global user skills
    "codex": Path.home() / ".agents" / "skills",
    # OpenCode global skills
    "opencode": Path.home() / ".config" / "opencode" / "skills",
    # Hermes global skills
    "hermes": Path.home() / ".hermes" / "skills",
}


def is_ours(dest: Path) -> bool:
    skill_md = dest / "SKILL.md"
    return skill_md.exists() and f"name: {SKILL_NAME}" in skill_md.read_text(encoding="utf-8")


def install_deps() -> None:
    req_file = Path(__file__).resolve().parent / "requirements.txt"
    if req_file.exists():
        print(f"Installing dependencies from {req_file}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    else:
        print("requirements.txt not found, skipping dependencies.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(TARGETS) + ", workspace")
    ap.add_argument("--workspace", action="store_true", help="install into current working directory's .agents/skills")
    ap.add_argument("--deps", action="store_true", help="install python dependencies from requirements.txt")
    ap.add_argument("--uninstall", action="store_true", help="uninstall skill from targets")
    ap.add_argument("--list", action="store_true", help="print target paths and exit")
    args = ap.parse_args()

    targets_map = dict(TARGETS)
    if args.workspace:
        targets_map["workspace"] = Path.cwd() / ".agents" / "skills"

    if args.list:
        print(f"Target paths for '{SKILL_NAME}' skill:")
        for name, path in targets_map.items():
            print(f"  {name:15} -> {path / SKILL_NAME}")
        return 0

    if args.deps:
        install_deps()

    # Determine source directory
    base_dir = Path(__file__).resolve().parent
    if (base_dir / "skills" / SKILL_NAME / "SKILL.md").exists():
        src = base_dir / "skills" / SKILL_NAME
    elif (base_dir / "SKILL.md").exists() and (base_dir / "scripts").exists():
        src = base_dir
    else:
        sys.exit(f"Error: Could not locate skill source files in {base_dir}")

    # Choose targets
    if args.only:
        chosen = [c.strip() for c in args.only.split(",")]
        unknown = [c for c in chosen if c not in targets_map]
        if unknown:
            ap.error(f"Unknown target(s): {', '.join(unknown)}")
    else:
        # Default: install to all standard agent paths AND current workspace
        chosen = list(targets_map)
        targets_map["workspace"] = Path.cwd() / ".agents" / "skills"
        if "workspace" not in chosen:
            chosen.append("workspace")

    for name in chosen:
        dest = targets_map[name] / SKILL_NAME
        if dest.exists() and not is_ours(dest):
            print(f"  {name:15} SKIPPED: {dest} exists and was not created by this installer.")
            continue

        if dest.exists():
            shutil.rmtree(dest)

        if args.uninstall:
            print(f"  {name:15} UNINSTALLED: {dest}")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            src,
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git*", "scratch*", "node_modules*")
        )
        print(f"  {name:15} INSTALLED -> {dest}")

    if not args.uninstall:
        print(f"\n[OK] Successfully configured '{SKILL_NAME}' skill!")
        print("Remember to set your Groq API key in your environment or .env file:")
        print("  export GROQ_API_KEY=\"gsk_...\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
