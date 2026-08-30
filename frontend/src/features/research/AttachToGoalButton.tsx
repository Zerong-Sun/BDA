import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckIcon, TargetIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import {
  attachToResearchGoal,
  buildGoalTree,
  flattenGoalTree,
  listResearchGoals,
} from '../../lib/api/researchGoals'

/**
 * Hang this resource on the question it answers.
 *
 * The goal tree exists so dry and wet work can be read off one structure, which
 * needs an attach action wherever a resource lives - not only in the tree itself,
 * and not only through the agent. One control serves all of them: the link is stored
 * as `(resource_type, resource_id)`, so nothing here is per-domain.
 *
 * Indentation follows the tree, because "which goal" is usually answered by where a
 * goal sits rather than by its title alone. Goals this resource is already on are
 * shown ticked and inert - the server treats a repeat as a double-click and returns
 * the existing link, but offering the click again would suggest it means something.
 *
 * The tree is fetched when the menu opens, not when the button mounts. This control
 * renders once per row in the protein library and the readouts table, so mounting it
 * must cost nothing: a page that only lists constructs should not request the goal
 * tree at all.
 */

interface AttachToGoalButtonProps {
  projectId: string
  resourceType: 'experiment_result' | 'finding' | 'candidate' | 'job' | 'protein'
  resourceId: string
  /** Rendered on the trigger; defaults to the shared short label. */
  label?: string
}

export function AttachToGoalButton({
  projectId,
  resourceType,
  resourceId,
  label,
}: AttachToGoalButtonProps) {
  const { t, format } = useI18n()
  const copy = t.research.goals
  const showToast = useToastStore((s) => s.show)
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)

  const goalsQuery = useQuery({
    queryKey: ['research-goals', projectId],
    queryFn: () => listResearchGoals(projectId),
    enabled: open && Boolean(projectId),
    staleTime: 30_000,
  })

  const attach = useMutation({
    mutationFn: (goalId: string) =>
      attachToResearchGoal(goalId, { resource_type: resourceType, resource_id: resourceId }),
    onSuccess: (_link, goalId) => {
      const goal = (goalsQuery.data ?? []).find((item) => item.id === goalId)
      showToast(format(copy.attached, { title: goal?.title ?? '' }), 'success')
      void queryClient.invalidateQueries({ queryKey: ['research-goals', projectId] })
    },
    onError: (err) =>
      showToast(err instanceof Error ? err.message : copy.attachFailed, 'error'),
  })

  const nodes = flattenGoalTree(buildGoalTree(goalsQuery.data ?? []))

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        render={
          <Button type="button" variant="outline" size="sm" disabled={attach.isPending}>
            <TargetIcon aria-hidden="true" />
            {label ?? copy.attachShort}
          </Button>
        }
      />
      <DropdownMenuContent align="start" className="max-h-80 w-72 overflow-y-auto">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{copy.attachTitle}</DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        {goalsQuery.isLoading ? (
          <DropdownMenuItem disabled>{copy.attachLoading}</DropdownMenuItem>
        ) : nodes.length ? (
          nodes.map(({ goal, depth }) => {
            const already = (goal.links ?? []).some(
              (link) => link.resource_type === resourceType && link.resource_id === resourceId,
            )
            return (
              <DropdownMenuItem
                key={goal.id}
                disabled={already || attach.isPending}
                onClick={() => {
                  if (!already) attach.mutate(goal.id)
                }}
              >
                <span
                  className="min-w-0 flex-1 truncate"
                  style={{ paddingInlineStart: `${depth * 0.75}rem` }}
                >
                  {goal.title}
                </span>
                {already ? <CheckIcon aria-hidden="true" className="text-accent" /> : null}
              </DropdownMenuItem>
            )
          })
        ) : (
          <DropdownMenuItem disabled>{copy.attachNoGoals}</DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
