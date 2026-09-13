import { useAppStore } from '../../lib/store/appStore'
import { Disclosure } from '../../components/ui/Disclosure'
import { Link } from 'react-router'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'
import type { ProjectOverview } from '../../lib/api/projects'
import { currentStageIndex, PIPELINE_STAGES } from '../workflow/pipelineStages'

export function ProjectNextAction({ overview }: { overview: ProjectOverview }) {
  const { language, t } = useI18n()
  const index = currentStageIndex(true, overview)
  const stage = PIPELINE_STAGES[index]
  const project = encodeURIComponent(overview.project.id)
  const ready = overview.target_readiness?.ready_for_workflow === true
  const copy = language === 'zh' ? [
    '确认研究目标与靶标身份，补齐目标结构和证据。',
    '选择适用方案，绑定输入，再检查执行环境。',
    '审查候选结果，选出要进入实验验证的样品。',
    '准备样品并记录测量结果，关联回研究问题。',
    '比较计算与实验结果，记录判断并确定下一轮问题。',
  ] : [
    'Confirm the objective and target identity, then complete evidence and structure inputs.',
    'Choose a suitable route, bind inputs and check the execution environment.',
    'Review candidates and select samples for experimental validation.',
    'Prepare samples and record measurements against the research question.',
    'Compare predictions with measurements and record the next research decision.',
  ]
  return <section className="mb-6 rounded-xl border border-accent-border bg-accent-bg p-5" aria-label={language === 'zh' ? '当前任务' : 'Current task'}>
    <p className="text-xs text-text-secondary">{language === 'zh' ? '当前步骤' : 'Current step'} · {index + 1} / 5</p>
    <h2 className="mt-1 text-lg font-semibold">{t.nav[stage.navKey]}</h2>
    <p className="my-3 text-sm">{copy[index]}</p>
    {!ready && overview.target_readiness?.blockers.length ? <Disclosure className="mb-3 text-sm" title={language === 'zh' ? '查看待补充信息' : 'Review missing information'}>
      <ul className="mt-2 list-disc pl-5">{overview.target_readiness.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>
    </Disclosure> : null}
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="outline" onClick={() => { useAppStore.getState().setCopilotDraft(''); useAppStore.getState().setCopilotOpen(true) }}>{language === 'zh' ? '让助手准备下一步' : 'Prepare the next step with Copilot'}</Button>
      <Button render={<Link to={`${stage.path}?project=${project}${index === 0 ? '&tab=goals' : ''}`} />}>{language === 'zh' ? '继续当前任务' : 'Continue current task'}</Button>
      <Button variant="outline" render={<Link to={`/research?project=${project}&tab=timeline`} />}>{language === 'zh' ? '查看决策记录' : 'Decision record'}</Button>
    </div>
  </section>
}
