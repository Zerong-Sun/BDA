import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FlaskIcon,
  FolderPlusIcon,
  ListChecksIcon,
  SparkleIcon,
  SpinnerGapIcon,
  TargetIcon,
} from '@phosphor-icons/react'
import { useNavigate } from 'react-router'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'
import { applyRoutePlan, planRoute } from '../../lib/api/copilot'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'

interface CopilotActionsProps {
  onNavigate?: () => void
}

export function CopilotActions({ onNavigate }: CopilotActionsProps) {
  const { t, format, language } = useI18n()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { projectId, activeProject } = useProjectContext()
  const appMode = useAppStore((state) => state.appMode)
  const showToast = useToastStore((state) => state.show)
  const isDemo = appMode === 'demo'

  const go = (path: string) => {
    const query = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
    navigate(`${path}${query}`)
    onNavigate?.()
  }

  const buildWorkflow = useMutation({
    mutationFn: async () => {
      if (isDemo) throw new Error(t.copilot.actions.demoModeHint)
      if (!projectId) throw new Error(t.copilot.actions.errorNoProject)
      const objective =
        (activeProject ? projectText(activeProject, 'summary', language).trim() : '') ||
        `Design workflow for ${activeProject ? projectText(activeProject, 'name', language) : 'this project'}`
      const plan = await planRoute({ project_id: projectId, target: objective, objective })
      const route = plan.route_options.find((option) => option.recommended) ?? plan.route_options[0]
      if (!route) throw new Error(t.copilot.actions.errorNoRoute)
      const moduleIds = route.modules
        .filter((module) => module.available)
        .map((module) => module.module_id)
      await applyRoutePlan({
        project_id: projectId,
        route_id: route.route_id,
        objective,
        target: plan.target ?? objective,
        selected_module_ids: moduleIds,
      })
      return route.label
    },
    onSuccess: (routeLabel) => {
      void queryClient.invalidateQueries({ queryKey: ['workflow-runs', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['workflow-run', 'current', projectId] })
      showToast(format(t.copilot.actions.successBuiltRoute, { routeLabel }), 'success')
      go('/workflow')
    },
    onError: (error) =>
      showToast(error instanceof Error ? error.message : t.copilot.actions.errorBuildFailed, 'error'),
  })

  return (
    <Accordion className="border-b" defaultValue={['quick-actions']}>
      <AccordionItem value="quick-actions" className="border-0">
        <AccordionTrigger className="px-3 py-2 uppercase tracking-wide text-primary">
          {t.copilot.actions.quickActions}
        </AccordionTrigger>
        <AccordionContent className="px-3 pb-3">
          {!projectId ? (
            <Button
              type="button"
              variant="outline"
              className="h-auto w-full justify-start whitespace-normal text-left"
              onClick={() => go('/projects')}
            >
              <FolderPlusIcon aria-hidden="true" />
              {t.copilot.actions.selectProjectFirst}
            </Button>
          ) : (
            <div className="grid gap-2">
              <Button
                type="button"
                className="h-auto w-full justify-start whitespace-normal text-left"
                disabled={isDemo || buildWorkflow.isPending}
                title={isDemo ? t.copilot.actions.demoModeHint : undefined}
                onClick={() => buildWorkflow.mutate()}
              >
                {buildWorkflow.isPending ? (
                  <SpinnerGapIcon
                    className="animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                ) : (
                  <SparkleIcon aria-hidden="true" />
                )}
                {buildWorkflow.isPending
                  ? t.copilot.actions.planAndBuildPending
                  : t.copilot.actions.planAndBuild}
              </Button>
              <div className="grid grid-cols-3 gap-2">
                <ActionChip
                  icon={<TargetIcon aria-hidden="true" />}
                  label={t.copilot.actions.analyzeTarget}
                  onClick={() => go('/research')}
                />
                <ActionChip
                  icon={<ListChecksIcon aria-hidden="true" />}
                  label={t.copilot.actions.candidates}
                  onClick={() => go('/candidates')}
                />
                <ActionChip
                  icon={<FlaskIcon aria-hidden="true" />}
                  label={t.copilot.actions.results}
                  onClick={() => go('/results')}
                />
              </div>
            </div>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

function ActionChip({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-auto min-w-0 flex-col gap-1 whitespace-normal px-2 py-2 text-[11px]"
      onClick={onClick}
    >
      {icon}
      {label}
    </Button>
  )
}
