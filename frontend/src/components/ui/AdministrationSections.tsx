import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardTextIcon, HeartbeatIcon, PlusIcon, UsersThreeIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToastStore } from './toastStore'
import { useI18n } from '../../lib/i18n'
import { currentRole } from '../../features/research/jsonHelpers'
import {
  addOrganizationMember,
  createOrganization,
  getOperationsSummary,
  listAuditLogs,
  listOrganizationMembers,
  listOrganizations,
} from '../../lib/api/administration'

/**
 * Organizations, their members, and the audit trail.
 *
 * All three tables are declared in the flow matrix with `ui: ["administration"]`, and
 * that screen did not exist — the matrix checks that a table is declared, not that the
 * interface it names is real. Everything here is read-first: the audit log is only ever
 * read, and membership is shown before it can be changed, because the write endpoint
 * has always existed while the read endpoint did not.
 */

const MEMBER_ROLES = ['owner', 'admin', 'researcher', 'viewer'] as const

function OrganizationsSection() {
  const { t, format } = useI18n()
  const copy = t.settingsExt.administration
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState<string>('researcher')

  const organizations = useQuery({
    queryKey: ['organizations'],
    queryFn: listOrganizations,
    staleTime: 60_000,
  })

  const activeId = selected ?? organizations.data?.[0]?.id ?? null

  const members = useQuery({
    queryKey: ['organization-members', activeId],
    queryFn: () => listOrganizationMembers(activeId!),
    enabled: Boolean(activeId),
    staleTime: 30_000,
  })

  const fail = (err: unknown, fallback: string) =>
    showToast(err instanceof Error ? err.message : fallback, 'error')

  const create = useMutation({
    mutationFn: () => createOrganization(name.trim()),
    onSuccess: (organization) => {
      setName('')
      setSelected(organization.id)
      void queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
    onError: (err) => fail(err, copy.createOrgFailed),
  })

  const addMember = useMutation({
    mutationFn: () => addOrganizationMember(activeId!, userId.trim(), role),
    onSuccess: () => {
      setUserId('')
      showToast(copy.memberAdded, 'success')
      void queryClient.invalidateQueries({ queryKey: ['organization-members', activeId] })
    },
    onError: (err) => fail(err, copy.addMemberFailed),
  })

  return (
    <section className="space-y-3 border-b border-border-soft p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <UsersThreeIcon className="h-4 w-4 text-accent" />
        {copy.organizations}
      </div>

      {organizations.data?.length ? (
        <>
          <Select value={activeId ?? ''} onValueChange={(next) => next && setSelected(next)}>
            <SelectTrigger className="h-8 w-full text-xs" aria-label={copy.organization}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {organizations.data.map((organization) => (
                <SelectItem key={organization.id} value={organization.id}>
                  {organization.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {members.data?.length ? (
            <ul className="grid gap-1">
              {members.data.map((member) => (
                <li
                  key={member.user_id}
                  className="flex items-baseline gap-2 rounded-md border border-border-soft px-3 py-1.5 text-xs"
                >
                  <span className="min-w-0 flex-1 truncate text-text-primary">
                    {member.display_name}
                  </span>
                  <span className="font-mono text-text-muted">{member.username}</span>
                  <span className="text-text-secondary">{member.role}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-secondary">{copy.noMembers}</p>
          )}
        </>
      ) : (
        <p className="text-xs text-text-secondary">{copy.noOrganizations}</p>
      )}

      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (name.trim()) create.mutate()
        }}
      >
        <Input
          className="min-w-0 flex-1"
          value={name}
          placeholder={copy.orgNamePlaceholder}
          aria-label={copy.orgNamePlaceholder}
          onChange={(event) => setName(event.target.value)}
        />
        <Button type="submit" size="sm" variant="outline" disabled={!name.trim() || create.isPending}>
          <PlusIcon aria-hidden="true" />
          {copy.createOrg}
        </Button>
      </form>

      {activeId ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (userId.trim()) addMember.mutate()
          }}
        >
          <Input
            className="min-w-0 flex-1"
            value={userId}
            placeholder={copy.memberIdPlaceholder}
            aria-label={copy.memberIdPlaceholder}
            onChange={(event) => setUserId(event.target.value)}
          />
          <Select value={role} onValueChange={(next) => next && setRole(next)}>
            <SelectTrigger className="h-8 w-28 text-xs" aria-label={copy.memberRole}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MEMBER_ROLES.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="submit"
            size="sm"
            variant="outline"
            disabled={!userId.trim() || addMember.isPending}
          >
            {copy.addMember}
          </Button>
        </form>
      ) : null}
      <p className="text-xs text-text-muted">{format(copy.upsertNotice, {})}</p>
    </section>
  )
}

function AuditSection() {
  const { t } = useI18n()
  const copy = t.settingsExt.administration
  const [action, setAction] = useState('')

  const logs = useQuery({
    queryKey: ['audit-logs', action],
    queryFn: () => listAuditLogs({ action, limit: 50 }),
    staleTime: 15_000,
  })

  return (
    <section className="space-y-3 border-b border-border-soft p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <ClipboardTextIcon className="h-4 w-4 text-accent" />
        {copy.audit}
      </div>
      <Input
        value={action}
        placeholder={copy.auditFilterPlaceholder}
        aria-label={copy.auditFilterPlaceholder}
        onChange={(event) => setAction(event.target.value)}
      />
      {logs.data?.length ? (
        <ul className="grid max-h-64 gap-1 overflow-y-auto">
          {logs.data.map((entry) => (
            <li key={entry.id} className="rounded-md border border-border-soft px-3 py-1.5 text-xs">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-text-primary">{entry.action}</span>
                <span className="ml-auto text-text-muted">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
              </div>
              <p className="mt-0.5 text-text-secondary">
                {entry.entity_type}
                {entry.result ? ` · ${entry.result}` : ''}
                {/* The trace id is what ties an entry to the request that caused it. */}
                {entry.trace_id ? ` · ${entry.trace_id}` : ''}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-text-secondary">{copy.noAudit}</p>
      )}
    </section>
  )
}

function PlatformHealthSection() {
  const { t } = useI18n()
  const copy = t.settingsExt.administration
  const summary = useQuery({
    queryKey: ['operations-summary'],
    queryFn: getOperationsSummary,
    staleTime: 20_000,
  })

  const data = summary.data
  // Two of these mean something is wrong rather than merely busy, so they read as
  // numbers with a verdict attached instead of another row of counts.
  const stuck = [
    { label: copy.outboxBacklog, value: data?.outbox_backlog ?? 0 },
    { label: copy.missingArtifacts, value: data?.missing_artifacts ?? 0 },
  ]

  return (
    <section className="space-y-3 border-b border-border-soft p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <HeartbeatIcon className="h-4 w-4 text-accent" />
        {copy.platformHealth}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {stuck.map((item) => (
          <div key={item.label} className="rounded-md border border-border-soft px-3 py-2">
            <p className="text-xs text-text-secondary">{item.label}</p>
            <p
              className={
                item.value > 0
                  ? 'text-lg font-semibold tabular-nums text-accent'
                  : 'text-lg font-semibold tabular-nums text-text-primary'
              }
            >
              {item.value}
            </p>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-secondary">
        {copy.byStatus}: {Object.entries(data?.operations_by_status ?? {})
          .map(([status, count]) => `${status} ${count}`)
          .join(' · ') || '—'}
      </p>
      <p className="text-xs text-text-secondary">
        {copy.jobsByStatus}: {Object.entries(data?.jobs_by_status ?? {})
          .map(([status, count]) => `${status} ${count}`)
          .join(' · ') || '—'}
      </p>
    </section>
  )
}

export function AdministrationSections() {
  // Every endpoint behind these two panels is admin-only on the server; rendering them
  // to anyone else would be a row of controls that always 403s.
  if (currentRole() !== 'admin') return null
  return (
    <>
      <PlatformHealthSection />
      <OrganizationsSection />
      <AuditSection />
    </>
  )
}
