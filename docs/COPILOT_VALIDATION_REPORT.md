# Copilot Validation and Repair Report

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；当前平台与科研总状态以 docs/refactor/CURRENT_STATE_2026-08-29.md 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

Validated on 2026-07-28 against the backend API, workers, frontend, PostgreSQL,
Redis, MinIO, and the configured provider-backed Copilot path.

## Six-dimension result

| Dimension | Validation result | Resolution |
| --- | --- | --- |
| Requirement completeness | Chat previously had no controlled path to repair Research gaps. Capability configuration and UI routing did not describe the real mutation boundary. | Added nine canonical capabilities, five controlled queue/draft actions, the Research gap API and UI, configuration validation, permission checks, audit attribution, and explicit pending/draft states. |
| Logical correctness | Advice questions and words containing `search` could authorize a literature write. Multi-capability prompts could be silently routed to the first matching skill. | Added clause-aware positive/negative request checks with ASCII word boundaries. Focused frontend hints are used only for one unambiguous capability; composite prompts retain the full configured capability set. |
| Boundary cases | Unknown/disabled capabilities, an empty gap-resolution scope, ambiguous molecular identities, cross-project IDs, sensitive nested context, duplicate delivery, stale operations, provider failure, and concurrent conversation turns were incomplete or unsafe. | Added 422 rejections, exact project/entity revalidation, bounded recursive redaction, `requires_review` for non-unique UniProt identity, row locks, stale-operation protection, source-message failure status, and conversation serialization. |
| Code quality | Capability definitions and frontend triggers had drifted; tool collections and gap variables exposed type-check errors. | Centralized capability metadata and aliases, delegated gap actions to the domain service, generated the API client from OpenAPI, and made all touched Python and TypeScript pass static checks. |
| Test coverage | There were no tests for controlled Copilot writes, capability narrowing, advice/negation, nested secrets, review routing, gap imports, stale completion, ambiguous targets, or failure status. | Added unit, API, frontend, contract, idempotency, audit, and worker integration tests. Focused Copilot/Research line coverage is 81%. |
| Actual runtime | GPR65/TDAG8 and four composite/modified targets were exercised in the deployed stack. The latter were incorrectly counted as structure failures even though they cannot map to one molecular entity. | GPR65/TDAG8 completed with two automated resolutions and zero failures. All 25 Research targets now report `completed_with_remaining_scientific_gaps`; retrievable repair operation failures are zero. |

## Repair checklist

- [x] Replace Research read-only behavior with a controlled, permission-checked
  gap-resolution command.
- [x] Keep workflow application, compute confirmation/submission, scientific
  approval, deletion, shell access, and arbitrary file/database access outside
  ordinary chat.
- [x] Reject unknown or project-disabled capability hints before enqueueing.
- [x] Prevent advice, questions, negation, and substring collisions from
  authorizing writes.
- [x] Preserve composite intents instead of selecting a hidden first skill.
- [x] Redact nested credential/token/URL/object-key fields and bound context
  depth, item count, text length, and selected entity ID length.
- [x] Reject gap requests with both resolution scopes disabled.
- [x] Lock concurrent gap requests and complete AlphaFold import under the same
  target lock.
- [x] Prevent an older gap operation from overwriting the latest operation.
- [x] Mark a pending Copilot source message failed when its task fails.
- [x] Serialize turns within one conversation.
- [x] Treat composite, modified, or otherwise non-unique molecular identities as
  `requires_review`, not as an automated repair failure.
- [x] Regenerate OpenAPI and the TypeScript client.

## Verification evidence

- Backend: `213 passed, 2 skipped`; one deprecation warning from Starlette's
  current TestClient dependency.
- Focused line coverage: 81% total (`actions` 98%, `capabilities` 94%,
  `project_context` 89%, `research.service` 90%).
- Frontend: `198 passed` across 59 test files.
- Static checks: Ruff, mypy (28 source files), ESLint, TypeScript production
  build, and `git diff --check` passed.
- Runtime health: PostgreSQL, Redis, and MinIO readiness checks passed; API,
  frontend, nginx, Copilot worker, Research worker, generic worker, and beat
  containers started successfully.
- Test entity `0964f127-9572-46d7-aa0d-21147a079803`
  (`GPR65/TDAG8`): `completed_with_remaining_scientific_gaps`,
  `resolved_count=2`, `failed_count=0`.

Scientific validation, wet-lab evidence, clinical evidence, patent review, and
experimental structures intentionally remain open until reviewed evidence is
created or imported.
