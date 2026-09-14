import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRightIcon } from '@phosphor-icons/react'
import { isLive, listAgentRuns, type AgentRun } from '../lib/api/agentRuns'
import { listClusterDrafts, listLiteratureClaims } from '../lib/api/copilot'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useI18n } from '../lib/i18n'
import { projectText } from '../lib/i18n/projectText'
import { ApiState } from '../components/ui/ApiState'
import { Button } from '../components/ui/Button'
import { BotAvatar } from '../features/copilot/BotAvatar'
import { useCopilotReadOnly } from '../features/copilot/commandAccess'
import { useCopilotHandoffs } from '../features/copilot/handoffs'
import { resolveBot, useCopilotBots, type CopilotBot } from '../features/copilot/bots/registry'
import { botHref } from '../features/copilot/bots/workbenches'
import { deliveryLabel, deliveryState } from '../features/copilot/taskPresentation'

/**
 * What is waiting on a person in this project.
 *
 * The Bots prepare, draft and claim; a few things only a person may do with the
 * result - supply what a task is missing, accept a delivery, confirm compute
 * that spends budget, accept an extracted claim, check a claim that cites
 * nothing. Those were spread across the task list, the workflow inspector, the
 * literature panel and the handoff record. This page only gathers them and links
 * to where each decision is made; it decides nothing itself.
 */
export function InboxPage() {
  const { projectId } = useProjectContext()
  return <DecisionInbox key={projectId} />
}

const INPUT_STATES = new Set(['needs_input', 'blocked'])
const REVIEW_STATES = new Set(['completed', 'partial', 'review_required'])
const REVIEW_LIMIT = 8

function DecisionInbox() {
  const { language } = useI18n()
  const zh = language === 'zh'
  const { activeProject, projectId, projectsLoading, projectsError, projectsQueryError, refetchProjects } = useProjectContext()
  const readOnly = useCopilotReadOnly()
  const bots = useCopilotBots()
  const runs = useQuery({ queryKey: ['agent-runs', projectId], queryFn: () => listAgentRuns(projectId), enabled: Boolean(projectId), refetchInterval: (q) => q.state.data?.some(isLive) ? 4000 : false })
  const drafts = useQuery({ queryKey: ['cluster-drafts', projectId], queryFn: () => listClusterDrafts(projectId), enabled: Boolean(projectId) })
  const claims = useQuery({ queryKey: ['literature-claims', projectId, 'pending_review'], queryFn: () => listLiteratureClaims(projectId, 'pending_review'), enabled: Boolean(projectId) })
  const handoffs = useCopilotHandoffs(projectId || null)
  const roster = bots.data ?? []
  const project = encodeURIComponent(projectId)

  // Only top-level tasks a person started; a delegated child reports through its parent.
  const settled = (runs.data ?? []).filter((run) => !run.parent_run_id && !isLive(run))
  const needInput = settled.filter((run) => INPUT_STATES.has(deliveryState(run)))
  const toReview = settled.filter((run) => REVIEW_STATES.has(deliveryState(run))).sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  const pendingDrafts = (drafts.data?.items ?? []).filter((draft) => draft.status === 'draft')
  const pendingClaims = claims.data?.items.length ?? 0
  const unsupported = (handoffs.data ?? []).filter((handoff) => (handoff.claims ?? []).some((claim) => claim.confidence === 'unsupported'))
  const loaded = runs.isSuccess && drafts.isSuccess && claims.isSuccess && handoffs.isSuccess
  const total = needInput.length + toReview.length + pendingDrafts.length + pendingClaims + unsupported.length
  const taskHref = (run: AgentRun) => {
    const owner = resolveBot(run.bot, roster)
    return owner ? `${botHref(owner.id, projectId)}&run=${encodeURIComponent(run.id)}` : `/bots?project=${project}&view=tasks&run=${encodeURIComponent(run.id)}`
  }
  const taskRow = (run: AgentRun) => {
    const owner = resolveBot(run.bot, roster)
    return <Link key={run.id} to={taskHref(run)} className="inbox-row">
      <span className="inbox-row-main">{owner ? <BotAvatar id={owner.id} stance={owner.stance} /> : null}
        <span><small>{owner ? name(owner, zh) : (zh ? '未指定负责人' : 'No assigned owner')} · {deliveryLabel(run, zh)}</small>{run.goal}</span></span>
      <ArrowRightIcon aria-hidden="true" />
    </Link>
  }

  return <section className="bot-page inbox-page" data-tour-id="decision-inbox">
    <header className="science-page-header">
      <div><p className="science-eyebrow">{zh ? '需要你来决定' : 'YOUR DECISIONS'}</p>
        <h1>{zh ? '待我决定' : 'Needs your decision'}</h1>
        <p>{activeProject ? projectText(activeProject, 'name', language) : (zh ? '选择项目，查看等待你决定的事项。' : 'Choose a project to see what is waiting on you.')}</p>
      </div>
    </header>
    <ApiState isLoading={projectsLoading} isError={projectsError} error={projectsQueryError} onRetry={() => void refetchProjects()}>
      {!activeProject ? <div className="science-empty"><h2>{zh ? '先选择一个研究项目' : 'Start with a research project'}</h2><Button type="button" render={<Link to="/projects" />}>{zh ? '查看项目' : 'Browse projects'}<ArrowRightIcon /></Button></div> : <>
        <p className="inbox-intro">{zh ? 'Bot 负责准备、起草和提出断言；下面这些只有你能确认。这里只汇总并链接到做决定的地方，不会替你执行任何操作。' : 'Bots prepare, draft and claim; these are the things only you can settle. This page gathers them and links to where each decision is made; it does nothing on your behalf.'}
          {readOnly ? (zh ? ' 当前为只读模式，可以查看，确认需要研究员权限。' : ' You are in read-only mode: you can inspect these, but settling them needs researcher access.') : null}</p>
        {loaded && total === 0 ? <p role="status" className="inbox-clear">{zh ? '目前没有需要你决定的事项。' : 'Nothing needs your decision right now.'}</p> : null}
        <div className="inbox-grid">
          <InboxSection label={zh ? '需要你补充信息' : 'Needs your input'} count={runs.isSuccess ? needInput.length : null} query={runs}
            empty={zh ? '没有等待补充信息的任务。' : 'No task is waiting for your input.'}>
            {needInput.map(taskRow)}
          </InboxSection>
          <InboxSection label={zh ? '交付物待你审核' : 'Ready for your review'} count={runs.isSuccess ? toReview.length : null} query={runs}
            empty={zh ? '没有等待审核的交付物。' : 'No delivery is waiting for review.'}
            footer={toReview.length > REVIEW_LIMIT ? <Link to={`/bots?project=${project}&view=tasks`}>{zh ? `查看全部 ${toReview.length} 项` : `See all ${toReview.length}`}</Link> : null}>
            {toReview.slice(0, REVIEW_LIMIT).map(taskRow)}
          </InboxSection>
          <InboxSection label={zh ? '计算草稿待确认' : 'Compute drafts to confirm'} count={drafts.isSuccess ? pendingDrafts.length : null} query={drafts}
            empty={zh ? '没有等待确认的计算草稿。' : 'No compute draft is waiting for confirmation.'}
            footer={pendingDrafts.length ? <span>{zh ? '确认会占用集群资源；确认前可请 Auditor 核对资源声明。' : 'Confirming spends cluster resources; ask Auditor to check the declared resources first.'}</span> : null}>
            {pendingDrafts.map((draft) => <Link key={draft.id} to={`/workflow?project=${project}`} className="inbox-row">
              <span className="inbox-row-main"><span><small>{draft.backend}</small>{draft.name}</span></span><ArrowRightIcon aria-hidden="true" />
            </Link>)}
          </InboxSection>
          <InboxSection label={zh ? '文献断言待审核' : 'Literature claims to review'} count={claims.isSuccess ? pendingClaims : null} query={claims}
            empty={zh ? '没有等待审核的文献断言。' : 'No extracted claim is waiting for review.'}>
            {pendingClaims ? <Link to={`/research?project=${project}&tab=evidence`} className="inbox-row">
              <span className="inbox-row-main"><span><small>{zh ? '文献与证据' : 'Literature & evidence'}</small>{zh ? `${pendingClaims} 条从文献中抽取的断言等待接受或拒绝` : `${pendingClaims} extracted ${pendingClaims === 1 ? 'claim is' : 'claims are'} waiting to be accepted or rejected`}</span></span><ArrowRightIcon aria-hidden="true" />
            </Link> : null}
          </InboxSection>
          <InboxSection label={zh ? '缺少依据的断言' : 'Claims without evidence'} count={handoffs.isSuccess ? unsupported.length : null} query={handoffs}
            empty={zh ? '交接记录中没有缺少依据的断言。' : 'No handover carries a claim without evidence.'}>
            {unsupported.map((handoff) => {
              const from = resolveBot(handoff.from_bot, roster)
              const to = resolveBot(handoff.to_bot, roster)
              const count = (handoff.claims ?? []).filter((claim) => claim.confidence === 'unsupported').length
              return <Link key={handoff.id} to={to ? botHref(to.id, projectId) : `/bots?project=${project}&view=handoffs`} className="inbox-row">
                <span className="inbox-row-main">{from ? <BotAvatar id={from.id} stance={from.stance} /> : null}
                  <span><small>{from ? name(from, zh) : handoff.from_bot} → {to ? name(to, zh) : handoff.to_bot} · {zh ? `${count} 条无依据` : `${count} unsupported`}</small>{handoff.summary}</span></span>
                <ArrowRightIcon aria-hidden="true" />
              </Link>
            })}
          </InboxSection>
        </div>
      </>}
    </ApiState>
  </section>
}

function name(bot: CopilotBot, zh: boolean) {
  return zh ? bot.title_zh : bot.title
}

function InboxSection({ label, count, query, empty, footer, children }: {
  label: string
  count: number | null
  query: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown }
  empty: string
  footer?: ReactNode
  children: ReactNode
}) {
  return <section className="inbox-section" aria-label={label}>
    <h2>{label}{count !== null ? <span className="inbox-count">{count}</span> : null}</h2>
    <ApiState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => void query.refetch()}>
      {count === 0 ? <p className="text-sm text-text-secondary">{empty}</p> : <div>{children}</div>}
      {footer ? <p className="inbox-footer">{footer}</p> : null}
    </ApiState>
  </section>
}
