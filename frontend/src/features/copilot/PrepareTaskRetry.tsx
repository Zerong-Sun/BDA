import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '../../components/ui/Button'
import type { AgentRun } from '../../lib/api/agentRuns'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'

/** Prepare only. A retry has its own execution and needs a fresh write review. */
export function PrepareTaskRetry({ run, followup, disabled }: { run: AgentRun; followup: string; disabled: boolean }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const navigate = useNavigate()
  const [confirmReplace, setConfirmReplace] = useState(false)
  const service = run.task_contract?.service_kind
  if (run.parent_run_id || !['failed', 'cancelled', 'succeeded'].includes(run.status)
    || typeof service !== 'string' || !['brief', 'literature', 'planning', 'execution', 'interpretation'].includes(service)) return null

  const prepare = (replace = false) => {
    if (disabled) return
    const state = useAppStore.getState()
    if (!replace && state.copilotTaskDrafts[run.project_id]?.goal.trim()) {
      setConfirmReplace(true)
      return
    }
    const methods = run.task_contract?.procedural_skills
    state.setCopilotTaskDraft(run.project_id, {
      goal: followup.trim() ? `${run.goal}\n\n${zh ? '补充要求' : 'Additional requirements'}:\n${followup.trim()}` : run.goal,
      bot: run.bot ?? null,
      service,
      preview: true,
      writes: [],
      maxTurns: run.max_turns,
      maxCost: run.max_cost_usd_cents == null ? '' : String(run.max_cost_usd_cents),
      proceduralSkills: Array.isArray(methods)
        ? methods.flatMap((method) => method && typeof method === 'object' && 'id' in method && typeof method.id === 'string' ? [method.id] : [])
        : [],
      retrySource: run.id,
    })
    state.setCopilotDraft('')
    navigate(`/bots?${new URLSearchParams({ project: run.project_id, view: 'tasks' })}`)
  }

  return <div className="space-y-2">
    <Button type="button" variant="outline" disabled={disabled} onClick={() => prepare()}>
      {zh ? '准备重新尝试' : 'Prepare a new attempt'}
    </Button>
    <p className="text-xs text-text-secondary">{zh
      ? '复制目标、补充要求和方法到新草稿。新任务使用当前平台调用限制；检查失败原因，重新选择写入授权后再开始。'
      : 'Copy the goal, added requirements and methods into a new draft. New tasks use the current platform call limit. Review the failure and choose any write permissions before starting.'}</p>
    {confirmReplace ? <div role="group" aria-label={zh ? '已有任务草稿' : 'Existing task draft'} className="space-y-2">
      <p className="text-sm">{zh ? '此项目已有任务草稿。替换后会打开新计划供检查，不会立即执行。' : 'This project already has a task draft. Replacing it opens the new plan for review without starting it.'}</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={disabled} onClick={() => prepare(true)}>{zh ? '替换草稿并检查' : 'Replace draft and review'}</Button>
        <Button type="button" variant="ghost" onClick={() => setConfirmReplace(false)}>{zh ? '保留现有草稿' : 'Keep existing draft'}</Button>
      </div>
    </div> : null}
  </div>
}
