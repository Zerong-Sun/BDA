import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { XIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ApiState } from '../../components/ui/ApiState'
import { DrawerShell } from '../../components/ui/DrawerShell'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { useAppStore } from '../../lib/store/appStore'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { currentRole } from '../../features/research/jsonHelpers'
import { useI18n } from '../../lib/i18n'
import { isSettled, listOperations, type Operation } from '../../lib/api/operations'

/**
 * What was queued, and where it got to.
 *
 * Every domain that queues work records an operation, and none of it was listable:
 * an operation lived only as a local variable in whichever component started it, so
 * navigating away from an import lost the handle to work that kept running. This is
 * that handle, kept.
 *
 * Deliberately not here, each for its own reason: no progress bar (`progress` is
 * written in one place in the whole backend, and as context rather than a fraction);
 * no cancel button (there is no endpoint, and no hook into the Celery task); and jobs
 * are linked to rather than restated, since they already have the workflow surface.
 */

/** "all" is admin-only, matching the server: a non-admin's listing is fenced anyway. */
type Scope = 'mine' | 'project' | 'all'

const STATUS_FILTERS = ['', 'pending', 'running', 'succeeded', 'failed'] as const

/** Where an operation's resource can be looked at, when the app has a page for it. */
function resourceLink(operation: Operation): string | null {
  const project = operation.project_id
  if (!project) return null
  switch (operation.resource_type) {
    case 'job':
    case 'workflow_run':
      return `/workflow?project=${encodeURIComponent(project)}`
    case 'candidate':
      return `/candidates?project=${encodeURIComponent(project)}&candidate=${encodeURIComponent(operation.resource_id)}`
    case 'experiment_result':
      return `/results?project=${encodeURIComponent(project)}`
    default:
      return null
  }
}

function elapsed(operation: Operation): string {
  const start = new Date(operation.started_at ?? operation.created_at).getTime()
  const end = new Date(operation.finished_at ?? Date.now()).getTime()
  const seconds = Math.max(0, Math.round((end - start) / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

export function ActivityDrawer() {
  const { t, format } = useI18n()
  const copy = t.operations
  const { activityOpen, setActivityOpen } = useAppStore()
  const { projectId } = useProjectContext()
  const isAdmin = currentRole() === 'admin'
  const [scope, setScope] = useState<Scope>('mine')
  const [status, setStatus] = useState<string>('')

  const query = useQuery({
    queryKey: ['operations', scope, status, projectId],
    queryFn: () =>
      listOperations({
        mine: scope === 'mine',
        projectId: scope === 'project' ? projectId || undefined : undefined,
        status: status || undefined,
        limit: 50,
      }),
    enabled: activityOpen,
    // Anything unsettled will change on its own; anything settled will not. Polling
    // stops as soon as the page holds nothing in flight.
    refetchInterval: (result) =>
      (result.state.data?.items ?? []).some((item) => !isSettled(item)) ? 4000 : false,
  })

  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const scopes: Scope[] = isAdmin ? ['mine', 'project', 'all'] : ['mine', 'project']

  return (
    <DrawerShell
      open={activityOpen}
      onClose={() => setActivityOpen(false)}
      widthClass="sm:max-w-[32rem]"
      title={copy.title}
      header={
        <div className="flex w-full items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{copy.eyebrow}</p>
            <h2 className="text-lg font-semibold text-text-primary">{copy.title}</h2>
            <p className="text-sm text-text-secondary">{copy.subtitle}</p>
          </div>
          <Button
            type="button"
            aria-label={copy.close}
            variant="outline"
            size="icon-sm"
            onClick={() => setActivityOpen(false)}
          >
            <XIcon className="h-4 w-4" />
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Select value={scope} onValueChange={(next) => next && setScope(next as Scope)}>
            <SelectTrigger className="h-8 w-32 text-xs" aria-label={copy.scope}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopes.map((item) => (
                <SelectItem key={item} value={item}>
                  {copy.scopes[item]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={(next) => setStatus(next ?? '')}>
            <SelectTrigger className="h-8 w-32 text-xs" aria-label={copy.statusFilter}>
              <SelectValue placeholder={copy.anyStatus} />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((item) => (
                <SelectItem key={item || 'any'} value={item}>
                  {item ? copy.status[item as keyof typeof copy.status] : copy.anyStatus}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <ApiState isLoading={query.isLoading} error={query.error} onRetry={() => void query.refetch()}>
          {items.length ? (
            <ul className="grid gap-2">
              {items.map((operation) => {
                const href = resourceLink(operation)
                return (
                  <li
                    key={operation.id}
                    className="rounded-md border border-border-soft bg-bg-app px-3 py-2 text-xs"
                  >
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className="font-mono text-text-primary">{operation.kind}</span>
                      <StatusPill label={operation.status} tone={statusTone(operation.status)} />
                      <span className="ml-auto tabular-nums text-text-muted">{elapsed(operation)}</span>
                    </div>
                    <p className="mt-1 text-text-secondary">
                      {new Date(operation.created_at).toLocaleString()}
                      {href ? (
                        <>
                          {' · '}
                          <Link className="text-accent hover:underline" to={href}>
                            {format(copy.openResource, { type: operation.resource_type })}
                          </Link>
                        </>
                      ) : null}
                    </p>
                    {operation.error_message ? (
                      <p className="mt-1 break-words text-crit">{operation.error_message}</p>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="text-xs text-text-secondary">{copy.empty}</p>
          )}
          {query.data?.next_cursor ? (
            <p className="mt-2 text-xs text-text-muted">{copy.moreBeyondWindow}</p>
          ) : null}
        </ApiState>
      </div>
    </DrawerShell>
  )
}
