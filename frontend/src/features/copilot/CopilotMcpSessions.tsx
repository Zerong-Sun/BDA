import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { WarningIcon } from '@phosphor-icons/react'
import {
  isSpent,
  issueMcpSession,
  listMcpSessions,
  revokeMcpSession,
  type McpSession,
  type McpSessionGrant,
} from '../../lib/api/mcpSessions'
import { isLive, listAgentRuns } from '../../lib/api/agentRuns'
import { listSkillsApiV2CopilotSkillsGet } from '../../lib/api/generated/sdk.gen'
import { ApiError } from '../../lib/api/client'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useToastStore } from '../../components/ui/toastStore'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Checkbox } from '../../components/ui/checkbox'
import { Label } from '../../components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { StatusPill } from '../../components/ui/StatusPill'
import type { StatusTone } from '../../components/ui/statusTone'

/**
 * Issue, read and revoke the grants that let an outside agent use this project's
 * copilot tools over MCP.
 *
 * Two things about this panel are load-bearing rather than cosmetic.
 *
 * The **token is shown once**. The server stores a SHA-256 hash, so there is no
 * endpoint that could show it again, and the panel says so instead of implying
 * the value can be found later.
 *
 * The **tool counts are the server's current answer**, not the grant's stored
 * contents. A capability switched off for the project, or a bound agent run that
 * has finished, narrows an outstanding grant without anyone revoking it — so the
 * row has to be re-read rather than remembered, and a grant that has gone
 * read-only says that in place of the write count.
 */

//: The sentinel for "no bound run". See the Select below.
const NONE_RUN = '__none__'

function toneFor(session: McpSession): StatusTone {
  if (session.revoked_at) return 'neutral'
  if (isSpent(session)) return 'amber'
  return session.write_tools.length > 0 ? 'blue' : 'green'
}

export function CopilotMcpSessions() {
  const { t, format } = useI18n()
  const copy = t.copilot.mcp
  const { projectId } = useProjectContext()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)

  const [label, setLabel] = useState('')
  const [expiry, setExpiry] = useState('24')
  const [runId, setRunId] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [issued, setIssued] = useState<McpSessionGrant | null>(null)
  const [copiedToken, setCopiedToken] = useState(false)

  const skills = useQuery({
    queryKey: ['copilot-skills'],
    queryFn: async () => (await listSkillsApiV2CopilotSkillsGet<true>({ throwOnError: true })).data,
    staleTime: 5 * 60_000,
  })

  const sessions = useQuery({
    // Keyed by project, like every other project-scoped query: a grant list must
    // not survive into another project's view.
    queryKey: ['mcp-sessions', projectId],
    queryFn: () => listMcpSessions(projectId as string),
    enabled: Boolean(projectId),
  })

  // Only live runs can back a grant. Offering a finished one would produce a
  // 422 at issue time and read as a bug rather than as the rule it is.
  const runs = useQuery({
    queryKey: ['agent-runs', projectId],
    queryFn: () => listAgentRuns(projectId as string),
    enabled: Boolean(projectId),
  })
  const liveRuns = (runs.data ?? []).filter(isLive)

  const issue = useMutation({
    mutationFn: () => {
      if (!projectId) throw new Error(copy.noProject)
      return issueMcpSession({
        project_id: projectId,
        label: label.trim(),
        capabilities: selected,
        agent_run_id: runId || null,
        expires_in_hours: Number(expiry) || 24,
      })
    },
    onSuccess: (grant) => {
      setIssued(grant)
      setCopiedToken(false)
      setLabel('')
      setRunId('')
      setSelected([])
      void queryClient.invalidateQueries({ queryKey: ['mcp-sessions', projectId] })
    },
    onError: (error) => showToast(error instanceof Error ? error.message : String(error), 'error'),
  })

  const revoke = useMutation({
    mutationFn: (session: McpSession) => revokeMcpSession(session.id, session.version),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp-sessions', projectId] }),
    onError: (error) => {
      // 412 is the ordinary outcome of two people revoking the same grant. Reload
      // and say so; insisting would overwrite a decision that already happened.
      if (error instanceof ApiError && error.status === 412) {
        showToast(copy.conflict, 'info')
        void queryClient.invalidateQueries({ queryKey: ['mcp-sessions', projectId] })
        return
      }
      showToast(error instanceof Error ? error.message : String(error), 'error')
    },
  })

  if (!projectId) {
    return <p className="px-3 py-2 text-sm text-text-secondary">{copy.noProject}</p>
  }

  return (
    <div className="space-y-4 px-3 py-3" data-testid="copilot-mcp-sessions">
      <p className="text-xs text-text-secondary">{copy.intro}</p>

      {issued ? (
        <div className="space-y-2 rounded-md border border-border bg-surface-2 p-3">
          <p className="text-sm font-medium">{copy.issued}</p>
          <label className="flex flex-col gap-1 text-xs">
            <span>{copy.token}</span>
            <div className="flex items-center gap-2">
              <Input readOnly value={issued.token} className="font-mono text-xs" />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  void navigator.clipboard?.writeText(issued.token)
                  setCopiedToken(true)
                }}
              >
                {copiedToken ? copy.copied : copy.copy}
              </Button>
            </div>
          </label>
          <p className="text-xs text-text-secondary">
            {copy.endpointLabel}: <code className="font-mono">{issued.endpoint}</code>
          </p>
          <p className="flex items-start gap-1 text-xs text-warning">
            <WarningIcon aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
            {copy.tokenWarning}
          </p>
          <Button type="button" size="sm" variant="ghost" onClick={() => setIssued(null)}>
            {copy.dismiss}
          </Button>
        </div>
      ) : null}

      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault()
          issue.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span>{copy.label}</span>
          <Input
            placeholder={copy.labelPlaceholder}
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>

        <fieldset className="space-y-1">
          <legend className="text-sm">{copy.capabilities}</legend>
          <div className="flex flex-wrap gap-2">
            {(skills.data ?? []).map((skill) => (
              <div key={skill.id} className="flex items-center gap-1.5 text-xs">
                <Checkbox
                  id={`mcp-capability-${skill.id}`}
                  checked={selected.includes(skill.id)}
                  onCheckedChange={(checked) =>
                    setSelected((current) =>
                      checked === true
                        ? [...current, skill.id]
                        : current.filter((item) => item !== skill.id),
                    )
                  }
                />
                <Label htmlFor={`mcp-capability-${skill.id}`} className="text-xs font-normal">
                  {skill.title}
                </Label>
              </div>
            ))}
          </div>
          <p className="text-xs text-text-secondary">{copy.capabilitiesHint}</p>
        </fieldset>

        <div className="grid gap-1">
          <Label htmlFor="mcp-bind-run">{copy.bindRun}</Label>
          <Select
            // `NONE_RUN` rather than '': an empty string is not a selectable
            // value in this registry's Select, and "no mandate" is a real choice
            // here, not the absence of one.
            value={runId || NONE_RUN}
            onValueChange={(value) => setRunId(value === NONE_RUN ? '' : (value ?? ''))}
          >
            <SelectTrigger id="mcp-bind-run" className="w-full" aria-label={copy.bindRun}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_RUN}>{copy.bindRunNone}</SelectItem>
              {liveRuns.map((run) => (
                <SelectItem key={run.id} value={run.id}>
                  {run.goal.slice(0, 80)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-xs text-text-secondary">{copy.bindRunHint}</span>
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>{copy.expiry}</span>
            <Input
              type="number"
              min={1}
              max={720}
              className="w-20 tabular-nums"
              value={expiry}
              onChange={(event) => setExpiry(event.target.value)}
            />
          </label>
          <Button
            type="submit"
            size="sm"
            disabled={!label.trim() || selected.length === 0 || issue.isPending}
          >
            {issue.isPending ? copy.issuing : copy.issue}
          </Button>
        </div>
      </form>

      {sessions.isError ? (
        <p className="text-sm text-destructive" role="alert">
          {copy.loadFailed}
        </p>
      ) : null}

      {sessions.data && sessions.data.length > 0 ? (
        <ul className="space-y-2">
          {sessions.data.map((session) => (
            <li key={session.id} className="rounded-md border border-border-soft p-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{session.label}</span>
                <StatusPill tone={toneFor(session)}>
                  {session.revoked_at
                    ? copy.revoked
                    : isSpent(session)
                      ? copy.expired
                      : copy.active}
                </StatusPill>
                {!session.revoked_at && !isSpent(session) ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="ml-auto h-auto px-0 py-0 text-xs"
                    onClick={() => revoke.mutate(session)}
                    disabled={revoke.isPending}
                  >
                    {revoke.isPending ? copy.revoking : copy.revoke}
                  </Button>
                ) : null}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                <span>{format(copy.toolCount, { count: String(session.tools.length) })}</span>
                {session.write_tools.length > 0 ? (
                  <span>
                    {format(copy.writeEnabled, { count: String(session.write_tools.length) })}
                  </span>
                ) : (
                  <span>{copy.readOnly}</span>
                )}
                <span>{format(copy.calls, { count: String(session.call_count) })}</span>
                <span>
                  {session.last_used_at
                    ? format(copy.lastUsed, {
                        when: new Date(session.last_used_at).toLocaleString(),
                      })
                    : copy.neverUsed}
                </span>
              </div>
              {session.agent_run_id && !session.mandate_live && !session.revoked_at ? (
                <p className="mt-1 text-[11px] text-warning">{copy.mandateSpent}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-secondary">{copy.empty}</p>
      )}
    </div>
  )
}
