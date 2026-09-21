#!/usr/bin/env python3
"""
Build the math-buddy-designer's own agent config.

Reads prompts/math-buddy-designer.md and emits a self-contained
~/.kiro/agents/math-buddy-designer.json with the prompt INLINED (not
referenced via file://), for the same portability reason as every other
bundle in this system: the config must work correctly the instant it's copied
to another machine's ~/.kiro/agents/, with no path rewriting.

Usage:
    python3 build_designer_agent.py           # write the config
    python3 build_designer_agent.py --check    # validate only, write nothing

Edit prompts/math-buddy-designer.md, then re-run this script to regenerate
math-buddy-designer.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
PROMPTS = SRC / "prompts"
OUT = SRC.parent  # ~/.kiro/agents/

AGENT_NAME = "math-buddy-designer"

DESCRIPTION = (
    "Interviews a mathematician about a specific research project and "
    "generates a Theoritian-style orchestrator + subagent bundle for them "
    "(fixed core of proof-writer + researcher, conditional formalizer/"
    "numerics/visualization workers, and an always-present critic), without "
    "requiring them to understand agent configuration or orchestration "
    "mechanics. Source files: ~/.kiro/agents/math_buddy_designer_src/ "
    "(prompts/, REFERENCE_PATTERN.md, templates/, generate_bundle.py). "
    "Edit math_buddy_designer_src/prompts/math-buddy-designer.md and re-run "
    "build_designer_agent.py to regenerate this config."
)


def load_prompt() -> str:
    path = PROMPTS / f"{AGENT_NAME}.md"
    if not path.is_file():
        raise SystemExit(f"missing prompt source: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"empty prompt source: {path}")
    return text


def build() -> dict:
    return {
        "name": AGENT_NAME,
        "description": DESCRIPTION,
        "prompt": load_prompt(),
        "tools": [
            "read",
            "grep",
            "glob",
            "code",
            "write",
            "shell",
            "web_search",
            "web_fetch",
            "subagent",
            "todo_list",
        ],
        # Auto-approve reading/searching/research; writes and shell still
        # prompt, since this agent writes into ~/.kiro/agents/ itself and
        # runs the generator script — both worth a confirmation.
        "allowedTools": [
            "read",
            "grep",
            "glob",
            "code",
            "web_search",
            "web_fetch",
            "todo_list",
        ],
        "toolsSettings": {
            "write": {
                # Scoped to its own source dir plus wherever generated
                # bundles land — which is ~/.kiro/agents/ itself, since that
                # is this agent's entire purpose. No narrower scope is
                # possible without defeating the point of the agent.
                "allowedPaths": [
                    "math_buddy_designer_src/**",
                    "*.json",
                ]
            },
            "shell": {
                "autoAllowReadonly": True,
                "allowedCommands": [
                    r"^python3\s+.*generate_bundle\.py.*$",
                    r"^mkdir\s+-p\s+.*$",
                    r"^ls(\s.*)?$",
                ],
            },
        },
        "resources": [
            "file://math_buddy_designer_src/REFERENCE_PATTERN.md",
        ],
        "welcomeMessage": (
            "What's the research project, and who's it for? Let's start "
            "with a project nickname."
        ),
    }


def verify(cfg: dict) -> list[str]:
    problems: list[str] = []
    if cfg.get("name") != AGENT_NAME:
        problems.append("name field mismatch")
    if not cfg.get("prompt"):
        problems.append("empty prompt")
    if "model" in cfg:
        problems.append("must not pin a model")
    if "subagent" not in cfg["tools"]:
        problems.append("missing subagent tool (needed for research fan-out)")
    if "shell" not in cfg["tools"]:
        problems.append("missing shell tool (needed to run generate_bundle.py)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only")
    args = ap.parse_args()

    cfg = build()
    problems = verify(cfg)
    if problems:
        print("FAILED invariant checks:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if args.check:
        print(f"OK: config valid ({len(cfg['prompt']):,} char prompt), nothing written")
        return 0

    dest = OUT / f"{AGENT_NAME}.json"
    dest.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest}  ({len(cfg['prompt']):,} char prompt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
