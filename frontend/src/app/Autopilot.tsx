import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { Alert, AlertDescription, AlertTitle } from '@/components/reui/alert'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/label'
import { PageHead } from '@/components/ui/PageHead'
import { Textarea } from '@/components/ui/textarea'
import {
  cancelAutopilotCampaign,
  completeAutopilotStage,
  confirmAutopilotDraft,
  createAutopilotDraft,
  getAutopilotCampaign,
  startAutopilotCampaign,
  releaseAutopilotStage,
  takeOverAutopilotCampaign,
} from '../lib/api/autopilot'
import type { AutopilotCampaignResponse, AutopilotDraftResponse } from '../lib/api/generated/types.gen'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useProjectAccess } from '../lib/hooks/useProjectAccess'
import { useAppStore } from '../lib/store/appStore'
import { useI18n } from '../lib/i18n'

export function AutopilotPage() {
  const { projectId, projectsLoading } = useProjectContext()
  const { language } = useI18n()
  if (!projectId) return <p role="status">{projectsLoading ? language === 'zh' ? '正在加载项目…' : 'Loading project…' : language === 'zh' ? '请先选择项目。' : 'Select a project first.'}</p>
  return <AutopilotWorkspace key={projectId} projectId={projectId} />
}

function AutopilotWorkspace({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const access = useProjectAccess(projectId)
  const isDemoMode = useAppStore((state) => state.appMode === 'demo')
  const canOperate = !isDemoMode && access.isSuccess && access.data?.permissions.autopilot === true
  const accessMessage = language === 'zh' ? '当前工作区无分阶段任务操作权限。' : 'You cannot operate staged tasks in this workspace.'
  const requireAccess = () => { if (!canOperate) throw new Error(accessMessage) }
  const active = useRef(true)
  useEffect(() => {
    active.current = true
    return () => { active.current = false }
  }, [])
  const [prompt, setPrompt] = useState('')
  const [name, setName] = useState('')
  const [gpuHours, setGpuHours] = useState('')
  const [draft, setDraft] = useState<AutopilotDraftResponse | null>(null)
  const [draftEtag, setDraftEtag] = useState('')
  const [draftPrompt, setDraftPrompt] = useState('')
  const [confirmedGpuSeconds, setConfirmedGpuSeconds] = useState<number | null>(null)
  const [startAccepted, setStartAccepted] = useState(false)
  const [cancelAccepted, setCancelAccepted] = useState(false)
  const [campaign, setCampaign] = useState<AutopilotCampaignResponse | null>(null)
  const [operationId, setOperationId] = useState<string | null>(null)

  const budgetSeconds = Math.round(Number(gpuHours) * 3600)
  const budgetValid = gpuHours.trim() !== '' && Number.isFinite(Number(gpuHours)) && Number(gpuHours) > 0
    && Number.isSafeInteger(budgetSeconds) && budgetSeconds > 0 && budgetSeconds <= 2_147_483_647
  const draftCurrent = draft !== null && draftPrompt === prompt

  const draftMutation = useMutation({
    mutationFn: (requestedPrompt: string) => { requireAccess(); return createAutopilotDraft(projectId, requestedPrompt) },
    onSuccess: ({ draft: nextDraft, etag }, requestedPrompt) => {
      if (!active.current) return
      setDraftPrompt(requestedPrompt)
      setDraft(nextDraft)
      setDraftEtag(etag)
      setCampaign(null)
      setOperationId(null)
      setConfirmedGpuSeconds(null)
      setStartAccepted(false)
      setCancelAccepted(false)
    },
  })
  const confirmMutation = useMutation({
    mutationFn: async () => {
      requireAccess()
      if (!draftCurrent || !draft || !name.trim() || !budgetValid || campaign) throw new Error(language === 'zh' ? '请重新检查预览、名称和预算。' : 'Review the current preview, name and budget before confirming.')
      const next = await confirmAutopilotDraft(draft.id, draftEtag, name.trim(), budgetSeconds)
      return { campaign: next, gpuSeconds: budgetSeconds }
    },
    onSuccess: (confirmed) => {
      if (!active.current) return
      setCampaign(confirmed.campaign)
      setConfirmedGpuSeconds(confirmed.gpuSeconds)
    },
  })
  const startMutation = useMutation({
    mutationFn: () => {
      requireAccess()
      if (!campaign || campaign.status !== 'confirmed' || confirmedGpuSeconds === null || startAccepted) throw new Error(language === 'zh' ? '该任务不能再次启动。' : 'This campaign cannot be started again.')
      return startAutopilotCampaign(campaign.id, confirmedGpuSeconds)
    },
    onSuccess: (accepted) => {
      if (!active.current) return
      setOperationId(accepted.operation_id)
      setStartAccepted(true)
      refreshMutation.mutate()
    },
  })
  const cancelMutation = useMutation({
    mutationFn: () => { requireAccess(); return cancelAutopilotCampaign(campaign!.id) },
    onSuccess: (accepted) => {
      if (!active.current) return
      setOperationId(accepted.operation_id)
      setCancelAccepted(true)
      refreshMutation.mutate()
    },
  })
  // Re-read after starting: the stages only acquire their trunk resources once the worker
  // has run the adapter, and the deep links below are the point of showing them at all.
  const refreshMutation = useMutation({
    mutationFn: () => getAutopilotCampaign(campaign!.id),
    onSuccess: (next) => { if (active.current) setCampaign(next) },
  })
  const takeoverMutation = useMutation({
    mutationFn: () => { requireAccess(); return takeOverAutopilotCampaign(campaign!.id, campaign!.version) },
    onSuccess: (next) => { if (active.current) setCampaign(next) },
  })
  // Releasing changes one stage, so the campaign is re-read rather than patched locally:
  // the server decides whether the hold is now clear, and a client that decided for itself
  // would be the second authority the gate exists to prevent.
  const releaseMutation = useMutation({
    mutationFn: (stage: { id: string; version: number }) => {
      requireAccess(); return releaseAutopilotStage(campaign!.id, stage.id, stage.version)
    },
    onSuccess: () => { if (active.current) refreshMutation.mutate() },
  })
  // Completing is a different question from releasing and gets its own control:
  // a release says *may this act*, which only a held stage has open, and this
  // says *is this done*, which only a stage doing human work has. Re-reads the
  // campaign for the same reason - the server decides what happens next, and a
  // client that advanced the chain locally would be a second authority.
  const completeMutation = useMutation({
    mutationFn: (stage: { id: string; version: number }) => {
      requireAccess(); return completeAutopilotStage(campaign!.id, stage.id, stage.version)
    },
    onSuccess: () => { if (active.current) refreshMutation.mutate() },
  })
  // A campaign that has reached an outcome has nothing left to start, cancel or
  // take over, and the server refuses all three. Offering them anyway would put
  // a control in front of somebody whose only possible result is a 409 - and
  // before the chain could reach its own end, two of these had no reason to be
  // disabled at all, which is why they were not.
  const settled =
    campaign !== null &&
    ['succeeded', 'failed', 'cancelled', 'manual_takeover'].includes(campaign.status)
  const actionPending = startMutation.isPending || cancelMutation.isPending || takeoverMutation.isPending || releaseMutation.isPending || completeMutation.isPending
  // Keep reads and state changes in order so an older refresh cannot undo a takeover in the UI.
  const actionDisabled = !canOperate || actionPending || refreshMutation.isPending
  const formLocked = !canOperate || Boolean(campaign) || confirmMutation.isPending

  /**
   * The same control in two branches; the difference between them is upstream.
   *
   * A function returning JSX, not a component declared in this body. A component
   * defined during render is a new type on every render, so React unmounts and
   * remounts it each time - the button loses focus mid-interaction, which is a
   * real regression and one the lint gate does not catch.
   */
  const completeStageButton = (stage: { id: string; version: number; status: string }) =>
    stage.status === 'ready' ? (
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={actionDisabled || settled || cancelAccepted}
        onClick={() => completeMutation.mutate(stage)}
      >
        {language === 'zh' ? '标记这一阶段完成' : 'Mark this stage done'}
      </Button>
    ) : null

  const error =
    draftMutation.error ??
    confirmMutation.error ??
    startMutation.error ??
    cancelMutation.error ??
    refreshMutation.error ??
    takeoverMutation.error ??
    releaseMutation.error ??
    completeMutation.error

  return (
    <section className="mx-auto max-w-5xl" data-tour-id="autopilot-page">
      <PageHead eyebrow="Autopilot" title={language === 'zh' ? '分阶段研究任务' : 'Staged research tasks'} />
      {access.isError ? <Alert variant="destructive" className="mb-3"><AlertDescription>{language === 'zh' ? '项目权限读取失败，操作暂不可用。' : 'Project permissions could not be loaded. Actions are unavailable.'}</AlertDescription><Button type="button" variant="outline" onClick={() => void access.refetch()}>{language === 'zh' ? '重试权限检查' : 'Retry permission check'}</Button></Alert>
        : (isDemoMode || access.isSuccess) && !canOperate ? <p role="status" className="mb-3 text-sm">{accessMessage}</p> : null}
      <Alert className="mb-5" variant="warning">
        <AlertTitle>{language === 'zh' ? '先预览，再确认，再启动' : 'Preview, confirm, then start'}</AlertTitle>
        <AlertDescription>
          {language === 'zh'
            ? '先检查执行步骤和预算上限，再确认启动。需要人工决定的阶段会暂停等待审核。'
            : 'Review the steps and budget limit before starting. Stages that need a decision pause for your review.'}
        </AlertDescription>
      </Alert>
      <div className="grid gap-5 lg:grid-cols-2">
        <AppFrame heading={language === 'zh' ? '1. 自然语言需求' : '1. Natural-language request'} panelClassName="space-y-4 p-5">
          <Textarea
            className="min-h-52 w-full border border-border bg-background p-3 text-sm"
            value={prompt}
            aria-label={language === 'zh' ? '研究需求' : 'Research request'}
            disabled={formLocked}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={language === 'zh' ? '描述目标、约束、成功标准和所需阶段…' : 'Describe objectives, constraints, success criteria, and stages…'}
          />
          <Button type="button" disabled={!projectId || prompt.trim().length < 10 || draftMutation.isPending || formLocked} onClick={() => draftMutation.mutate(prompt)}>
            {language === 'zh' ? '生成结构化预览' : 'Generate structured preview'}
          </Button>
        </AppFrame>
        <AppFrame heading={language === 'zh' ? '2. 检查任务计划' : '2. Review the plan'} panelClassName="space-y-4 p-5">
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap border border-border bg-muted p-3 text-xs">
            {draftCurrent ? JSON.stringify(draft.normalized_spec, null, 2) : (language === 'zh' ? '请先生成当前需求的计划。' : 'Generate a plan for the current request.')}
          </pre>
          {draft && !draftCurrent ? <p role="status" className="text-sm">{language === 'zh' ? '需求已改变，请重新生成预览后确认。' : 'The request changed. Generate a new preview before confirming.'}</p> : null}
          <div className="grid gap-2">
            <Label htmlFor="autopilot-name">{language === 'zh' ? '任务名称' : 'Campaign name'}</Label>
            <Input id="autopilot-name" disabled={formLocked} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="autopilot-budget">{language === 'zh' ? 'GPU 小时硬上限' : 'GPU-hour hard limit'}</Label>
            <Input id="autopilot-budget" disabled={formLocked} type="number" min="0.01" step="0.25" value={gpuHours} onChange={(event) => setGpuHours(event.target.value)} />
          </div>
          <Button
            type="button"
            disabled={!draftCurrent || !name.trim() || !budgetValid || formLocked || draftMutation.isPending}
            onClick={() => confirmMutation.mutate()}
          >
            {language === 'zh' ? '确认计划和预算' : 'Confirm plan and budget'}
          </Button>
          {gpuHours && !budgetValid ? <p role="alert" className="text-sm">{language === 'zh' ? '请输入有效的正数 GPU 小时预算。' : 'Enter a supported positive GPU-hour budget.'}</p> : null}
          {campaign ? <p className="text-sm text-muted-foreground">{language === 'zh' ? '计划和预算已确认，启动将使用这份已审核版本。' : 'The plan and budget are confirmed. Starting uses this reviewed version.'}</p> : null}
        </AppFrame>
      </div>
      {campaign ? (
        <AppFrame className="mt-5" heading={language === 'zh' ? '3. 启动与取消' : '3. Start and cancel'} panelClassName="flex flex-wrap items-center gap-3 p-5">
          <span className="text-sm">{campaign.name} · {campaign.status}</span>
          <Button type="button" onClick={() => startMutation.mutate()} disabled={actionDisabled || campaign.status !== 'confirmed' || startAccepted || cancelAccepted}>{language === 'zh' ? '启动已确认计划' : 'Start confirmed plan'}</Button>
          <Button type="button" variant="outline" onClick={() => cancelMutation.mutate()} disabled={actionDisabled || settled || cancelAccepted}>{language === 'zh' ? '取消任务' : 'Cancel campaign'}</Button>
          <Button type="button" variant="outline" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending || actionPending}>{language === 'zh' ? '刷新阶段' : 'Refresh stages'}</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => takeoverMutation.mutate()}
            disabled={actionDisabled || settled || cancelAccepted}
          >
            {language === 'zh' ? '人工接管' : 'Take over'}
          </Button>
          {operationId ? <span className="text-xs text-muted-foreground">{language === 'zh' ? '请求已接收' : 'Request accepted'}: {operationId}</span> : null}
        </AppFrame>
      ) : null}
      {campaign?.status === 'manual_takeover' ? (
        <Alert className="mt-5" variant="info">
          <AlertTitle>{language === 'zh' ? '已由人工接管' : 'Under manual control'}</AlertTitle>
          <AlertDescription>
            {language === 'zh'
              ? '自动推进已停止。请打开已有产物，继续手工处理。'
              : 'Automatic progress has stopped. Open the existing outputs to continue manually.'}
          </AlertDescription>
        </Alert>
      ) : null}
      {campaign?.stages?.length ? (
        <AppFrame className="mt-5" heading={language === 'zh' ? '4. 阶段与产物' : '4. Stages and their products'} panelClassName="p-5">
          <p className="mb-3 text-xs text-muted-foreground">
            {language === 'zh'
              ? '打开阶段产物进行检查。计算草稿仍需在工作流中预览并确认提交。'
              : 'Open each output to review it. Workflow drafts still require preview and submission confirmation.'}
          </p>
          <ol className="space-y-2">
            {campaign.stages.map((stage) => (
              <li
                key={stage.id}
                className={`flex flex-wrap items-baseline gap-2 border-l-2 pl-3 text-sm ${
                  stage.held ? 'border-l-warning' : 'border-l-border'
                }`}
              >
                <span className="font-medium">{stage.stage_key}</span>
                <span className="text-xs text-muted-foreground">{stage.status}</span>
                {/* Who is accountable for this step, and — where nobody is — why not.
                    A stage attributed to no one with no explanation reads as an
                    oversight rather than as the decision it is, which is the same
                    reason `hold_reason` travels with a hold.

                    The absent case shows its reason as text rather than a `title`.
                    A tooltip is hover-only, invisible on a touch screen, and not
                    announced on a bare span — the exact objection that moved the
                    operator summary out of a `title` in the Copilot picker, made
                    again one file over. `hold_reason` sits inline in this same row,
                    so two explanations on one line were being treated differently
                    for no reason. */}
                {stage.operator ? (
                  <span className="text-xs text-muted-foreground">· {stage.operator}</span>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {stage.operator_reason ??
                      (language === 'zh' ? '· 无负责 bot' : '· no operator')}
                  </span>
                )}
                {stage.held ? (
                  <>
                    {/* The reason travels with the hold: a stop nobody can explain reads
                        as a failure rather than as a decision. */}
                    <span className="text-xs text-warning">{stage.hold_reason}</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={actionDisabled || settled || cancelAccepted}
                      onClick={() => releaseMutation.mutate(stage)}
                    >
                      {language === 'zh' ? '放行这一阶段' : 'Release this stage'}
                    </Button>
                  </>
                ) : stage.resource_type === 'workflow_run' && stage.resource_id ? (
                  <>
                    <Link className="text-xs underline" to={`/workflow?project=${encodeURIComponent(projectId)}&run=${encodeURIComponent(stage.resource_id)}`}>
                      {language === 'zh' ? '打开工作流' : 'Open workflow'}
                    </Link>
                    {/* A workflow run is a draft handed over, not a product that
                        reports back - so the person who finished it is the one
                        who can say the step is over. Without this the chain
                        reached a compute stage and stopped there, which is the
                        same dead end `review` had one stage earlier. */}
                    {completeStageButton(stage)}
                  </>
                ) : stage.resource_type === 'copilot_agent_run' && stage.resource_id ? (
                  // An agent run has no page of its own; naming it is still better than
                  // "no automatic product", which would be false.
                  <span className="text-xs text-muted-foreground">
                    {language === 'zh'
                      ? `助手任务 · ${stage.operator ?? 'Bot'}`
                      : `Assistant task · ${stage.operator ?? 'Bot'}`}
                  </span>
                ) : (
                  <>
                    <span className="text-xs text-muted-foreground">
                      {language === 'zh' ? '这一阶段没有自动产物，需要人工完成' : 'no automatic product — a human step'}
                    </span>
                    {/* ...and a way to say it is done. Without this the chain
                        reached a human step and stopped there with no action
                        available anywhere, which the default campaign - ending
                        in `review` - did every time. */}
                    {completeStageButton(stage)}
                  </>
                )}
              </li>
            ))}
          </ol>
        </AppFrame>
      ) : null}
      {error ? <Alert className="mt-5" variant="destructive"><AlertDescription>{error instanceof Error ? error.message : String(error)}</AlertDescription></Alert> : null}
    </section>
  )
}
