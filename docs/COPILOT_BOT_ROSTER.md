# BDA Copilot Bot Roster

状态：活跃

最后核验：2026-09-13（Asia/Shanghai；本轮新增 bot 名册、结构分析与故障诊断能力，并加入 stance 轴、交接通道与 conductor/steward/auditor）

权威范围：Copilot bot 名册、各 bot 的职责边界、交接协议，以及 bot 可用的 skill/MCP 清单。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：不取代 [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md)（能力与权限的权威），也不取代 [MCP capability surface](MCP_CAPABILITY_SURFACE.md)（外部调用契约）。本文在两者之上定义“谁负责链条的哪一段”；职责轴（stance）、交接协议与委派规则在 [Copilot bot governance](COPILOT_BOT_GOVERNANCE.md)。

## Why a roster rather than one assistant

Until now BDA had one Copilot with a configurable capability set. That is enough
to answer questions and enough to run one bounded agent run, but it leaves the
research chain without owners: the same undifferentiated assistant is asked to
turn a vague sentence into a research question, to sort literature, to pick a
route, to wait on a cluster job, to explain why that job died, and to write the
result back into the record. Those are different jobs with different failure
modes, and one system prompt cannot state the boundary of all of them at once.

A **bot** is a named operator that owns one phase of the chain. It is not a new
execution engine and not a second tool layer. It is a declaration of:

- which capabilities the phase needs, and — more importantly — which it does not,
- what the operator is accountable for and what it must refuse,
- which bot the work goes to next.

The one law that makes the roster safe to add:

> **A bot narrows; a bot never widens.**
> The capabilities in force are `bot.capabilities ∩ project.enabled_skills`.
> Naming a bot can only take capabilities away. A bot that names a capability
> the project has not enabled does not get it, and a project that enabled
> everything still gets only what the bot declares.

This is the rule `capabilities_for_turn` already applies to a single-capability
hint, generalised from one to a set. It is what stops “select the planner bot”
from becoming a privilege-escalation path, and it is the property the adversarial
tests exist to attack.

## The chain and its twelve operators

The phases run in order, but the chain is a loop, not a line: `medic` sends work
back to `planner`, and `archivist` sends the next question back to `briefing`.

Nine of the twelve *produce*: they own a phase. The other three do not do the
work at all — `conductor` decides who works next, and `steward` and `auditor`
judge what a producer claimed. That is the `stance` axis, and it is enforced at
import rather than stated in a charter; the argument for it, and the rules it
imposes, are in [Copilot bot governance](COPILOT_BOT_GOVERNANCE.md).

Every operator that hands off also holds `chain-messaging`. Before that, a
charter could say "hand this to medic" while the platform had no way to carry
anything across the boundary, which made the handoff a sentence rather than a
step.

| # | Bot | 中文 | Stance | Owns | Capabilities | Hands off to |
| --- | --- | --- | --- | --- | --- | --- |
| — | `conductor` | 总调度 | direct | Deciding which operator works next, delegating to it, and saying when the chain stops | `project-read`, `research-read`, `chain-orchestration`, `chain-messaging` | `auditor` |
| 0 | `briefing` | 选题起草 | produce | Turning an intent into a stated, falsifiable research question with success criteria | `project-read`, `research-read`, `knowledge-authoring`, `chain-messaging` | `librarian`, `scout` |
| 1 | `librarian` | 文献整理 | produce | Finding, ingesting and organising literature with retrievable provenance | `research-read`, `literature-search`, `chain-messaging` | `briefing`, `scout` |
| 2 | `scout` | 靶点情报 | produce | Target identity, target intelligence, and closing retrievable Research gaps | `project-read`, `research-read`, `target-intelligence`, `research-gap-repair`, `chain-messaging` | `structuralist`, `planner` |
| 3 | `structuralist` | 结构与残基 | produce | Reading structures: chains, residues, gaps, contacts, sites, confidence | `project-read`, `structure-analysis`, `chain-messaging` | `planner`, `analyst` |
| 4 | `planner` | 路线规划 | produce | Choosing the route and drafting the compute that implements it | `project-read`, `research-read`, `workflow-planning`, `compute-drafting`, `chain-messaging` | `runner` |
| 4 | `steward` | 资源守门 | review | Checking a plugin's declared resources against what the chosen queue will actually give it | `project-read`, `review-audit`, `chain-messaging` | `planner` |
| 5 | `runner` | 步骤推进 | produce | Carrying a confirmed run across its waits and reporting what settled | `project-read`, `workflow-planning`, `agent-orchestration`, `chain-messaging` | `medic`, `analyst` |
| 6 | `medic` | 故障诊断 | produce | Explaining why a job failed, in terms of what was declared versus what ran | `project-read`, `failure-diagnosis`, `chain-messaging` | `planner`, `runner` |
| 7 | `analyst` | 结果解读 | produce | Interpreting recorded computational and bench results without inventing any | `project-read`, `result-interpretation`, `wetlab-read`, `wetlab-authoring`, `chain-messaging` | `archivist`, `structuralist` |
| 8 | `archivist` | 记录归档 | produce | Attaching evidence to research goals and drafting the record of what was decided | `research-read`, `research-trace-authoring`, `knowledge-authoring`, `chain-messaging` | `briefing` |
| — | `auditor` | 复核 | review | Ruling on an operator's claims against the evidence it produced and the charter it works under | `project-read`, `research-read`, `review-audit`, `chain-messaging` | `conductor` |

### What each bot must refuse

A bot's charter is mostly a list of refusals, because that is the part a
capability set cannot express. These go into the `charter` string and reach the
model verbatim.

- `briefing` — must not answer the research question it is drafting. Its output
  is a question, its success criteria and its unknowns, saved as a pending-review
  note. A brief that already contains the conclusion was written backwards.
- `librarian` — must not summarise a paper it has not retrieved. A queued search
  is queued, not done; a citation without a checksum-backed excerpt is a lead,
  not evidence.
- `scout` — must not invent target identity. Composite or modified molecular
  identities stay `requires_review` until one exact entity maps to a UniProt
  accession. Scientific gaps are not “repaired”; only retrievable ones are.
- `structuralist` — must not infer function from geometry. It reports residues,
  distances, gaps and confidence. “These residues are within 4.5 Å” is a
  measurement; “this is the active site” is a claim that needs evidence from
  `librarian` or a recorded experiment. It must state model confidence whenever
  the structure is predicted, because a contact list computed from a
  low-confidence loop is arithmetic on noise.
- `planner` — must not confirm or submit. It produces a draft and the reasons for
  it, including the reasons against the routes it did not pick.
- `runner` — must not poll, must not assume an outcome, and does not advance
  anything itself: the run moves because the platform moves it, and the bot's job
  is to wait correctly and report what settled. A failed job is a result to
  report, not an error to retry silently.
- `medic` — must not guess. Every diagnosis names the evidence it rests on and
  says plainly when that evidence does not determine the cause.
- `analyst` — must not invent measurements, and must not rank by a score whose
  mechanism it has not checked. It reports what was recorded, with units and the
  analysis version that produced it.
- `archivist` — must not decide, and cannot close a goal. Marking a goal answered
  is a scientific judgement and stays with a person; the bot says which linked
  result it thinks answers a goal and leaves the call to the reader. The charter
  originally instructed it to mark goals answered, which was an instruction to do
  something no tool exposes — the failure mode being a model that reports having
  done it.
- `conductor` — must not do the work, and must not authorise it. It holds no
  capability that changes the research record, and delegating is not a way to
  reach one: the delegated operator runs under its own charter and its own
  capabilities. It also cannot supply the user's words — a delegated run's write
  gate reads the *originating* request, so an instruction the director wrote can
  steer work but never unlock a write.
- `steward` — must not edit the draft it reviews and must not confirm it. It
  reports the two numbers that disagree and hands the finding to `planner`. It
  must also approve when the declaration is sound, because a review that only
  ever objects stops being read. Its charter named four numbers — slots,
  per-host span, thread budget, GPU — that no tool exposed: `get_compute_status`
  returns a draft's free-form specification, while the numbers that reach LSF
  come from the plugin registry row and from the queue chosen on the `bsub`
  command line. `review_compute_declaration` reads them the way the cluster
  does, so the charter stopped naming work the platform could not do — the same
  defect `archivist` had, caught the same way.
- `auditor` — must not repair what it finds. Its output is a verdict per claim
  (`supported` / `unsupported` / `contradicted` / `outside_charter`), ruled on
  what the operator actually called rather than on what it said it did. A claim
  citing nothing is `unsupported`, and a handover with no run behind it is
  *unreviewable* rather than clean.

### Handoff protocol

A handoff is still not a transfer of control: the bot names which operator should
take the next step, and the client — chat UI, agent-run creation, or an MCP
caller — selects it. The platform does not switch bots by itself, because a bot
that could re-select itself with wider capabilities would defeat the narrowing
law. `handoff` remains advisory and is validated only for referential integrity.

What changed is that a handoff now **leaves something behind**. `post_handoff`
appends a row to `copilot_handoffs` carrying the summary, the ids the next
operator needs, the questions this one could not settle, and — the load-bearing
part — a list of claims, each with the evidence reference behind it. A prose
summary can only be read; a claim with its reference can be checked, which is
what gives `auditor` a defined output rather than a second opinion. A claim
submitted without a reference is recorded as `unsupported` rather than rejected,
because rejecting it would keep the operator's own mistake out of the record and
leave the handover looking clean.

The one exception to "the client selects" is `conductor`, whose
`delegate_to_operator` opens a child run owned by a *different* operator. The
child's tools are `target.capabilities ∩ project.enabled_skills` — the project's
bound, not the director's. Intersecting against the parent, the way
`spawn_subagent` does, would be wrong here rather than merely strict: a director
holds none of a librarian's literature tools, so the intersection removes
`start_literature_search` and hands back a child that reads like an operator
that failed. The invariant that matters is that both runs stay inside what the
project authorised, and that the director executes none of the child's tools.
Delegation requires a durable run, so chat can only ever recommend an operator.

## New capabilities this roster adds

Two phases had no capability to stand on, so the roster adds two read-only ones;
the responsibility axis adds three more (`chain-messaging`, `chain-orchestration`
and `review-audit`), described in
[Copilot bot governance](COPILOT_BOT_GOVERNANCE.md).

### `structure-analysis` — 结构与残基分析

The platform stored structures and rendered them in the browser, but nothing on
the server could answer a question about a residue. `structuralist` needs that,
and so does every bot that wants to talk about an interface.

Implemented as a table-free domain, `backend_v2/app/structures/`:

- `kernels.py` — pure functions over PDB/mmCIF **text**. No database, no object
  storage, no network. The parsing and the geometry live here, and this is what
  the unit tests exercise directly.
- `service.py` — the one impure step: artifact id → project check → bytes from
  object storage → kernel. It mirrors `wetlab/analysis.py`, which already
  established that shape for instrument files.

It declares no models and no router, so it needs no migration, no flow-matrix row
and no module descriptor. Structures arrive as artifacts, which are already
write-once and checksummed; a second table would only be somewhere for a copy to
go stale.

Three tools:

| Tool | Answers |
| --- | --- |
| `analyse_structure` | What is in this file: format, chains, residue counts, per-chain one-letter sequence, numbering gaps, ligands and solvent counted separately, disulfides, and a pLDDT or B-factor summary |
| `list_structure_contacts` | Which residues of one chain lie within a cutoff of another, with the closest atom pair and its distance — the interface, as measurements |
| `describe_structure_site` | Which residues lie within a radius of a named site (a residue, or a ligand by component code), with distances — the pocket, as measurements |

`structuralist` pairs this with `project-read` and nothing else, and the pairing
is load-bearing rather than incidental: the structure tools all take an
`artifact_id`, and `project-read` is the bot's only route to one. Targets carry
`structure_artifact_id`; candidates carry both `structure_artifact_id` and
`complex_artifact_id`, and the second is what an interface question is actually
asked about. Drop `project-read` from this bot and it keeps three tools it can
never supply an argument to.

All three are `execution_mode="read"` under capability `structure-analysis`, and
therefore appear on the MCP surface automatically: an external MCP client holding
a grant for a project can analyse that project's structures with no new transport
code.

### `failure-diagnosis` — 故障诊断

`get_compute_status` reports `error_code` and `error_message`. That is enough to
see that a job failed and never enough to see why. The recurring failures in this
project are not exceptions in the platform; they are disagreements between what a
job declared and what it was actually given:

- a stage whose comment says it needs no GPU, submitted to a queue that merges
  `GPU_REQ` into every job;
- `-n`, `span[ptile=]` and the tool's own thread count disagreeing;
- a plugin registry row whose declaration makes the job exit in seconds with an
  empty log;
- a staged-input loop that verified a manifest which never listed the missing
  file.

`diagnose_compute_failure` gathers the recorded evidence for one job — status,
error code and message, the status-event timeline, the retry chain, and the
declared `runtime_spec` — and runs an explicit rule set over it.

Which records those are took a correction. The first version read `JobAttempt`,
which has `status`, `error` and `finished_at` columns and looks like the history
of a job's attempts. It is not: exactly one row is written per job, at dispatch,
with `status="dispatching"`, and it is never updated, so those columns are
permanently `"dispatching"` and `NULL`. Three rules read them and could not fire
on any real job. The records that do exist are the `JobEvent` rows — one per
status transition, each timestamped — and the retry chain, which is a linked list
of *separate* `Job` rows joined by the `retry_of` payload on each `job.pending`
event. Runtime is measured from acceptance rather than row creation, so a long
queue wait cannot hide a fast failure. Each rule produces a
finding with a confidence of `confirmed` (the evidence states it) or `possible`
(the evidence is consistent with it), the evidence it used, and a remedy. A job
whose evidence matches no rule returns no findings and says so: an invented cause
is worse than no cause, because it ends the investigation.

The rules are data, not prose, so they can be tested one at a time and extended
without touching the tool.

## Chat, agent runs and MCP now offer the same tools

The roster's first version shipped with `structuralist` and `medic` inert in
chat, and the cause was older than either of them.

`registry.py` exists because a tool used to be declared in three places and
nothing failed when one was missed — the tool simply became unreachable. The
agent loop and the MCP surface were moved onto it; **chat was not**. It kept
three hand-written schema lists covering the tools that need the research
context, the project context or the action service, and no list was ever written
for the ones needing only a session. Thirteen registry tools — every bench tool,
the research-goal tools, and the whole structure and diagnosis surface — were
declared in `capabilities.py` as chat tools, returned by
`tools_for_capabilities`, dispatchable through `REGISTRY.execute`, and silently
dropped before the model ever saw them.

So `structuralist` resolved its capabilities, passed the narrowing law, appeared
in the picker, and had none of its tools; `medic` kept `get_compute_status` and
lost the tool that says *why* a job failed — the exact state it exists to fix.

Chat now derives its schemas from the registry, using the same `requires` rule
`REGISTRY.execute` enforces, so what is offered and what will run cannot
disagree. A second list drifted the same way: `WRITE_TOOL_NAMES`, which
`tasks.py` filters through the user's own words before allowing a write, named
five of the registry's ten writes. That was harmless only while the other five
were unreachable; deriving the schemas without also deriving this set would have
exposed five writes with no intent check. It now derives from
`REGISTRY.write_ids()`, and `actions.request_allows` answers **no** for a write
whose bilingual vocabulary nobody has written rather than raising.

One consequence is worth stating plainly: the five bench and trace writes
(`analyse_bli_run`, `analyse_akta_run`, `analyse_enzyme_plate`,
`promote_candidate_to_bench`, `attach_to_research_goal`) have no entry in
`actions._ACTION_REQUEST_TERMS`, so in chat they are denied and therefore not
offered. They remain available inside a durable agent run. Giving one of them a
vocabulary is what turns it on in chat, deliberately and one at a time.

## Skill and MCP inventory

“Skill” in this repository means one capability id, and the capability is what
grants tools. After this change the full list is:

| Capability (skill) | Mode | Tools | Bots that hold it |
| --- | --- | --- | --- |
| `agent-orchestration` | read (async) | `await_compute_job`, `spawn_subagent` | runner |
| `chain-orchestration` | read (async) | `list_operators`, `delegate_to_operator` | conductor |
| `failure-diagnosis` | read | `get_compute_status`, `diagnose_compute_failure` | medic |
| `project-read` | read | `list_project_targets`, `list_project_candidates`, `list_experiment_results`, `get_workflow_status`, `get_compute_status` | conductor, briefing, scout, structuralist, planner, steward, runner, medic, analyst, auditor |
| `research-read` | read | `research_overview`, `search_research`, `get_research_items`, `get_dataset_slice`, `get_reference`, `get_reference_content`, `list_research_goals` | conductor, briefing, librarian, scout, planner, archivist, auditor |
| `result-interpretation` | read | `list_project_candidates`, `list_experiment_results` | analyst |
| `review-audit` | read | `list_operator_charters`, `read_operator_work`, `review_compute_declaration` | steward, auditor |
| `structure-analysis` | read | `analyse_structure`, `list_structure_contacts`, `describe_structure_site` | structuralist |
| `wetlab-read` | read | `list_proteins`, `compute_concentration`, `plan_dilution_series` | analyst |
| `chain-messaging` | draft | `post_handoff`, `read_handoffs` | conductor, briefing, librarian, scout, structuralist, planner, steward, runner, medic, analyst, archivist, auditor |
| `compute-drafting` | draft | `get_compute_status`, `create_compute_draft` | planner |
| `knowledge-authoring` | draft | `search_project_knowledge`, `create_knowledge_draft` | briefing, archivist |
| `research-trace-authoring` | draft | `attach_to_research_goal` | archivist |
| `wetlab-authoring` | draft | `promote_candidate_to_bench`, `analyse_bli_run`, `analyse_akta_run`, `analyse_enzyme_plate` | analyst |
| `workflow-planning` | draft | `get_workflow_status` | planner, runner |
| `literature-search` | queue | `start_literature_search` | librarian |
| `research-gap-repair` | queue | `resolve_research_gaps` | scout |
| `target-intelligence` | queue | `start_target_intelligence` | scout |

Everything in that table is reachable over MCP except the two async ones.
`agent-orchestration` and `chain-orchestration` are excluded by construction:
`await_compute_job`, `spawn_subagent` and `delegate_to_operator` declare
`requires="agent_run"`, an MCP client has no run to suspend, and `mcp.py`
refuses to list them. `runner` and `conductor` are therefore the two operators
whose full capability set exists only inside a durable agent run — `conductor`
can read the roster and the handover record from chat, and can only recommend an
operator there rather than delegate to one.

`chain-messaging` is a `draft` capability that an unbound MCP grant still does
not get: `mcp.available_tools` degrades such a grant with `REGISTRY.write_ids()`,
which is the conservative set and includes `post_handoff`. The narrower
`user_intent_write_ids()` — the set the chat intent gate filters — is the one
that excludes it, and it has to be asked for by name.

## Surfaces

One declaration, three surfaces, no duplication:

- `GET /copilot/bots` lists the roster with its capabilities, charter, phase,
  stance, handoffs and — for each producer — who reviews it. The frontend reads
  that response rather than restating it: the hand-written skill registry it sits
  beside kept its own copy of the backend's capability list, and a copy is what
  drifts. The picker groups by stance rather than by phase, because a director is
  not the step before `briefing` and a reviewer is not the step after
  `archivist`, which is what one ordered list would say.
- `GET /copilot/projects/{id}/handoffs` returns the chain's handovers, newest
  first, with each claim's evidence reference and confidence. A record only the
  operators could read would make the channel's justification — that what one
  operator claimed is auditable afterwards — true for `auditor` and false for the
  person it is ultimately for.
- `POST /copilot/agent-runs` accepts `bot`. The server resolves the bot to its
  capability set, intersects it with the project configuration, and derives
  `allowed_tools` from the result — the client never names a tool.
- `POST /copilot/chat` accepts `bot` as a turn hint, with the same intersection.
  The existing single-capability `skill` hint stays, and `bot` and `skill` are
  mutually exclusive: two narrowing hints in one request is an ambiguity, not a
  finer filter.

### The charter has to travel with the run

A durable run records its bot (`copilot_agent_runs.bot`, migration
`0059_copilot_agent_run_bot`). Narrowing the tools alone would not have been
enough: most of the roster shares a tool set with some other bot, and two bots
with the same tools and the same instructions are the same operator. The column
holds the **id**, never the charter text, so the loop reads the charter from the
roster on every turn — editing a charter changes how runs already in flight
behave, instead of leaving each run operating under a snapshot of what the
charter said the day it started. An id the roster no longer knows contributes
nothing, which leaves an undifferentiated run rather than a broken one.

A subagent inherits its parent's bot unless given one. A child doing part of the
medic's work is still doing the medic's work, and a child that silently lost its
parent's refusals would be the one place the roster stopped applying.
`delegate_to_operator` is the exception that gives one, and it is why a director
needs a tool of its own rather than a flag on `spawn_subagent`.

What a child must **not** inherit is the authority to write. The write-intent
gate reads the user's own request, and a child's goal is written by the parent
model — so `agent_loop.authorising_text` walks to the root run and reads its
goal. Without that, a director emitting "search the literature and save it"
would be authoring the user's half of the conversation. The same hole existed in
`spawn_subagent` before delegation did, and the walk closes both.

## Where the roster reaches the rest of the platform

- **The chat client no longer keeps its own capability list.** The hand-written
  `features/copilot/skills/registry.ts` — nine capability ids with their own
  bilingual triggers, plus a `systemPrompt` field nothing ever read — is retired.
  Its vocabulary now sits on the operators that own it, and matching resolves
  specificity by containment: a matched token loses to another matched token that
  contains it, which is what lets "literature review" reach `librarian` without
  `auditor`'s bare "review" turning it into a tie. See
  [Copilot bot governance](COPILOT_BOT_GOVERNANCE.md).
- **An Autopilot stage names the operator accountable for it**
  (`autopilot_stages.operator`, migration `0061`), frozen at confirmation like
  its risk tier, and the stages whose product is reasoning open a durable run
  owned by that operator. It grants nothing: the run resolves
  `bot.capabilities ∩ project.enabled_skills`, its authorising text is the brief
  a person confirmed, and a held stage never reaches the adapter. Scope and
  maturity stay as recorded in
  [Autopilot campaigns](AUTOPILOT_CAMPAIGNS.md) — a stage with an operator is not
  a complete unattended loop.

## What this does not change

- No bot executes shell commands, reads arbitrary paths, or reaches credentials.
- No bot confirms or submits compute, applies a route, cancels a job, approves
  evidence, or deletes project data. Those remain user actions, as recorded in
  the capability plan.
- Write tools still require the user's own words to authorise them in the same
  turn. Selecting a bot is not a request, and neither is delegating to one:
  `actions.request_allows` still reads what the person asked for, now resolved
  through the root run rather than the run that happens to be executing.
- A reviewer cannot repair what it finds and a director cannot do the work, and
  neither is a matter of charter wording: both are import-time roster errors.
- Budgets, depth limits, audit attribution and citation policy are unchanged. A
  bot is a narrower mandate inside the existing envelope, never a wider one.

## Acceptance

Each of these holds, and has a test that fails when it stops holding.

| # | Property | Where |
| --- | --- | --- |
| 1 | Every bot's capabilities are registered ids; every `handoff` names a bot that exists; a roster that breaks either fails at import | `test_copilot_bots.py` |
| 2 | For every bot and every project configuration, resolved == declared ∩ enabled | `test_copilot_bots.py` |
| 3 | A bot cannot reach a capability the project disabled, and its tools are absent from `allowed_tools` | `test_copilot_bots.py` |
| 4 | An unknown bot hint resolves to nothing rather than to the project ceiling; `bot` + `skill` together are denied, at the API and again in `narrow` | `test_copilot_bots.py`, `test_v2_domains.py` |
| 5 | An unknown bot id is 404 from the API and from run creation, never a silent fallback | `test_copilot_bots.py`, `test_v2_domains.py` |
| 6 | A run created for a bot carries that bot's charter into every turn; a run without one carries only the loop policy; a retired id degrades to undifferentiated; a subagent inherits | `test_copilot_bots.py` |
| 7 | PDB and mmCIF of the same structure yield the same chains, residues and sequences; numbering gaps are reported rather than closed; a FASTA, a JSON and prose are refused | `test_structure_kernels.py` |
| 8 | Contacts are symmetric — (A, B) is the transpose of (B, A) — reported by closest atom pair, monotonic in cutoff, and exclude solvent | `test_structure_kernels.py` |
| 9 | A predicted model's B-factor column is labelled possible pLDDT only when the file declares no resolution; a malformed resolution is absent, not zero | `test_structure_kernels.py` |
| 10 | Structure tools refuse an artifact from another project, a deleted one, and one over the size cap; a non-structure is 422, not 500 | `test_structure_service.py` |
| 11 | Every diagnosis rule fires on the evidence it claims to read and stays silent on a baseline that lacks it; unrecognised evidence yields no findings and says so | `test_compute_diagnosis.py` |
| 12 | Every finding names its evidence, its remedy and its confidence; the evidence bundle carries no object keys or credentials | `test_compute_diagnosis.py` |
| 13 | `diagnose_compute_failure` refuses a job id from another project | `test_compute_diagnosis.py` |
| 14 | The new capabilities reach an external MCP client with no transport code of their own | `test_copilot_mcp.py` |
| 15 | The chat sends a selected bot instead of a matched skill and never both; a roster that failed to load leaves the chat working, unhinted | `CopilotChat.test.tsx`, `bots/registry.test.ts` |
| 16 | A `review` bot declaring a write capability, a `direct` bot declaring one, a stance-only capability on the wrong stance, and review or delegation aimed at a non-producer all fail at import | `test_copilot_bots.py` |
| 17 | Every producer is reviewed by somebody, and no producer names its own reviewer | `test_copilot_bots.py` |
| 18 | Every operator that hands off holds `chain-messaging`, so no charter names a step the platform cannot take | `test_copilot_bots.py` |
| 19 | A delegated run is owned by the target operator and keeps the tools that define it; a subagent of the *same* operator is still bounded by its parent | `test_copilot_chain.py` |
| 20 | A director may delegate only to the operators it declares, and an operator with nothing enabled is refused rather than delegated to | `test_copilot_chain.py` |
| 21 | A delegated run's write gate reads the originating user request, not the director's instruction — and the same holds for a subagent | `test_copilot_chain.py` |
| 22 | A reviewer reads what an operator called rather than what it said, cannot read across projects, and resolves to no write it could repair with | `test_copilot_chain.py` |
| 23 | A handover names two real operators, never itself, and cannot be edited | `test_copilot_handoffs.py` |
| 24 | A claim citing nothing is recorded as `unsupported` rather than dropped, and an operator cannot assert its way past a missing reference | `test_copilot_handoffs.py` |
| 25 | An unowned turn cannot hand over; a person can read the chain over REST | `test_copilot_handoffs.py` |
| 26 | `post_handoff` is the only write outside the user-intent gate, and an unbound MCP grant still does not get it | `test_copilot_chat_surface.py` |
| 27 | The picker groups operators by stance, drops a stance it cannot label, and renders nothing for an empty roster | `bots/registry.test.ts` |
| 28 | A turn that named no operator is not offered the tools that need one; reading the roster and the handover record never needs one | `test_copilot_chat_surface.py` |
| 29 | A settled delegation and a settled subagent fold back under the tool that opened them | `test_copilot_chain.py` |
| 30 | A slot count above one without evidence, and a CPU-only stage on a GPU-forcing queue, are both violations; a sound declaration is reported as sound | `test_compute_declarations.py` |
| 31 | The queue rules do not fire on a backend that ignores the queue | `test_compute_declarations.py` |
| 32 | `steward` can reach a declaration from a plugin id or a workflow node, and reviewing one changes nothing | `test_copilot_chain.py` |
| 33 | A delegated or spawned child run is dispatched through the outbox when it is created, so the pair cannot deadlock | `test_copilot_chain.py` |
| 34 | No two operators claim one trigger; no trigger is a bare common verb; every case the retired client-side skill registry routed still resolves | `test_copilot_bots.py` |
| 35 | Each Autopilot stage's operator is frozen at confirmation, names a producer, and is absent on every held stage | `test_autopilot_operators.py` |

Gates run for this change, on `bda-public/main`:

| Gate | Result |
| --- | --- |
| `ruff check backend_v2` | pass |
| `mypy backend_v2/app backend_v2/scripts` (CI form, no `--config-file`) | pass, 255 files |
| `pytest backend_v2/tests` | pass, 1007 tests |
| `pytest` with `BDA_V2_RUN_DB_TESTS=1` against PostgreSQL | pass |
| `check_coverage.py` | pass, overall 86.32% |
| `package_validation` branch coverage | pass, 96.57% |
| `export_openapi.py` then `git diff` | no drift |
| `npm run generate:api` then `git diff` | no drift |
| `npm test` / `npm run build` | pass, 115 files / 596 tests |
| `npm run test:browser` (browser vertical slice) | pass, 148/148 cases |
| `check_flow_matrix.py` | pass, 78 tables / 191 paths |
| `check_document_inventory.py` | pass, 21 active documents |
| `check_plugin_cpu_declarations.py` | pass |
| `alembic upgrade head`, `alembic check`, `alembic downgrade base` | pass, on a throwaway database |

The flow matrix is unchanged because `structures` declares no table: a structure
reaches it as an artifact, which is already write-once and checksummed, and a
second table would only be somewhere for a derived residue list to go stale.
