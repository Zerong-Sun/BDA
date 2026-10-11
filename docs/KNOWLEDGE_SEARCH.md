# Project knowledge search and provenance

状态：活跃

最后核验：2026-10-11（项目隔离、字面检索与 PostgreSQL 回归）

权威范围：知识库服务端搜索、分页和来源保留；不声称提供语义向量检索。

数据来源：knowledge repository、Bot project context、KnowledgePanel 及对应测试。

替代关系：取代前端前 200 条和 Bot 前 500 条的本地筛选；保持现有知识条目协议。

The knowledge workbench and Bot now search the complete project collection on the server. The previous browser filter over the first 200 entries and Bot filter over the most recent 500 entries could silently miss older matching observations.

## Read contract

`GET /api/v2/projects/{project_id}/knowledge` retains its project authorization, UUID cursor and response shape, and adds:

| Parameter | Behavior |
| --- | --- |
| `q` | Optional, at most 500 characters; trim outer whitespace, then literal case-insensitive substring matching across title, content or an individual tag. Blank browses all entries. |
| `entry_type` | Optional exact type filter, 1–80 characters. |
| `limit` | Existing 1–200 bound, default 50. The workbench loads 50 per page. |
| `cursor` | Existing UUID keyset cursor; use the same search and type filters for continuation. |

SQL applies the project and search predicates before the cursor and limit. `%`, `_` and the escape character remain literal input. Tags are searched as decoded JSON elements, including Chinese tags, using PostgreSQL `json_array_elements_text` or SQLite `json_each`. This is substring search, not semantic retrieval, ranking by relevance, or full-text stemming. Case behavior follows the database's case-insensitive comparison rules.

Bot `ProjectContextService.search_knowledge` uses the same repository predicate and returns the most recent matching rows (bounded at 50); it no longer limits the searchable collection to 500 rows. Existing Bot source sanitization and output-size limits remain in force.

## Workbench behavior and provenance

- The search field and entry-type filter query the server; “Load more knowledge” follows actual matching result pages. Empty search opens the project collection.
- A saved record keeps the entire original `source` object. String citations remain editable, while structured citation objects remain visible in the original-source disclosure and are preserved unless explicitly replaced. Nested editor metadata is merged.
- Missing confidence is displayed in the data contract as `unassessed`; missing recorded review status is `unknown`. Loading a knowledge record no longer invents `curated` confidence or a citation.
- Manual creation/editing records `pending_review` and `unassessed`; this does not claim that a scientific review has occurred. Unknown provenance fields and original message IDs remain attached.
- Write controls use the current project's permission response. Selecting another project resets the editor. Edits retain the version captured when the record was selected and use the existing If-Match contract. A rejected update is shown without automatic overwrite/retry.

No database migration, model provider, embedding service or new infrastructure is required. Vector/hybrid retrieval can later be introduced as an explicit retrieval mode with its own provenance and evaluation; this change makes no semantic-search claim.

## Verification

- `backend_v2/tests/test_knowledge_search.py`: HTTP authorization and project scoping, literal wildcards/case/Chinese tags, type/length limits, filtering before keyset pagination, and retrieval beyond 520 newer unrelated rows.
- `backend_v2/tests/test_knowledge_search_postgres.py`: opt-in real PostgreSQL regression in a randomly named temporary schema; rolls back fixture data and removes only its own schema. Uses `BDA_GATE_TEST_DATABASE_URL`, or `BDA_V2_RUN_DB_TESTS=1` with the configured test database.
- `frontend/src/lib/api/knowledgeSearch.test.ts`: generated transport filters/cursor, honest review defaults, structured source/citation preservation and If-Match forwarding.
- `frontend/src/features/research/KnowledgePanel.test.tsx`: real continuation loading, source disclosure, permission gating and visible stale-version failure.
