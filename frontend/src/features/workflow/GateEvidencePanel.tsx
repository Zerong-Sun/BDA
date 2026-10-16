import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../../components/ui/accordion'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../components/ui/select'
import { Checkbox } from '../../components/ui/checkbox'
import { useI18n } from '../../lib/i18n'
import { managesProject, useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { listProjectArtifacts } from '../../lib/api/artifacts'
import { ingestLiterature } from '../../lib/api/copilot'
import { getEvidenceSourceRetrieval } from '../../lib/api/evidenceNotes'
import { scientificGates, scientificSources, saveScientificEvidence, reviewScientificEvidence,
  type ScientificGate, type ScientificSource, type ScientificEvidenceInput } from '../../lib/api/scientificGates'

const split = (value: string) => value.split(/[,，\n]/).map(x => x.trim()).filter(Boolean)
const blockerText: Record<string, [string, string]> = {
  scientific_evidence_approval_required: ['缺少与当前参数绑定的科学审阅', 'Current parameters need scientific approval'],
  scientific_evidence_stale: ['工作流或参数已改变，请重新提交依据', 'Workflow or parameters changed; submit new evidence'],
  scientific_parameters_incomplete: ['参数依据不完整', 'Incomplete parameter coverage'],
  scientific_calibration_required: ['缺少本地对照校准', 'Local control calibration is missing'],
  scientific_method_scope_mismatch: ['算法或版本与当前工作流不符', 'Method or version differs from the workflow'],
  scientific_source_method_mismatch: ['论文适用方法与参数方法不符', 'Source method scope differs'],
  scientific_source_changed: ['原文内容已改变，需要重新核对', 'Source text changed; review again'],
  scientific_calibration_changed: ['校准文件已改变，需要重新核对', 'Calibration changed; review again'],
  scientific_parameter_value_mismatch: ['参数值与当前配置不符', 'Parameter value differs'],
}
export function GateEvidencePanel({ workflowId, edgeId, canWrite, readOnly }: {
  workflowId: string; edgeId: string; canWrite: boolean; readOnly: boolean
}) {
  const { language } = useI18n(); const zh = language === 'zh'
  const data = useQuery({ queryKey: ['scientific-gates', workflowId], queryFn: () => scientificGates(workflowId) })
  const gate = data.data?.items.find(x => x.edge_id === edgeId)
  return <section aria-label={zh ? '文献与参数依据' : 'Scientific parameter evidence'} className="my-4 grid gap-3 rounded border border-border-soft p-3">
    <h3 className="font-semibold">{zh ? '文献与参数依据' : 'Scientific parameter evidence'}</h3>
    {data.isPending ? <p>{zh ? '正在读取门控证据…' : 'Loading gate evidence…'}</p> : null}
    {data.isError ? <div role="alert">{zh ? '无法读取依据，不能据此判断已通过。' : 'Evidence unavailable; approval cannot be assumed.'}<Button type="button" size="sm" onClick={() => data.refetch()}>{zh ? '重新读取依据' : 'Reload evidence'}</Button></div> : null}
    {gate ? <EvidenceForm key={`${workflowId}:${gate.binding.project_id}:${edgeId}:${gate.binding.workflow_version}:${gate.binding.parameter_hash}`} gate={gate} workflowId={workflowId} canWrite={canWrite && !readOnly} /> : !data.isPending && !data.isError ? <p>{zh ? '请先保存连线，才能绑定参数依据。' : 'Save the connection before binding evidence.'}</p> : null}
  </section>
}
function EvidenceForm({ gate, workflowId, canWrite }: { gate: ScientificGate; workflowId: string; canWrite: boolean }) {
  const { language } = useI18n(); const zh = language === 'zh'
  const cache = useQueryClient()
  const access = useProjectAccess(gate.binding.project_id)
  const canReview = canWrite && managesProject(access.data)
  const [query, setQuery] = useState(''); const [sourceQuery, setSourceQuery] = useState<string | null>(null)
  const [selected, setSelected] = useState<Array<ScientificSource & { supported_methods: string[] }>>([])
  const [details, setDetails] = useState<Record<string, { unit: string; meaning: string }>>({})
  const [applicability, setApplicability] = useState('')
  const [report, setReport] = useState(''); const [raw, setRaw] = useState<string[]>([])
  const [positive, setPositive] = useState(''); const [negative, setNegative] = useState('')
  const [construct, setConstruct] = useState(''); const [protocol, setProtocol] = useState('')
  const [criteria, setCriteria] = useState(''); const [summary, setSummary] = useState('')
  const [rationale, setRationale] = useState(''); const [searchId, setSearchId] = useState('')
  const [notice, setNotice] = useState('')
  const sources = useQuery({ queryKey: ['scientific-sources', workflowId, gate.edge_id, sourceQuery],
    queryFn: () => scientificSources(workflowId, gate.edge_id, sourceQuery || ''), enabled: sourceQuery !== null })
  const artifacts = useQuery({ queryKey: ['project-artifacts', gate.binding.project_id],
    queryFn: () => listProjectArtifacts(gate.binding.project_id), enabled: canWrite })
  const retrieval = useQuery({ queryKey: ['gate-literature-search', searchId], queryFn: () => getEvidenceSourceRetrieval(searchId), enabled: !!searchId,
    refetchInterval: query => ['pending', 'running'].includes(query.state.data?.search.status ?? 'pending') ? 3000 : false })
  const retrievalStatus = retrieval.data?.search.status
  useEffect(() => {
    if (retrievalStatus === 'succeeded' || retrievalStatus === 'completed') {
      void cache.invalidateQueries({ queryKey: ['scientific-sources', workflowId, gate.edge_id] })
    }
  }, [retrievalStatus, cache, workflowId, gate.edge_id])
  const refresh = async () => {
    await cache.invalidateQueries({ queryKey: ['scientific-gates', workflowId] })
    await cache.invalidateQueries({ queryKey: ['workflow-preflight', workflowId] })
  }
  const search = useMutation({ mutationFn: () => ingestLiterature(gate.binding.project_id, query, 5),
    onSuccess: row => { setSourceQuery(''); setSearchId(row.id); setNotice(zh ? '文献检索已提交；找到论文不代表参数已经获得支持。' : 'Search submitted; a matching paper does not establish parameter support.') } })
  const save = useMutation({ mutationFn: () => {
    const body: ScientificEvidenceInput = { workflow_version: gate.binding.workflow_version,
      sources: selected.map(({ document_id, chunk_id, quote, locator, supported_methods }) => ({ document_id, chunk_id, quote, locator, supported_methods })),
      parameters: Object.entries(gate.binding.required_parameters).map(([path, value]) => ({ path, value,
        unit: details[path]?.unit ?? '', meaning: details[path]?.meaning ?? '',
        method_key: gate.binding.required_methods[path]?.method_key ?? '', method_version: gate.binding.required_methods[path]?.method_version ?? '',
        source_indexes: selected.map((_, i) => i) })), applicability,
      calibration: report ? { artifact_id: report, raw_data_artifact_ids: raw, positive_controls: split(positive), negative_controls: split(negative), construct, protocol, acceptance_criteria: criteria, summary } : null }
    return saveScientificEvidence(workflowId, gate.edge_id, body)
  }, onSuccess: async () => { setNotice(zh ? '候选依据已保存，尚未授权自动放行。' : 'Candidate evidence saved; automatic release is not authorized.'); await refresh() } })
  const review = useMutation({ mutationFn: ({ id, decision }: { id: string; decision: 'approve' | 'reject' }) =>
    reviewScientificEvidence(workflowId, gate.edge_id, id, { workflow_version: gate.binding.workflow_version, decision, rationale }),
  onSuccess: async () => { setNotice(zh ? '审阅决定已保存。' : 'Review decision saved.'); await refresh() } })
  const explain = (reason: string) => blockerText[reason]?.[zh ? 0 : 1] ?? reason
  const entries = Object.entries(gate.binding.required_parameters)
  const ready = selected.length > 0 && selected.every(x => x.supported_methods.length && x.quote.length >= 12 && x.locator.length >= 3)
    && entries.length > 0 && entries.every(([path]) => details[path]?.unit.trim() && (details[path]?.meaning.trim().length ?? 0) >= 12) && applicability.trim().length >= 20
  const text = (label: string, value: string, set: (s: string) => void, placeholder = '') => <label className="grid gap-1 text-xs">{label}<Textarea aria-label={label} value={value} onChange={e => set(e.target.value)} placeholder={placeholder} className="min-h-16 w-full rounded border bg-surface-2 p-2" /></label>
  return <div className="grid gap-3">
    <p className="text-xs">{gate.required ? (gate.allowed ? (zh ? '当前自动门控已有有效审阅' : 'Automatic gate has a current approval') : (zh ? '自动门控待审，执行阶段会阻断' : 'Automatic gate is held at execution')) : (zh ? '当前为人工/依赖门；切换自动门后需要重新绑定审阅。' : 'Manual/dependency mode; automatic mode requires a new bound review.')}</p>
    {gate.blockers.map(x => <p key={x} className="text-xs text-danger">{explain(x)}</p>)}
    <Accordion><AccordionItem value="parameters"><AccordionTrigger>{zh ? '当前参数与算法' : 'Current parameters and methods'}</AccordionTrigger><AccordionContent>
      {entries.map(([path, value]) => <div key={path} className="my-2 break-all text-xs"><strong>{path}</strong><p>{JSON.stringify(value)}</p><p>{gate.binding.required_methods[path]?.method_key || '—'} · {gate.binding.required_methods[path]?.method_version || '—'}</p></div>)}
      {!entries.length ? <p>{zh ? '当前连线没有可绑定的筛选参数。' : 'No screening parameters are available.'}</p> : null}
    </AccordionContent></AccordionItem></Accordion>
    <label className="grid gap-1 text-xs">{zh ? '论文检索词' : 'Paper search query'}<Input aria-label={zh ? '论文检索词' : 'Paper search query'} value={query} onChange={e => setQuery(e.target.value)} placeholder="RFdiffusion interaction PAE" /></label>
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => setSourceQuery(query)}>{zh ? '查找项目原文' : 'Search imported sources'}</Button>
      <Button size="sm" variant="outline" disabled={!canWrite || query.trim().length < 3 || search.isPending || ['pending', 'running'].includes(retrievalStatus ?? '')} onClick={() => search.mutate()}>{zh ? '检索论文并获取原文' : 'Find papers and retrieve text'}</Button>
    </div>
    {retrieval.data ? <p className="text-xs">{zh ? '论文检索' : 'Literature search'}: {retrievalStatus} · {retrieval.data.search.result_count} {retrieval.data.search.error || ''}</p> : null}
    {sources.isFetching ? <p>{zh ? '正在查找原文…' : 'Searching sources…'}</p> : null}
    {sources.data?.items.length === 0 ? <p>{zh ? '没有匹配原文；可修改检索词或从外部获取论文。' : 'No source match; revise the query or retrieve papers.'}</p> : null}
    <div className="grid max-h-64 gap-2 overflow-auto">{sources.data?.items.map(source => <article key={source.chunk_id} className="rounded border p-2 text-xs"><strong>{source.title}</strong><p className="line-clamp-4 whitespace-pre-wrap">{source.quote}</p><p>{source.locator}</p>{source.url && /^https?:\/\//.test(source.url) ? <a href={source.url} target="_blank" rel="noreferrer">{zh ? '来源' : 'Source'}</a> : null}<Button size="sm" variant="outline" disabled={!canWrite || selected.some(x => x.chunk_id === source.chunk_id)} onClick={() => setSelected(s => [...s, { ...source, supported_methods: [] }])}>{zh ? '选为待审依据' : 'Select candidate source'}</Button></article>)}</div>
    {canWrite ? <Accordion defaultValue={['candidate']}><AccordionItem value="candidate"><AccordionTrigger>{zh ? '整理参数依据与本地校准' : 'Prepare parameter evidence and local calibration'}</AccordionTrigger><AccordionContent><div className="mt-3 grid gap-3">
      <p className="text-xs">{zh ? '保存的是待审候选。论文适用范围和校准结论须由项目管理员核验；无需填造缺失的校准。' : 'Save a candidate for review. A project administrator must verify applicability and calibration; leave unavailable calibration empty.'}</p>
      {selected.map((source, index) => <div key={source.chunk_id} className="grid gap-2 border p-2"><strong>{source.title}</strong>
        {text(zh ? `原文摘录 ${index + 1}` : `Source quote ${index + 1}`, source.quote, quote => setSelected(s => s.map((x, i) => i === index ? { ...x, quote } : x)))}
        <label>{zh ? '原文定位' : 'Source locator'}<Input value={source.locator} onChange={e => setSelected(s => s.map((x, i) => i === index ? { ...x, locator: e.target.value } : x))} /></label>
        <label>{zh ? '论文适用方法（逗号分隔）' : 'Methods supported by the paper (comma separated)'}<Input value={source.supported_methods.join(', ')} onChange={e => setSelected(s => s.map((x, i) => i === index ? { ...x, supported_methods: split(e.target.value) } : x))} /></label>
        <Button size="sm" variant="ghost" onClick={() => setSelected(s => s.filter((_, i) => i !== index))}>{zh ? '取消选择' : 'Remove source'}</Button></div>)}
      {entries.map(([path, value]) => <fieldset key={path} className="grid gap-2 border p-2"><legend className="break-all text-xs">{path}</legend><p className="break-all text-xs">{JSON.stringify(value)}</p>
        <label>{zh ? '单位或尺度' : 'Unit or scale'}<Input aria-label={`${path} ${zh ? '单位或尺度' : 'unit'}`} value={details[path]?.unit || ''} onChange={e => setDetails(s => ({ ...s, [path]: { unit: e.target.value, meaning: s[path]?.meaning || '' } }))} /></label>
        {text(`${path} ${zh ? '科学含义与依据' : 'scientific rationale'}`, details[path]?.meaning || '', meaning => setDetails(s => ({ ...s, [path]: { unit: s[path]?.unit || '', meaning } })))}
      </fieldset>)}
      {text(zh ? '适用条件与限制' : 'Applicability and limitations', applicability, setApplicability)}
      <div>{zh ? '本地校准报告（可暂缺）' : 'Local calibration report (optional for drafts)'}<Select value={report} items={[{ value: '', label: zh ? '尚无校准，保持待审' : 'No calibration; keep pending' }, ...(artifacts.data ?? []).map(x => ({ value: x.id, label: x.filename }))]} onValueChange={value => { setReport(value ?? ''); setRaw([]) }}><SelectTrigger aria-label={zh ? '本地校准报告' : 'Local calibration report'} className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="">{zh ? '尚无校准，保持待审' : 'No calibration; keep pending'}</SelectItem>{artifacts.data?.map(x => <SelectItem key={x.id} value={x.id}>{x.filename}</SelectItem>)}</SelectContent></Select></div>
      {report ? <>
        <fieldset className="grid gap-2"><legend>{zh ? '校准原始数据（可多选）' : 'Raw calibration data (multiple)'}</legend>{artifacts.data?.filter(x => x.id !== report && x.artifact_type !== 'analysis_report').map(x => <label key={x.id} className="flex items-center gap-2"><Checkbox checked={raw.includes(x.id)} onCheckedChange={checked => setRaw(ids => checked ? [...ids, x.id] : ids.filter(id => id !== x.id))} />{x.filename}</label>)}</fieldset>
        {text(zh ? '正对照标识' : 'Positive control identifiers', positive, setPositive)}{text(zh ? '负对照标识' : 'Negative control identifiers', negative, setNegative)}
        {text(zh ? '构建与样品身份' : 'Construct and sample identity', construct, setConstruct)}{text(zh ? '校准协议与版本' : 'Calibration protocol and version', protocol, setProtocol)}
        {text(zh ? '校准通过标准' : 'Calibration acceptance criteria', criteria, setCriteria)}{text(zh ? '校准结果及局限' : 'Calibration results and limitations', summary, setSummary)}
      </> : null}
      <Button size="sm" disabled={!ready || save.isPending} onClick={() => save.mutate()}>{zh ? '保存待审依据' : 'Save candidate evidence'}</Button>
    </div></AccordionContent></AccordionItem></Accordion> : null}
    <h4 className="font-medium">{zh ? '依据版本与审阅历史' : 'Evidence versions and review history'}</h4>
    {gate.items.length === 0 ? <p className="text-xs">{zh ? '尚未保存参数依据。' : 'No parameter evidence saved.'}</p> : null}
    {gate.items.map(item => <article key={item.id} className="grid gap-2 rounded border p-2 text-xs"><strong>{item.approved ? (zh ? '审阅有效' : 'Current approval') : (zh ? '未授权自动放行' : 'Automatic release not authorized')}</strong><p>{item.created_at}</p><p className="whitespace-pre-wrap">{item.evidence.applicability}</p>{item.sources.map((s, i) => <p key={i}>{s.title} · {s.locator}</p>)}{item.issues.map(x => <p key={x}>{explain(x)}</p>)}{item.review ? <p>{item.review.decision} · {item.review.rationale} · {item.review.created_at}</p> : null}
      {canReview ? <div className="flex gap-2"><Button size="sm" variant="outline" disabled={item.issues.length > 0 || rationale.trim().length < 20 || review.isPending} onClick={() => review.mutate({ id: item.id, decision: 'approve' })}>{zh ? '管理员确认依据' : 'Administrator approval'}</Button><Button size="sm" variant="outline" disabled={rationale.trim().length < 20 || review.isPending} onClick={() => review.mutate({ id: item.id, decision: 'reject' })}>{zh ? '管理员驳回依据' : 'Administrator rejection'}</Button></div> : null}</article>)}
    {canReview && gate.items.length > 0 ? text(zh ? '审阅理由（至少20字）' : 'Review rationale (at least 20 characters)', rationale, setRationale) : null}
    {notice ? <p role="status" className="text-xs">{notice}</p> : null}
    {[sources.error, search.error, retrieval.error, save.error, review.error, artifacts.error, access.error].filter(Boolean).map((error, i) => <p key={i} role="alert" className="text-danger">{error?.message}</p>)}
  </div>
}
