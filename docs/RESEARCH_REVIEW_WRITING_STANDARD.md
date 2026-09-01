# Research Review Writing Standard

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

BDA Project review entries must read like rigorous life-science literature reviews—not platform marketing, checklists, or truncated bullet fragments.

## Core rules

- **No word-count ceiling**: write as much as needed for completeness; avoid repetition and filler.
- **Two prompt modes**:
  - **Per-source deep read** (`references_reading`): one finding per PDB / PMID / DOI / UniProt link.
  - **Thematic synthesis** (all other tracks): synthesize across sources; do not paste paper-by-paper lists.
- **Title + body**: every finding has an independent summary title (6–15 words) and a full `statement` body.
- **No platform meta-narrative**: never justify entries as “BDA platform value”, “regression test”, “operating contract”, or “decision gate”.
- **Evidence grading**: distinguish established facts, plausible interpretations, and speculative hypotheses.

## Per-source literature read (`references_reading`)

Use this structure inside each finding `statement` (English, technical):

1. **Concise Summary** — central question, key findings, experimental/computational approaches.
2. **Scientific Rationale and Workflow** — step-by-step study logic; how analyses connect to the hypothesis.
3. **Innovations and Technical Advances** — novel methods, models, tools, datasets, mechanisms.
4. **Significance and Impact** — why the work matters in the field.
5. **Critical Evaluation** — limitations, open questions, alternative interpretations.
6. **Scientific Questions Raised** — 1–2 follow-up questions with brief hypotheses grounded in the paper.
7. **Relevance to this BDA project** — concrete implications for target definition, binder construct, algorithms, and validation.

**Title example**: `Anti-THC Fab T3 co-crystal defines a hydrophobic hapten pocket (PDB 3LS4)`

**Bad**: `PDB 3LS4 — Keep this source linked to the project.`

## Thematic section synthesis (other tracks)

| BDA track | Review synthesis focus |
|-----------|------------------------|
| `meaning_application` | Introduction + biological/medical significance for this project |
| `target_mechanism_structure` | Mechanistic understanding + working model + **project target packet** (sequence boundaries, construct, coordinates, protected/samplable residues) |
| `prior_art_landscape` | Field history, thematic synthesis, controversies—**cross-cite sources without repeating full reads** |
| `binding_strategy` | Scaffold/epitope/hapten logic; competing routes and evidence strength |
| `design_strategy` | Methods review: what each algorithm addresses, strengths, limits, stepwise workflow mapping |
| `purification_plan` | Expression/purification/QC as developability evidence |
| `functional_validation` | Assay logic, controls, how readouts support or limit claims |
| `developability_risk` | Cross-study limitations and failure modes |
| `success_criteria` | Testable Go/No-Go predictions from the working model |
| `open_questions_next` | Specific future experiments with required evidence types |

Synthesis requirements:

- Organize by **theme/mechanism**, not paper order.
- When studies disagree, explain **why** (model, assay, species, sample size).
- Methods must be tied to **what biological conclusion they can support**.
- **Do not duplicate** full source reads: `prior_art` synthesizes; `references_reading` holds depth.

## Copilot write-back format

```
Summary title line (6–15 words)

Body paragraphs following the appropriate structure above.
```

Do not use section names as titles. Do not truncate titles at abbreviations such as `E. coli`.

## Good vs bad examples

| Bad | Good |
|-----|------|
| `The platform value is high because...` | The design objective requires sub-μM affinity while preserving selectivity against structurally related off-targets. |
| `For small de novo binders, screen E` (truncated) | Title: `Expression system to build small de novo binders` |
| `anti-THC Fab gives a concrete precedent` (one line) | Full structured read for PDB 3LS4 with pocket geometry, CDR contacts, metabolite gaps |
| `freeze a target packet containing sequence boundaries...` (generic) | Project-specific: THC vs THC-COOH chemistry, 3LS4 chain IDs, protected CDR framework residues |

## Citation integrity

- Do not invent DOI, PMID, PDB IDs, or quantitative results.
- Mark uncertain claims as needing verification.
- Prefer primary sources for mechanistic claims; use reviews for field-level background only.
