# Security requirements for BDA changes

Read `CLAUDE.md` for architecture and commands and `docs/SECURITY_ENGINEERING.md`
for the security contract. These requirements apply to API routes, services,
workers, migrations, scripts, UI state and release packaging.

- Derive identity and permissions on the server. A project UUID is a selector,
  never proof of access. Verify every referenced object's project matches the
  destination project before writing or dispatching, including for administrators.
- Missing project context must fail closed. Never substitute the first project,
  migrate unscoped chat into a project, or issue an unscoped project query.
- Keep project and account identity in caches. Cancel old work on account/project
  changes and reject late responses before state updates or chained requests.
- Preserve transaction-local PostgreSQL RLS context and verify the deployed API
  and ordinary worker roles cannot bypass RLS. Maintenance/scheduler credentials
  belong only to their dedicated processes.
- Explicitly authorize artifact access before issuing signed URLs. Verify worker
  inputs and outputs, project ownership, paths, checksums and bounds again.
- Public deployments have no implicit model/provider selection or bundled API
  credentials. External LLM origins require operator approval; validate before
  every send and do not follow redirects carrying credentials or research data.
- Cluster hosts, accounts and roots are deployment configuration. Keep SSH host
  verification and Docker mTLS verification enabled. Do not concatenate untrusted
  shell tokens or allow paths to escape an operation's staging directory.
- Never log or reflect passwords, provider keys, signed URLs, sequences or complete
  validation inputs. Never include private research or local configuration in
  public commits, container contexts, release assets or test evidence.
- Add regression tests proving cross-project/cross-account rejection and valid
  same-project behavior. For changes to the boundary, run the security suite,
  PostgreSQL isolation tests, dependency audits and the normal CI gates.
- Publish software from the public source tree, then use the one-way sync for the
  private overlay. Do not publish private overlay history. Release and deployment
  claims must name the exact commit and the checks actually completed.
