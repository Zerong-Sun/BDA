import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Checkbox } from '../../components/ui/checkbox'
import { Disclosure } from '../../components/ui/Disclosure'
import { useI18n } from '../../lib/i18n'
import { getProceduralSkill, listProceduralSkills, type ProceduralSkillSummary } from '../../lib/api/copilot'

function SkillDetails({ skill }: { skill: ProceduralSkillSummary }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [open, setOpen] = useState(false)
  const detail = useQuery({ queryKey: ['copilot-procedural-skill', skill.id, skill.checksum_sha256], queryFn: () => getProceduralSkill(skill.id), enabled: open })
  return <div className="space-y-2">
    <Button type="button" size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>{zh ? '查看方法与来源' : 'Method & provenance'}</Button>
    {open ? <div className="space-y-3 rounded-md border border-border p-3 text-xs">
      <p>{zh ? '作者独立编写的科学流程；来源链接用于说明方法参考，不是本项目的文献证据。' : 'Independently authored methods. Reference links describe method provenance, not evidence for this project.'}</p>
      <p>{skill.author} · {skill.license} · v{skill.version}</p>
      <p className="break-all font-mono">SHA-256: {skill.checksum_sha256}</p>
      <ul className="list-disc space-y-1 pl-4">{skill.provenance.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer" className="underline">{source.title}</a><p className="text-text-secondary">{source.note}</p></li>)}</ul>
      <p className="break-words">{zh ? '建议读取工具：' : 'Suggested read tools: '}{skill.tool_requests.join(', ')}</p>
      <p>{zh ? '可选写入仍需单独授权：' : 'Optional writes still need separate authorization: '}{skill.optional_write_tools.join(', ') || (zh ? '无' : 'None')}</p>
      {detail.isPending ? <p role="status">{zh ? '加载方法…' : 'Loading method…'}</p> : null}
      {detail.isError ? <div role="alert"><p>{zh ? '无法加载方法正文。' : 'Could not load method instructions.'}</p><Button type="button" size="sm" variant="outline" onClick={() => void detail.refetch()}>{zh ? '重试' : 'Retry'}</Button></div> : null}
      {detail.data ? <>
        <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap break-words font-sans leading-relaxed">{detail.data.instructions}</pre>
        <Disclosure title={zh ? '输入与交付格式' : 'Input and delivery contract'}><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify({ input: detail.data.input_schema, output: detail.data.output_schema }, null, 2)}</pre></Disclosure>
      </> : null}
    </div> : null}
  </div>
}

export function ProceduralSkillCatalog() {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [filter, setFilter] = useState('')
  const skills = useQuery({ queryKey: ['copilot-procedural-skills'], queryFn: listProceduralSkills })
  const matches = skills.data?.filter((skill) => `${skill.id} ${skill.title} ${skill.title_zh} ${skill.description} ${skill.description_zh}`.toLowerCase().includes(filter.toLowerCase())) ?? []
  return <section className="space-y-4 p-4" aria-label={zh ? '科学方法库' : 'Scientific methods'}>
    <div><h2 className="font-semibold">{zh ? '科学方法库' : 'Scientific methods'}</h2><p className="mt-1 text-sm text-text-secondary">{zh ? '在任务计划中选择方法。每次运行冻结方法版本、原文与校验值；交付时检查格式和实际工具引用，科学结论仍需复核。' : 'Select methods in the task plan. Each run freezes instructions, version and checksum. Deliveries are checked for format and actual tool references; scientific conclusions still need review.'}</p></div>
    <Input aria-label={zh ? '搜索科学方法' : 'Search scientific methods'} placeholder={zh ? '证据、实验设计、结构、统计…' : 'Evidence, experiment design, structure, statistics…'} value={filter} onChange={(event) => setFilter(event.target.value)} />
    {skills.isPending ? <p role="status">{zh ? '加载方法库…' : 'Loading methods…'}</p> : null}
    {skills.isError ? <div role="alert"><p>{zh ? '方法库暂时不可用。' : 'The method library is unavailable.'}</p><Button type="button" variant="outline" onClick={() => void skills.refetch()}>{zh ? '重新加载' : 'Reload'}</Button></div> : null}
    {skills.isSuccess && matches.length === 0 ? <p>{zh ? '没有匹配的方法。' : 'No matching methods.'}</p> : null}
    <div className="grid gap-3 xl:grid-cols-2">{matches.map((skill) => <article key={skill.id} className="min-w-0 space-y-2 rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium">{zh ? skill.title_zh : skill.title}</h3><span className="text-xs text-text-muted">v{skill.version}</span></div>
      <p className="text-sm text-text-secondary">{zh ? skill.description_zh : skill.description}</p>
      <SkillDetails skill={skill} />
    </article>)}</div>
  </section>
}

export function ProceduralSkillSelector({ serviceKind, value, onChange, disabled = false }: {
  serviceKind: string
  value: string[] | null
  onChange: (value: string[] | null) => void
  disabled?: boolean
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const skills = useQuery({ queryKey: ['copilot-procedural-skills'], queryFn: listProceduralSkills })
  const selected = value ?? skills.data?.filter((skill) => skill.default_for.includes(serviceKind)).map((skill) => skill.id) ?? []
  return <fieldset className="space-y-2 rounded-md border border-border p-3" disabled={disabled}>
    <legend className="px-1 text-sm font-medium">{zh ? '应用科学方法（最多 3 项）' : 'Applied scientific methods (up to 3)'}</legend>
    <p className="text-xs text-text-secondary">{zh ? '方法指导分析步骤，不增加工具权限或费用额度。新方法包含结构化交付检查，效果需在项目中验证。' : 'Methods guide analysis without granting tools or increasing the budget. Structured delivery checks apply; effectiveness needs project validation.'}</p>
    {skills.isPending ? <p role="status">{zh ? '加载建议方法…' : 'Loading suggested methods…'}</p> : null}
    {skills.isError ? <div role="status"><p className="text-sm">{zh ? '无法显示方法。启动时将沿用服务的默认方法；也可选择不使用方法。' : 'Methods could not load. Starting uses the service defaults, or you can opt out below.'}</p><Button type="button" size="sm" variant="ghost" onClick={() => void skills.refetch()}>{zh ? '重试' : 'Retry'}</Button></div> : null}
    <div className="grid gap-2 md:grid-cols-2">{skills.data?.map((skill) => <label key={skill.id} className="flex items-start gap-2 text-sm">
      <Checkbox checked={selected.includes(skill.id)} disabled={disabled || (!selected.includes(skill.id) && selected.length >= 3)} onCheckedChange={(checked) => onChange(checked ? [...selected, skill.id] : selected.filter((id) => id !== skill.id))} />
      <span>{zh ? skill.title_zh : skill.title}<small className="ml-1 text-text-muted">v{skill.version}</small></span>
    </label>)}</div>
    <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => onChange(null)}>{zh ? '使用推荐' : 'Use recommended'}</Button><Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => onChange([])}>{zh ? '不使用方法包' : 'No method packages'}</Button></div>
    <p className="text-xs text-text-muted">{value === null ? (zh ? '使用该任务类型的推荐方法。' : 'Using recommendations for this task type.') : (zh ? `已明确选择 ${selected.length} 项方法。` : `${selected.length} methods explicitly selected.`)}</p>
  </fieldset>
}

export function AppliedProceduralSkills({ contract, outcome }: { contract: Record<string, unknown>; outcome: Record<string, unknown> }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const snapshots = Array.isArray(contract.procedural_skills) ? contract.procedural_skills.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object') : []
  const outputs = outcome.skill_outputs && typeof outcome.skill_outputs === 'object' ? outcome.skill_outputs as Record<string, unknown> : {}
  if (!snapshots.length) return null
  return <Disclosure title={zh ? '本次运行的科学方法与交付' : 'Scientific methods and delivery for this run'}>
    <div className="space-y-3 py-2">{snapshots.map((skill) => <div key={String(skill.id)} className="space-y-1 rounded-md border border-border p-3 text-sm">
      <p className="font-medium">{String(zh ? skill.title_zh : skill.title)} · v{String(skill.version)}</p>
      <p className="break-all text-xs text-text-muted">SHA-256: {String(skill.checksum_sha256)}</p>
      {outputs[String(skill.id)] && typeof outputs[String(skill.id)] === 'object' ? <dl className="space-y-2">{Object.entries(outputs[String(skill.id)] as Record<string, unknown>).map(([key, entry]) => <div key={key}><dt className="text-xs font-medium text-text-secondary">{key.replaceAll('_', ' ')}</dt><dd className="whitespace-pre-wrap break-words">{Array.isArray(entry) ? entry.map(String).join('\n') || '—' : String(entry)}</dd></div>)}</dl> : <p className="text-text-secondary">{zh ? '尚无通过格式及引用检查的方法交付。' : 'No method delivery has passed format and reference checks yet.'}</p>}
      <Disclosure title={zh ? '查看冻结的方法原文' : 'Inspect frozen instructions'}><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-xs">{String(skill.instructions)}</pre></Disclosure>
    </div>)}</div>
  </Disclosure>
}
