import { Play, Plus } from '@phosphor-icons/react'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'

interface WorkflowToolbarProps {
  isDemoMode: boolean
  readOnly: boolean
  workflowRunId?: string
  createPending: boolean
  startPending: boolean
  submitDisabled?: boolean
  creationDisabled?: boolean
  onCreateRun: () => void
  onNewRoute: () => void
  onAddNode: () => void
  onStart: () => void
}

export function WorkflowToolbar({
  isDemoMode,
  readOnly,
  workflowRunId,
  createPending,
  startPending,
  submitDisabled = false,
  creationDisabled = false,
  onCreateRun,
  onNewRoute,
  onAddNode,
  onStart,
}: WorkflowToolbarProps) {
  const { t, language } = useI18n()

  if (isDemoMode) {
    return <p className="mb-3 text-xs text-text-secondary">{t.workflowExt.toolbar.demoMode}</p>
  }

  if (!workflowRunId) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button type="button" disabled={createPending || creationDisabled} onClick={onCreateRun}>
          <Plus className="h-4 w-4" />
          {language === 'zh' ? '手工创建空白工作流' : 'Create a blank workflow manually'}
        </Button>
      </div>
    )
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <Button type="button"
        variant="ghost"
        size="sm"
        disabled={createPending || creationDisabled}
        onClick={onNewRoute}
        title={t.workflowExt.toolbar.newRouteTitle}
      >
        <Plus className="h-4 w-4" />
        {t.workflowExt.toolbar.newRoute}
      </Button>
      <Button type="button" variant="outline" size="sm" disabled={readOnly} onClick={onAddNode}>
        <Plus className="h-4 w-4" />
        {t.workflow.addNode}
      </Button>
      <Button type="button"
        variant="default"
        size="sm"
        disabled={startPending || submitDisabled}
        onClick={onStart}
      >
        <Play className="h-4 w-4" />
        {t.workflow.startWorkflow}
      </Button>
    </div>
  )
}
