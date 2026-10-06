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
    python3 generate_bundle.py --spec bundle_spec.json --only <agent> [<agent>...]
    python3 generate_bundle.py --list-invariants

The prompt `.md` files named in the spec are the single source of truth for
prompt text; the JSON `prompt` field is generated from them. Edit the `.md`
and regenerate — never hand-edit a generated `prompt` field, or the next run
will revert it. `--only` narrows the write to named agents (for a bundle's own
agent-editor updating one sibling) while still building and checking the whole
bundle; it refuses to name the agent-editor itself.

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

# REFERENCE_PATTERN.md §6a: only these roles get the knowledge base. The
# orchestrator needs it for strategy context, the critic to audit claims
# against the same material, the researcher to avoid re-discovering what is
# already there. Workers are briefed from shared/ instead.
KB_ROLES = {"researcher"}

EDITOR_ROLE = "agent-editor"

# One shell-safe argument token: no whitespace and no metacharacter that could
# chain a second command onto an allowed one. The agent-editor's shell
# allowlist must be written in terms of this rather than a trailing `.*`,
# because a trailing `.*` turns any allowed command into arbitrary shell
# (`cat x && python3 -c ...`) and so defeats its write scoping entirely.
TOKEN = r"[^\s;&|<>$`'\"\\()]+"

# REFERENCE_PATTERN.md §11: the agent-editor's write scope is the one
# exception to the task-dir convention, and it is narrow. Verified empirically
# against kiro-cli 2.10.0: in `deniedPaths`, a `~/`-prefixed or absolute glob
# is matched and the write is hard-rejected, but a BARE FILENAME never matches
# (the write goes through), because the pattern is compared against the
# resolved absolute path and not against the basename. Every denial written
# here must therefore be `~/`-prefixed or absolute — a bare filename is a
# silently unenforced rule.
def home_glob(path: str | Path) -> str:
    """Render an absolute path as a portable `~/...` glob when it is under $HOME."""
    p = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        return "~/" + str(p.relative_to(home))
    except ValueError:
        return str(p)

# Verified empirically against `kiro-cli agent validate` (kiro-cli 2.10.0):
# a knowledgeBase resource is a tagged object whose `source` must be a
# file:// URI. A bare filesystem path parses but fails schema validation.
def kb_resource(path: str) -> dict:
    p = path.rstrip("/")
    if not p.startswith("file://"):
        p = "file://" + p
    return {"type": "knowledgeBase", "source": p, "autoUpdate": True}


# A knowledgeBase resource is indexed into a separate store and queried with
# the `knowledge` tool — it is NOT loaded into context. An agent given the
# resource but not the tool therefore has a knowledge base it cannot read:
# indexing happens, `kiro-cli agent validate` passes, and every search silently
# fails. Verified live against a real bundle, where the orchestrator reported no
# knowledge tool and its 32 KB research dossier had been unreachable since
# generation. Resource and tool are attached together here so they cannot drift
# apart (REFERENCE_PATTERN.md §6a).
def attach_kb(cfg: dict, path: str | None) -> None:
    if not path:
        return
    cfg["resources"] = list(cfg.get("resources", [])) + [kb_resource(path)]
    if "knowledge" not in cfg["tools"]:
        cfg["tools"] = list(cfg["tools"]) + ["knowledge"]
    allowed = cfg.setdefault("allowedTools", [])
    if "knowledge" not in allowed:
        allowed.append("knowledge")


def spec_entries(spec: dict) -> list[dict]:
    """Every agent entry in the spec, orchestrator and critic included."""
    return [spec["orchestrator"], *spec["workers"], spec["critic"]]


def prompt_source_globs(spec: dict) -> list[str]:
    """`*.md` globs covering every directory the spec draws prompt sources from.

    REFERENCE_PATTERN.md §3b: the `.md` prompt source is the single source of
    truth and the JSON `prompt` field is generated from it. An agent-editor
    that could write only the JSON would have its prompt edits silently
    reverted by the next generator run, so the sources must be in scope.
    """
    dirs = {str(Path(e["prompt_file"]).expanduser().resolve().parent) for e in spec_entries(spec)}
    return sorted(home_glob(d) + "/*.md" for d in dirs)


def editor_write_scope(spec: dict, editor_agent_name: str, editor_prompt_file: str) -> dict:
    """Bundle-scoped write access for the agent-editor.

    Scoped to *this bundle's* configs and prompt sources — not
    `~/.kiro/agents/*.json`, which would also cover every unrelated agent on
    the machine (other bundles, the designer itself). Its own config and its
    own prompt source are both denied: denying only the JSON would leave the
    `.md` that generates that JSON writable, which is the same capability one
    regenerate away.
    """
    nickname = spec["nickname"]
    return {
        "allowedPaths": [
            f"~/.kiro/agents/{nickname}.json",
            f"~/.kiro/agents/{nickname}-*.json",
            *prompt_source_globs(spec),
        ],
        "deniedPaths": [
            f"~/.kiro/agents/{editor_agent_name}.json",
            home_glob(editor_prompt_file),
        ],
    }


def editor_shell_commands(spec_cmds: list[str]) -> list[str]:
    """Shell allowlist for the agent-editor: validation plus targeted regeneration.

    The generator is the authority on bundle invariants (§3b), so the editor
    has to be able to run it. `--only` limits the write to named agents and
    refuses to name the agent-editor itself, so this grant cannot be turned
    into a self-edit.
    """
    gen = r"python3\s+" + TOKEN + r"generate_bundle\.py"
    return [
        rf"^kiro-cli\s+agent\s+validate\s+--path\s+{TOKEN}$",
        rf"^{gen}\s+--spec\s+{TOKEN}\s+--check$",
        rf"^{gen}\s+--spec\s+{TOKEN}\s+--only\s+{TOKEN}(\s+{TOKEN})*$",
        rf"^{gen}\s+--list-invariants$",
        *spec_cmds,
    ]


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

    # No `file://shared/*.md` resource, deliberately. A `file://` resource is
    # ALWAYS loaded into context (unlike `skill://`, which loads on demand), so
    # globbing the ledger here injects every file in shared/ into every request
    # — including critic_notes.md, which the critic appends to each cycle and
    # which therefore grows without bound. Observed in a real bundle: 177 KB of
    # shared/ auto-loaded, 123 KB of it critic notes, ~44k tokens before the
    # mathematician typed anything. The ledger is read on demand with
    # read/grep/glob instead (REFERENCE_PATTERN.md §6).
    cfg["resources"] = []

    attach_kb(cfg, spec.get("knowledge_base"))

    return cfg


def build_worker(
    nickname: str,
    worker_spec: dict,
    knowledge_base: str | None = None,
    spec: dict | None = None,
) -> dict:
    cfg = load_template("worker")
    cfg["name"] = f"{nickname}-{worker_spec['name']}"
    cfg["description"] = worker_spec["description"]
    cfg["prompt"] = load_prompt(worker_spec["prompt_file"])

    is_editor = worker_spec["name"] == EDITOR_ROLE
    if is_editor:
        # Special case, not the generic own-task-dir + shared/** pattern
        # (REFERENCE_PATTERN.md §3b, §11): the agent-editor's job is this
        # bundle's own configs and prompt sources under ~/.kiro/agents/,
        # outside the project tree entirely.
        if spec is None:
            raise SystemExit("internal error: agent-editor needs the full spec for scoping")
        cfg["toolsSettings"]["write"] = editor_write_scope(
            spec, cfg["name"], worker_spec["prompt_file"]
        )
        # It never works in the project tree, so the worker template's
        # `file://shared/*.md` context would load files it has no business
        # reading and, from ~/.kiro/agents/, would not resolve anyway.
        cfg.pop("resources", None)
    else:
        cfg["toolsSettings"]["write"]["allowedPaths"] = [
            worker_spec["own_task_dir"],
            "shared/**",
        ]

    extra_tools = worker_spec.get("extra_tools", [])
    cfg["tools"] = ["read", "grep", "glob", "code", "write"] + list(extra_tools)
    cfg["allowedTools"] = ["read", "grep", "glob", "code"]

    shell_cmds = worker_spec.get("shell_allowed_commands", [])
    if is_editor:
        shell_cmds = editor_shell_commands(list(shell_cmds))
    if shell_cmds:
        if "shell" not in cfg["tools"]:
            cfg["tools"].append("shell")
        cfg["toolsSettings"]["shell"] = {
            "autoAllowReadonly": True,
            "allowedCommands": shell_cmds,
        }
    else:
        cfg["toolsSettings"].pop("shell", None)

    if worker_spec["name"] in KB_ROLES:
        attach_kb(cfg, knowledge_base)

    return cfg


def build_critic(nickname: str, critic_spec: dict, worker_specs: list[dict],
                 knowledge_base: str | None = None) -> dict:
    cfg = load_template("critic")
    cfg["name"] = f"{nickname}-critic"
    cfg["description"] = critic_spec["description"]
    cfg["prompt"] = load_prompt(critic_spec["prompt_file"])
    denylist = sorted({w["own_task_dir"] for w in worker_specs if w.get("own_task_dir")})
    cfg["toolsSettings"]["write"]["deniedPaths"] = denylist
    attach_kb(cfg, knowledge_base)
    return cfg


def build(spec: dict) -> dict[str, dict]:
    nickname = spec["nickname"]
    kb = spec.get("knowledge_base")
    worker_agent_names = [f"{nickname}-{w['name']}" for w in spec["workers"]]
    critic_name = f"{nickname}-critic"

    configs: dict[str, dict] = {}
    configs[nickname] = build_orchestrator(spec, worker_agent_names, critic_name)
    for w in spec["workers"]:
        agent_name = f"{nickname}-{w['name']}"
        configs[agent_name] = build_worker(nickname, w, kb, spec=spec)
    configs[critic_name] = build_critic(nickname, spec["critic"], spec["workers"], kb)

    # An empty `resources` array is the normal case now that the ledger is read
    # on demand; drop the key rather than emitting `"resources": []`.
    for cfg in configs.values():
        if not cfg.get("resources"):
            cfg.pop("resources", None)

    return configs


# The authoritative statement of the bundle's invariants, in human-readable
# form, kept adjacent to the code that enforces them. `--list-invariants`
# prints this, so no other file — no agent prompt, no doc — needs to carry its
# own copy of the list and drift out of step with the checks in verify().
# Change a check below, change its line here in the same edit.
INVARIANTS = [
    "No agent pins a `model` field — every bundle is model-agnostic.",
    "Every prompt is inlined in the JSON as a string, never a `file://` reference.",
    "Every agent's `name` field matches its filename, and no prompt is empty.",
    "No template `{{PLACEHOLDER}}` survives into a generated config.",
    "Only the orchestrator has the `subagent` tool; no worker or critic can spawn agents.",
    "The orchestrator's crew lists exactly the bundle's workers plus the critic.",
    "Only the researcher role gets `web_search` / `web_fetch`.",
    "Each non-editor worker writes only its own task directory plus `shared/**`, and no other worker's directory.",
    "The critic is read-only except its own review-notes file, and is never absent.",
    "The knowledge base goes to the orchestrator, critic, and researcher only, as a tagged "
    "`knowledgeBase` resource whose `source` is a `file://` URI.",
    "Every agent holding a `knowledgeBase` resource also has the `knowledge` tool — the "
    "resource is queried by that tool, not loaded into context, so without it the knowledge "
    "base is indexed but unreadable.",
    "No agent carries a `file://` resource pointing into `shared/`. A `file://` resource is "
    "always loaded into context, and the ledger contains an append-only critic notes file that "
    "grows without bound; the ledger is read on demand instead.",
    "Only the agent-editor may write under `~/.kiro/agents/`, scoped to this bundle's own "
    "configs and prompt sources — never the whole agents directory.",
    "The agent-editor's own config and own prompt source are both denied, as `~/`-prefixed or "
    "absolute patterns (a bare filename is not enforced at runtime).",
    "The agent-editor's shell allowlist contains no trailing `.*`, which would let any allowed "
    "command chain into arbitrary shell and bypass its write scoping.",
]


def verify(spec: dict, configs: dict[str, dict], allow_overwrite: bool = False) -> list[str]:
    """Hard invariants — mirrors the checks used for the Theoritian bundle."""
    problems: list[str] = []
    nickname = spec["nickname"]

    editor_agent_name = next(
        (f"{nickname}-{w['name']}" for w in spec["workers"] if w["name"] == EDITOR_ROLE),
        None,
    )

    for name, cfg in configs.items():
        if cfg.get("name") != name:
            problems.append(f"{name}: name field mismatch")
        if not cfg.get("prompt"):
            problems.append(f"{name}: empty prompt")
        if str(cfg.get("prompt", "")).startswith("file://"):
            problems.append(
                f"{name}: prompt must be inlined, not a file:// reference (portability)"
            )
        if "model" in cfg:
            problems.append(f"{name}: must not pin a model (bundle is model-agnostic)")
        if name != editor_agent_name:
            agents_dir_paths = [
                p
                for p in cfg.get("toolsSettings", {}).get("write", {}).get("allowedPaths", [])
                if ".kiro/agents" in p
            ]
            if agents_dir_paths:
                problems.append(
                    f"{name}: only the agent-editor may write under ~/.kiro/agents/, "
                    f"got {agents_dir_paths}"
                )
        # An unfilled {{PLACEHOLDER}} from a template is a silent corruption:
        # the JSON is well-formed but the agent config is invalid. Match only
        # the opening marker — "}}" occurs naturally as nested JSON braces.
        blob = json.dumps(cfg)
        if "{{" in blob:
            leftovers = sorted(
                {"{{" + tok.split("}}")[0] + "}}" for tok in blob.split("{{")[1:]}
            )
            problems.append(f"{name}: unfilled template placeholder(s): {leftovers}")

        # A `file://` resource is always loaded into context. Pointing one at
        # the ledger injects the whole of shared/ into every request, and
        # critic_notes.md there is append-only, so the cost grows every cycle
        # until requests start failing. Read the ledger on demand instead.
        eager_shared = [
            r
            for r in cfg.get("resources", [])
            if isinstance(r, str) and "shared/" in r
        ]
        if eager_shared:
            problems.append(
                f"{name}: must not load the ledger as a `file://` resource {eager_shared} "
                "— it is always loaded into context and shared/critic_notes.md grows without "
                "bound; read shared/ on demand instead"
            )

        # A knowledgeBase is queried with the `knowledge` tool, not loaded into
        # context. Resource without tool = indexed but unreadable, and nothing
        # else in the bundle would notice.
        if any(
            isinstance(r, dict) and r.get("type") == "knowledgeBase"
            for r in cfg.get("resources", [])
        ) and "knowledge" not in cfg.get("tools", []):
            problems.append(
                f"{name}: has a knowledgeBase resource but no `knowledge` tool "
                "— the knowledge base would be indexed and unreadable"
            )

    existing = {p.stem for p in AGENTS_DIR.glob("*.json")}
    collisions = set(configs) & existing
    if collisions and not allow_overwrite:
        problems.append(
            f"name collision with existing agents in {AGENTS_DIR}: {sorted(collisions)} "
            "— choose a different nickname, or pass --allow-overwrite to "
            "regenerate a bundle you already own"
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

        if w["name"] == EDITOR_ROLE:
            # Special case (REFERENCE_PATTERN.md §3b, §11): the agent-editor
            # writes this bundle's own configs and prompt sources under
            # ~/.kiro/agents/, not shared/** or a project task dir.
            wr = cfg["toolsSettings"]["write"]
            denied = wr.get("deniedPaths", [])
            expected = editor_write_scope(spec, agent_name, w["prompt_file"])

            for want in expected["deniedPaths"]:
                if want not in denied:
                    problems.append(
                        f"{agent_name}: must deny writing {want} "
                        "(own config and own prompt source are both off limits)"
                    )
            for d in denied:
                if not (d.startswith("~/") or d.startswith("/")):
                    problems.append(
                        f"{agent_name}: deniedPaths entry {d!r} is not `~/`-prefixed or absolute "
                        "— verified against kiro-cli 2.10.0, a bare filename never matches and "
                        "the rule is silently unenforced"
                    )
            if sorted(paths) != sorted(expected["allowedPaths"]):
                problems.append(
                    f"{agent_name}: write allowedPaths must be exactly this bundle's configs and "
                    f"prompt sources {sorted(expected['allowedPaths'])}, got {sorted(paths)}"
                )
            if "shared/**" in paths or w.get("own_task_dir") in paths:
                problems.append(
                    f"{agent_name}: should not have project-tree write access "
                    "(its scope is this bundle's configs and prompt sources)"
                )
            for c in cfg["toolsSettings"].get("shell", {}).get("allowedCommands", []):
                if ".*" in c:
                    problems.append(
                        f"{agent_name}: shell pattern {c!r} contains `.*`, which lets an allowed "
                        "command chain into arbitrary shell and bypass its write scoping"
                    )
            if any(
                isinstance(r, dict) or str(r).startswith("file://shared/")
                for r in cfg.get("resources", [])
            ):
                problems.append(
                    f"{agent_name}: must not carry project-tree or knowledge-base resources "
                    "(it never works in the project tree)"
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

    # REFERENCE_PATTERN.md §6a/§11: the knowledge base goes to the
    # orchestrator, critic, and researcher only. Anywhere else is a scope
    # change, not a default.
    if spec.get("knowledge_base"):
        allowed_kb_agents = {nickname, critic_name} | {
            f"{nickname}-{r}" for r in KB_ROLES
        }
        for name, cfg in configs.items():
            has_kb = any(
                isinstance(r, dict) and r.get("type") == "knowledgeBase"
                for r in cfg.get("resources", [])
            )
            if has_kb and name not in allowed_kb_agents:
                problems.append(
                    f"{name}: must not have knowledge base access "
                    "(orchestrator, critic, researcher only)"
                )
            if not has_kb and name in allowed_kb_agents:
                problems.append(f"{name}: missing knowledge base resource")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="path to bundle_spec.json")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="permit regenerating a bundle whose agent files already exist",
    )
    ap.add_argument(
        "--only",
        nargs="+",
        metavar="AGENT",
        help="write only these agent configs (implies --allow-overwrite). The whole bundle is "
        "still built and checked; the write is narrowed. Cannot name the bundle's agent-editor.",
    )
    ap.add_argument(
        "--list-invariants",
        action="store_true",
        help="print the bundle invariants this script enforces, and exit",
    )
    args = ap.parse_args()

    if args.list_invariants:
        for line in INVARIANTS:
            print(f"- {line}")
        return 0
    if not args.spec:
        ap.error("--spec is required")

    spec = json.loads(Path(args.spec).expanduser().read_text(encoding="utf-8"))
    configs = build(spec)

    targets = list(configs)
    if args.only:
        nickname = spec["nickname"]
        editor_agent_name = next(
            (f"{nickname}-{w['name']}" for w in spec["workers"] if w["name"] == EDITOR_ROLE),
            None,
        )
        unknown = [n for n in args.only if n not in configs]
        if unknown:
            print(f"not agents of this bundle: {unknown}", file=sys.stderr)
            return 1
        # The agent-editor runs this script, so --only is a path by which it
        # could regenerate its own config from its own prompt source and
        # sidestep the tool-level denial (REFERENCE_PATTERN.md §3b). Refuse.
        if editor_agent_name and editor_agent_name in args.only:
            print(
                f"refusing to regenerate {editor_agent_name} via --only: an agent-editor may not "
                "rewrite its own config. Run a full generation as the designer instead.",
                file=sys.stderr,
            )
            return 1
        targets = list(args.only)

    problems = verify(
        spec, configs, allow_overwrite=args.allow_overwrite or bool(args.only)
    )
    if problems:
        print("FAILED invariant checks:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if args.check:
        print(f"OK: {len(configs)} configs valid (nothing written)")
        return 0

    for name in targets:
        cfg = configs[name]
        dest = AGENTS_DIR / f"{name}.json"
        dest.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {dest}  ({len(cfg['prompt']):,} char prompt)")
    if args.only:
        print(f"(--only: {len(configs) - len(targets)} other config(s) left untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
