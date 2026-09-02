import { useQuery } from '@tanstack/react-query'
import { GitBranchIcon } from '@phosphor-icons/react'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameDescription, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { DecisionTreeView } from '../timeline/DecisionTreeView'
import { listResearchGoals } from '../../lib/api/researchGoals'
import { listAllTimeline } from '../../lib/api/timeline'
import { useI18n } from '../../lib/i18n'

/**
 * The dry-lab decision tree, inside the research workspace.
 *
 * This used to render its own tree: timeline entries grouped into phase columns, with
 * `supersedes_id` and `caused_by_id` drawn as links. That was a second, weaker answer to
 * the same question `ProjectTimeline` already answers, and the two drifted immediately -
 * this one showed every entry type rather than decisions, and knew nothing about the goal
 * tree, `decision_ref`, `lane` or `alternatives`, which are the fields that separate a
 * decision record from a diary.
 *
 * `DECISION_TREE_DESIGN.md` section 6 asks for *three readings of one record*, not four
 * renderings of it, so this now shows the same tree `ProjectTimeline` shows. The
 * placement is what differs and what is worth keeping: a researcher reading the project's
 * evidence should not have to leave for another page to see what the evidence closed off.
 */
export function DryLabDecisionTree({ projectId }: { projectId: string }) {
  const { t } = useI18n()
  const copy = t.research.workspace
  const tl = t.timeline

  // Same query keys as ProjectTimeline on purpose: opening one after the other should hit
  // the cache rather than refetch, and an invalidation from either must reach both.
  const timelineQuery = useQuery({
    queryKey: ['project-timeline', projectId],
    queryFn: () => listAllTimeline(projectId),
    staleTime: 60_000,
  })
  const goalsQuery = useQuery({
    queryKey: ['research-goals', projectId],
    queryFn: () => listResearchGoals(projectId),
    staleTime: 60_000,
  })

  const isLoading = timelineQuery.isLoading || goalsQuery.isLoading
  const isError = timelineQuery.isError || goalsQuery.isError

  return (
    <Frame data-tour-id="dry-lab-decision-tree">
      <FramePanel className="grid gap-4">
        <FrameHeader className="px-0 py-0">
          <div className="flex items-center gap-2">
            <GitBranchIcon aria-hidden="true" className="size-5 text-primary" />
            <FrameTitle>{copy.decisionTreeTitle}</FrameTitle>
          </div>
          <FrameDescription>{copy.decisionTreeDescription}</FrameDescription>
        </FrameHeader>
        {isLoading ? <p className="text-sm text-muted-foreground" role="status">{tl.loading}</p> : null}
        {isError ? (
          <Alert variant="destructive" role="alert">
            <AlertDescription>
              <p>{tl.loadFailed}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => {
                  if (timelineQuery.isError) void timelineQuery.refetch()
                  if (goalsQuery.isError) void goalsQuery.refetch()
                }}
              >
                {t.common.retry}
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        {!isLoading && !isError ? (
          <DecisionTreeView goals={goalsQuery.data ?? []} entries={timelineQuery.data ?? []} />
        ) : null}
      </FramePanel>
    </Frame>
  )
}
