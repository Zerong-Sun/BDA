# Frontend plugin verification — 2026-09-07

状态：活跃

最后核验：2026-09-07（Asia/Shanghai）

权威范围：本次前端插件检查与修复；不构成集群运行验收。

数据来源：仓库代码、回归测试及本次构建。

替代关系：补充 FRONTEND_V2.md，不替代插件运行证据。

The registry-backed node editor can render plugin parameter schemas, bind input ports,
and construct workflow requests. Runtime readiness still requires backend preflight and
fingerprinted runtime validation; a visible card or an enabled registry entry is not proof
that a model has executed successfully.

## Repairs

- Parse JSON parameter drafts before both node creation and node update. Reject malformed
  JSON and object/array mismatches before issuing the write request.
- Keep cleared numeric inputs empty. Reject nonfinite numbers, fractional integer counts,
  and declared bound violations before writing. Clearing an optional numeric value omits
  it; it no longer silently becomes zero or JSON null.
- Treat explicitly empty parameter schemas as authoritative instead of injecting fallback
  model parameters that may violate `additionalProperties: false`.
- Derive GPU/CPU card labels from declared GPU resources when available.
- Distinguish registry loading, errors, and empty results; provide retry on failures and
  prevent adding from a failed registry query. Surface add errors in the builder.

The server remains authoritative for full JSON Schema constraints and execution readiness.
No scheduler allocation or plugin resource declaration is changed by these UI fixes.

## Verification scope

Regression tests exercise typed JSON node creation, malformed drafts, experiment-count
bounds, clearing inputs, explicit empty schemas, GPU labels, and registry retry. Existing
workflow bindings, read-only editing, API mapping, plugin manifest/interface, port migration,
and QM command tests are also checked. No live cluster jobs are submitted for this review.

The existing running UI reaches its sign-in page. Authenticated deployed operation is a
separate verification step; local tests do not establish that the deployed service has
received this revision or that every registered plugin has runtime proof.
