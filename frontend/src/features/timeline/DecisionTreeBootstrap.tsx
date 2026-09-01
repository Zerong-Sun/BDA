import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AppFrame } from '../../components/ui/AppFrame'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/textarea'
import { Input } from '../../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { useI18n } from '../../lib/i18n'
import {
  createDecisionTreeDraft,
  flattenDraftGoals,
  importDecisionTree,
  removeGoal,
  renameGoal,
  waitForDecisionTreeDraft,
  type DecisionTreeProposal,
  type DraftBranch,
} from '../../lib/api/decisionTree'

/**
 * Draft a starting decision tree from the project's brief, then review it item by item.
 *
 * The review is the feature. A model proposing goals is cheap and a model *setting* them
 * is not acceptable here, so nothing lands until a person has looked at each row and
 * submitted what survived. That is why this component holds an editable copy and posts
 * the copy - there is no "accept all" call, on either side of the wire.
 */

interface Props {
  projectId: string
  hasPrompt: boolean
}

export function DecisionTreeBootstrap({ projectId, hasPrompt }: Props) {
  const { t, format } = useI18n()
  const tl = t.timeline
  const queryClient = useQueryClient()
  const [proposal, setProposal] = useState<DecisionTreeProposal | null>(null)

  const draft = useMutation({
    mutationFn: async () => {
      const { draft_id: draftId } = await createDecisionTreeDraft(projectId)
      return waitForDecisionTreeDraft(draftId)
    },
    onSuccess: (result) => {
      if (result.status === 'ready') setProposal(result.draft)
    },
  })

  const submit = useMutation({
    mutationFn: () => importDecisionTree(projectId, proposal as DecisionTreeProposal),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['research-goals', projectId] })
      await queryClient.invalidateQueries({ queryKey: ['project-timeline', projectId] })
      setProposal(null)
      draft.reset()
    },
  })

  if (!hasPrompt) {
    return (
      <AppFrame panelClassName="p-4">
        <p className="text-sm text-text-secondary">{tl.bootstrapNeedsPrompt}</p>
      </AppFrame>
    )
  }

  const dropBranch = (index: number) =>
    setProposal((current) =>
      current ? { ...current, branches: current.branches.filter((_, n) => n !== index) } : current,
    )

  const editBranch = (index: number, patch: Partial<DraftBranch>) =>
    setProposal((current) =>
      current
        ? {
            ...current,
            branches: current.branches.map((branch, n) => (n === index ? { ...branch, ...patch } : branch)),
          }
        : current,
    )

  return (
    <AppFrame panelClassName="p-4">
      <div className="mb-3">
        <h2 className="text-lg font-semibold text-text-primary">{tl.bootstrapTitle}</h2>
        <p className="text-sm text-text-secondary">{tl.bootstrapSubtitle}</p>
      </div>

      {proposal === null ? (
        <div className="grid gap-2">
          <Button type="button" size="sm" disabled={draft.isPending} onClick={() => draft.mutate()}>
            {draft.isPending ? tl.bootstrapDrafting : tl.bootstrapDraft}
          </Button>
          {draft.data?.status === 'failed' ? (
            <p className="text-xs text-warning">{draft.data.error ?? tl.bootstrapFailed}</p>
          ) : null}
          {draft.isError ? <p className="text-xs text-warning">{tl.bootstrapFailed}</p> : null}
        </div>
      ) : (
        <div className="grid gap-4">
          <p className="rounded-md border border-border-soft bg-surface-2 p-2 text-xs text-text-secondary">
            {tl.bootstrapReviewHint}
          </p>

          <section>
            <h3 className="mb-1 text-xs uppercase tracking-wide text-text-muted">{tl.bootstrapGoals}</h3>
            <ul className="grid gap-1">
              {flattenDraftGoals(proposal.goals).map(({ goal, depth }) => (
                <li
                  key={goal.title}
                  className="flex items-center gap-2"
                  style={{ marginInlineStart: `${depth * 1.25}rem` }}
                >
                  <Input
                    aria-label={format(tl.bootstrapGoalLabel, { title: goal.title })}
                    className="flex-1"
                    value={goal.title}
                    onChange={(event) =>
                      setProposal((current) =>
                        current ? renameGoal(current, goal.title, event.target.value) : current,
                      )
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setProposal((current) => (current ? removeGoal(current, goal.title) : current))
                    }
                  >
                    {tl.bootstrapDrop}
                  </Button>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="mb-1 text-xs uppercase tracking-wide text-text-muted">{tl.bootstrapBranches}</h3>
            <ul className="grid gap-2">
              {proposal.branches.map((branch, index) => (
                <li key={`${branch.goal_title}:${branch.title}`} className="rounded-md border border-border-soft p-2">
                  <div className="flex items-center gap-2">
                    <Input
                      aria-label={format(tl.bootstrapBranchLabel, { title: branch.title })}
                      className="flex-1"
                      value={branch.title}
                      onChange={(event) => editBranch(index, { title: event.target.value })}
                    />
                    <Select
                      value={branch.lane}
                      onValueChange={(value) =>
                        editBranch(index, { lane: (value ?? 'dry') as DraftBranch['lane'] })
                      }
                    >
                      <SelectTrigger
                        aria-label={format(tl.bootstrapLaneLabel, { title: branch.title })}
                        className="min-w-28"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="dry">{tl.lane.dry}</SelectItem>
                        <SelectItem value="wet">{tl.lane.wet}</SelectItem>
                        <SelectItem value="both">{tl.lane.both}</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button type="button" variant="ghost" size="sm" onClick={() => dropBranch(index)}>
                      {tl.bootstrapDrop}
                    </Button>
                  </div>
                  <p className="mt-1 text-[11px] text-text-muted">
                    {format(tl.bootstrapUnder, { title: branch.goal_title })}
                  </p>
                  {branch.summary ? (
                    <Textarea
                      rows={2}
                      className="mt-1 text-xs"
                      aria-label={format(tl.bootstrapSummaryLabel, { title: branch.title })}
                      value={branch.summary}
                      onChange={(event) => editBranch(index, { summary: event.target.value })}
                    />
                  ) : null}
                </li>
              ))}
            </ul>
          </section>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              disabled={submit.isPending || (!proposal.goals.length && !proposal.branches.length)}
              onClick={() => submit.mutate()}
            >
              {format(tl.bootstrapAccept, {
                goals: String(flattenDraftGoals(proposal.goals).length),
                branches: String(proposal.branches.length),
              })}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setProposal(null)}>
              {tl.bootstrapDiscard}
            </Button>
          </div>
          {submit.isError ? <p className="text-xs text-warning">{tl.bootstrapImportFailed}</p> : null}
        </div>
      )}
    </AppFrame>
  )
}
