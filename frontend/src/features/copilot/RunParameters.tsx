import type { AgentRun } from '../../lib/api/agentRuns'
import { useI18n } from '../../lib/i18n'
import { Disclosure } from '../../components/ui/Disclosure'

export function RunParameters({ run }: { run: AgentRun }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const unknown = zh ? '未记录' : 'Not recorded'
  const writes = run.task_contract?.authorized_writes
  const tools = run.allowed_tools.filter((value): value is string => typeof value === 'string')
  return <Disclosure title={zh ? '技术详情' : 'Technical details'}>
    <div className="run-parameters">
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
      <div><dt className="text-text-secondary">{zh ? '过程消息数' : 'Recorded messages'}</dt><dd className="mt-1 font-mono">{run.turn_count}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '配置轮数上限' : 'Configured turn limit'}</dt><dd className="mt-1 font-mono">{run.max_turns ?? unknown}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '模型费用上限' : 'Model cost ceiling'}</dt><dd className="mt-1 font-mono">{run.max_cost_usd_cents === undefined ? unknown : run.max_cost_usd_cents === null ? (zh ? '未设置' : 'Not set') : `${run.max_cost_usd_cents} ${zh ? '美分' : 'US cents'}`}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '任务类型' : 'Task type'}</dt><dd className="mt-1 break-words">{typeof run.task_contract?.service_kind === 'string' ? run.task_contract.service_kind : unknown}</dd></div>
      <div><dt className="text-text-secondary">{zh ? '记录版本' : 'Record version'}</dt><dd className="mt-1 font-mono">{run.version}</dd></div>
    </dl>
    <p className="mt-2 text-xs text-text-secondary">{zh ? '过程消息包含模型答复和工具结果。平台级调用与费用限制也会生效。' : 'Messages include model replies and tool results. Platform call and cost limits also apply.'}</p>
    {run.parent_run_id ? <p className="mt-2 text-xs text-text-secondary">{zh ? '此处显示子任务记录的额度；父任务的共享预算也适用。' : 'These are the subtask’s recorded limits. The parent’s shared budget also applies.'}</p> : null}
    <div className="mt-3 text-xs"><p className="text-text-secondary">{zh ? '已授权写入' : 'Authorized writes'}</p><p className="mt-1 break-words">{Array.isArray(writes) ? writes.filter((item) => typeof item === 'string').join(' · ') || (zh ? '无' : 'None') : unknown}</p></div>
    <Disclosure title={zh ? '工具范围与记录标识' : 'Tool scope and record IDs'}>
      <dl className="space-y-2 break-all text-xs">
        <div><dt>{zh ? '任务标识' : 'Run ID'}</dt><dd className="font-mono">{run.id}</dd></div>
        <div><dt>{zh ? '项目标识' : 'Project ID'}</dt><dd className="font-mono">{run.project_id}</dd></div>
        {run.parent_run_id ? <div><dt>{zh ? '父任务' : 'Parent run'}</dt><dd className="font-mono">{run.parent_run_id}</dd></div> : null}
        <div><dt>{zh ? '可用工具' : 'Allowed tools'}</dt><dd>{tools.join(' · ') || (zh ? '无' : 'None')}</dd></div>
      </dl>
    </Disclosure>
    </div>
  </Disclosure>
}
