# BDA Copilot Bot Roster

状态：活跃

最后核验：2026-09-14（Asia/Shanghai；名册由 12 个合并为 6 个：researcher、planner、runner、analyst 吸收原有产出型 bot，auditor 吸收 steward；退役 id 仅用于读取历史。本轮新增 `structure-interaction` 能力（planner 独有）与 `request_decision` 工具（随 `chain-messaging` 授予全员））

权威范围：Copilot bot 名册、各 bot 的职责边界、交接协议，以及 bot 可用的 skill/MCP 清单。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：不取代 [Copilot 服务与权限指南](COPILOT_SERVICE_GUIDE.md)（能力与权限的权威），也不取代 [MCP capability surface](MCP_CAPABILITY_SURFACE.md)（外部调用契约）。本文在两者之上定义“谁负责链条的哪一段”；职责轴（stance）、交接协议与委派规则在 [Copilot bot governance](COPILOT_BOT_GOVERNANCE.md)。

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

## The chain and its six operators

On 2026-09-14 the roster was consolidated from twelve operators to six. The
first version split each producer's phase into the narrowest job a charter could
state — question, literature, target, structure, route, wait, failure, result,
record — which gave people a team they had to learn before they could ask for
anything, and put handovers between operators that were one piece of work: a
brief and its literature, a structure and the route designed against it, a run
and its failure, a result and the decision it supported. The merge keeps every
refusal those charters stated and every rule `_validate_roster` enforces.

The chain is a loop, not a line: `runner` sends a failure back to `planner`, and
`analyst` sends the next question back to `researcher`.

Four of the six *produce*: they own a phase. `conductor` decides who works next
and `auditor` judges what a producer claimed, including a compute draft's
declared resources. That is the `stance` axis, enforced at import rather than
stated in a charter; the argument and its rules are in
[Copilot bot governance](COPILOT_BOT_GOVERNANCE.md).

| # | Bot | 中文 | Stance | Owns | Capabilities | Hands off to | Absorbed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | `conductor` | 总调度 | direct | Deciding which operator works next, delegating to it, and saying when the chain stops | `project-read`, `research-read`, `chain-orchestration`, `chain-messaging` | `auditor` | — |
| 1 | `researcher` | 研究员 | produce | A falsifiable question, its literature with retrievable provenance, and target identity | `project-read`, `research-read`, `knowledge-authoring`, `literature-search`, `target-intelligence`, `research-gap-repair`, `chain-messaging` | `planner` | `briefing`, `librarian`, `scout` |
| 2 | `planner` | 方案设计 | produce | Reading structures at residue level, pointing at them, choosing the route and drafting its compute | `project-read`, `research-read`, `structure-analysis`, `structure-interaction`, `workflow-planning`, `compute-drafting`, `chain-messaging` | `runner`, `analyst` | `structuralist` |
| 3 | `runner` | 执行与排障 | produce | Carrying a confirmed run across its waits and explaining failures from recorded evidence | `project-read`, `workflow-planning`, `agent-orchestration`, `failure-diagnosis`, `chain-messaging` | `planner`, `analyst` | `medic` |
| 4 | `analyst` | 解读与归档 | produce | Interpreting recorded results and recording what was decided on which evidence | `project-read`, `research-read`, `result-interpretation`, `wetlab-read`, `wetlab-authoring`, `research-trace-authoring`, `knowledge-authoring`, `chain-messaging` | `researcher`, `planner` | `archivist` |
| — | `auditor` | 复核 | review | Ruling on claims against evidence and charter, and on a draft's declared resources | `project-read`, `research-read`, `review-audit`, `chain-messaging` | `conductor`, `planner` | `steward` |

Retired ids are listed in `bots.RETIRED`. Runs and handoffs recorded under them
are history and are not rewritten: `bots.get` resolves a retired id to its
successor so an in-flight run keeps a charter (its tools were fixed when it
started, so the successor's charter widens nothing), `/copilot/bots` serves each
operator's `absorbs`, and the frontend groups and links that history under the
successor. `bots.require` refuses a retired id with `copilot_bot_retired`, naming
the successor, so nothing new is started or addressed under an old name, and a
retired chat hint narrows to nothing. Later sections that name retired operators
describe how the roster got here and are kept as that record.

### What each bot must refuse

A bot's charter is mostly a list of refusals, because that is the part a
capability set cannot express. These go into the `charter` string and reach the
model verbatim.

- `researcher` — must not answer the question it is drafting: a brief states the
  question, what would answer or falsify it, constraints and unknowns, never the
  finding. Must not summarise a paper it has not retrieved: a queued search is
  queued, not done, and a citation without a checksum-backed excerpt is a lead,
  not evidence. Must not invent target identity: composite or modified
  identities stay `requires_review` until one exact entity maps to a UniProt
  accession, and only retrievable gaps are "repaired".
- `planner` — must not infer function from geometry, and must state model
  confidence before any contact list from a predicted structure. Must not confirm
  or submit: it produces a draft and the reasons for it, including the reasons
  against the routes it did not pick, and states the resources the draft
  declares and why.
- `runner` — must not poll, must not assume an outcome, and does not submit,
  confirm or resubmit anything: the run moves because the platform moves it. A
  failed job is a result, and its diagnosis names the evidence it rests on and
  says plainly when that evidence does not determine the cause; the fix goes to
  `planner` as a change to the draft.
- `analyst` — must not invent measurements, must not rank by a score whose
  mechanism it has not checked, and reports units and analysis versions. Must not
  decide and cannot close a goal: marking a goal answered stays with a person, so
  it says which linked result it thinks answers a goal and leaves the call to the
  reader.
- `conductor` — must not do the work, and must not authorise it. It holds no
  capability that changes the research record, and delegating is not a way to
  reach one: the delegated operator runs under its own charter and its own
  capabilities. It also cannot supply the user's words — a delegated run's write
  gate reads the *originating* request, so an instruction the director wrote can
  steer work but never unlock a write.
- `auditor` — must not repair what it finds. Its output is a verdict per claim
  (`supported` / `unsupported` / `contradicted` / `outside_charter`), ruled on
  what the operator actually called rather than on what it said it did; a claim
  citing nothing is `unsupported`, and a handover with no run behind it is
  *unreviewable* rather than clean. For a compute draft it compares slots,
  per-host span, thread budget and GPU declaration through
  `review_compute_declaration`, reports the two numbers that disagree, and says
  so plainly when the declaration is sound.

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
holds none of a researcher's literature tools, so the intersection removes
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

Five tools:

| Tool | Answers |
| --- | --- |
| `analyse_structure` | What is in this file: format, chains, residue counts, per-chain one-letter sequence, numbering gaps, ligands and solvent counted separately, disulfides, and a pLDDT or B-factor summary |
| `list_structure_contacts` | Which residues of one chain lie within a cutoff of another, with the closest atom pair and its distance — the interface, as measurements |
| `measure_structure_interface` | How much surface two chains bury and what the contact is made of: buried area per side, the conventional interface area, per-residue burial, hydrogen bonds (donor/acceptor distance, no angle term - hydrogens are absent), salt bridges, hydrophobic fraction. Buried area is not an affinity |
| `compare_structures` | Fit one structure onto another: C-alpha RMSD before and after the fit, the residues that moved most, and a TM-score where its formula is defined. Residues are paired by author numbering, so a file missing a loop still compares; the TM-score is evaluated on this superposition and is not TM-align |
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
| `failure-diagnosis` | read | `get_compute_status`, `diagnose_compute_failure` | runner |
| `project-read` | read | `list_project_targets`, `list_project_candidates`, `list_experiment_results`, `get_workflow_status`, `get_compute_status` | conductor, researcher, planner, runner, analyst, auditor |
| `research-read` | read | `research_overview`, `search_research`, `get_research_items`, `get_dataset_slice`, `get_reference`, `get_reference_content`, `list_research_goals` | conductor, researcher, planner, analyst, auditor |
| `result-interpretation` | read | `list_project_candidates`, `list_experiment_results` | analyst |
| `review-audit` | read | `list_operator_charters`, `read_operator_work`, `review_compute_declaration` | auditor |
| `structure-analysis` | read | `analyse_structure`, `list_structure_contacts`, `describe_structure_site` | planner |
| `wetlab-read` | read | `list_proteins`, `compute_concentration`, `plan_dilution_series` | analyst |
| `chain-messaging` | draft | `post_handoff`, `read_handoffs` | conductor, researcher, planner, runner, analyst, auditor |
| `compute-drafting` | draft | `get_compute_status`, `create_compute_draft` | planner |
| `knowledge-authoring` | draft | `search_project_knowledge`, `create_knowledge_draft` | researcher, analyst |
| `research-trace-authoring` | draft | `attach_to_research_goal` | analyst |
| `wetlab-authoring` | draft | `promote_candidate_to_bench`, `analyse_bli_run`, `analyse_akta_run`, `analyse_enzyme_plate` | analyst |
| `workflow-planning` | draft | `get_workflow_status` | planner, runner |
| `literature-search` | queue | `start_literature_search` | researcher |
| `research-gap-repair` | queue | `resolve_research_gaps` | researcher |
| `target-intelligence` | queue | `start_target_intelligence` | researcher |

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

## Guided task ownership

A guided task is assigned to an operator, not to a recipe. Each recipe in
`task_contracts.SERVICES` has exactly one owner, declared in `task_services` on
the bot and checked at import; one operator may own several:

| Recipe | Owner |
| --- | --- |
| `brief` | `researcher` |
| `literature` | `researcher` |
| `planning` | `planner` |
| `execution` | `runner` |
| `interpretation` | `analyst` |

The owner must be a producer and must be able to call every step of its recipe
through `bot.capabilities ∩ recipe.capabilities`. `/copilot/bots` serves
`task_services` and, per recipe, `task_write_tools` — the recipe's optional writes
the owner can be granted; the researcher is offered both external search and
pending-review notes for a literature task. Starting a recipe with a bot that
does not own it is refused with `copilot_task_owner_mismatch`; a run with no bot
keeps the previous recipe-only behaviour. `conductor` and `auditor` own no recipe
and work through conversation, handoffs and delegation.

## Surfaces

One declaration, three surfaces, no duplication:

- `GET /copilot/bots` lists the roster with its capabilities, charter, phase,
  stance, handoffs and — for each producer — who reviews it. The frontend reads
  that response rather than restating it: the hand-written skill registry it sits
  beside kept its own copy of the backend's capability list, and a copy is what
  drifts. The picker groups by stance rather than by phase, because a director is
  not the step before `researcher` and a reviewer is not the step after
  `analyst`, which is what one ordered list would say.
- `GET /copilot/projects/{id}/handoffs` returns the chain's handovers, newest
  first, with each claim's evidence reference and confidence, and the Copilot
  drawer's **Chain** tab renders them. A record only the operators could read
  would make the channel's justification — that what one operator claimed is
  auditable afterwards — true for `auditor` and false for the person it is
  ultimately for. The view is built around the unsupported claim: it is not an
  error and is not hidden, because the operator made it and the server recorded
  it rather than dropping it, so the reader looking for what to check finds it
  first.
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
runner's work is still doing the runner's work, and a child that silently lost its
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
  contains it, which is what lets "literature review" reach `researcher` without
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

## `structure-interaction` — 指着结构说话，以及把选择交回给人

`structure-analysis` 回答「那里有什么」，本能力回答「我说的是哪一块，以及这该由谁定」。
三个工具，分工是设计本身：

| 工具 | 模式 | 语义 |
| --- | --- | --- |
| `render_structure_view` | read | 返回一份 [MolViewSpec](https://molstar.org/mol-view-spec-docs/) 场景（`.mvsj` 树），把指定残基挑出来。**只展示，不下结论**：传进去的残基是操作员已经量过的那些 |
| `propose_hotspot_set` | draft | 写一条 `proposed` 的位点集合（残基 + 理由 + 证据引用）。**不能确认** |
| `request_residue_selection` | draft | 用候选集合开一条决策请求，由人在选项之间做选择 |

**确认不是工具。** `target_hotspot_sets.origin` 用的是与 `project_timeline_entries.decided_by`
完全相同的三态词汇：操作员提出记为 `agent`/`proposed`，人自己选的记为 `human`/`confirmed`，
人接受了操作员的提案则变成 `agent_proposed_human_confirmed`。确认走
`POST /hotspot-sets/{id}/confirmations`（`require_command`），任何工具都到不了它——
而**只有已确认的集合**会被工作流节点表单固定为 `constrained` 参数
（RFdiffusion 的 `ppi.hotspot_res`、BindCraft 的 `target_hotspot_residues`）。

能力只给 `planner`：它在合并后拥有残基级的结构阅读，指着结构说话是同一件事的延伸。
reviewer 拿到它就等于能修自己审的东西。

## `request_decision` — 把一个只有人能定的选择交出去

随 `chain-messaging` 授予（与 `post_handoff`、`read_handoffs` 同一能力），因此每个会交接的
operator 都能用，包括 conductor 与 auditor：**问一个问题既不是修复自己发现的问题，也不是替人做事**。
判据沿用 `autopilot/gates.py` 已有的两条——是否不可逆、是价值问题还是经验问题——不另造分类。
回答由人通过 `POST /copilot/decision-requests/{id}/answers` 写入，并落成一条
`decided_by=agent_proposed_human_confirmed` 的 timeline 记录，记录里写明**未被选中的分支**。

## `sequence-analysis` — 下单之前先看这条序列会不会坑你

平台一直能算分子量与消光系数（浓度测量需要它们），但没有任何东西回答"这个构建体值不值得做"。
一个带游离半胱氨酸、界面上压着 N-糖基化位点、或者有九残基疏水斑块的设计，
会在台面上耗掉一个月——而仓库里搜不到 `pI`、liability、codon 任何一个词。

单个只读工具 `analyse_sequence`，接受 `candidate_id` / `target_id` / `protein_id` **三选一**
（候选物的序列就在 `properties["sequence"]`，与 `wetlab.service` 推上台面时读的是同一个键）。
**工具不接受直接粘贴的序列**：`test_sequences_are_unreachable_through_any_tool` 禁止任何工具带
`sequence` 参数，而理由比参数表更硬——工具调用的参数会被写进对话记录
（`copilot_messages.tool_calls`、`copilot_agent_turns`），接受残基等于在那里留下第二份明文。
服务层仍保留 `sequence=` 入口，供已经持有文本的调用方使用。

- **位点**：N-X-S/T 糖基化（排除 N-P-X）、NG/NS 脱酰胺、D-G/S/T 异构化、Asp-Pro 断裂、
  M/W 氧化、半胱氨酸配对（奇数即有游离）、RGD、Q/N 低复杂度段、疏水斑块（窗口与阈值随结果一起返回）；
- **性质**：pI、pH 7.4 与 6.0 下的净电荷、GRAVY、芳香性、不稳定指数、分子量与消光系数
  （后两者直接调用 `wetlab/kernels/calculators.py`，不另写一份）。

两条纪律写进了代码而不是注释：位点一律 **1-based 闭区间**，因为这些数字会被直接抄进引物；
以及**结果里永远没有序列本身**——`wetlab.models.Protein` 明写它的 `sequence` 是唯一的明文副本、
API 只对外给 sha256，一个把明文回传给模型的工具会一行之内把这条约定作废。

第二个只读工具 `analyse_conservation` 回答"哪些位点动不得"：读项目里已上传的比对文件
（FASTA / a3m / Stockholm，**按 artifact id**，同样不接受粘贴的比对——粘进来的比对第一条就是查询序列本身），
按查询序列的 1-based 编号给出每列的保守度、熵、gap 比例与有效深度，并返回最保守与最可变的若干位点。
三个判断写在 `app/sequences/conservation.py` 里：**默认做 Henikoff 加权**，
否则 500 条近乎相同的直系同源读起来处处高度保守；**gap 不算第二十一种残基**，
它被排除在残基分布之外、单独报 `gap_fraction`，因为"90% 是 gap、10% 是色氨酸"不是保守的色氨酸；
**结果里不含查询序列的残基字母**，逐位回传它等于把序列重新拼出来。
有效深度低于 3 的列标 `shallow`——那种数字是算术，不是证据。

能力给 `planner`（它设计构建体）与 `analyst`（它解读结果），两者都是 produce，且这是只读能力。

## `triage_candidates` — 把路线自己写下的门槛真正套到候选物上

`route_catalog` 从写下来那天起就带着验收门槛（`{"pae_interaction": "< 15", "binder_plddt": "> 70", …}`），
但没有任何代码读它：人是用眼睛对的，而这既是分诊里最慢的一步，也是最容易看错数字的一步。

工具 `triage_candidates`（只读，归 `result-interpretation`，即 analyst 的能力）接受一个
`route_id` 和至多 25 个候选物 id，套用**那条路线自己声明的**门槛，逐条给出结论。

设计上只有一个决定，但它贯穿全部：**一条判据有三种结果，不是两种。**

| 结果 | 含义 |
| --- | --- |
| `pass` | 指标已记录且满足门槛 |
| `fail` | 指标已记录且不满足 |
| `missing` | **从来没有人测过这一项** |

把 `missing` 并进 `fail` 是这个模块存在的理由。一个没有 Rosetta 分数的设计不是"没通过 Rosetta 门"，
而是没人跑过 Rosetta；两者报成一样，会让人把**还没评估过的工作**当作被否决的工作扔掉——
而这恰好最常发生在某个流水线阶段被跳过的时候，也就是最需要有人注意到的时候。

另外两条：判据会带上**是哪一行指标定的**（method 与 assessor），所以"设计模型给自己打的分"
不会被洗成独立验证；一条不声明任何 tier 的路线（比如 structure-acquisition，它约束的是
ensemble 大小而不是 binder 质量）会被明确拒绝，而不是返回一个读起来像"全过"的空结论。
