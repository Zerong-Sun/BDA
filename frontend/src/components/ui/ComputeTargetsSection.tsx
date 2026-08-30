import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HeartbeatIcon, PlusIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { StatusPill } from './StatusPill'
import { statusTone } from './statusTone'
import { useToastStore } from './toastStore'
import { useI18n } from '../../lib/i18n'
import { currentRole } from '../../features/research/jsonHelpers'
import {
  checkComputeNodeHealth,
  createComputeNode,
  disableComputeNode,
  listComputeNodes,
} from '../../lib/api/registry'

/**
 * Where the platform may dispatch, and how to add one.
 *
 * The connections panel above could already say "no compute nodes are registered" - it
 * simply had no way to do anything about it, because every registry write endpoint
 * existed without a caller. Registering a cluster meant writing a migration.
 *
 * Only the fields the scheduler reads are here. Credentials are not among them: the LSF
 * worker takes its password from a `file:` reference on the host that runs it, and this
 * form must never become a second, worse way to supply one.
 */

const BACKENDS = ['lsf', 'docker'] as const

export function ComputeTargetsSection() {
  const { t, format } = useI18n()
  const copy = t.settingsExt.computeTargets
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [backend, setBackend] = useState<string>('lsf')
  const [queue, setQueue] = useState('')

  const isAdmin = currentRole() === 'admin'

  const nodes = useQuery({
    queryKey: ['compute-nodes'],
    queryFn: listComputeNodes,
    staleTime: 30_000,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['compute-nodes'] })
  const fail = (err: unknown, fallback: string) =>
    showToast(err instanceof Error ? err.message : fallback, 'error')

  const register = useMutation({
    mutationFn: () =>
      createComputeNode({ name: name.trim(), backend, queue: queue.trim() || null }),
    onSuccess: (node) => {
      setName('')
      setQueue('')
      showToast(format(copy.registered, { name: node.name }), 'success')
      void invalidate()
    },
    onError: (err) => fail(err, copy.registerFailed),
  })

  const check = useMutation({
    mutationFn: (nodeId: string) => checkComputeNodeHealth(nodeId),
    onSuccess: () => void invalidate(),
    onError: (err) => fail(err, copy.healthCheckFailed),
  })

  const disable = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => disableComputeNode(id, version),
    onSuccess: () => void invalidate(),
    onError: (err) => fail(err, copy.disableFailed),
  })

  return (
    <section className="space-y-3 border-b border-border-soft p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <HeartbeatIcon className="h-4 w-4 text-accent" />
        {copy.title}
      </div>

      {nodes.data?.length ? (
        <ul className="grid gap-2">
          {nodes.data.map((node) => (
            <li
              key={node.id}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border-soft px-3 py-2 text-xs"
            >
              <span className="min-w-0 flex-1 truncate text-text-primary">{node.name}</span>
              <span className="text-text-secondary">{node.backend}</span>
              {node.queue ? <span className="font-mono text-text-muted">{node.queue}</span> : null}
              <StatusPill label={node.health_status} tone={statusTone(node.health_status)} />
              {isAdmin ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={check.isPending}
                    aria-label={format(copy.checkHealthOf, { name: node.name })}
                    onClick={() => check.mutate(node.id)}
                  >
                    {copy.checkHealth}
                  </Button>
                  {node.enabled ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={disable.isPending}
                      aria-label={format(copy.disableNode, { name: node.name })}
                      onClick={() => disable.mutate({ id: node.id, version: node.version })}
                    >
                      {copy.disable}
                    </Button>
                  ) : (
                    <span className="text-text-muted">{copy.disabled}</span>
                  )}
                </>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-text-secondary">{copy.empty}</p>
      )}

      {isAdmin ? (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (name.trim()) register.mutate()
          }}
        >
          <Input
            className="min-w-0 flex-1"
            value={name}
            placeholder={copy.namePlaceholder}
            aria-label={copy.namePlaceholder}
            onChange={(event) => setName(event.target.value)}
          />
          <Select value={backend} onValueChange={(next) => next && setBackend(next)}>
            <SelectTrigger className="h-8 w-24 text-xs" aria-label={copy.backendLabel}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BACKENDS.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            className="w-32"
            value={queue}
            placeholder={copy.queuePlaceholder}
            aria-label={copy.queuePlaceholder}
            onChange={(event) => setQueue(event.target.value)}
          />
          <Button type="submit" size="sm" disabled={!name.trim() || register.isPending}>
            <PlusIcon aria-hidden="true" />
            {register.isPending ? copy.registering : copy.register}
          </Button>
        </form>
      ) : (
        <p className="text-xs text-text-muted">{copy.adminOnly}</p>
      )}
      <p className="text-xs text-text-muted">{copy.credentialNotice}</p>
    </section>
  )
}
