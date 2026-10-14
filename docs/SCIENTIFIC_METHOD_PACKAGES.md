# Scientific method packages

状态：活跃

最后核验：2026-10-11（UTC；代码契约与自动化测试）

权威范围：2.6 开发分支的科学方法包、发现接口与持久任务集成。

数据来源：版本化 SKILL.md、manifest、执行器与本文列明的测试；方法参考链接随包保存。

替代关系：补充 Copilot 服务说明，不替代权限、预算及计算提交契约。

Status: implemented in the 2.6 development branch. Scientific quality and benefits
still require project-specific evaluation; package presence is not benchmark success.

## Purpose and scope

Copilot capabilities (`enabled_skills` and legacy `AgentRunCreate.skills`) authorize
tools. Procedural skills (`AgentRunCreate.procedural_skills`) describe how to analyze
evidence and how to return a reviewable result. Selecting a method never grants a
tool, a write permission, network access, compute submission, or a larger budget.

The eight bundled methods are evidence/refutation, experimental design, statistical
analysis planning, structure comparison, sequence/construct QC, model benchmarking,
experimental result review, and research decision reporting. They are independently
authored Apache-2.0 BDA instructions, with pinned method/format provenance links;
upstream executable code and mixed-license skill packs are not copied or installed.

## Packages and API

Each `backend_v2/app/copilot/skill_packages/<id>/` contains:

- `SKILL.md`: Agent Skills-compatible YAML frontmatter and procedural Markdown.
- `manifest.json`: BDA-specific version, author/license, instruction SHA-256,
  provenance, suggested read tools, optional write tools, data policy and JSON
  Schema input/output contracts. This is an application extension, not a claim
  that the open Agent Skills format requires those extra fields.

Authenticated catalog routes expose only bundled files:

- `GET /api/v2/copilot/procedural-skills` returns metadata and schemas.
- `GET /api/v2/copilot/procedural-skills/{skill_id}` also returns instructions.

IDs are matched against a fixed local catalog, never interpolated into paths.
There is no external installation endpoint, executable script runner, arbitrary
Python import, or remote skill loader. Global catalog content contains no project
data; all existing task operations still authorize their project.

## Actual task execution

In Research team → Scientific methods, users can inspect versions, methods and
provenance. In a task plan they can select up to three packages, use recommended
methods, or explicitly opt out. A null/omitted `procedural_skills` selects one
default for brief, literature, planning or interpretation; custom and execution
tasks have no automatic method. `[]` selects none. Duplicate/unknown IDs fail.

The service resolves the existing capability/bot/recipe/write scope first, then
records exact package instructions, manifest, package checksum and initial tool
availability in `task_contract.procedural_skills`. Runs and their children carry
the frozen snapshots across restarts and deployments. Every prompt rechecks the
snapshot checksum and recomputes method tool availability against the current
run's allowlist, so revoked tools cannot be reintroduced. Tool declarations are
method requirements/advice, not an additional authorization source. Methods do
not narrow necessary recipe evidence reads and do not replace capability checks.

Instructions are passed into the existing durable agent loop and therefore
included in model-cost reservation. No provider call is made past the existing
turn/cost gate. Chat without a durable task retains its existing behavior.

Final task JSON includes `skill_outputs`, keyed by selected package ID. The
server validates each object against its frozen output schema and verifies that
all cited tool-call IDs actually succeeded in this run. Missing outputs prevent
`completed`; malformed output or fabricated references require review. A
`needs_input`/`blocked` delivery can cite no successful call when nothing could be
read. These checks establish shape and transcript provenance, not whether a claim
is true or an experiment is reproducible. The run detail displays frozen methods
and validated method output alongside the original delivery.

## Updating and validating a package

Change the package version when changing instructions or contracts, then recompute
`instruction_sha256` over UTF-8 SKILL.md bytes. Package checksums also cover the
canonical manifest and instruction content. Existing runs retain old versions.
The loader validates JSON schemas, file integrity and registered tool names.

Focused checks: `test_copilot_procedural_skills.py` covers catalog authentication,
bounded selection, all eight output schemas, frozen replay, tamper rejection,
permission preservation, revoked tools, subagent inheritance, missing inputs,
fabricated evidence and budget gates. `ProceduralSkills.test.tsx` covers discovery,
on-demand reading, explicit selection/opt-out, read-only state, retry and frozen
run rendering. Existing task-contract, agent-loop and roster tests remain gates.

Next evaluation should compare each method with the current runner on blinded
project tasks: source accuracy, missing-input handling, contradictory evidence,
review effort and measured model cost. No performance improvement is claimed by
these software tests. PydanticAI/LangGraph, remote skills, tool catalog search and
model-provider changes remain separate, benchmark-gated decisions.
