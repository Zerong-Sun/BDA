# Copilot Bot Governance

状态：活跃

最后核验：2026-09-13（Asia/Shanghai；本轮引入 stance 轴、交接通道与 conductor/auditor/steward）

权威范围：bot 的职责轴（stance）、决定权与拒绝的机械约束、bot 之间的交接协议与委派规则。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：不取代 [Copilot bot roster](COPILOT_BOT_ROSTER.md)（名册与各 bot 的章程），也不取代 [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md)（能力与权限的权威）。本文定义名册之上的一层：谁可以判谁、谁可以调度谁、以及它们如何交谈。

## The defect this exists to fix

The roster shipped nine bots that differ by **which tools they hold**. That is a
split of functions wearing the vocabulary of a split of responsibilities, and
three properties of the code say so plainly:

1. **Deleting `BotSpec.charter` would change no behaviour.** The charter is
   prose handed to the model. `planner`'s charter forbids describing a draft as
   running; nothing checks whether it did.
2. **`handoff` is prose.** `bots.py` states it outright — *"Handoffs are
   advisory by design."* One bot cannot leave anything for another. There is no
   channel, so there is nothing to check either.
3. **A subagent inherits its parent's bot.** The only delegation mechanism in
   the system cannot cross a role boundary. A run has exactly one operator from
   start to finish.

Nine names, one responsibility structure: *the assistant, holding a smaller
toolbox this turn*.

## What a capability list cannot say

A responsibility is four things, and the roster expresses only the second — and
that one only as prose a model may ignore.

| | Question | Before |
|---|---|---|
| Decision rights | What may I **decide**, as opposed to propose? | absent |
| Refusals | What must I refuse although my tools allow it? | prose only |
| Accountability | Who judges my output, against what? | absent |
| Obligations | What must I hand over, in what form? | absent |

Adding more bots along the capability axis makes this worse, not better: it
multiplies operators without creating a single relationship between them.

## 1. Stance: one orthogonal axis, enforced at import

Every bot declares exactly one stance. Capabilities say what it can touch;
stance says what it is *for*, and what it may therefore never do.

| stance | produces | judges | routes | write capabilities |
|---|---|---|---|---|
| `produce` | its own phase | no | no | its phase's writes |
| `review` | no | yes | no | **none — enforced** |
| `direct` | no | no | yes | **none — enforced** |

"None" means no capability that changes the research record. Both stances still
hold `chain-messaging`, which writes a handover row — a reviewer that could not
report its verdict, or a director that could not say why it routed, would be
useless. That one exemption is named in `bots._INTERNAL_WRITE_CAPABILITIES`, its
tools declare `intent="internal"` in the registry so the same claim is made from
both sides, and the argument for it is below: the note changes no domain table.
The list is short on purpose; anything else added to it is a hole in this rule.

The enforcement is the entire point, and it lives in `_validate_roster()`
beside the existing unknown-capability check, so a violation fails at import
rather than in production:

- A `review` bot declaring any capability that grants a write is a roster error.
  **A reviewer that can fix what it found is not a reviewer** — it is a second
  producer, and nobody checks the fix. The whole value of the stance is that the
  finding has to travel back to the operator who made the mistake.
- A `direct` bot declaring any domain-write capability is a roster error. A
  director that can do the work will do the work instead of routing, and the
  chain silently collapses back to one operator.
- A `produce` bot declaring `chain-orchestration` or `review-audit` is a roster
  error — those are the powers of the other two stances.

This is the line between splitting functions and splitting responsibilities:
functions are *which tools*; responsibilities are *which tools, plus what you
are forbidden to do with the tools you hold* — and the forbidding has to be
mechanical, or it is decoration.

### Stance does not widen anything

Stance grants nothing. `resolve(bot, project_enabled) == bot.capabilities ∩
project_enabled` remains the only law that decides what a turn may call. Stance
only ever subtracts, by making certain capability combinations illegal to
declare in the first place.

## 2. The handoff record: how bots talk

Direct bot-to-bot calls would be the wrong primitive here. Nothing would be
recorded, the narrowing law would have no place to stand, and a reviewer would
have nothing to read. Instead bots exchange **append-only handoff notes**, and
the reviewer reads the same rows the recipient does.

`copilot_handoffs` — one row per handoff, never updated:

| column | meaning |
|---|---|
| `from_bot` / `to_bot` | operator ids, both validated against the roster |
| `summary` | what was done, in prose |
| `claims` | the load-bearing part — see below |
| `open_questions` | what this operator could not settle |
| `refs` | artifact / job / goal / reference ids the next operator needs |
| `produced_by_run` | the agent run that wrote it, when there was one |

### Claims are structured, and that is the whole design

A note is not "I did the thing". `claims` is a list of

```json
{ "statement": "...", "evidence_ref": "...", "confidence": "stated|consistent|unsupported" }
```

A prose summary can only be read. A list of claims each carrying the evidence
that supports it can be **checked** — `auditor` can say "claim 3 cites nothing"
without interpreting anything. This is what turns review from a vibes exercise
into work with a defined output, and it is why the channel is worth a table
rather than a string field.

### Posting a note is not a research write

The write-intent gate exists to stop a model changing **the research record**
without the user asking for it. A handoff note changes no domain table; it is
part of the copilot's own transcript, the same category as the chat message
that is already written every turn without an intent check. So `ToolSpec` gains
a declared `intent` field — `"user"` (default, must pass `request_allows`) or
`"internal"` (copilot-owned bookkeeping, audited, exempt). Declared per tool,
never inferred, so the exemption is visible in the catalogue rather than
implicit in a handler.

## 3. Three new bots

### `conductor` — 总调度 (stance: `direct`)

Capabilities: `project-read`, `research-read`, `chain-orchestration`,
`chain-messaging`. No domain writes.

- `list_operators()` — the roster, each operator's refusals and current
  reachability under this project's enabled skills
- `delegate_to_operator(bot, instruction)` — open a child run owned by a
  **different** bot and wait for it. The child's tools are
  `target.capabilities ∩ project.enabled_skills`: the project's bound, not the
  director's. `spawn_subagent` intersects against the parent because a subagent
  is the same operator splitting its own work; doing that here would strip each
  operator's defining tool — a delegated `librarian` would lose
  `start_literature_search` — and produce a child indistinguishable from one
  that failed.

**The sharpest constraint in this design: a director may route, but it may not
manufacture consent.** The write-intent gate reads the user's own words. A
delegated run therefore carries the *originating user request text* for intent
purposes, not the conductor's instruction — otherwise the conductor could emit
"请提交这个作业" and unlock every write in the project by writing the user's
side of the conversation. The instruction steers the work; it can never
authorise it.

Delegation requires an agent run (`requires="agent_run"`), so in chat the
conductor can only recommend an operator. That matches `spawn_subagent` and
keeps the chat surface incapable of opening runs behind the user's back.

### `auditor` — 复核 (stance: `review`)

Capabilities: `project-read`, `research-read`, `review-audit`,
`chain-messaging`. Zero writes.

- `read_operator_work(run_id)` — which tools an operator actually called and
  what came back, not what it said it did
- `list_operator_charters()` — the refusals it is checking against

Its output is a verdict per claim: `supported`, `unsupported`, `contradicted`,
or `outside_charter` — the last meaning the operator did something its own
charter forbids, which is the check nothing performed before. It cannot fix
what it finds; it posts the verdict back to the operator that made the claim.

### `steward` — 资源守门 (stance: `review`)

Capabilities: `project-read`, `review-audit`, `chain-messaging`. Zero writes.

Reviews a compute draft's declared resources before a human confirms it: `-n`,
`ptile`, the exported CPU count and the GPU declaration against what the tool
can actually use. This repository already encodes the rules in
`backend_v2/scripts/check_cluster_claims.py`, and treats a low-utilisation
inspection mail from the cluster as a violation rather than a notice. That makes
it the one review in the chain with a mechanical standard to check against, and
a distinct accountability from `planner`, which chooses the route.

## A tool that needs an operator is not offered without one

`registry.py` already refused to offer a tool whose service the turn lacks, and
`mcp.py` states the rule it upholds: *a tool that is not callable is not listed*,
because a refusal the model can retry reads as an obstacle rather than a
boundary. The operator is a second axis of the same thing, and the first version
of this change missed it — an undifferentiated turn was offered `post_handoff`,
which then always failed, because a handover whose sender is "the assistant"
names nobody accountable.

So `ToolSpec` gains `needs_operator`, declared rather than discovered inside a
handler, and both chat and the agent loop drop those tools from a turn that
named no bot. Reading the roster and reading the handover record deliberately do
*not* need one: a turn that has not chosen an operator is the likeliest to be
asking who the operators are.

## What is deliberately not added

More bots along the capability axis. The roster does not need a "reporter", a
"summariser" or a "searcher" — those are functions, and `archivist`,
`analyst` and `librarian` already own them. Every addition here has to answer
*whose decision does this take away from whom*, and a function split answers
nothing.

## Acceptance

| # | Statement | Where it is proven |
|---|---|---|
| 1 | A `review` bot declaring a write capability fails at import | `test_copilot_bots.py` |
| 2 | A `direct` bot declaring a domain-write capability fails at import | `test_copilot_bots.py` |
| 3 | Stance never widens: `resolve` is still the intersection for all 12 bots | `test_copilot_bots.py` |
| 4 | A delegated run is owned by the target bot, not the conductor | `test_copilot_chain.py` |
| 5 | A delegated run's write gate reads the user's words, not the conductor's | `test_copilot_chain.py` |
| 6 | A delegated run's tools are exactly target ∩ project, and a subagent's are still bounded by its parent | `test_copilot_chain.py` |
| 6b | A turn with no project capability set refuses to delegate rather than defaulting to the target's full declaration | `test_copilot_chain.py` |
| 7 | A handoff note names two real operators, and cannot be edited | `test_copilot_handoffs.py` |
| 8 | `internal` intent tools skip `request_allows`; `user` intent tools do not | `test_copilot_chat_surface.py` |
| 8b | A turn with no operator is not offered the tools that need one, and nothing else is withdrawn with them | `test_copilot_chat_surface.py` |
| 8c | A settled delegation folds back under `delegate_to_operator` and a settled subagent under `spawn_subagent` | `test_copilot_chain.py` |
| 9 | Every capability is owned by at least one bot | `test_v2_domains.py` |
