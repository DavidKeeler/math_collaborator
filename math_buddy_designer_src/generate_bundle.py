#!/usr/bin/env python3
"""
Bundle generator for the math-buddy-designer.

Fills the JSON templates in templates/ and writes a new, self-contained agent
bundle into ~/.kiro/agents/, following the same portability convention as the
Theoritian reference project: every agent's prompt is INLINED into its JSON
(no file:// prompt references), so the bundle works correctly the moment it's
copied to another machine's ~/.kiro/agents/, with no path rewriting.

This script is invoked by the math-buddy-designer agent itself (via the shell
tool) after it has interviewed the mathematician and drafted every worker's
prompt text as separate .md files. It does NOT contain any research-area
content or design judgment — see REFERENCE_PATTERN.md and the designer's own
prompt for that. This script only does mechanical JSON assembly + validation.

Usage:
    python3 generate_bundle.py --spec bundle_spec.json [--check]

bundle_spec.json shape:
{
  "nickname": "topobuddy",
  "orchestrator": {
    "description": "...",
    "prompt_file": "/path/to/drafted/orchestrator_prompt.md"
  },
  "workers": [
    {
      "name": "proof-writer",
      "description": "...",
      "prompt_file": "...",
      "own_task_dir": "proof/**",
      "extra_tools": [],
      "shell_allowed_commands": []
    },
    {
      "name": "researcher",
      "description": "...",
      "prompt_file": "...",
      "own_task_dir": "research_notes/**",
      "extra_tools": ["web_search", "web_fetch"],
      "shell_allowed_commands": []
    },
    {
      "name": "agent-editor",
      "description": "...",
      "prompt_file": "...",
      "own_task_dir": null,
      "extra_tools": [],
      "shell_allowed_commands": []
    }
  ],
  "critic": {
    "description": "...",
    "prompt_file": "..."
  }
}

Worker "name" fields are the bare role name (e.g. "proof-writer"); the actual
agent name written out is "<nickname>-<name>". The orchestrator agent name is
bare "<nickname>". The critic agent name is "<nickname>-critic".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
TEMPLATES = SRC / "templates"
AGENTS_DIR = SRC.parent  # ~/.kiro/agents/


def load_template(name: str) -> dict:
    path = TEMPLATES / f"{name}.template.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def load_prompt(prompt_file: str) -> str:
    path = Path(prompt_file).expanduser()
    if not path.is_file():
        raise SystemExit(f"missing prompt file: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"empty prompt file: {path}")
    return text


def build_orchestrator(spec: dict, worker_agent_names: list[str], critic_name: str) -> dict:
    nickname = spec["nickname"]
    cfg = load_template("orchestrator")
    cfg["name"] = nickname
    cfg["description"] = spec["orchestrator"]["description"]
    cfg["prompt"] = load_prompt(spec["orchestrator"]["prompt_file"])

    all_crew = sorted(worker_agent_names + [critic_name])
    cfg["toolsSettings"]["crew"]["availableAgents"] = all_crew
    cfg["toolsSettings"]["crew"]["trustedAgents"] = all_crew

    denylist = []
    for w in spec["workers"]:
        d = w.get("own_task_dir")
        if d:  # agent-editor and any similar role has no project task dir
            denylist.append(d)
    cfg["toolsSettings"]["write"]["deniedPaths"] = sorted(set(denylist))

    return cfg


def build_worker(nickname: str, worker_spec: dict) -> dict:
    cfg = load_template("worker")
    cfg["name"] = f"{nickname}-{worker_spec['name']}"
    cfg["description"] = worker_spec["description"]
    cfg["prompt"] = load_prompt(worker_spec["prompt_file"])

    if worker_spec["name"] == "agent-editor":
        # Special case, not the generic own-task-dir + shared/** pattern:
        # the agent-editor's job is editing sibling agent configs in
        # ~/.kiro/agents/, outside the project tree entirely. Its own config
        # file is explicitly denied (REFERENCE_PATTERN.md §3b, §11) — it may
        # never edit itself, even if asked.
        own_config = f"{cfg['name']}.json"
        cfg["toolsSettings"]["write"] = {
            "allowedPaths": ["~/.kiro/agents/*.json"],
            "deniedPaths": [own_config],
        }
    else:
        cfg["toolsSettings"]["write"]["allowedPaths"] = [
            worker_spec["own_task_dir"],
            "shared/**",
        ]

    extra_tools = worker_spec.get("extra_tools", [])
    cfg["tools"] = ["read", "grep", "glob", "code", "write"] + list(extra_tools)
    cfg["allowedTools"] = ["read", "grep", "glob", "code"]

    shell_cmds = worker_spec.get("shell_allowed_commands", [])
    if shell_cmds:
        if "shell" not in cfg["tools"]:
            cfg["tools"].append("shell")
        cfg["toolsSettings"]["shell"] = {
            "autoAllowReadonly": True,
            "allowedCommands": shell_cmds,
        }
    else:
        cfg["toolsSettings"].pop("shell", None)

    return cfg


def build_critic(nickname: str, critic_spec: dict, worker_specs: list[dict]) -> dict:
    cfg = load_template("critic")
    cfg["name"] = f"{nickname}-critic"
    cfg["description"] = critic_spec["description"]
    cfg["prompt"] = load_prompt(critic_spec["prompt_file"])
    denylist = sorted({w["own_task_dir"] for w in worker_specs if w.get("own_task_dir")})
    cfg["toolsSettings"]["write"]["deniedPaths"] = denylist
    return cfg


def build(spec: dict) -> dict[str, dict]:
    nickname = spec["nickname"]
    worker_agent_names = [f"{nickname}-{w['name']}" for w in spec["workers"]]
    critic_name = f"{nickname}-critic"

    configs: dict[str, dict] = {}
    configs[nickname] = build_orchestrator(spec, worker_agent_names, critic_name)
    for w in spec["workers"]:
        agent_name = f"{nickname}-{w['name']}"
        configs[agent_name] = build_worker(nickname, w)
    configs[critic_name] = build_critic(nickname, spec["critic"], spec["workers"])
    return configs


def verify(spec: dict, configs: dict[str, dict]) -> list[str]:
    """Hard invariants — mirrors the checks used for the Theoritian bundle."""
    problems: list[str] = []
    nickname = spec["nickname"]

    for name, cfg in configs.items():
        if cfg.get("name") != name:
            problems.append(f"{name}: name field mismatch")
        if not cfg.get("prompt"):
            problems.append(f"{name}: empty prompt")
        if "model" in cfg:
            problems.append(f"{name}: must not pin a model (bundle is model-agnostic)")

    existing = {p.stem for p in AGENTS_DIR.glob("*.json")}
    collisions = set(configs) & existing
    if collisions:
        problems.append(
            f"name collision with existing agents in {AGENTS_DIR}: {sorted(collisions)} "
            "— choose a different nickname"
        )

    orch = configs[nickname]
    if "subagent" not in orch["tools"]:
        problems.append(f"{nickname}: orchestrator missing subagent tool")
    crew = orch["toolsSettings"]["crew"]["availableAgents"]
    expected_crew = sorted(
        [f"{nickname}-{w['name']}" for w in spec["workers"]] + [f"{nickname}-critic"]
    )
    if sorted(crew) != expected_crew:
        problems.append(f"{nickname}: crew availableAgents mismatch, got {crew}")

    for w in spec["workers"]:
        agent_name = f"{nickname}-{w['name']}"
        cfg = configs[agent_name]
        if "subagent" in cfg["tools"]:
            problems.append(f"{agent_name}: workers must not have subagent (no sub-subagents)")
        paths = cfg["toolsSettings"]["write"]["allowedPaths"]

        if w["name"] == "agent-editor":
            # Special case (REFERENCE_PATTERN.md §3b, §11): the agent-editor
            # writes sibling agent configs in ~/.kiro/agents/, not
            # shared/** or a project task dir, and must deny its own config.
            denied = cfg["toolsSettings"]["write"].get("deniedPaths", [])
            if f"{agent_name}.json" not in denied:
                problems.append(f"{agent_name}: must deny writing its own config file")
            if "shared/**" in paths or w.get("own_task_dir") in paths:
                problems.append(
                    f"{agent_name}: should not have project-tree write access "
                    "(its scope is sibling agent configs, not shared/** or a task dir)"
                )
            continue

        if "shared/**" not in paths:
            problems.append(f"{agent_name}: cannot write shared notes")
        if w["own_task_dir"] not in paths:
            problems.append(f"{agent_name}: cannot write own task dir {w['own_task_dir']}")
        others = [
            ow["own_task_dir"]
            for ow in spec["workers"]
            if ow["name"] != w["name"] and ow.get("own_task_dir")
        ]
        for other_dir in others:
            if other_dir in paths:
                problems.append(f"{agent_name}: can write another worker's dir {other_dir}")
        if any(t not in ("web_search", "web_fetch") for t in w.get("extra_tools", [])):
            # Non-web extra tools are fine (e.g. none expected today, but not banned);
            # web tools should generally only be on a researcher-role worker.
            pass
        if w["name"] != "researcher" and {"web_search", "web_fetch"} & set(
            w.get("extra_tools", [])
        ):
            problems.append(
                f"{agent_name}: only the researcher role should have web_search/web_fetch"
            )

    critic_name = f"{nickname}-critic"
    critic_cfg = configs[critic_name]
    if "subagent" in critic_cfg["tools"] or "write" in critic_cfg["tools"] and any(
        p != "shared/critic_notes.md" for p in critic_cfg["toolsSettings"]["write"]["allowedPaths"]
    ):
        problems.append(f"{critic_name}: must be read-only except its own review-notes file")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="path to bundle_spec.json")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).expanduser().read_text(encoding="utf-8"))
    configs = build(spec)
    problems = verify(spec, configs)
    if problems:
        print("FAILED invariant checks:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if args.check:
        print(f"OK: {len(configs)} configs valid (nothing written)")
        return 0

    for name, cfg in configs.items():
        dest = AGENTS_DIR / f"{name}.json"
        dest.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {dest}  ({len(cfg['prompt']):,} char prompt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
