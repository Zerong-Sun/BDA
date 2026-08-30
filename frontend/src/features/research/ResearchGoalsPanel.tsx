import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusIcon, TrashIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ApiState } from '../../components/ui/ApiState'
import { useI18n } from '../../lib/i18n'
import { useToastStore } from '../../components/ui/toastStore'
import {
  buildGoalTree,
  createResearchGoal,
  deleteResearchGoal,
  detachFromResearchGoal,
  listResearchGoals,
  updateResearchGoal,
  type ResearchGoal,
  type ResearchGoalNode,
} from '../../lib/api/researchGoals'

/**
 * The research goal tree.
 *
 * The pre-refactor survey concluded that the one thing genuinely missing was a goal
 * layer: findings record what we believe and the timeline records how we got there, but
 * neither is a node you can hang a sub-question or an experiment on. The tables, the
 * cycle guard and the API landed; this is the surface, without which the tree only ever
 * grew when someone asked the agent to grow it.
 */

const STATUSES = ['open', 'answered', 'abandoned'] as const
type GoalStatus = (typeof STATUSES)[number]

/** The server may add a link type before this file knows about it; show the raw token
 *  rather than an empty chip, which would read as "attached to nothing". */
function linkTypeLabel(labels: Record<string, string>, resourceType: string): string {
  return labels[resourceType] ?? resourceType
}

interface ResearchGoalsPanelProps {
  projectId: string
}

export function ResearchGoalsPanel({ projectId }: ResearchGoalsPanelProps) {
  const { t, format } = useI18n()
  const copy = t.research.goals
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [parentId, setParentId] = useState<string | null>(null)

  const goalsQuery = useQuery({
    queryKey: ['research-goals', projectId],
    queryFn: () => listResearchGoals(projectId),
    enabled: Boolean(projectId),
    staleTime: 30_000,
  })

  const tree = useMemo(() => buildGoalTree(goalsQuery.data ?? []), [goalsQuery.data])
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['research-goals', projectId] })

  const fail = (err: unknown, fallback: string) =>
    showToast(err instanceof Error ? err.message : fallback, 'error')

  const addGoal = useMutation({
    mutationFn: () => createResearchGoal(projectId, { title: title.trim(), parent_id: parentId }),
    onSuccess: () => {
      setTitle('')
      setParentId(null)
      void invalidate()
    },
    onError: (err) => fail(err, copy.createFailed),
  })

  const setStatus = useMutation({
    mutationFn: ({ goal, status }: { goal: ResearchGoal; status: GoalStatus }) =>
      updateResearchGoal(goal.id, goal.version, { status }),
    onSuccess: () => void invalidate(),
    // 412 is the interesting one: the goal moved under us, so re-read rather than insist.
    onError: (err) => fail(err, copy.updateFailed),
  })

  const removeGoal = useMutation({
    mutationFn: (goal: ResearchGoal) => deleteResearchGoal(goal.id),
    onSuccess: (result) => {
      if ((result.removed_goals ?? 0) > 1) {
        showToast(format(copy.removedWithChildren, { count: result.removed_goals }), 'success')
      }
      void invalidate()
    },
    onError: (err) => fail(err, copy.deleteFailed),
  })

  const detach = useMutation({
    mutationFn: ({ goalId, linkId }: { goalId: string; linkId: string }) =>
      detachFromResearchGoal(goalId, linkId),
    onSuccess: () => void invalidate(),
    onError: (err) => fail(err, copy.detachFailed),
  })

  const renderNode = (node: ResearchGoalNode) => {
    const links = node.goal.links ?? []
    return (
    <li key={node.goal.id} style={{ marginInlineStart: `${node.depth * 1.25}rem` }}>
      <div className="flex flex-wrap items-baseline gap-2 rounded-md border border-border-soft bg-bg-app px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-text-primary">{node.goal.title}</span>
        <Select
          value={node.goal.status}
          onValueChange={(next) => {
            if (next) setStatus.mutate({ goal: node.goal, status: next as GoalStatus })
          }}
        >
          <SelectTrigger
            className="h-7 w-32 text-xs"
            aria-label={format(copy.statusOf, { title: node.goal.title })}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUSES.map((status) => (
              <SelectItem key={status} value={status}>
                {copy.status[status]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={format(copy.addChildTo, { title: node.goal.title })}
          onClick={() => setParentId(node.goal.id)}
        >
          <PlusIcon aria-hidden="true" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          aria-label={format(copy.deleteGoal, { title: node.goal.title })}
          onClick={() => removeGoal.mutate(node.goal)}
        >
          <TrashIcon aria-hidden="true" />
        </Button>
      </div>
      {node.goal.detail ? (
        <p className="px-3 pt-1 text-xs text-text-secondary">{node.goal.detail}</p>
      ) : null}
      {links.length ? (
        <ul className="mt-1 flex flex-wrap gap-1 px-3">
          {links.map((link) => (
            <li
              key={link.id}
              className="flex items-center gap-1 rounded-full border border-border-soft px-2 py-0.5 text-[11px] text-text-secondary"
            >
              <span>{linkTypeLabel(copy.linkType, link.resource_type)}</span>
              <span className="font-mono">{link.resource_id.slice(0, 8)}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-4 w-4 p-0 text-text-muted"
                aria-label={format(copy.detachLink, { type: link.resource_type })}
                onClick={() => detach.mutate({ goalId: node.goal.id, linkId: link.id })}
              >
                ×
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {node.children.length ? <ul className="mt-1 grid gap-1">{node.children.map(renderNode)}</ul> : null}
    </li>
    )
  }

  const parentTitle = parentId
    ? (goalsQuery.data ?? []).find((goal) => goal.id === parentId)?.title
    : null

  return (
    <section className="grid gap-3">
      <div>
        <h2 className="text-sm font-semibold text-text-primary">{copy.title}</h2>
        <p className="mt-1 text-xs text-text-secondary">{copy.help}</p>
      </div>

      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (title.trim()) addGoal.mutate()
        }}
      >
        <Input
          className="min-w-0 flex-1"
          value={title}
          placeholder={parentTitle ? format(copy.childPlaceholder, { title: parentTitle }) : copy.placeholder}
          aria-label={copy.placeholder}
          onChange={(event) => setTitle(event.target.value)}
        />
        {parentId ? (
          <Button type="button" size="sm" variant="outline" onClick={() => setParentId(null)}>
            {copy.clearParent}
          </Button>
        ) : null}
        <Button type="submit" size="sm" disabled={!title.trim() || addGoal.isPending}>
          {addGoal.isPending ? copy.adding : copy.add}
        </Button>
      </form>

      <ApiState
        isLoading={goalsQuery.isLoading}
        error={goalsQuery.error}
        onRetry={() => void goalsQuery.refetch()}
      >
        {tree.length ? (
          <ul className="grid gap-1">{tree.map(renderNode)}</ul>
        ) : (
          <p className="text-xs text-text-secondary">{copy.empty}</p>
        )}
      </ApiState>
    </section>
  )
}
