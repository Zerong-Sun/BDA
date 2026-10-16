import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getClusterHealth, listComputeNodes } from '../../lib/api/registry'
import { getHealth } from '../../lib/api/health'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useAppStore } from '../../lib/store/appStore'
import { StatusPill } from '../../components/ui/StatusPill'
import { useI18n } from '../../lib/i18n'
import { projectText } from '../../lib/i18n/projectText'
import { Select, SelectContent, SelectGroup, SelectLabel, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { Frame, FramePanel } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../../components/ui/accordion'
import { groupWorkflowRoutes, routePresentation, workflowRouteName } from './routePresentation'

interface WorkflowContextBarProps {
  workflowRunId?: string
  workflowStatus?: string
  projectWorkflowRuns: Array<{
    id: string
    name: string
    status: string
    graph: Record<string, unknown>
  }>
  onSelectRun: (runId: string) => void
}

export function WorkflowContextBar({
  workflowRunId,
  workflowStatus,
  projectWorkflowRuns,
  onSelectRun,
}: WorkflowContextBarProps) {
  const { activeProject } = useProjectContext()
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen)
  const { t, language } = useI18n()
  const { data: nodes = [] } = useQuery({
    queryKey: ['compute-nodes'],
    queryFn: listComputeNodes,
  })
  const { data: clusterHealth } = useQuery({
    queryKey: ['cluster-health'],
    queryFn: getClusterHealth,
    refetchInterval: 30_000,
  })
  const backendHealth = useQuery({ queryKey: ['backend-health'], queryFn: getHealth, retry: false, refetchInterval: 15_000, staleTime: 10_000 })

  const gpuAvailable = nodes.some(
    (node) =>
      String(node.labels.accelerator ?? node.labels.resource_type ?? '').toLowerCase().includes('gpu') &&
      node.enabled &&
      node.health_status === 'healthy',
  )
  const computeOffline = backendHealth.isError || (clusterHealth?.connected !== true && !gpuAvailable)
  const activeRun = projectWorkflowRuns.find((r) => r.id === workflowRunId)
  const runName = (run: WorkflowContextBarProps['projectWorkflowRuns'][number]) => workflowRouteName(run, language)
  const groups = groupWorkflowRoutes(projectWorkflowRuns)
  const presentation = routePresentation(activeRun)
  const detailFields = [['method', '设计方法', 'Method'], ['objective', '目标', 'Objective'], ['evidence', '证据状态', 'Evidence'], ['next_step', '下一步', 'Next step']] as const

  if (!activeProject) return null

  return (
    <Frame variant="inverse" spacing="xs" className="mb-3">
      <FramePanel fit className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          <span className="text-xs text-text-muted">{t.workflowExt.contextBar.project}</span>
          <p className="truncate font-medium text-text-primary" title={projectText(activeProject, 'name', language)}>
            {projectText(activeProject, 'name', language)}
          </p>
        </div>
        {activeRun || workflowStatus ? (
          <div className="min-w-0">
            <span className="text-xs text-text-muted">{t.workflowExt.contextBar.route}</span>
            <p className="truncate text-text-primary">
              {activeRun
                ? `${runName(activeRun)} · ${activeRun.status}`
                : workflowStatus ?? '—'}
            </p>
          </div>
        ) : null}
        {projectWorkflowRuns.length > 1 ? (
          <Select value={workflowRunId ?? null} items={projectWorkflowRuns.map((run) => ({ value: run.id, label: runName(run) }))} onValueChange={(value) => { if (value) onSelectRun(value) }}>
            <SelectTrigger className="w-full sm:w-80" aria-label={language === 'zh' ? '选择工作流' : 'Select workflow'}><SelectValue /></SelectTrigger>
            <SelectContent>{groups.map((group) => <SelectGroup key={group.category}>
              <SelectLabel>{group.labels[language === 'zh' ? 0 : 1]}</SelectLabel>
              {group.runs.map((run) => <SelectItem key={run.id} value={run.id}>
                {runName(run)}{typeof routePresentation(run).variant === 'string' && routePresentation(run).variant ? ` · ${routePresentation(run).variant}` : ''}
              </SelectItem>)}
            </SelectGroup>)}</SelectContent>
          </Select>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="ghost" className="h-auto flex-wrap gap-1.5 p-1" onClick={() => setSettingsOpen(true)}>
          <StatusPill
            label={computeOffline ? t.workflowExt.contextBar.computeOffline : t.workflowExt.contextBar.computeOnline}
            tone={computeOffline ? 'amber' : 'green'}
          />
          {clusterHealth?.mode === 'remote_lsf' ? (
            <StatusPill
              label={
                clusterHealth.connected
                  ? t.workflowExt.contextBar.lsfConnected
                  : t.workflowExt.contextBar.lsfUnreachable
              }
              tone={clusterHealth.connected ? 'green' : 'amber'}
            />
          ) : null}
          <StatusPill
            label={gpuAvailable ? t.workflowExt.contextBar.gpuAvailable : t.workflowExt.contextBar.gpuUnavailable}
            tone={gpuAvailable ? 'green' : 'neutral'}
          />
        </Button>
        <Button
          variant="link"
          size="sm"
          render={<Link to={`/projects?project=${encodeURIComponent(activeProject.id)}`} />}
        >
          {t.workflowExt.contextBar.manage}
        </Button>
      </div>
      </FramePanel>
      {typeof presentation.summary === 'string' ? <FramePanel className="space-y-2 border-t border-border-soft text-sm" data-testid="route-explanation">
        <p className="text-text-secondary">{presentation.summary}</p>
        <dl className="grid gap-2 sm:grid-cols-2">{detailFields.map(([key, zh, en]) => typeof presentation[key] === 'string' ? <div key={key}>
          <dt className="text-xs text-text-muted">{language === 'zh' ? zh : en}</dt><dd className="break-words text-text-secondary">{String(presentation[key])}</dd>
        </div> : null)}</dl>
        {Array.isArray(presentation.aliases) && presentation.aliases.length > 0 ? <Accordion className="text-xs text-text-muted"><AccordionItem value="aliases">
          <AccordionTrigger>{language === 'zh' ? '旧名称与追溯' : 'Previous names'}</AccordionTrigger>
          <AccordionContent><p className="mt-1 break-words">{presentation.aliases.filter((value): value is string => typeof value === 'string').join(' / ')}</p></AccordionContent>
        </AccordionItem></Accordion> : null}
      </FramePanel> : null}
    </Frame>
  )
}
