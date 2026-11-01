# math-buddy-designer

A Kiro CLI agent that interviews a mathematician about a specific research
project and generates a dedicated orchestrator + subagent bundle for them —
without requiring the mathematician to understand agent configuration,
prompting, or orchestration mechanics.

This repo contains **one agent**: the designer. Running it produces a
**separate, independent bundle** of agents (the orchestrator and its
subagents) tailored to the mathematician's specific project. The designer and
the bundles it generates are different things — see below.

## The design workflow

math-buddy-designer runs an eight-phase interview-then-build process. It
reads `math_buddy_designer_src/REFERENCE_PATTERN.md` before designing
anything — that document is the reusable architecture and the reasoning
behind it; the designer adapts it to each project rather than inventing
structure from scratch.

| Phase | What happens |
| --- | --- |
| 0 — Opening | Ask what the project is (the object/claim, what they want out of it). No file-reading, no mechanics talk — their account of the project comes first, before any of their existing material is read, to avoid anchoring on stale or superseded files. |
| 1 — Scoping | Settle success criteria, critic checkpoint tier (Full/Reduced/Minimal), knowledge base path, preferred research sources, and a project nickname. |
| 2 — Area & tasks interview | Enough about the subject area to brief a researcher, plus which tasks the project actually involves (formalization? simulation? figures?) — translated into archetypes by the designer, not named by the mathematician. |
| 3 — Research agenda | Propose a research agenda, get the mathematician's feedback, *then* fan out research subagents in parallel on confirmed topics. Never researches before feedback. |
| 4 — Refine | Bring findings back, ask follow-ups, loop into another research pass if real gaps remain. |
| 5 — Design | Map tasks to archetypes, build the project-specific integrity checklist, assemble the shared ledger structure, wire the knowledge base resource. Fixes *direction* (target claim, roster, checklist) — never *strategy* (no proof steps, no reduction, no decomposition baked into any generated prompt). |
| 6 — Implementation | Draft every agent's prompt as `.md`, assemble `bundle_spec.json`, run `generate_bundle.py --check` and fix any invariant violation, then generate for real. |
| 7 — Review | Self-check prompts for known failure patterns, a live smoke test (actually launch the new agents and confirm write-scoping is enforced), and a cross-file consistency review. |

Output: a brief summary of the roster and checklist, confirmation the three
Phase 7 checks passed, and an offer to adjust — the mathematician reacts to
the concrete result rather than approving each phase in advance.

## What gets generated: the orchestrator and its subagents

Every bundle the designer produces follows the same shape:

```
orchestrator ("collaborator")
├── proof-writer        (fixed core)
├── researcher           (fixed core)
├── agent-editor         (fixed core)
├── formalizer            (conditional)
├── numerics/sim agent    (conditional)
├── visualization agent   (conditional)
└── critic                (always present, tunable review frequency)
```

**Orchestrator ("collaborator").** The mathematician's single point of
contact — presented to them as a collaborator, not a project manager. Owns
strategy, explains theory on request, and dispatches the subagents below only
when a task genuinely needs one's specialized tools or discipline. Elicits
the mathematician's own approach and where they think the hard part is
*before* proposing anything, rather than opening with a proof architecture of
its own. All durable project state lives in files it maintains under
`shared/`, not in its own memory, since subagents are ephemeral and don't
talk to each other.

**Subagents it can dispatch:**

| Subagent | Always included? | Handles |
| --- | --- | --- |
| **proof-writer** | Yes (fixed core) | Drafts the informal, human-readable proof, with a discipline for labeling load-bearing claims and checking its own statement fidelity. |
| **researcher** | Yes (fixed core) | Literature discovery and citation verification. Tracks sources in `sources.md`; downloading the actual document stays the mathematician's/student's responsibility. |
| **agent-editor** | Yes (fixed core) | Updates the bundle's own agent configs as the project evolves. Can't touch its own config; safety-relevant changes need the mathematician's confirmation before being written. |
| **formalizer** | Conditional | Machine-checked verification (Lean/Coq/Isabelle) of key results, with axiom-hygiene checks to catch a stuck prover faking its way to a green build. |
| **numerics/sim agent** | Conditional | Simulations and numerical experiments, with checks that the real method ran and a disclosed log of every analytic choice. |
| **visualization agent** | Conditional | Figures, diagrams, and plots, checked for honest data provenance, honest chart construction, and captions that match what's shown. |
| **critic** | Yes (fixed role, tunable frequency) | Independently reviews the orchestrator's strategy and every subagent's output. Read-only everywhere except its own review notes. |

All of the above live in `shared/*.md` files (`proof_status.md`,
`verified_claims.md`, `integrity_checklist.md`, `glossary.md`,
`sources.md`), read on demand by every agent rather than auto-loaded, so the
ledger can grow without ballooning every request's context.

See `math_buddy_designer_src/REFERENCE_PATTERN.md` for the full reasoning
behind each of these — why the roster is shaped this way, the verification
discipline specific to each subagent, and the write-scoping rules that keep
them from stepping on each other's work.

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
