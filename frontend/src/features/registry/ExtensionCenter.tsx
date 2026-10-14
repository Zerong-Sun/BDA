import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Disclosure } from '../../components/ui/Disclosure'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { assessExtension, getExtensionCatalog, type ExtensionAssessment, type ExtensionCatalog, type ExtensionEntry } from '../../lib/api/extensions'
import { currentRole } from '../research/jsonHelpers'

function RegistryChoice({ label, placeholder, value, options, disabled, onChange }: {
  label: string; placeholder: string; value: string; options: Array<{ id: string; label: string }>; disabled: boolean; onChange: (value: string) => void
}) {
  return <div className="space-y-1 text-sm"><p>{label}</p><Select value={value} disabled={disabled} onValueChange={(next) => onChange(next ?? '')}>
    <SelectTrigger aria-label={label} className="w-full"><SelectValue>{options.find((item) => item.id === value)?.label ?? placeholder}</SelectValue></SelectTrigger>
    <SelectContent><SelectItem value="">{placeholder}</SelectItem>{options.map((item) => <SelectItem key={item.id} value={item.id}>{item.label}</SelectItem>)}</SelectContent>
  </Select></div>
}

function AssessmentResult({ value }: { value: ExtensionAssessment }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  return <div className="space-y-3 text-sm" aria-label={zh ? '配置评估结果' : 'Configuration assessment'}>
    <p className="font-medium">{value.state === 'built_in' ? (zh ? '已内置实现；具体部署仍需验收' : 'Implementation is bundled; deployment acceptance is separate') : value.ready_for_trial ? (zh ? '登记条件满足受控试验预检' : 'Recorded prerequisites meet controlled-trial preflight') : (zh ? '仍有准备工作或尚未提供执行适配' : 'Preparation or an execution adapter is still needed')}</p>
    <p className="text-xs text-text-secondary">{zh ? '科研有效性未评估。登记、许可复核、运行指纹和实际实验验证分别判断。' : 'Scientific validity is not assessed. Registration, use review, runtime proof and experimental validation are separate.'}</p>
    {value.blockers.length ? <div><h4 className="font-medium">{zh ? '待解决条件' : 'Prerequisites to resolve'}</h4><ul className="list-disc space-y-1 pl-5">{value.blockers.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
    <Disclosure title={zh ? '检查依据与范围' : 'Checks and scope'}><ul className="space-y-2 py-2">{value.checks.map((item) => <li key={item.id}><span className="mr-2 rounded border border-border px-1 text-xs">{item.status}</span>{item.message}</li>)}</ul></Disclosure>
    <ul className="space-y-1 text-xs text-text-secondary">{value.warnings.map((item) => <li key={item}>{item}</li>)}</ul>
  </div>
}

function ExtensionInspector({ entry, catalog, canAssess }: { entry: ExtensionEntry; catalog: ExtensionCatalog; canAssess: boolean }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [model, setModel] = useState('')
  const [node, setNode] = useState('')
  const [provider, setProvider] = useState('')
  const [reviews, setReviews] = useState({ license_review_ref: '', data_review_ref: '', validation_plan_ref: '', budget_review_ref: '' })
  const assessment = useMutation({ mutationFn: () => assessExtension(entry.manifest.id, {
    ...reviews, model_plugin_id: model || null, compute_node_id: node || null, llm_provider_id: provider || null,
  }) })
  const data = entry.manifest
  const values = [
    [zh ? '资源与运行要求' : 'Resources and operations', data.resources],
    [zh ? '许可边界' : 'License boundary', data.license_boundary],
    [zh ? '数据边界' : 'Data boundary', data.data_boundary],
    [zh ? '投入触发条件' : 'Rollout trigger', data.rollout_trigger],
    [zh ? '规划成本' : 'Planning cost', data.effort],
  ]
  return <section className="min-w-0 space-y-4 rounded-lg border border-border p-4" aria-label={zh ? '扩展详情' : 'Extension details'}>
    <div><h2 className="text-lg font-semibold">{zh ? data.title_zh : data.title}</h2><p className="mt-1 text-sm text-text-secondary">{zh ? data.description_zh : data.description}</p><p className="mt-1 text-xs text-text-muted">v{data.version} · {data.function_ids.join(' · ')}</p></div>
    <dl className="space-y-3 text-sm">{values.map(([label, value]) => <div key={label}><dt className="font-medium">{label}</dt><dd className="mt-1 text-text-secondary">{value}</dd></div>)}</dl>
    <Disclosure title={zh ? '集成要求与参考' : 'Integration requirements and references'}><ul className="space-y-2 py-2 text-sm">{data.requirements.map((requirement) => <li key={requirement.id}><strong>{zh ? requirement.title_zh : requirement.title}</strong><p className="text-text-secondary">{requirement.boundary}</p></li>)}</ul><ul className="space-y-1 text-xs">{data.sources.map((source) => <li key={source}><a href={source} target="_blank" rel="noopener noreferrer" className="break-all underline">{source.replace('https://github.com/', '')}</a></li>)}</ul></Disclosure>
    <AssessmentResult value={assessment.data ?? entry.assessment} />
    {data.adapter !== 'builtin' ? <form className="space-y-3 border-t border-border pt-4" onSubmit={(event) => { event.preventDefault(); if (canAssess) assessment.mutate() }}>
      <h3 className="font-medium">{zh ? '检查拟选配置' : 'Inspect a proposed configuration'}</h3>
      <p className="text-xs text-text-secondary">{zh ? '只比较已有登记与填写的复核记录，不安装、不调用模型、不连接设备，也不保存配置。' : 'Compares registry records and supplied review references. It does not install, call models, connect devices or save configuration.'}</p>
      {!canAssess ? <p role="status" className="text-sm text-text-secondary">{zh ? '当前可查看全部要求；配置评估由管理员在应用模式中执行。' : 'You can inspect all requirements. Configuration assessments are available to administrators in application mode.'}</p> : null}
      <fieldset disabled={!canAssess || assessment.isPending} className="space-y-3">
        {data.adapter === 'model_registry' ? <>
          <RegistryChoice label={zh ? '模型插件' : 'Model plugin'} placeholder={zh ? '选择已登记插件' : 'Choose a registered plugin'} value={model} disabled={!canAssess || assessment.isPending} onChange={(value) => { setModel(value); assessment.reset() }} options={catalog.models.map((item) => ({ id: item.id, label: `${item.name} · ${item.plugin_version}${item.enabled ? '' : ' (disabled)'}` }))} />
          <RegistryChoice label={zh ? '计算节点' : 'Compute node'} placeholder={zh ? '选择已登记节点' : 'Choose a registered node'} value={node} disabled={!canAssess || assessment.isPending} onChange={(value) => { setNode(value); assessment.reset() }} options={catalog.compute_nodes.map((item) => ({ id: item.id, label: `${item.name}${item.enabled ? '' : ' (disabled)'}` }))} />
        </> : null}
        {data.adapter === 'provider_registry' ? <RegistryChoice label={zh ? '模型服务' : 'Model provider'} placeholder={zh ? '选择已登记服务' : 'Choose a registered provider'} value={provider} disabled={!canAssess || assessment.isPending} onChange={(value) => { setProvider(value); assessment.reset() }} options={catalog.providers.map((item) => ({ id: item.id, label: `${item.name}${item.enabled ? '' : ' (disabled)'}` }))} /> : null}
        {([
          ['license_review_ref', zh ? '许可复核记录' : 'License review reference'],
          ['data_review_ref', zh ? '数据边界复核记录' : 'Data review reference'],
          ['validation_plan_ref', zh ? '验收方案记录' : 'Validation plan reference'],
          ['budget_review_ref', zh ? '预算复核记录' : 'Budget review reference'],
        ] as const).map(([key, label]) => <label key={key} className="block text-sm">{label}<Input maxLength={500} value={reviews[key]} placeholder={zh ? '已有复核文档或记录编号' : 'Existing review document or record ID'} onChange={(event) => { setReviews((current) => ({ ...current, [key]: event.target.value })); assessment.reset() }} /></label>)}
        <Button type="submit" disabled={!canAssess || assessment.isPending}>{assessment.isPending ? (zh ? '检查中…' : 'Checking…') : (zh ? '检查准备情况' : 'Check readiness')}</Button>
      </fieldset>
      {assessment.error ? <p role="alert" className="text-sm text-destructive">{assessment.error instanceof Error ? assessment.error.message : String(assessment.error)}</p> : null}
    </form> : null}
  </section>
}

export function ExtensionCenter() {
  const { language } = useI18n()
  const zh = language === 'zh'
  const mode = useAppStore((state) => state.appMode)
  const canAssess = currentRole() === 'admin' && mode === 'application'
  const catalog = useQuery({ queryKey: ['registry-extensions'], queryFn: getExtensionCatalog })
  const [selected, setSelected] = useState('scientific-models')
  const [filter, setFilter] = useState('')
  const stateLabel = (value: string) => ({ built_in: zh ? '已内置' : 'Built in', needs_configuration: zh ? '待配置／复核' : 'Needs configuration', disabled: zh ? '已禁用' : 'Disabled', not_installed: zh ? '未登记安装' : 'Not registered', planned: zh ? '后续方案' : 'Planned' })[value] ?? value
  const entries = catalog.data?.extensions.filter(({ manifest }) => `${manifest.title} ${manifest.title_zh} ${manifest.description} ${manifest.function_ids.join(' ')}`.toLowerCase().includes(filter.toLowerCase())) ?? []
  const current = catalog.data?.extensions.find((item) => item.manifest.id === selected)
  return <section className="space-y-5 p-4 md:p-6" data-testid="extension-center">
    <header className="science-page-header"><div><p className="science-eyebrow">{zh ? '平台能力 / 集成与验收' : 'PLATFORM / INTEGRATION & QUALIFICATION'}</p><h1>{zh ? '扩展中心' : 'Extension center'}</h1><p>{zh ? '从现有登记检查可用条件，把长期方案转为具体的集成与验收要求。' : 'Inspect recorded prerequisites and turn future options into concrete integration and acceptance requirements.'}</p></div><Button type="button" variant="outline" onClick={() => void catalog.refetch()}>{zh ? '刷新登记状态' : 'Refresh registry state'}</Button></header>
    <p className="text-sm text-text-secondary">{zh ? '本页不探测主机。已配置不代表已运行，已运行不代表科研有效；正式提交继续使用工作流预检和现有确认流程。' : 'This page never probes hosts. Configured does not mean observed to run, and runtime proof does not establish scientific validity. Submission retains workflow preflight and confirmation.'}</p>
    {catalog.isPending ? <p role="status">{zh ? '读取扩展与模型登记…' : 'Loading extension and model records…'}</p> : null}
    {catalog.error ? <p role="alert">{catalog.error instanceof Error ? catalog.error.message : String(catalog.error)}</p> : null}
    {catalog.data ? <>
      <div className="flex flex-wrap gap-3 text-xs text-text-secondary"><span>{catalog.data.extensions.length} {zh ? '项集成' : 'integrations'}</span><span>{catalog.data.models.length} {zh ? '项模型登记' : 'model declarations'}</span><span>{zh ? '读取时间：' : 'Read at: '}{new Date(catalog.data.assessed_at).toLocaleString()}</span></div>
      {catalog.data.inventory_truncated ? <p role="status">{zh ? '各类登记仅显示前 500 项；请通过登记管理接口检查其余资源。' : 'Each resource list is limited to 500 records; inspect the remaining inventory through registry management.'}</p> : null}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)]">
        <aside className="space-y-3"><Input aria-label={zh ? '搜索集成能力' : 'Search integrations'} value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={zh ? '模型、机器人、F14…' : 'Models, robotics, F14…'} /><nav className="space-y-2" aria-label={zh ? '集成方案' : 'Integration options'}>{entries.map((entry) => <Button type="button" key={entry.manifest.id} variant={selected === entry.manifest.id ? 'secondary' : 'outline'} aria-pressed={selected === entry.manifest.id} className="h-auto w-full flex-col items-start gap-1 whitespace-normal p-3 text-left" onClick={() => setSelected(entry.manifest.id)}><span>{zh ? entry.manifest.title_zh : entry.manifest.title}</span><small className="text-text-secondary">{stateLabel(entry.assessment.state)}</small></Button>)}</nav>{!entries.length ? <p>{zh ? '没有匹配的集成。' : 'No matching integrations.'}</p> : null}</aside>
        {current ? <ExtensionInspector key={current.manifest.id} entry={current} catalog={catalog.data} canAssess={canAssess} /> : null}
      </div>
      <section aria-label={zh ? '模型资格与运行依据' : 'Model qualification and runtime evidence'} className="space-y-3 border-t border-border pt-5"><h2 className="font-semibold">{zh ? '模型资格与运行依据' : 'Model qualification and runtime evidence'}</h2>
        {!catalog.data.models.length ? <p className="text-sm text-text-secondary">{zh ? '尚未登记模型插件。' : 'No model plugins are registered.'}</p> : null}
        <div className="grid gap-3 xl:grid-cols-2">{catalog.data.models.map((model) => <article key={model.id} className="min-w-0 space-y-2 rounded-lg border border-border p-3 text-sm"><h3 className="font-medium">{model.name} · {model.plugin_version}</h3><p className="text-xs text-text-secondary">{model.enabled ? (zh ? '已启用' : 'Enabled') : (zh ? '已禁用' : 'Disabled')} · {model.manifest_pinned ? (zh ? '清单已锁定' : 'Pinned manifest') : (zh ? '未锁定清单' : 'Unpinned manifest')} · {model.runtime_proof_current ? (zh ? '运行指纹一致' : 'Current runtime proof') : (zh ? '运行尚未证实／指纹已变化' : 'Runtime unproven or changed')}</p><ul className="list-disc space-y-1 pl-4">{[...model.blockers, ...model.warnings].map((message) => <li key={message}>{message}</li>)}</ul></article>)}</div>
        <Link to="/workflow" className="text-sm underline">{zh ? '前往工作流查看具体提交预检' : 'Open workflow submission preflight'}</Link>
      </section>
    </> : null}
  </section>
}
