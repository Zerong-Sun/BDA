# Project evidence curation

状态：活跃

最后核验：2026-10-25

权威范围：项目文献用途、证据整理、历史项目入口与展示去重。

数据来源：项目隔离服务、研究工作区、文献工作台及回归测试。

替代关系：补充现有文献工作台规范，保留来源与历史记录。

A reference belongs to a project because its stored document is project scoped.
Its usefulness for a particular question is a separate editorial decision.
Publication identity checks do not establish relevance, verify an interpretation,
or establish that a local candidate works.

`LiteratureDocument.metadata.evidence_curation` records `project_id`, `scope`,
`reason`, `author`, and an editorial version key. Supported scopes are `core`,
`method`, `context`, `excluded`, and `unreviewed`. The literature workbench opens
the direct evidence group after classification. Its argument view, paper view,
counts, and exports use the same group. A disposition copied from another
project is quarantined; unknown notes cannot enter through the argument view.
Legacy `project_scope_status=excluded` records are also kept out of direct evidence.

Each authored note keeps a project assertion, a reported result, the reasoning
connecting the result to the assertion, and a source-specific limitation. A
short exact quote, its source link, reading level, and locator are retained.
Matching an abstract or a saved excerpt does not imply that full text was read.
The draft generator determines full-text availability from content provenance,
not from the mere existence of a stored chunk.

An explicitly selected project evidence review uses
`ResearchBrief.scope.display_role=project_evidence_review`. It may be displayed
while its scientific review status remains a draft. Previous accepted reviews,
findings, original figures, tables, numerical source anchors, and attachments
remain available. A curated reading view does not repeat earlier model prose.
Evidence packets check their project and document identity before rendering;
archive download URLs are displayed only when the artifact belongs to the same
project. Project-wide historical bundles are labelled as such.

Imported projects do not inherit a source project's editorial selection, evidence
note IDs, or working evidence packet. Source dispositions and packets remain
provenance, and new references require project-specific relevance review.
Generated assertions require claim-level review even if their references have
verified bibliographic metadata. Generic words such as “protein” and “design”
cannot independently qualify an unrelated target paper for discovery.

The curation path does not require an LLM provider. The existing provider adapter
continues to accept a configured endpoint, model, credentials, and provider
options through the OpenAI-compatible completion interface. A connection test
checks transport and credentials; it does not generate or certify project
evidence. Providers can be changed without regenerating the reviewed corpus.

Portfolio consolidation is explicit and reversible. A historical project's
`localized_content.portfolio_consolidation` names its canonical project and
`role=historical_source`. Hide that entry only when the canonical project still
exists in the same organization. Keep its candidates, results, attachments and
direct authorized link. The client resolves that link separately from the
portfolio and never substitutes the previously selected project after a failed
lookup. Empty duplicate and interface-test projects may be moved to trash after
checking they have no candidates, workflows, jobs, results or artifacts.

Within a project, duplicate publication records use
`metadata.presentation_duplicate_of`. The reference view validates the target's
project and presents one publication, with `consolidated_document_ids` and
`consolidated_ref_ids` retaining old note and citation identities. Distinct notes
remain visible and editable, while a bibliography counts the publication once.
Do not consolidate publications across projects merely because they share a DOI.
Identical finding records may use the same presentation pointer; raw history
remains available. Missing or invalid targets must not silently hide evidence.

Each primary project's opening paragraph states its specific objective, current
evidence and decisive unresolved question. Put it before the section index.
Follow it with source-backed claims, reported results, reasoning and specific
limits. Avoid generic instructions to “add evidence” where the actual missing
measurement can be named. Unresolved identities and archived projects should
state that concrete gap rather than borrowing a different project's literature.
