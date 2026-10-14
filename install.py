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

ENV_TEMPLATE = """# Humanizer Skill Configuration
# 1. Get a free API key at: https://console.groq.com/keys
GROQ_API_KEY="{groq_key}"

# Optional fallback provider:
# AWS_BEDROCK_API_KEY=""
"""


def is_ours(dest: Path) -> bool:
    skill_md = dest / "SKILL.md"
    return skill_md.exists() and f"name: {SKILL_NAME}" in skill_md.read_text(encoding="utf-8")


def detect_existing_groq_key() -> str:
    """Check if GROQ_API_KEY is already present in environment or nearby .env."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key and key != "gsk_...":
        return key

    # Check cwd, parent, home, or active project .env files
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path.home() / ".env",
        Path.home() / "Documents" / "antigravity projects" / "Lema" / ".env",
        Path.home() / "Documents" / "antigravity projects" / "Humanizer" / ".env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val and val != "gsk_...":
                            return val
            except Exception:
                pass
    return "gsk_..."



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
        chosen = list(targets_map)
        targets_map["workspace"] = Path.cwd() / ".agents" / "skills"
        if "workspace" not in chosen:
            chosen.append("workspace")

    existing_groq_key = detect_existing_groq_key()
    installed_records = []

    for name in chosen:
        dest = targets_map[name] / SKILL_NAME
        if dest.exists() and not is_ours(dest):
            print(f"  {name:15} SKIPPED: {dest} exists and was not created by this installer.")
            continue

        # Preserve existing .env if already configured
        saved_env_content = None
        if dest.exists():
            env_path = dest / ".env"
            if env_path.is_file():
                try:
                    content = env_path.read_text(encoding="utf-8")
                    if "gsk_" in content and "gsk_..." not in content:
                        saved_env_content = content
                except Exception:
                    pass
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

        # Write or restore .env file inside the skill folder
        env_dest = dest / ".env"
        if saved_env_content:
            env_dest.write_text(saved_env_content, encoding="utf-8")
        else:
            env_dest.write_text(ENV_TEMPLATE.format(groq_key=existing_groq_key), encoding="utf-8")

        print(f"  {name:15} INSTALLED -> {dest}")
        installed_records.append((name, dest, env_dest))

    if not args.uninstall and installed_records:
        print("\n" + "=" * 76)
        print(f" [OK] Humanizer skill installed successfully across {len(installed_records)} location(s)!")
        print("=" * 76)
        for name, dest, env_dest in installed_records:
            print(f"\n  [{name.upper()}]")
            print(f"  Skill Path : {dest}")
            print(f"  Env Config : {env_dest}")

        print("\n" + "-" * 76)
        if existing_groq_key and existing_groq_key != "gsk_...":
            print(f"  [NOTE] Automatically configured GROQ_API_KEY from your environment!")
        else:
            print("  [ACTION REQUIRED] To activate the engine, add your Groq API key to:")
            for _, _, env_dest in installed_records:
                print(f"  -> {env_dest}")
            print("  (Set: GROQ_API_KEY=\"gsk_...\") - Free at https://console.groq.com")
        print("=" * 76 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
