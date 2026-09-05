import { useState } from 'react'
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
  confirmAutopilotDraft,
  createAutopilotDraft,
  getAutopilotCampaign,
  startAutopilotCampaign,
  takeOverAutopilotCampaign,
} from '../lib/api/autopilot'
import type { AutopilotCampaignResponse, AutopilotDraftResponse } from '../lib/api/generated/types.gen'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useI18n } from '../lib/i18n'

export function AutopilotPage() {
  const { language } = useI18n()
  const { projectId } = useProjectContext()
  const [prompt, setPrompt] = useState('')
  const [name, setName] = useState('')
  const [gpuHours, setGpuHours] = useState('')
  const [draft, setDraft] = useState<AutopilotDraftResponse | null>(null)
  const [draftEtag, setDraftEtag] = useState('')
  const [campaign, setCampaign] = useState<AutopilotCampaignResponse | null>(null)
  const [operationId, setOperationId] = useState<string | null>(null)

  const draftMutation = useMutation({
    mutationFn: () => createAutopilotDraft(projectId, prompt),
    onSuccess: ({ draft: nextDraft, etag }) => {
      setDraft(nextDraft)
      setDraftEtag(etag)
      setCampaign(null)
      setOperationId(null)
    },
  })
  const confirmMutation = useMutation({
    mutationFn: () => confirmAutopilotDraft(
      draft!.id,
      draftEtag,
      name,
      Math.round(Number(gpuHours) * 3600),
    ),
    onSuccess: setCampaign,
  })
  const startMutation = useMutation({
    mutationFn: () => startAutopilotCampaign(campaign!.id, Math.round(Number(gpuHours) * 3600)),
    onSuccess: (accepted) => setOperationId(accepted.operation_id),
  })
  const cancelMutation = useMutation({
    mutationFn: () => cancelAutopilotCampaign(campaign!.id),
    onSuccess: (accepted) => setOperationId(accepted.operation_id),
  })
  // Re-read after starting: the stages only acquire their trunk resources once the worker
  // has run the adapter, and the deep links below are the point of showing them at all.
  const refreshMutation = useMutation({
    mutationFn: () => getAutopilotCampaign(campaign!.id),
    onSuccess: setCampaign,
  })
  const takeoverMutation = useMutation({
    mutationFn: () => takeOverAutopilotCampaign(campaign!.id, campaign!.version),
    onSuccess: setCampaign,
  })
  const error =
    draftMutation.error ??
    confirmMutation.error ??
    startMutation.error ??
    cancelMutation.error ??
    refreshMutation.error ??
    takeoverMutation.error

  return (
    <section className="mx-auto max-w-5xl">
      <PageHead eyebrow="Autopilot" title={language === 'zh' ? '冻结协议自动执行' : 'Frozen-protocol execution'} />
      <Alert className="mb-5" variant="warning">
        <AlertTitle>{language === 'zh' ? '先预览，再确认，再启动' : 'Preview, confirm, then start'}</AlertTitle>
        <AlertDescription>
          {language === 'zh'
            ? '系统没有默认 400 GPU 小时。监督式 campaign 必须显式填写硬预算，确认后 prompt 与 spec 不可修改。'
            : 'There is no default 400 GPU-hour allowance. Supervised campaigns require an explicit hard budget; prompt and spec become immutable after confirmation.'}
        </AlertDescription>
      </Alert>
      {!projectId ? <Alert variant="info"><AlertDescription>{language === 'zh' ? '请先选择项目。' : 'Select a project first.'}</AlertDescription></Alert> : null}
      <div className="grid gap-5 lg:grid-cols-2">
        <AppFrame heading={language === 'zh' ? '1. 自然语言需求' : '1. Natural-language request'} panelClassName="space-y-4 p-5">
          <Textarea
            className="min-h-52 w-full border border-border bg-background p-3 text-sm"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={language === 'zh' ? '描述目标、约束、成功标准和所需阶段…' : 'Describe objectives, constraints, success criteria, and stages…'}
          />
          <Button type="button" disabled={!projectId || prompt.trim().length < 10 || draftMutation.isPending} onClick={() => draftMutation.mutate()}>
            {language === 'zh' ? '生成结构化预览' : 'Generate structured preview'}
          </Button>
        </AppFrame>
        <AppFrame heading={language === 'zh' ? '2. Draft / Spec 预览' : '2. Draft / spec preview'} panelClassName="space-y-4 p-5">
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap border border-border bg-muted p-3 text-xs">
            {draft ? JSON.stringify(draft.normalized_spec, null, 2) : (language === 'zh' ? '尚未生成 draft。' : 'No draft yet.')}
          </pre>
          <div className="grid gap-2">
            <Label htmlFor="autopilot-name">{language === 'zh' ? 'Campaign 名称' : 'Campaign name'}</Label>
            <Input id="autopilot-name" value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="autopilot-budget">{language === 'zh' ? 'GPU 小时硬上限' : 'GPU-hour hard limit'}</Label>
            <Input id="autopilot-budget" type="number" min="0.01" step="0.25" value={gpuHours} onChange={(event) => setGpuHours(event.target.value)} />
          </div>
          <Button
            type="button"
            disabled={!draft || !name.trim() || Number(gpuHours) <= 0 || confirmMutation.isPending}
            onClick={() => confirmMutation.mutate()}
          >
            {language === 'zh' ? '确认不可变 Campaign' : 'Confirm immutable campaign'}
          </Button>
        </AppFrame>
      </div>
      {campaign ? (
        <AppFrame className="mt-5" heading={language === 'zh' ? '3. 启动与取消' : '3. Start and cancel'} panelClassName="flex flex-wrap items-center gap-3 p-5">
          <span className="text-sm">{campaign.name} · {campaign.status}</span>
          <Button type="button" onClick={() => startMutation.mutate()} disabled={startMutation.isPending}>{language === 'zh' ? '预留预算并启动' : 'Reserve budget and start'}</Button>
          <Button type="button" variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>{language === 'zh' ? '幂等取消' : 'Idempotent cancel'}</Button>
          <Button type="button" variant="outline" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}>{language === 'zh' ? '刷新阶段' : 'Refresh stages'}</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => takeoverMutation.mutate()}
            disabled={takeoverMutation.isPending || campaign.status === 'manual_takeover' || campaign.status === 'cancelled'}
          >
            {language === 'zh' ? '人工接管' : 'Take over'}
          </Button>
          {operationId ? <span className="text-xs text-muted-foreground">operation: {operationId}</span> : null}
        </AppFrame>
      ) : null}
      {campaign?.status === 'manual_takeover' ? (
        <Alert className="mt-5" variant="info">
          <AlertTitle>{language === 'zh' ? '已由人工接管' : 'Under manual control'}</AlertTitle>
          <AlertDescription>
            {language === 'zh'
              ? '协议仍然冻结，但自动推进已停止，产物改由人工编辑。接管记录写在 ledger 上。'
              : 'The protocol stays frozen, automatic advance has stopped, and the products are now edited by hand. The handover is on the ledger.'}
          </AlertDescription>
        </Alert>
      ) : null}
      {campaign?.stages?.length ? (
        <AppFrame className="mt-5" heading={language === 'zh' ? '4. 阶段与产物' : '4. Stages and their products'} panelClassName="p-5">
          <p className="mb-3 text-xs text-muted-foreground">
            {language === 'zh'
              ? '每个阶段的产物落在与人工完全相同的表上，因此可以直接在 Workflow 页打开、检查和修改。'
              : 'Each stage lands on the same tables manual work does, so its product opens in the Workflow page like any other run.'}
          </p>
          <ol className="space-y-2">
            {campaign.stages.map((stage) => (
              <li key={stage.id} className="flex flex-wrap items-baseline gap-2 border-l-2 border-l-border pl-3 text-sm">
                <span className="font-medium">{stage.stage_key}</span>
                <span className="text-xs text-muted-foreground">{stage.status}</span>
                {stage.resource_type === 'workflow_run' && stage.resource_id ? (
                  <Link className="text-xs underline" to={`/workflow?run=${stage.resource_id}`}>
                    {language === 'zh' ? '在 Workflow 页打开' : 'Open in Workflow'}
                  </Link>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {language === 'zh' ? '这一阶段没有自动产物，需要人工完成' : 'no automatic product — a human step'}
                  </span>
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
