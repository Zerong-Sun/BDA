import { Children, isValidElement, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Checkbox } from '../components/ui/checkbox'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/textarea'
import { Disclosure } from '../components/ui/Disclosure'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { DataGrid } from '../components/reui/data-grid/data-grid'
import { DataGridTable } from '../components/reui/data-grid/data-grid-table'
import { Button } from '../components/ui/Button'
import { useI18n } from '../lib/i18n'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useAppStore } from '../lib/store/appStore'
import { listAllCandidates } from '../lib/api/candidates'
import { ArtifactUploadDropzone } from '../features/artifacts/ArtifactUploadDropzone'
import { listProjectArtifacts } from '../lib/api/artifacts'
import { listResearchGoals } from '../lib/api/researchGoals'
import { getProjectAccess } from '../lib/api/projects'
import * as learning from '../lib/api/learning'
import type { ObservationCreate, StudyCreate } from '../lib/api/generated/types.gen'
import './learning.css'

const values = (event: FormEvent<HTMLFormElement>) => new FormData(event.currentTarget)
const text = (data: FormData, key: string) => String(data.get(key) ?? '').trim()
const numeric = (data: FormData, key: string) => Number(text(data, key))
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(object) : []
const numberLabel = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(4) : '—'

function Choice({ children, name, value, onChange, required }: {
  children: ReactNode; name?: string; value?: string; required?: boolean;
  onChange?: (event: { target: { value: string } }) => void;
}) {
  const options = Children.toArray(children).filter(isValidElement<{ value?: string; children: ReactNode }>).map((child) => ({
    value: child.props.value ?? String(child.props.children), label: child.props.children,
  }))
  const [chosen, setChosen] = useState('')
  const selected = value ?? (options.some((o) => o.value === chosen) ? chosen : options[0]?.value ?? '')
  return <Select name={name} required={required} value={selected} onValueChange={(next) => {
    if (next === null) return
    setChosen(next); onChange?.({ target: { value: next } })
  }} items={options}>
    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
    <SelectContent>{options.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
  </Select>
}

function LearningTable({ headings, cells }: { headings: string[]; cells: ReactNode[][] }) {
  const table = useReactTable<ReactNode[]>({ data: cells, columns: headings.map((header, index) => ({
    id: String(index), header, cell: ({ row }) => row.original[index],
  })), getCoreRowModel: getCoreRowModel() })
  return <DataGrid table={table} recordCount={cells.length}><DataGridTable /></DataGrid>
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="learning-field"><span>{label}</span>{children}</label>
}
function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="learning-section"><h2>{title}</h2>{children}</section>
}
function JsonDetails({ label, data }: { label: string; data: unknown }) {
  return <Disclosure className="learning-details" title={label}><pre>{JSON.stringify(data, null, 2)}</pre></Disclosure>
}

export function LearningPage() {
  const { projectId } = useProjectContext()
  // A project change unmounts drafts and selections before new data is loaded.
  return projectId ? <LearningWorkbench key={projectId} projectId={projectId} /> : null
}

function LearningWorkbench({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const copy = (cn: string, en: string) => zh ? cn : en
  const cache = useQueryClient()
  const demo = useAppStore((state) => state.appMode) === 'demo'
  const [studyId, setStudyId] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [failure, setFailure] = useState('')
  const [selectedResults, setSelectedResults] = useState<string[]>([])
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, string>>({})
  const [measurementStatus, setMeasurementStatus] = useState<ObservationCreate['status']>('measured')
  const access = useQuery({ queryKey: ['project-access', projectId], queryFn: () => getProjectAccess(projectId) })
  const query = useQuery({ queryKey: ['learning-workspace', projectId], queryFn: async () => {
    const [assays, studies, datasets, models, decisions, results, candidates, artifacts, goals] = await Promise.all([
      learning.listLearning(projectId, 'assays'), learning.listLearning(projectId, 'studies'),
      learning.listLearning(projectId, 'datasets'), learning.listLearning(projectId, 'models'),
      learning.listLearning(projectId, 'decisions'), learning.listLearningResults(projectId),
      listAllCandidates(projectId, { limit: 200 }), listProjectArtifacts(projectId), listResearchGoals(projectId),
    ])
    return { assays, studies, datasets, models, decisions, results, candidates: candidates.items, artifacts, goals }
  } })
  const writable = !demo && access.data?.permissions.write === true
  const experimentWritable = !demo && access.data?.permissions.experiment === true
  const data = query.data
  const study = data?.studies.find((row) => row.id === studyId) ?? data?.studies[0]
  const assay = data?.assays.find((row) => row.id === study?.assay_id)
  const datasets = data?.datasets.filter((row) => row.study_id === study?.id) ?? []
  const models = data?.models.filter((row) => row.study_id === study?.id) ?? []
  const decisions = data?.decisions.filter((row) => row.study_id === study?.id) ?? []
  const observations = data?.results.filter((row) => object(row.result_metadata.learning).assay_id === assay?.id) ?? []
  const measuredValue = !['failed', 'missing'].includes(measurementStatus)

  async function perform(action: () => Promise<unknown>) {
    if (busy) return
    setBusy(true); setFailure(''); setNotice('')
    try {
      await action()
      await cache.invalidateQueries({ queryKey: ['learning-workspace', projectId] })
      await cache.invalidateQueries({ queryKey: ['timeline', projectId] })
      setNotice(copy('已保存，可继续下一步。', 'Saved. Continue when ready.'))
    } catch (error) {
      const detail = object(error).detail
      setFailure(typeof detail === 'string' ? detail : error instanceof Error ? error.message : copy('操作失败，请刷新后重试。', 'Request failed. Refresh before retrying.'))
    } finally { setBusy(false) }
  }
  function submit(event: FormEvent<HTMLFormElement>, action: (form: FormData) => Promise<unknown>) {
    event.preventDefault()
    const form = values(event)
    void perform(() => action(form))
  }
  async function download(decisionId: string) {
    const evidence = await learning.exportLearningDecision(projectId, decisionId)
    const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url; link.download = `learning-evidence-${decisionId}.json`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <div className="learning-workbench" data-tour-id="learning-page">
    <header className="learning-header">
      <span className="learning-eyebrow">ITERAVIA · 2.6 PREVIEW</span>
      <h1>{copy('项目学习工作台', 'Project learning workbench')}</h1>
      <p>{copy('把每轮实验变成下一轮决策的依据。', 'Turn each experimental round into evidence for the next decision.')}</p>
      <p className="learning-limit">{copy('当前提供可复现的单测定基线。模型提升表示通过回顾性检查；实验效果仍需前瞻验证。', 'A reproducible single-assay baseline. Promotion passes retrospective checks; experimental benefit still needs prospective validation.')}</p>
    </header>
    <ol className="learning-steps">{[copy('定义目标与测定', 'Define goal & assay'), copy('录入与冻结证据', 'Record & freeze evidence'), copy('评估项目模型', 'Evaluate project model'), copy('审阅下一批实验', 'Review the next batch')].map((label, index) => <li key={label}><span>{index + 1}</span>{label}</li>)}</ol>
    {(query.isPending || access.isPending) && <p role="status">{copy('正在读取项目证据…', 'Loading project evidence…')}</p>}
    {(query.isError || access.isError) && <div role="alert"><p>{copy('项目数据加载失败，操作已暂停。', 'Project data could not be loaded. Actions are paused.')}</p><Button type="button" variant="outline" onClick={() => { void query.refetch(); void access.refetch() }}>{copy('重试', 'Retry')}</Button></div>}
    {failure && <div role="alert" className="learning-message">{failure}<Button type="button" variant="outline" onClick={() => void query.refetch()}>{copy('刷新数据', 'Refresh data')}</Button></div>}
    {notice && <p role="status" className="learning-message">{notice}</p>}
    {data && !query.isError && !access.isError && <>
      {!writable && <p>{copy('当前为只读模式。', 'You have read-only access.')}</p>}
      <Section title={copy('01 · 目标与测定契约', '01 · Goal and assay contract')}>
        <div className="learning-grid">
          <Disclosure defaultOpen={!data.assays.length} title={copy('新建测定方法', 'Define an assay')}>
            <form onSubmit={(event) => submit(event, (form) => learning.createAssay(projectId, { name: text(form, 'name'), method: text(form, 'method'), unit: text(form, 'unit'), conditions: { context: text(form, 'conditions') } }))}>
              <fieldset disabled={!experimentWritable || busy}>
                <Field label={copy('测定名称', 'Assay name')}><Input name="name" required maxLength={200} /></Field>
                <Field label={copy('方法、仪器与处理方式', 'Method, instrument and processing')}><Textarea name="method" required maxLength={4000} /></Field>
                <Field label={copy('单位（例如 nM）', 'Unit (for example nM)')}><Input name="unit" required maxLength={40} /></Field>
                <Field label={copy('条件与对照', 'Conditions and controls')}><Textarea name="conditions" required maxLength={3000} /></Field>
                <Button type="submit">{copy('保存测定', 'Save assay')}</Button>
              </fieldset>
            </form>
          </Disclosure>
          <Disclosure defaultOpen={!data.studies.length} title={copy('新建学习目标', 'Create a learning study')}>
            {!data.goals.length && <p><Link to={`/research?project=${projectId}`}>{copy('先在研究页面建立项目目标', 'Create a project goal in Research first')}</Link></p>}
            <form onSubmit={(event) => submit(event, async (form) => {
              const created = await learning.createStudy(projectId, { name: text(form, 'name'), assay_id: text(form, 'assay'), research_goal_id: text(form, 'goal'), direction: text(form, 'direction') as StudyCreate['direction'], threshold: text(form, 'threshold') ? numeric(form, 'threshold') : null, currency: text(form, 'currency') as StudyCreate['currency'], batch_budget_cents: Math.round(numeric(form, 'budget') * 100), max_batch_size: numeric(form, 'size') })
              setStudyId(created.id); setSelectedResults([]); setSelectedCandidates({})
            })}>
              <fieldset disabled={!writable || busy || !data.assays.length || !data.goals.length}>
                <Field label={copy('学习目标名称', 'Study name')}><Input name="name" required maxLength={200} /></Field>
                <Field label={copy('研究目标', 'Research goal')}><Choice name="goal" required>{data.goals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}</Choice></Field>
                <Field label={copy('测定契约', 'Assay contract')}><Choice name="assay" required>{data.assays.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.unit}</option>)}</Choice></Field>
                <Field label={copy('优化方向', 'Optimization direction')}><Choice name="direction"><option value="maximize">{copy('越大越好', 'Maximize')}</option><option value="minimize">{copy('越小越好', 'Minimize')}</option></Choice></Field>
                <Field label={copy('目标阈值（可选）', 'Target threshold (optional)')}><Input name="threshold" type="number" step="any" /></Field>
                <div className="learning-grid"><Field label={copy('每批预算', 'Budget per batch')}><Input name="budget" type="number" min="0.01" max="1000000" step="0.01" required /></Field><Field label={copy('币种', 'Currency')}><Choice name="currency">{['USD', 'EUR', 'GBP', 'CNY'].map((c) => <option key={c}>{c}</option>)}</Choice></Field></div>
                <Field label={copy('每批最多候选数', 'Maximum candidates per batch')}><Input name="size" type="number" min="1" max="96" defaultValue="12" required /></Field>
                <Button type="submit">{copy('冻结目标与预算', 'Freeze goal and budget')}</Button>
              </fieldset>
            </form>
          </Disclosure>
        </div>
        {study && <Field label={copy('当前学习目标', 'Current study')}><Choice value={study.id} onChange={(event) => { setStudyId(event.target.value); setSelectedResults([]); setSelectedCandidates({}) }}>{data.studies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Choice></Field>}
        {study && <p>{assay?.name} · {assay?.unit} · {study.direction === 'maximize' ? copy('最大化', 'Maximize') : copy('最小化', 'Minimize')} · {study.currency} {(study.batch_budget_cents / 100).toFixed(2)} / {copy('批', 'batch')} · ≤ {study.max_batch_size} {copy('个候选', 'candidates')}</p>}
        {study && <JsonDetails label={copy('查看冻结目标与测定依据', 'Inspect frozen goal and assay')} data={{ study, assay }} />}
      </Section>
      {study && assay && <>
        <Section title={copy('02 · 实验结果与冻结数据集', '02 · Observations and frozen datasets')}>
          <Disclosure title={copy('上传原始实验文件', 'Upload source experimental data')}>
            <ArtifactUploadDropzone projectId={projectId} disabled={busy} readOnly={demo || access.data?.permissions.artifact !== true} onUploaded={() => { void cache.invalidateQueries({ queryKey: ['learning-workspace', projectId] }) }} />
          </Disclosure>
          <Disclosure title={copy('录入实验结果', 'Record an observation')}>
            <p>{copy('先把原始文件上传至项目；方法或条件变化时建立新测定。重复编号表示同一次生物学重复，技术重复使用相同编号。', 'Upload the source file to the project first. Use a new assay when methods or conditions change. Replicate keys identify a biological replicate; technical repeats share that key.')}</p>
            <form onSubmit={(event) => submit(event, (form) => learning.createObservation(projectId, { assay_id: assay.id, candidate_id: text(form, 'candidate'), source_artifact_id: text(form, 'artifact'), batch_key: text(form, 'batch'), replicate_key: text(form, 'replicate'), replicate_type: text(form, 'replicateType') as ObservationCreate['replicate_type'], status: measurementStatus, value: measuredValue ? numeric(form, 'value') : null, unit: assay.unit, qc_accepted: form.get('qc') === 'on', note: text(form, 'note') }))}>
              <fieldset disabled={!experimentWritable || busy || !data.candidates.length || !data.artifacts.some((a) => a.status === 'available')}>
                <div className="learning-grid">
                  <Field label={copy('候选', 'Candidate')}><Choice name="candidate" required>{data.candidates.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Choice></Field>
                  <Field label={copy('原始证据文件', 'Source artifact')}><Choice name="artifact" required>{data.artifacts.filter((a) => a.status === 'available').map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}</Choice></Field>
                  <Field label={copy('实验批次', 'Batch')}><Input name="batch" required maxLength={200} /></Field>
                  <Field label={copy('生物学重复编号', 'Biological replicate key')}><Input name="replicate" required maxLength={120} /></Field>
                  <Field label={copy('重复类型', 'Replicate type')}><Choice name="replicateType"><option value="biological">{copy('生物学重复', 'Biological')}</option><option value="technical">{copy('技术重复', 'Technical')}</option></Choice></Field>
                  <Field label={copy('结果状态', 'Result status')}><Choice value={measurementStatus} onChange={(event) => setMeasurementStatus(event.target.value as ObservationCreate['status'])}>{(['measured', 'failed', 'below_limit', 'above_limit', 'missing'] as const).map((s, i) => <option key={s} value={s}>{zh ? ['测得数值', '实验失败', '低于检测限', '高于检测限', '数据缺失'][i] : s.replaceAll('_', ' ')}</option>)}</Choice></Field>
                  {measuredValue && <Field label={`${copy('测量值 / 检测限', 'Value / detection limit')} (${assay.unit})`}><Input name="value" type="number" step="any" required /></Field>}
                </div>
                <Field label={copy('结果说明与质控依据', 'Result notes and QC rationale')}><Textarea name="note" required maxLength={2000} /></Field>
                <label className="learning-check"><Checkbox name="qc" />{copy('已检查原始证据，质控通过', 'Source evidence checked; QC accepted')}</label>
                <Button type="submit">{copy('保存实验结果', 'Save observation')}</Button>
              </fieldset>
            </form>
          </Disclosure>
          {!observations.length ? <p>{copy('当前测定还没有结果。', 'No observations for this assay yet.')}</p> : <>
            <p>{copy('选择本轮纳入审查的结果（最多 256 条）；失败、检测限和未通过质控的结果会保留并注明排除原因。', 'Select up to 256 observations for review. Failed, censored and unaccepted results remain in the manifest with exclusion reasons.')}</p>
            <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('纳入', 'Include'), copy('候选', 'Candidate'), copy('结果', 'Result'), copy('批次 / 重复', 'Batch / replicate'), 'QC']} cells={observations.map((r) => {
 const meta = object(r.result_metadata.learning)
 return [<><Checkbox aria-label={`${copy('选择结果', 'Select result')} ${r.id}`} checked={selectedResults.includes(r.id)} disabled={busy || !writable || (selectedResults.length >= 256 && !selectedResults.includes(r.id))} onCheckedChange={(checked) => setSelectedResults((current) => checked ? [...current, r.id] : current.filter((id) => id !== r.id))} /></>, <>{data.candidates.find((c) => c.id === r.candidate_id)?.name ?? r.candidate_ref ?? '—'}</>, <>{numberLabel(r.value)} {r.unit} · {String(meta.status)}</>, <>{r.batch_key} / {String(meta.replicate_key)}</>, <>{meta.qc_accepted === true ? '✓' : '—'}</>]
 })} /></div>
            <Button type="button" disabled={!writable || busy || !selectedResults.length} onClick={() => void perform(() => learning.freezeDataset(projectId, study.id, selectedResults))}>{copy('冻结所选数据', 'Freeze selected data')} ({selectedResults.length})</Button>
          </>}
          {datasets.map((d) => <article className="learning-record" key={d.id}><p><strong>{copy('冻结数据集', 'Frozen dataset')} · {d.digest.slice(0, 12)}</strong> · {rows(d.manifest.included).length} {copy('纳入', 'included')} / {rows(d.manifest.excluded).length} {copy('排除', 'excluded')}</p><JsonDetails label={copy('查看来源与排除原因', 'Inspect sources and exclusions')} data={d.manifest} /><Button type="button" variant="outline" disabled={!writable || busy} onClick={() => void perform(() => learning.trainLearningModel(projectId, d.id))}>{copy('训练并评估基线', 'Train and evaluate baseline')}</Button></article>)}
        </Section>
        <Section title={copy('03 · 项目模型与验证', '03 · Project models and validation')}>
          {!models.length && <p>{copy('冻结至少四组不同序列的有效结果后，训练项目基线。', 'Train a project baseline after freezing valid measurements for at least four distinct sequences.')}</p>}
          {models.map((m) => <article className="learning-record" key={m.id}>
            <h3>{m.algorithm} · {m.status} · {m.id.slice(0, 8)}</h3>
            <dl className="learning-metrics"><div><dt>{copy('独立序列组', 'Sequence groups')}</dt><dd>{String(m.evaluation.groups)}</dd></div><div><dt>RMSE</dt><dd>{numberLabel(m.evaluation.rmse)}</dd></div><div><dt>{copy('均值基线 RMSE', 'Mean baseline RMSE')}</dt><dd>{numberLabel(m.evaluation.mean_baseline_rmse)}</dd></div></dl>
            <p>{copy('按序列整组留出验证；相似家族与批次偏差仍可能影响评估。', 'Validation holds out entire sequences; family and batch confounding may remain.')}</p>
            <JsonDetails label={copy('查看验证记录与限制', 'Inspect evaluation and limits')} data={m.evaluation} />
            {m.status !== 'retired' && <form onSubmit={(event) => submit(event, (form) => learning.reviewLearningModel(projectId, m, text(form, 'action') as 'promote' | 'retire', text(form, 'reason')))}><fieldset disabled={!writable || busy}><Field label={copy('模型审阅理由', 'Model review rationale')}><Input name="reason" required maxLength={2000} /></Field><Field label={copy('处理方式', 'Review action')}><Choice name="action">{m.status === 'shadow' && m.evaluation.eligible_for_promotion === true && <option value="promote">{copy('提升为项目模型', 'Promote to project model')}</option>}<option value="retire">{copy('停用模型', 'Retire model')}</option></Choice></Field><Button type="submit" variant="outline">{copy('保存模型审阅', 'Save model review')}</Button></fieldset></form>}
          </article>)}
        </Section>
        <Section title={copy('04 · 下一轮候选与决策', '04 · Next batch and decision')}>
          <p>{copy('预算为本批估算上限；当前建议采用贪心探索与利用策略。审阅建议不会预订预算或提交实验。', 'The budget caps estimated batch cost. Selection uses a greedy exploration/exploitation policy. Reviewing a proposal does not reserve budget or submit experiments.')}</p>
          <form onSubmit={(event) => submit(event, (form) => learning.createLearningDecision(projectId, { study_id: study.id, model_id: text(form, 'model'), exploration_fraction: numeric(form, 'explore') / 100, candidates: Object.entries(selectedCandidates).map(([candidate_id, cost]) => ({ candidate_id, cost_cents: Math.round(Number(cost) * 100) })) }))}>
            <fieldset disabled={!writable || busy || !models.some((m) => m.status !== 'retired')}>
              <Field label={copy('使用模型', 'Model')}><Choice name="model" required>{models.filter((m) => m.status !== 'retired').map((m) => <option key={m.id} value={m.id}>{m.algorithm} · {m.status} · {m.id.slice(0, 8)}</option>)}</Choice></Field>
              <Field label={copy('探索比例（%）', 'Exploration share (%)')}><Input name="explore" type="number" min="0" max="100" defaultValue="25" required /></Field>
              <p>{copy('选择待评估候选并填写每个候选的完整实验估价（最多 256 个）。训练中已测得的序列会自动排除。', 'Select up to 256 candidates and enter the complete experimental estimate for each. Sequences already measured in training are automatically excluded.')}</p>
              <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('选择', 'Select'), copy('候选', 'Candidate'), `${copy('实验估价', 'Experiment estimate')} (${study.currency})`]} cells={data.candidates.map((c) => [<><Checkbox aria-label={`${copy('选择候选', 'Select candidate')} ${c.name}`} checked={c.id in selectedCandidates} disabled={Object.keys(selectedCandidates).length >= 256 && !(c.id in selectedCandidates)} onCheckedChange={(checked) => setSelectedCandidates((current) => { const next = { ...current }; if (checked) next[c.id] = ''; else delete next[c.id]; return next })} /></>, <>{c.name}</>, <>{c.id in selectedCandidates && <Input aria-label={`${copy('实验估价', 'Estimate')} ${c.name}`} type="number" min="0.01" max="1000000" step="0.01" value={selectedCandidates[c.id]} required onChange={(event) => setSelectedCandidates((current) => ({ ...current, [c.id]: event.target.value }))} />}</>])} /></div>
              <Button type="submit" disabled={!Object.keys(selectedCandidates).length}>{copy('生成批次建议', 'Generate batch proposal')}</Button>
            </fieldset>
          </form>
          {decisions.map((d) => <article className="learning-record" key={d.id}>
            <h3>{d.proposal.action === 'stop_no_feasible_candidate' ? copy('停止：当前预算内无可行候选', 'Stop: no feasible candidate in budget') : copy('候选批次建议', 'Candidate batch proposal')} · {d.review_status}</h3>
            <p>{String(d.proposal.currency)} {(Number(d.proposal.estimated_cost_cents) / 100).toFixed(2)} · {copy('模型状态', 'Model state')}: {String(d.proposal.model_status)}</p>
            <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('候选', 'Candidate'), copy('预测', 'Prediction'), copy('选择理由', 'Selection reason'), copy('训练域外', 'Out of domain')]} cells={rows(d.proposal.selected).map((r) => [<>{String(r.candidate_name)}</>, <>{numberLabel(r.prediction)} {assay.unit}</>, <>{String(r.selection_reason)}</>, <>{r.out_of_domain ? copy('是', 'Yes') : copy('否', 'No')}</>])} /></div>
            <JsonDetails label={copy('审查所有评分、排除原因与限制', 'Inspect all scores, exclusions and limits')} data={d.proposal} />
            {d.review_status === 'pending' && <form onSubmit={(event) => submit(event, (form) => learning.reviewLearningDecision(projectId, d, text(form, 'review') === 'approve', text(form, 'reason')))}><fieldset disabled={!writable || busy}><Field label={copy('决策理由', 'Decision rationale')}><Textarea name="reason" required maxLength={2000} /></Field><Field label={copy('决策', 'Decision')}><Choice name="review"><option value="reject">{copy('拒绝，补充证据', 'Reject; gather more evidence')}</option>{d.proposal.model_status === 'promoted' && <option value="approve">{copy('同意建议', 'Approve proposal')}</option>}</Choice></Field><Button type="submit" variant="outline">{copy('记录决策', 'Record decision')}</Button></fieldset></form>}
            {d.review_note && <p>{d.review_note}</p>}
            <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(() => download(d.id))}>{copy('下载证据包', 'Download evidence package')}</Button>
            {d.timeline_entry_id && <Link to={`/timeline?project=${projectId}`}>{copy('查看项目决策时间线', 'Open decision timeline')}</Link>}
          </article>)}
        </Section>
      </>}
    </>}
  </div>
}
