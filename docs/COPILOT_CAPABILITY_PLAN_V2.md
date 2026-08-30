# BDA Copilot Capability Plan V2

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## Goal

BDA Copilot is one project-scoped assistant. It reads canonical project data,
uses bounded tools, and performs only explicitly requested, permission-checked
actions. The model never receives arbitrary filesystem, shell, credential, or
database access.

## Capability and action matrix

| Capability | Chat behavior | Mutation level | Required control |
| --- | --- | --- | --- |
| Project data | Read targets, candidates, experiments, workflows, jobs, drafts | Read | Project membership |
| Research evidence | Read workspace entities, datasets, references, saved excerpts | Read | Project membership and citations |
| Result interpretation | Explain recorded results and limitations | Read | No invented measurements |
| Knowledge authoring | Search notes; create `copilot_draft` notes | Draft | Explicit request; pending human review |
| Literature search | Queue Europe PMC search and ingestion | Queue | Explicit request; auditable query and traces |
| Target intelligence | Queue analysis for an exact operational Target UUID | Queue | Explicit request; exact project target |
| Research gap repair | Queue reference/AlphaFold repairs for an exact Research target UUID | Queue | Explicit request; scientific gaps remain open |
| Workflow planning | Inspect and recommend routes | Draft | Applying a route remains a user action |
| Compute drafting | Create Docker/LSF draft | Draft | Explicit request; confirmation and submission remain user actions |
| Durable agent run | Persist a bounded multi-turn task; suspend on a job or one child run and resume | Queue | Explicit run creation, project scope, tool allow-list, cost and depth limits |

The durable runner stores its transcript, tool calls, pending tasks and accumulated cost
on the server. A run may wait for a submitted compute job or spawn one level of child
work, but those abilities do not grant direct shell access or bypass normal compute
draft/confirmation controls. The archived binder-agent prototype's dedicated prompt and
direct GPU-submission behavior are intentionally not part of the public contract.

## Always prohibited from ordinary chat

- Applying workflow routes.
- Confirming or submitting compute.
- Cancelling jobs.
- Reviewing or approving scientific evidence.
- Deleting project data.
- Executing shell commands or reading arbitrary paths.
- Exposing credentials, object keys, or access tokens.
- Reporting queued work as completed.

## Execution contract

1. The authenticated user and project are recorded server-side.
2. Project configuration defines the maximum enabled capability set.
3. A capability hint narrows the current turn to one enabled capability and
   never grants a disabled capability.
4. A write tool is exposed only when the current message contains a
   domain-specific positive action request. Negated requests such as “do not
   search” or “不要创建” do not authorize it.
5. Each write action repeats the positive-request check before mutation.
6. Exact entity IDs are revalidated against the current project.
7. Queue and draft results return their real pending/draft state.
8. Successful actions and permission/scope rejections are attributed in the
   audit log without persisting raw action arguments.
9. The source message and conversation are locked to tolerate duplicate task
   delivery and serialize turns.
10. Gap requests and predicted-structure imports lock the Research target;
    stale operations cannot overwrite the latest status.
11. A failed Copilot task moves its pending source message to `failed`.
12. A turn may make at most six tool calls before returning a bounded answer.
13. Grounded scientific review runs only when the answer actually cites a
    checksum- and retrieval-trace-backed literature excerpt.
14. Composite, modified, or otherwise non-unique molecular identities remain
    `requires_review` until one exact entity is mapped to a UniProt accession.
15. Durable runs persist budget use and pending work transactionally; cancellation walks
    the child/task tree, and a periodic sweep only recovers missed wake-ups.

## Acceptance experiments

Each tool must pass:

1. Unit execution with structured arguments and result logging.
2. Cross-project and invalid-ID rejection where an entity is required.
3. Rejection when the current user message did not explicitly request a write.
4. API contract and frontend routing-hint tests.
5. A real provider-backed Copilot conversation.
6. Database verification of created resource state and attributed audit entry.
7. Duplicate-delivery or concurrent-request verification for mutation paths.
8. Negative-language, prohibited-action, and disabled-capability guard tests.
9. Durable-run restart, budget exhaustion, one-level child limit, job wake-up and
   cancellation propagation tests.
