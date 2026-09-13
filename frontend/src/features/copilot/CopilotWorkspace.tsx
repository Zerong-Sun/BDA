import { useEffect, useId, useRef, useState } from 'react'
import { requireCopilotWrite, useCopilotReadOnly } from './commandAccess'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Textarea } from '../../components/ui/textarea'
import { Checkbox } from '../../components/ui/checkbox'
import { Input } from '../../components/ui/Input'
import { Disclosure } from '../../components/ui/Disclosure'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useAppStore, type CopilotTaskDraft } from '../../lib/store/appStore'
import { assessTaskReadiness, getTaskReadiness, isLive, listAgentRuns, listTaskServices, startAgentRun } from '../../lib/api/agentRuns'
import { AgentRunDetail } from './CopilotAgentRuns'
import { CopilotChat } from './CopilotChat'
import { deliveryLabel, isQuestion, suggestService, type ServiceKind } from './taskPresentation'

interface WorkspaceProps {
  pageContext?: string
  initialGoal?: string
  initialService?: ServiceKind
  ignoreDraft?: boolean
  rememberDraft?: boolean
  openRunId?: string | null
  onRunChange?: (id: string | null) => void
}

export function CopilotWorkspace({ initialGoal = '', ignoreDraft = false, rememberDraft = false, ...props }: WorkspaceProps) {
  const { projectId } = useProjectContext()
  return <ProjectTaskWorkspace key={projectId} projectId={projectId} initialGoal={initialGoal} ignoreDraft={ignoreDraft} rememberDraft={rememberDraft} {...props} />
}

function ProjectTaskWorkspace({ projectId, pageContext, initialGoal, initialService, ignoreDraft, rememberDraft, openRunId, onRunChange }: WorkspaceProps & { projectId: string; initialGoal: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const fieldId = useId()
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const queryClient = useQueryClient()
  const draft = useAppStore((s) => ignoreDraft ? '' : s.copilotDraft)
  const readOnly = useCopilotReadOnly()
  const [localDraft, setLocalDraft] = useState<CopilotTaskDraft>({ goal: initialGoal, selected: initialService ?? null, preview: Boolean(initialService), writes: [], maxTurns: 24, maxCost: '' })
  const savedDraft = useAppStore((s) => s.copilotTaskDrafts[projectId])
  const { goal, selected, preview, writes, maxTurns, maxCost } = rememberDraft ? savedDraft ?? localDraft : localDraft
  const updateDraft = (patch: Partial<CopilotTaskDraft>) => {
    if (rememberDraft) {
      const state = useAppStore.getState()
      state.setCopilotTaskDraft(projectId, { ...(state.copilotTaskDrafts[projectId] ?? localDraft), ...patch })
    } else setLocalDraft((current) => ({ ...current, ...patch }))
  }
  const [localRunId, setLocalRunId] = useState<string | null>(null)
  const runId = onRunChange ? openRunId : localRunId
  const setRunId = onRunChange ?? setLocalRunId
  const [question, setQuestion] = useState<string | null>(null)
  const [chat, setChat] = useState(Boolean(draft))
  const services = useQuery({ queryKey: ['copilot-task-services'], queryFn: listTaskServices, enabled: Boolean(projectId) })
  const readiness = useQuery({ queryKey: ['copilot-task-readiness', projectId], queryFn: () => getTaskReadiness(projectId), enabled: Boolean(projectId) })
  const runs = useQuery({ queryKey: ['agent-runs', projectId], queryFn: () => listAgentRuns(projectId), enabled: Boolean(projectId), refetchInterval: (q) => q.state.data?.some(isLive) ? 4000 : false })
  const kind = selected ?? suggestService(goal)
  const service = services.data?.find((s) => s.id === kind)
  const qualified = readiness.data?.eligible_services?.includes(kind) ?? false
  const validTurns = Number.isInteger(maxTurns) && maxTurns >= 1 && maxTurns <= 200
  const validCost = maxCost.trim() === '' || (Number.isInteger(Number(maxCost)) && Number(maxCost) >= 0 && Number(maxCost) <= 1000000)
  const assess = useMutation({ mutationFn: () => { requireCopilotWrite(); return assessTaskReadiness(projectId) }, onSuccess: (data) => {
    queryClient.setQueryData(['copilot-task-readiness', projectId], data)
    void queryClient.invalidateQueries({ queryKey: ['copilot-config', projectId] })
  } })
  const start = useMutation({ mutationFn: () => { requireCopilotWrite(); return startAgentRun({ project_id: projectId, goal: goal.trim(), service_kind: kind,
    authorized_writes: writes, max_turns: maxTurns, max_cost_usd_cents: maxCost.trim() === '' ? null : Number(maxCost) }) },
    onSuccess: ({ run }) => {
      // A durable task may start after the user has moved to another project
      // or surface. Refresh its list without navigating them back there.
      if (mounted.current) setRunId(run.id)
      void queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] })
    },
  })
  const error = start.error ?? assess.error ?? services.error ?? readiness.error ?? runs.error
  const requestTask = (text: string) => { updateDraft({ goal: text, selected: suggestService(text), writes: [], preview: true }); setChat(false); setQuestion(null) }
  if (!projectId) return <div className="space-y-3 p-4"><p>{zh ? '先创建或选择项目，助手就能围绕你的目标开展工作。' : 'Create or choose a project to work toward a research goal.'}</p>
    <Button type="button" render={<Link to="/projects" />}>{zh ? '创建或选择项目' : 'Choose a project'}</Button>
    <Button type="button" variant="outline" render={<Link to="/tools" />}>{zh ? '直接使用实验工具' : 'Open experiment tools'}</Button></div>
  if (runId) return <AgentRunDetail key={runId} runId={runId} projectId={projectId} onBack={() => setRunId(null)} />
  if (chat || draft) return <div className="flex min-h-0 flex-1 flex-col"><Button type="button" variant="ghost" onClick={() => { useAppStore.getState().setCopilotDraft(''); setChat(false); setQuestion(null) }}>{zh ? '返回当前任务' : 'Back to tasks'}</Button><CopilotChat pageContext={pageContext} initialQuestion={question ?? undefined} onTaskRequested={requestTask} /></div>
  return <div className="space-y-4 overflow-y-auto p-4">
    {readOnly ? <p role="status" className="text-sm text-text-secondary">{zh ? '只读模式：可以查看任务与交付物。' : 'Read-only mode: you can inspect tasks and deliverables.'}</p> : null}
    <div><h3 className="font-semibold">{zh ? '你希望完成什么？' : 'What would you like to accomplish?'}</h3>
      <p className="mt-1 text-sm text-text-secondary">{zh ? '说明目标，助手会准备步骤、跟进结果，并在需要你判断时停下来。' : 'Describe your goal. The assistant prepares steps, tracks results and pauses for your input.'}</p></div>
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!selected && isQuestion(goal)) { setQuestion(goal); setChat(true) } else { updateDraft({ preview: true }) } }}>
      <Textarea aria-label={zh ? '希望完成的工作' : 'Task goal'} value={goal} onChange={(e) => { updateDraft({ goal: e.target.value, preview: false, writes: [] }) }} placeholder={zh ? '例如：调研这个靶点的证据，比较方法并准备下一步方案' : 'For example: research this target and compare the available methods'} />
      <div className="grid grid-cols-1 gap-1 sm:grid-cols-2" aria-label={zh ? '服务类型' : 'Service type'}>
        {services.data?.map((s) => <Button type="button" variant={selected === s.id ? 'secondary' : 'outline'} key={s.id} className="h-auto justify-start whitespace-normal text-left" aria-pressed={selected === s.id} onClick={() => { updateDraft({ selected: s.id as ServiceKind, writes: [], preview: true }) }}>{zh ? s.title_zh : s.title}</Button>)}
      </div>
      {!preview ? <Button type="submit" disabled={!goal.trim()}>{zh ? '继续' : 'Continue'}</Button> : null}
    </form>
    {preview && service ? <section aria-label={zh ? '任务计划' : 'Task plan'} className="space-y-3 rounded-lg border border-border p-3">
      <h4 className="font-semibold">{zh ? service.title_zh : service.title}</h4>
      <p className="text-sm">{zh ? service.deliverable_zh : service.deliverable}</p>
      <ol className="list-decimal space-y-1 pl-5 text-sm">{service.steps.map((s, i) => <li key={i}>{String(zh ? s.title_zh : s.title)}</li>)}</ol>
      {service.write_tools.map((tool) => <label key={tool} className="flex items-start gap-2 text-sm"><Checkbox checked={writes.includes(tool)} onCheckedChange={(checked) => updateDraft({ writes: checked ? [...writes, tool] : writes.filter((v) => v !== tool) })} />
        {tool === 'start_literature_search' ? (zh ? '允许发起外部文献检索并摄取结果' : 'Allow external literature search and ingestion') : (zh ? '允许保存待审核研究笔记' : 'Allow saving research notes for review')}</label>)}
      <p className="text-xs text-text-secondary">{writes.length ? (zh ? '将在本项目内执行以上勾选操作。' : 'Checked actions will run in this project.') : (zh ? '当前只读取已有资料并生成答复。' : 'Reads existing data and prepares an answer.')} {zh ? '工作流运行仍需检查并确认提交。' : 'Workflow execution still requires review and confirmation.'}</p>
      <Disclosure title={zh ? '高级参数与直接编辑' : 'Advanced options and direct editing'}>
        <div className="flex flex-wrap gap-2 py-2"><label>{zh ? '轮数上限' : 'Turn limit'}<Input type="number" min={1} max={200} step={1} aria-invalid={!validTurns} aria-describedby={!validTurns ? `${fieldId}-turns-error` : undefined} value={maxTurns} onChange={(e) => updateDraft({ maxTurns: Number(e.target.value) })} /></label>
          <label>{zh ? '模型费用估算额度（美分，可选）' : 'Estimated model budget (cents, optional)'}<Input type="number" min={0} max={1000000} step={1} aria-invalid={!validCost} aria-describedby={!validCost ? `${fieldId}-cost-error` : undefined} value={maxCost} onChange={(e) => updateDraft({ maxCost: e.target.value })} /></label></div>
        <p className="mb-2 text-xs text-text-secondary">{zh ? '设置费用额度需要管理员配置模型单价；平台按保守估算控制调用，实际账单以模型服务商为准。' : 'Cost budgets require administrator-configured rates. Calls use conservative estimates; actual billing belongs to the provider.'}</p>
        <div className="flex flex-wrap gap-2 text-sm"><Link to={`/workflow?project=${projectId}`}>{zh ? '编辑工作流' : 'Edit workflow'}</Link><Link to={`/lab?project=${projectId}`}>{zh ? '实验工作台' : 'Lab'}</Link><Link to={`/autopilot?project=${projectId}`}>{zh ? '按批准方案运行（高级）' : 'Run an approved plan (advanced)'}</Link></div>
        <p className="mt-2 text-xs text-text-secondary">{zh ? '高级运行保留独立的方案确认和计算预算；完整无人值守闭环尚未开放。' : 'Advanced execution has its own plan confirmation and compute budget. Unattended end-to-end execution is not available.'}</p>
      </Disclosure>
      {!qualified ? <div role="status" className="space-y-2 text-sm"><p>{zh ? '此模型尚未通过本服务的任务检查。检查会调用模型，验证结构、引用和工具协议，不执行实验操作。' : 'This model needs task checks. These call the model to check structure, citations and tool protocol, without experiment actions.'}</p>
        <Button type="button" variant="outline" disabled={!readiness.data?.model || assess.isPending || readOnly} onClick={() => assess.mutate()}>{assess.isPending ? (zh ? '检查中…' : 'Checking…') : (zh ? '检查模型任务能力' : 'Check model task capabilities')}</Button>
        {readiness.data?.checked_at ? <p>{Object.entries(readiness.data.checks ?? {}).map(([name, passed]) => `${name}: ${passed ? '✓' : '×'}`).join(' · ')}</p> : null}</div> : null}
      {!validTurns ? <p id={`${fieldId}-turns-error`} role="alert" className="text-sm text-destructive">{zh ? '轮数必须为 1–200 的整数。' : 'Turn limit must be a whole number from 1 to 200.'}</p> : null}
      {!validCost ? <p id={`${fieldId}-cost-error`} role="alert" className="text-sm text-destructive">{zh ? '费用额度须为 0–1,000,000 美分的整数，或留空。' : 'Budget must be a whole number from 0 to 1,000,000 cents, or left empty.'}</p> : null}
      <Button type="button" disabled={!qualified || !goal.trim() || start.isPending || readOnly || !validTurns || !validCost} onClick={() => start.mutate()}>{start.isPending ? (zh ? '启动中…' : 'Starting…') : (zh ? '按以上计划开始' : 'Start this plan')}</Button>
    </section> : null}
    {preview && !service && !services.isError ? <p role="status" className="text-sm text-text-secondary">{services.isLoading ? (zh ? '加载可用服务…' : 'Loading available services…') : (zh ? '此服务暂不可用，请选择其他服务或开始对话。' : 'This service is unavailable. Choose another service or start a conversation.')}</p> : null}
    {services.isError || readiness.isError || runs.isError ? <Button type="button" variant="outline" onClick={() => { if (services.isError) void services.refetch(); if (readiness.isError) void readiness.refetch(); if (runs.isError) void runs.refetch() }}>{zh ? '重新加载任务工作区' : 'Reload task workspace'}</Button> : null}
    {error ? <p role="alert" className="text-sm text-destructive">{error instanceof Error ? error.message : String(error)}</p> : null}
    <Button type="button" variant="ghost" onClick={() => setChat(true)}>{zh ? '询问或解释一个问题' : 'Ask or explain a question'}</Button>
    <section className="space-y-2"><h4 className="font-semibold">{zh ? '我的任务与交付物' : 'Tasks and deliverables'}</h4>
      {runs.isLoading ? <p role="status">{zh ? '加载任务…' : 'Loading tasks…'}</p> : null}
      {runs.data?.filter((r) => !r.parent_run_id).map((run) => <Button key={run.id} type="button" variant="outline" className="h-auto w-full flex-col items-start whitespace-normal text-left" onClick={() => setRunId(run.id)}><span className="text-xs">{deliveryLabel(run, zh)}</span><span>{run.goal}</span></Button>)}
      {runs.data?.length === 0 ? <p className="text-sm text-text-secondary">{zh ? '启动后，进度和产物会保存在这里。' : 'Task progress and deliverables will stay here.'}</p> : null}
    </section>
  </div>
}
