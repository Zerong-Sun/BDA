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
  const detailFields = [['method', '设计方法', 'Method'], ['objective', '目标', 'Objective']] as const

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
      {activeRun ? <div className="project-summary-grid" data-testid="route-explanation">
        <section className="project-summary-card">
          <h2>{language === 'zh' ? '路线与现状' : 'Route and status'}</h2>
          <p className="text-sm text-text-secondary">{typeof presentation.summary === 'string' && presentation.summary.trim() ? presentation.summary : (language === 'zh' ? '尚未保存路线总结。节点与产物见下方工作流。' : 'No route summary saved. Inspect nodes and outputs in the workflow below.')}</p>
          <Accordion><AccordionItem value="method"><AccordionTrigger>{language === 'zh' ? '方法与目标' : 'Method and objective'}</AccordionTrigger><AccordionContent>
            <dl className="space-y-2">{detailFields.map(([key, zh, en]) => typeof presentation[key] === 'string' ? <div key={key}><dt className="text-xs text-text-muted">{language === 'zh' ? zh : en}</dt><dd className="text-sm break-words">{String(presentation[key])}</dd></div> : null)}</dl>
          </AccordionContent></AccordionItem></Accordion>
          {Array.isArray(presentation.aliases) && presentation.aliases.length > 0 ? <Accordion><AccordionItem value="aliases"><AccordionTrigger>{language === 'zh' ? '旧名称与追溯' : 'Previous names'}</AccordionTrigger><AccordionContent>{presentation.aliases.filter((v): v is string => typeof v === 'string').join(' / ')}</AccordionContent></AccordionItem></Accordion> : null}
        </section>
        <section className="project-summary-card">
          <h2>{language === 'zh' ? '证据与复核' : 'Evidence and review'}</h2>
          <p className="text-sm text-text-secondary">{typeof presentation.evidence === 'string' && presentation.evidence.trim() ? presentation.evidence : (language === 'zh' ? '尚未记录证据摘要。' : 'No evidence summary recorded.')}</p>
          <nav className="project-card-actions"><Link to={`/research?project=${encodeURIComponent(activeProject.id)}&tab=evidence`}>{language === 'zh' ? '查看证据' : 'View evidence'} →</Link><Link to={`/inbox?project=${encodeURIComponent(activeProject.id)}`}>{language === 'zh' ? '待办复核' : 'Review queue'} →</Link></nav>
        </section>
        <section className="project-summary-card project-summary-card--next">
          <h2>{language === 'zh' ? '下一步' : 'Next step'}</h2>
          <p className="text-sm text-text-secondary">{typeof presentation.next_step === 'string' && presentation.next_step.trim() ? presentation.next_step : (language === 'zh' ? '尚未记录下一步；先检查节点结果和门控。' : 'No next step recorded; inspect node results and gates first.')}</p>
          <nav className="project-card-actions"><Link to={`/research?project=${encodeURIComponent(activeProject.id)}`}>{language === 'zh' ? '项目结果与报告' : 'Project results and reports'} →</Link></nav>
        </section>
      </div> : null}
    </Frame>
  )
}
