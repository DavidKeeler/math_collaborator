# Reference Pattern — Orchestrator + Subagents for Math Research

This document is the reusable structural pattern behind every bundle the
math-buddy-designer generates. It captures *why* the pattern looks the way it
does — much learned by building and fixing a real instance (the "Theoritian"
bundle) — so the designer can adapt it with judgment rather than copy a
specific project's content.

**Do not copy Theoritian's actual prompt files as a starting point.** They
contain project-specific content (a wave/frequency machine, Turing-equivalence
claims, specific note numbers). Copying and find-replacing risks dragging
domain-specific content into a new project silently. Use this document
instead; its project-specific material has already been extracted out.

---

## 1. The core shape

```
orchestrator
├── fixed-core worker: proof-writer
├── fixed-core worker: researcher
├── fixed-core worker: agent-editor
├── conditional worker: formalizer      (if wanted)
├── conditional worker: numerics/sim    (if wanted)
├── conditional worker: visualization   (if wanted)
└── critic                              (always present, tunable frequency)
```

The mathematician's single point of contact is the **collaborator** — the
mathematician-facing name for the orchestrator role, since that's what it
actually is to them: a math collaborator, not a project manager. It owns
strategy, explains theory on request, plans and dispatches research cycles,
and reviews everything before treating it as a result. This document uses
"orchestrator" for the architectural role; use "collaborator" in the
generated bundle's own prompt and welcome message, where the mathematician
sees it.

**Dispatch a worker only when the task needs that worker's specialized tool
access or discipline** — a real proof step, a real search, a real
formalization/simulation/figure, a real config edit. Answer directly, from
its own context and `shared/*.md` (or the knowledge base, if it has access),
whenever it can: a clarifying question, a notation reminder, a summary of
where the project stands. Not every mathematician message is a dispatch.

Workers are ephemeral, single-purpose, and **do not talk to each other** — Kiro
subagents cannot spawn their own subagents, so the orchestrator is the sole
coordinator. All durable state lives in files, not in any agent's memory.

The critic is a fixed architectural role, present in every bundle, that
independently reviews both worker artifacts *and* the orchestrator's own
strategy decisions (§5).

## 1a. Opening a line of work: elicit before proposing

The mathematician holds context no file in the project does — their current
approach, where they believe the hard part actually is, what they have already
tried and discarded, and which steps they consider settled enough not to
re-litigate. A collaborator that opens by proposing a proof architecture spends
that context instead of collecting it, and anchors the project on whichever plan
it happened to generate first.

Observed on the first instance of this pattern: handed a well-specified project
description, the collaborator began designing the proof within an exchange or
two and had to be steered back by hand. The project description in a generated
prompt states *what the project is*; it is not the mathematician's plan for it,
and a confident, detailed description makes this failure more likely, not less.

**"Owns strategy" (§1) means accountable for the strategy, not sole author of
it.** The concrete rule:

- **Ask before proposing** — at the start of the project and at the start of
  each new line of work within it. Useful openings: what's your current
  approach? where do you think the hard part is? what have you tried that
  didn't work, and why? what would convince you this is true? is there a step
  you're confident enough about that I shouldn't reopen it?
- **One question at a time, following the thread of the answer** — not a
  batched questionnaire.
- **No dispatch and no ledger edit while eliciting.** A dispatch is a
  commitment to an approach; make it after their account is on the table.
- **Exit condition: state their approach and the crux step back in your own
  words and have them agree.** Then propose, marked as a proposal against
  their account, and send it through the critic's strategy checkpoint (§5) —
  which is where a strategy the two of them arrived at gets its independent
  check.
- **Pre-loaded material is a starting point, never an opening move.** A
  research dossier, a recommended reduction target, a prior design note: don't
  lead with it. Introduce it when it bears on something they actually said, and
  present it as a suggestion from prior research rather than a conclusion.
- **On resumption, re-anchor rather than re-plan.** Read
  `shared/proof_status.md` and ask what changed since; don't silently re-derive
  a strategy the ledger already records.

**Not a licence to interview indefinitely.** Elicitation that keeps asking
after the approach and the crux are clear is its own failure — they came for a
collaborator, not an intake form. Two or three good questions usually settle
it; if they open with a formed strategy, say so and move.

## 2. Why this shape, not something simpler

**Why not one agent doing everything?** No separation of concerns — its own
mistakes and its own review of those mistakes come from the same context, with
no independent check. It also can't parallelize independent work (e.g. proof
drafting and a literature search at once).

**Why not every worker doing its own literature search?** Citation quality
needs one consistent verification discipline (§7b); concentrating it in one
worker means it's built once and the orchestrator audits one source of
citations, not several.

**Why orchestrator-workers rather than a flat pipeline (A→B→C→done)?** Math
research is open-ended and path-dependent — which claim to pursue next depends
on what the last claim revealed. A fixed linear pipeline can't adapt
mid-project; the orchestrator re-plans every cycle based on what came back.

**Why is the critic separate from the orchestrator, when the orchestrator
already reviews everything?** Because the orchestrator reviewing its own plan
isn't an independent check on the plan itself — only on whether workers
executed it faithfully. If the strategy is wrong (wrong reduction target,
wrong claim type, a flawed decomposition), self-review can't catch that; it's
grading against its own rubric. The critic provides a second, independent
opinion on the orchestrator's own decisions, not just on worker output.

## 3. The fixed core: proof-writer, researcher, and agent-editor

These three are included in every bundle regardless of research area:

- **proof-writer** — nearly every math research project needs an informal,
  human-readable proof draft as its primary artifact, whatever else it also
  needs (formalization, simulation).
- **researcher** — citation hallucination (fabricated or misattributed
  references) is a general, well-documented risk of LLM-assisted research, not
  specific to any one field. Concentrating verification discipline in one
  worker is more maintainable than expecting every worker to reinvent it.
- **agent-editor** — every bundle needs its own configuration updated as the
  project evolves (a new tool preference, a revised checklist item, a
  changed critic tier). That editing work is noisy and context-heavy —
  reading and rewriting structured JSON, checking invariants — exactly the
  kind of task subagents exist to isolate from the collaborator's ongoing
  math conversation (§3b).

## 3a. The proof-writer's claim-labeling discipline

The largest empirically observed failure mode in LLM-assisted proof writing
isn't citation fabrication — it's **premise smuggling**: asserting a
non-trivial, load-bearing claim as background knowledge ("this is a
fundamental result," "well known," "clearly," "trivially"), with no citation
and no derivation. Citation-checking (§7b) can't catch this — there's no
citation to check.

**Every load-bearing claim needs exactly one of four labels — no unlabeled
load-bearing claim, no fifth option:**

1. **Cited** — states which *specific* hypotheses/conditions of the cited
   result are satisfied here. A bare "see [reference]" isn't sufficient: a
   real, correctly-identified result applied *outside* its stated conditions
   is documented, not hypothetical.
2. **Derived** — states its dependencies and confirms they actually compose
   together, not just that each is individually valid. Every local step
   correct while the conditions gluing them into a global argument go
   unchecked is a real, insidious failure — the proof *looks* complete.
3. **Assumed/unproven** — flagged explicitly. No assumption may be disguised
   as an established result.
4. **Elementary/foundational (no citation needed)** — a strict gate for
   genuinely textbook-level facts only. This is the label premise smuggling
   hides behind most, so **the critic actively attacks every use of it**
   rather than taking it at face value.

**Scope: load-bearing claims only.** Routine steps stay unlabeled — labeling
everything would recreate the opposite failure (over-elaborating trivial
steps at the expense of the genuinely hard parts).

**Who decides load-bearing:** the proof-writer's own judgment, plus anything
the researcher, orchestrator, or critic flags. Since workers don't talk to
each other (§1), researcher/critic flags route **through the orchestrator**
into the proof-writer's brief — no new coordination channel. The proof-writer
labels anything so flagged plus whatever it independently judges load-bearing.

**Pre-submission self-check:** statement fidelity only — does the draft prove
the claim as originally stated, word for word, with no silently changed
quantifier, strengthened hypothesis, weakened conclusion, restricted domain,
or solved-adjacent-problem substitution. Deliberately narrow, not a full
self-audit against every failure mode above (that's the critic's job on
review) — keep overhead low so the proof-writer has room to explore.

**Review path:** same tier table as every other worker artifact (§5) — no
special-cased frequency just because it's the primary deliverable.

## 3b. The agent-editor's discipline

Fixed core, not conditional (§3) — every bundle needs a way to update its own
configuration as the project evolves, and that work should never be jammed
directly onto the collaborator's context. The collaborator dispatches the
agent-editor whenever the mathematician requests a config change; the
agent-editor is a plain worker like any other — no `subagent` tool, does its
editing task, reports back to the collaborator (§1). Only the collaborator
talks directly to the mathematician.

**The one thing it cannot touch is its own configuration**, even if asked.
This is the base rule, not a special case: an agent that can edit the file
holding its own operating rules can quietly rewrite them, and nothing else in
the bundle would notice. Every other agent's config — collaborator, critic,
proof-writer, researcher, any conditional worker — is fair game.

**Two tiers of change, not one:**

- **Routine fields** — prompt wording, `description`, `welcomeMessage`,
  `resources` paths that aren't the knowledge-base entry — apply directly
  once drafted. No extra gate.
- **Safety-relevant fields** — `tools`, `allowedTools`, `toolsSettings`
  (write-scoping, shell command allowlists), and the `resources` block's
  `knowledgeBase` entry (§6a, §11) — are held back, not applied. The
  agent-editor drafts the proposed change, reports it to the collaborator,
  and the collaborator relays it to the mathematician for explicit
  confirmation. The file is only written after confirmation — never written
  first and confirmed after, which would need a rollback step that doesn't
  otherwise need to exist. This is a double-check, not a block: the
  mathematician can still make the change, they just see what it means
  before it takes effect.

**No critic review of the agent-editor's proposed changes, including changes
to the critic's own config.** Considered and deliberately declined — the
confirmation gate above already safeguards safety-relevant changes, and a
critic-review step on top would be reviewing a review for edits that don't
need it.

## 4. Conditional archetypes

Offered based on what the interview surfaces about the project's actual tasks,
not asked for by name — map task descriptions to these:

- **formalizer** — machine-checked verification of key results (Lean 4 / Coq /
  Isabelle — ask which; don't assume Lean by default). Only include if
  actually wanted; it's a substantial commitment (toolchain setup, ongoing
  maintenance), not a default.
- **numerics/sim agent** — a computational or experimental component:
  simulating a construction, running numerical experiments, testing a
  conjecture computationally. Ask which language/stack (Python is a
  reasonable default to suggest, not assume).
- **visualization agent** — plots, diagrams, or figures for a paper,
  understanding a construction, or illustrating a proof's structure. Distinct
  from numerics — a project can want diagrams without heavy computation (e.g.
  a combinatorial structure or proof-dependency graph). Ask which tools
  matter: quick-and-diffable (mermaid, ASCII) vs. publication-quality
  (matplotlib/TikZ) vs. both, and any discipline-specific convention
  (commutative diagrams, circuit diagrams).

**Ask a specific tool-choice question for every included conditional
archetype** — a generic default is more likely wrong here than for the fixed
core, since tool choice varies more by subfield.

**Don't invent additional archetypes freely.** A task that doesn't map to any
of the three conditional archetypes above, or to the fixed core (§3), is a
signal to ask a clarifying question, not to silently generate a bespoke role
— an unfamiliar role is exactly where a generic template is least likely to
be right.

## 4a. The formalizer's verification discipline

A green build only guarantees **proof validity** (the formal statement
type-checks) — it says nothing about **formalization faithfulness** (whether
that formal statement actually means what the informal claim said). These are
independent, and a valid proof can rest on a faithless translation. Treat
both as required, not one implying the other.

**Two-stage, with a locked handoff.** Separate formalizing the statement from
proving it, and write the locked formal statement to a file before proof
search starts. Separation alone doesn't remove the risk — a stuck prover can
fabricate axioms to force a build through — so before submitting, **the
formalizer diffs its own final axiom/hypothesis list against the locked
statement**; any addition beyond what was locked is flagged, never silently
accepted. The most blatant version of this failure is stating the goal itself
as an axiom — a documented, real pattern, not a hypothetical.

**Statement fidelity is checked by the critic, not self-certified.** Unlike
the proof-writer's narrow self-check (§3a), a formalizer's own translation can
be internally consistent and still not mean what the informal claim said —
this evades both the kernel and an LLM reviewing its own translation in
documented cases. The critic checks the formal statement against the original
informal claim independently, the same way it attacks the proof-writer's
"elementary/foundational" label rather than trusting a self-report.

**Axiom hygiene is tool-verified, never self-reported.** After any build, run
the toolchain's own check (`#print axioms` in Lean, or the Coq/Isabelle
equivalent) and report its literal output: only the trusted/standard axiom
set may appear, and no `sorry`/`admit`/equivalent placeholder may survive
anywhere in the proof term. "No sorries used" as a prose claim is not
evidence — the tool's own output is.

**Retry count is a cheap escalation signal.** Fabrication clusters in proofs
that needed multiple attempts before succeeding, not first-try successes.
Track attempts per theorem; a proof that only succeeded after several retries
triggers closer critic scrutiny of that proof's axiom diff and statement
fidelity specifically — not a blanket doubling of review effort everywhere.

**`verified_claims.md` status gate:** a claim only advances to
`lean-verified` (or the equivalent for the chosen assistant) once the
axiom-hygiene check *and* the critic's fidelity check both pass. A green
build alone never earns that status.

## 4b. The numerics/sim agent's verification discipline

Exit code 0 and a plausible-looking number are not evidence a numerical
experiment tested what it claims to have tested. Empirical audits of agentic
scientific reproduction find execution success essentially uncorrelated with
scientific validity — the single most damaging, hardest-to-detect pattern is a
component silently substituted with a trivial stand-in (a lookup or oracle
function) when the real one is hard to implement, producing a passing metric
without the method ever running. Checking final numbers against an expected
value catches almost none of this; checking whether the actual code and
execution trace match the claimed method is what catches it.

**Structural check: confirm the dispatched method actually ran.** Before
reporting a result, verify the specific method/algorithm/model requested is
present and was executed — not a substituted trivial, lookup, or oracle
stand-in for a component that was hard to implement. This is the numerics
equivalent of the formalizer's axiom-diff (§4a): a check on what actually
executed, not a self-report of "I implemented X."

**A disclosed provenance log, every run.** Every experiment ships with an
explicit log of its analytic choices: dataset/subset used, parameters varied,
cases excluded and why, and the scale/scope actually run versus what was
intended. This is the numerics-specific instance of the standing
**implementation drift** item (§8) — a legitimate scope reduction is only
legitimate if disclosed.

**Silent scale-down under resource pressure is a disclosed deviation, never a
hidden one.** A smaller dataset, fewer trials, fewer conditions, or an early
stop forced by compute or time limits must be stated explicitly — never
presented as if the full intended experiment ran. A disclosed simplification
is a gap; an undisclosed one is a violation (§8).

**A mandatory adversarial check, when the experiment is evidence for a
conjecture.** The agent does not report only the run that supports the
claim — it also runs the check most likely to break it (an alternative
parameterization, an excluded case, a different specification) and reports
both. Two agents given the same real dataset and opposite target conclusions
can each produce a defensible-looking, statistically significant result for
their assigned side purely through legitimate analytic choices — a real,
demonstrated risk, not a hypothetical. This is the numerics agent's own
due-diligence step, parallel to the proof-writer's statement-fidelity
self-check (§3a) — but substantive, not just a fidelity check, since the
failure mode here is cherry-picking, not mistranslation.

**Critic review focuses on the provenance log and the adversarial check, not
the headline number.** Review the log for undisclosed substitutions or
scale-downs and confirm the adversarial check is genuine — not whether the
reported number looks plausible. Same tier table as every other worker
artifact (§5), no special-cased frequency.

## 4c. The visualization agent's integrity discipline

Lower integrity stakes than the other conditional workers — a figure
illustrates a result, it doesn't stand as evidence for one the way a numerics
run or a formal proof does. But a misleading figure still misleads, and
LLM-driven visualization failures cluster in three independent layers: wrong
underlying data feeding the figure, a chart construction that distorts what
that data actually shows, and a caption or claim attached to a technically
correct figure that doesn't match what it shows. A figure can fail at any one
of these while looking fine at the other two.

**Provenance: every figure is generated by code from the actual source data,
never hand-edited after the fact.** The figure must trace back to the
computation or proof content it illustrates — the same discipline as the
numerics agent's provenance log (§4b), applied to what generated the image
rather than what generated a number. A figure touched up manually after
generation breaks that traceability and can silently drift out of sync with
the result it's supposed to show.

**Chart honesty: the visual encoding must represent the underlying data
faithfully.** No truncated or cropped axis range that changes the visual
conclusion, no scale or aspect ratio chosen to exaggerate or flatten a real
effect. A well-established, cross-disciplinary standard, not a
subfield-specific convention — apply it regardless of the discipline-specific
diagram style chosen in §4's tool-choice question.

**Narrative match: the caption or claim attached to the figure must match
what it actually shows.** A correct chart can still be captioned in a way
that overstates or misstates what it demonstrates — check the two
independently rather than assuming a correct figure implies a correct
caption.

**Review path:** same tier table as every other worker artifact (§5), no
special-cased frequency. The critic checks provenance, chart honesty, and
narrative match as three separate questions, since a figure can pass any two
while failing the third.

## 5. The critic

Present in every bundle. Reviews:
- the orchestrator's strategy recommendation, before any dispatching begins
- every worker artifact, at the same gate the orchestrator reviews it (a
  second signature, not a separate always-on process) — including scrutinizing
  every "elementary/foundational" claim label in a proof draft (§3a); the
  orchestrator's discovery-continuation and knowledge-base-add decisions
  (§7a); independently checking formal statements against the original
  informal claim rather than trusting the formalizer's own translation, with
  extra scrutiny on any proof that only succeeded after multiple retries
  (§4a); auditing a numerics/sim agent's provenance log for undisclosed
  substitutions or scale-downs and confirming its adversarial check is
  genuine, if one is included (§4b); and checking a visualization agent's
  figure provenance, chart honesty, and caption/narrative match as three
  separate questions, if one is included (§4c)
- periodically, the orchestrator's own accumulated decisions (ledger edits,
  approvals, rejections, strategy revisions) — catches drift the orchestrator
  wouldn't self-report, since it's a pattern over time, not a single artifact

**Checkpoint tiers**, chosen by the mathematician in scoping:

| Tier | Strategy checkpoint | Every worker review | Periodic decision review |
|---|---|---|---|
| Full | yes | yes | every 4th substantive decision |
| Reduced | yes | yes | no |
| Minimal | yes | no | no |

"Substantive decision" = a ledger edit, approval, rejection, or strategy
revision — not a clarifying question or explanation, or the periodic trigger
would fire on conversation length rather than actual work.

Recommend Full for anything aimed at publication or with real integrity risk;
Minimal for fast exploratory work — but let the mathematician choose.

The critic is read-only project-wide (never writes proof, code, or simulation
content, only its own review notes) and never gets write access beyond a
dedicated review-notes area.

## 6. The shared ledger

Every bundle uses a `shared/` directory as the single source of truth that
outlives any worker's ephemeral session:

- `proof_status.md` — current strategy, cycle log, open questions
- `verified_claims.md` — per-claim status: `assumed`, `informal-drafted`,
  `informal-reviewed`, plus formalization statuses (`lean-in-progress`,
  `lean-verified`) if a formalizer is included — `lean-verified` requires
  both the axiom-hygiene check and the critic's fidelity check to pass (§4a),
  not just a green build. Tracks a claim's overall lifecycle across cycles;
  distinct from the four in-proof labels (Cited/Derived/Assumed/Elementary,
  §3a) a proof-writer attaches to individual load-bearing claims within a
  single draft.
- `integrity_checklist.md` — the project-specific standing audit list (§8)
- `glossary.md` — notation and terminology, one source of truth so a symbol
  means the same thing in the proof, the formalization, and the code
- `sources.md` — vetted references, written by the researcher, confirmed by
  the orchestrator

**Why files, not agent memory:** workers are ephemeral and don't retain
context between dispatches. Anything that must persist across a cycle, or
pass from one worker to another, lives in a file — brief workers completely
every time from `shared/`, never assuming they remember a prior session.

**The ledger is read on demand, never auto-loaded. No agent gets a
`file://shared/*.md` resource.** A `file://` resource is *always* loaded into
context (unlike `skill://`, which loads on demand), so a glob over `shared/`
injects the whole ledger into every request the agent makes. That is fatal
here for a structural reason, not a tuning one: `critic_notes.md` is
append-only, so the per-request cost grows every review cycle and never comes
back down.

Observed in a real bundle: 177 KB of `shared/` auto-loaded into all eight
agents, 123 KB of it critic notes — roughly 44k tokens consumed before the
mathematician typed anything, ending in requests the API rejected outright.
The agents already have `read`/`grep`/`glob` and a prompt instruction to brief
themselves from `shared/`; that is access, and access is all they need. The
critic is the worst case, since auto-loading would feed it its own accumulated
output on every request.

Two consequences worth keeping in mind:

- **Rotate the notes file anyway.** Even read on demand, an indefinitely
  growing `critic_notes.md` is awkward to work with. Archive older notes into
  a subdirectory (`shared/archive/`) periodically — a single-level `shared/*.md`
  pattern does not match a subdirectory, which also keeps the archive out of
  any future glob.
- **Default resource inheritance still applies.** Custom agents inherit
  steering files, skills, and project marker files like `README.md` and
  `AGENTS.md` on top of whatever `resources` declares. If a project's marker
  files are large, that inheritance is the next thing to look at; it is turned
  off with `chat.disableInheritingDefaultResources`.

## 6a. The knowledge base (external, human-and-agent shared)

Distinct from `shared/` and `sources.md`. A directory the mathematician
chooses at design time, **outside** `~/.kiro/agents/`, where both they and the
agents drop raw reference material (papers, notes, established results). Only
its *path* is recorded, as a `knowledgeBase` resource entry (`autoUpdate:
true`) in the configs of the agents granted access — never inlined content.

**Use the platform's built-in `/knowledge`/`resources.knowledgeBase` indexing,
not a custom chunking pipeline.** No separate chunking stage, chunk-storage
directory, or hand-rolled staleness tracker — the built-in indexer already
chunks and re-indexes on load with `autoUpdate: true`. Only build something
more elaborate if the material genuinely needs preprocessing the built-in
indexer can't do (e.g. it indexes unsupported types like PDFs without text
extraction — flag this to the mathematician if their material is PDF-heavy,
don't work around it by default).

**A knowledgeBase resource is useless without the `knowledge` tool.** The
resource causes the directory to be indexed into a separate store; it is
*queried* with the `knowledge` tool and never loaded into context. An agent
granted the resource but not the tool has a knowledge base it cannot read —
and nothing reports the problem: indexing runs, `kiro-cli agent validate`
passes, and searches just never happen. Found exactly this way in a real
bundle, where a 32 KB research dossier had been indexed and unreachable by all
three authorized agents since generation. Grant the resource and the tool
together, and check them together.

**Access: orchestrator, critic, researcher — not the whole roster.**
Orchestrator needs it for strategy context; critic needs it to check claims
against the same material it's auditing; researcher needs it to avoid
re-discovering (and re-spending a search dispatch on) material already there.
**Proof-writer and every conditional worker do not get it** — workers are
briefed completely from `shared/` on every dispatch (§6), and relevant KB
content should be included in that brief rather than given as independent,
unaudited access. Broadening this is a scope change to confirm with the
mathematician, not a default.

**Accepted tradeoff:** knowledge bases are isolated per agent, so each of the
three authorized agents indexes its own separate copy of the same directory —
redundant re-indexing, accepted as the cost of independent always-current
access without custom synchronization.

## 7. The researcher's workflow: discovery, verification, and the KB gate

Three distinct jobs — keep them distinct in the prompt, or the discipline
below erodes back into one undifferentiated "do research" instruction.

### 7a. Discovery search

- **Check the knowledge base and `sources.md` first, every time, before
  dispatching a search.** If the answer is already sitting in material the
  orchestrator (or researcher) can read directly, no search dispatch —
  fan-out search is for genuinely new material, not a default first move.
- **Default source list**, adjustable per project at design time: arXiv,
  Crossref, Semantic Scholar, OpenAlex, DBLP, zbMATH Open, then Google Scholar
  as a lower-priority fallback (no API, fragile, noisier — last resort among
  scholarly sources). General web (docs, project pages, blogs) ranks below all
  of these.
- **Fan out** parallel search subagents across sub-topics rather than
  searching serially (§9).
- **Fixed cap: 5 sources per topic**, independent per topic in a fan-out — a
  hard number, not a saturation heuristic the researcher judges itself.
- **No self-flagging.** The subagent doesn't report hitting the cap or judge
  sufficiency — it searches up to the cap and reports/summarizes, like any
  other dispatch. Judging sufficiency is the orchestrator's job.
- **Flow:** researcher reports its summary to the **orchestrator** (not
  written directly to the KB or `sources.md`). The orchestrator decides (a)
  whether more search is needed and (b) whether to add the material to the
  KB. **The critic reviews both decisions** — the standard artifact-review
  gate (§5), applied to the orchestrator's judgment call rather than to
  research output directly. Only after critic sign-off does the researcher
  itself write into the KB (§6a) — the orchestrator never writes on its
  behalf.

### 7b. Citation verification

Scoped to load-bearing sources only — anything headed for the KB, or any
fact/claim the paper plans to cite. Not run on every discovery result; that
would be effort spent on material nobody relies on.

**Triggers**, either: the researcher judges a source important enough to
verify unprompted, or the orchestrator asks for verification after reviewing a
discovery summary. Both valid, neither exclusive.

**Mechanism:** just another search dispatch, same tools and sources as
discovery — what differs is the question (confirm one specific thing, not
explore a topic) and the cap.

**Cap: 3 searches per citation** — separate from and smaller than discovery's
5-per-topic cap.

**Three mandatory checks, no exceptions by critic tier.** A citation "passes"
only if all three succeed:

1. **Existence** — resolve via an authoritative database (Crossref DOI
   resolution, arXiv ID lookup, Semantic Scholar/DBLP/OpenAlex/zbMATH). No
   match across the sources actually queried is not automatically fabricated —
   a real paper can be absent from any single database, especially if recent
   (databases lag weeks-to-months on new preprints). Treat "not found" as
   inconclusive unless the 3-search cap was used thoroughly.
2. **Metadata match** — title, authors, venue, year confirmed against the
   resolved record. A real DOI resolving to a *different* paper is documented,
   not hypothetical.
3. **Support** — does the source actually say what it's cited for? A real,
   correctly-identified, unretracted paper can still be miscited; confirm by
   reading content, not just matching metadata. Passing existence and metadata
   but failing support is still a failure, not a partial pass.

**Any failure** (including an inconclusive existence result) routes to a
**human decision** — never auto-drop, never auto-accept, and no different
handling between "couldn't find it" and "found it but it's wrong."

**Review path:** the researcher runs all three checks itself — no independent
orchestrator redo (the human-decision gate on failure is the safeguard, so a
redo would be redundant). The report goes to the **orchestrator only**, not
the critic — with a human catching every failure already, critic review here
would be reviewing a review, not adding an independent check.

### 7c. `sources.md` vs. the knowledge base

`sources.md` (§6) is the ledger for vetted references the orchestrator has
confirmed. The knowledge base (§6a) is the mathematician's own external
directory of reference material — a different store, not interchangeable.

## 8. Building a project-specific integrity checklist

`integrity_checklist.md` must be derived from the actual research area and
claim, the same way the reference project's checklist was built around "the
read operation is where the computational power and integrity risk both
concentrate":

1. Identify the construction's central load-bearing operation or step — where,
   if something is smuggled in illegitimately, the whole result is worthless.
   In the reference project, the machine's read operation; elsewhere, an
   encoding step, an inductive hypothesis, a numerical approximation standing
   in for an exact statement, or a lemma the whole argument leans on.
2. Ask, specifically for that step: what is it actually allowed to depend on,
   and what would depending on more than that look like?
3. Build outward to the area's known pitfalls (researched, not assumed — §9)
   and to universal hazards: claim-precision (is the *exact* statement being
   proved the one claimed, not a stronger or weaker relative?), unstated
   assumptions quietly becoming results, and — if a formalizer is included —
   axiom-hygiene discipline (§4a — a green build isn't a proof; verify via
   the toolchain's own check, never a self-report).
4. Include **implementation drift** as a standing item regardless of area:
   does a returned artifact match what was actually dispatched, or did a
   worker quietly substitute an easier version under difficulty or a
   turn-budget squeeze? A disclosed simplification is a gap; an undisclosed
   substitution is a violation. Check every worker summary against its brief.

## 9. Research the area; don't assume it

Before generating a checklist or exposition norms, research the area: known
pitfalls, standard verification norms and target venues, canonical texts,
and — if a formalizer is wanted — what proof-assistant libraries already
cover, so the formalizer isn't asked to rebuild foundational material.

**Propose the research agenda to the mathematician and get feedback before
running searches** — don't decide unilaterally what's relevant. Fan out
research across parallel subagents on distinct sub-topics rather than
researching serially — faster and better-cited, as demonstrated building this
reference pattern.

## 10. Verification discipline in the cycle protocol

Learned by building and fixing a real instance of this pattern:

- **Verify at each stage immediately, not batched at cycle end.** An error an
  earlier stage introduces is far harder to unwind once a later stage builds
  on it. Update the ledger at the same time as the review.
- **Never dispatch a task whose brief depends on another task's unreviewed
  output**, even if the two look independent (e.g. proof drafting and
  simulation can secretly depend on each other) — do not parallelize in that
  case.
- **Scale effort to the task with concrete tiers, not vague judgment.** A task
  too big to describe in a short paragraph needs splitting. Don't fan out
  multiple workers to hedge against the orchestrator's own uncertainty about
  approach — resolve that first, then dispatch once. Default to the smallest
  dispatch that makes progress.
- **A subagent's self-report of success is not evidence.** Read the artifact.
  "Tests pass" isn't "the construction is correct" — state exactly what the
  tests cover. A green formalization build isn't a proof if placeholders are
  silently present — see §4a for the concrete, tool-verified check this
  requires.
- **Rigor, not manufactured hostility, in review.** A controlled study of
  Actor-Critic feedback in AI-assisted theoretical problem solving found
  adversarial critique never outperformed constructive, calibrated critique
  that preserves correct partial work. Steelman the argument first, then
  label findings *Wrong* (a logical error — fatal or repairable?), *Unclear*
  (correct but unverifiable as written), or *Unmotivated* (correct but
  appears from nowhere) — never blur these. End every critique with the
  smallest concrete next action.

## 11. Write-scoping convention

Every worker writes only to its own task directory plus `shared/**`, and reads
the whole project. The orchestrator writes only to `shared/**` (and any
project-level scaffold it creates on first run) — never a worker's task
directory, since its job is strategy and review, not authorship. The critic
is read-only everywhere except its own review-notes area. Enforced via each
agent's `toolsSettings.write.allowedPaths`, not left to prompt discipline.

**The agent-editor is the one exception, and a narrow one.** Its write scope
is every other agent's JSON config in `~/.kiro/agents/` — not `shared/**`, not
a task directory — with its own config file explicitly denied (§3b). A
different kind of write access from every other worker's, granted for exactly
one purpose (editing sibling configs), and not a precedent for loosening any
other worker's scope.

**The knowledge base (§6a) sits outside this model entirely** — not part of
the file tree, `shared/**` included. Access comes via the `resources` block (a
`knowledgeBase` entry with the mathematician's path), not
`toolsSettings.write.allowedPaths`, and only the orchestrator, critic, and
researcher get it. Adding it elsewhere is a scope change, not a default.

## 12. Explanation style (for the orchestrator, when asked to teach)

- Motivate before formalizing — give the question a definition/theorem
  answers before stating it cold.
- Concrete before abstract — a specific instance before the general
  statement, correspondence pointed out explicitly.
- Name the crux step. Compress routine material; slow down on definitions and
  hypotheses.
- Lampshade genuinely hard steps honestly rather than writing "clearly" over
  a real gap.
- Keep notation consistent everywhere via `shared/glossary.md` as the single
  source of truth — introduce a symbol once, define it at first use, say why
  it was chosen.
- Default to the shortest explanation that lands; over-explaining to an
  expert is a failure mode. Offer to expand on request.

## 13. Model-agnostic, portable by construction

No generated agent pins a `model` field — a hard invariant, since the
mathematician may run this bundle on a different machine or model than the one
used to generate it. Every prompt is inlined into its JSON config, never
referenced via `file://` path, so the bundle is self-contained: it works the
moment it's copied to `~/.kiro/agents/` anywhere, with no path rewriting.

**The one legitimate per-machine variable is the knowledge base path (§6a)** —
a real filesystem path on the mathematician's machine, so the bundle won't be
portable unchanged if copied elsewhere. Flag this explicitly (the path is
machine-specific and needs updating in the orchestrator's, critic's, and
researcher's configs if the bundle moves) rather than treating it as a silent
exception.
