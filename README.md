# math-buddy-designer

A Kiro CLI agent that interviews a mathematician about a specific research
project and generates a Theoritian-style orchestrator + subagent bundle for
them — fixed core of proof-writer + researcher, conditional
formalizer/numerics/visualization workers, and an always-present critic —
without requiring them to understand agent configuration or orchestration.

## Layout

| Path | Purpose |
| --- | --- |
| `math-buddy-designer.json` | The built agent config (prompt inlined). |
| `math_buddy_designer_src/prompts/math-buddy-designer.md` | Prompt source of truth. |
| `math_buddy_designer_src/REFERENCE_PATTERN.md` | The reusable bundle pattern the designer reads before designing. |
| `math_buddy_designer_src/templates/*.template.json` | Skeletons the generator fills (orchestrator, worker, critic). |
| `math_buddy_designer_src/generate_bundle.py` | Assembles a generated bundle's JSON and enforces its invariants. |
| `math_buddy_designer_src/build_designer_agent.py` | Rebuilds `math-buddy-designer.json` from the prompt source. |

## Install

Copy the config and its source directory into the global Kiro agents
directory:

```bash
mkdir -p ~/.kiro/agents
cp math-buddy-designer.json ~/.kiro/agents/
cp -r math_buddy_designer_src ~/.kiro/agents/
```

Verify and run:

```bash
kiro-cli agent list          # math-buddy-designer should appear as Global
kiro-cli chat --agent math-buddy-designer
```

## Editing the prompt

Edit `math_buddy_designer_src/prompts/math-buddy-designer.md`, then rebuild
and reinstall:

```bash
python3 math_buddy_designer_src/build_designer_agent.py
cp math-buddy-designer.json ~/.kiro/agents/
```

Never hand-edit the `prompt` field in the JSON — it is generated.
