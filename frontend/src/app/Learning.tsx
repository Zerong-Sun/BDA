import { Fragment, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Checkbox } from '../components/ui/checkbox'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/textarea'
import { Disclosure } from '../components/ui/Disclosure'
import { Button } from '../components/ui/Button'
import { useI18n } from '../lib/i18n'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useAppStore } from '../lib/store/appStore'
import { listAllCandidates } from '../lib/api/candidates'
import { ArtifactUploadDropzone } from '../features/artifacts/ArtifactUploadDropzone'
import { listProjectArtifacts } from '../lib/api/artifacts'
import { listResearchGoals } from '../lib/api/researchGoals'
import { getProjectAccess, listProjectWorkflowRuns } from '../lib/api/projects'
import * as learning from '../lib/api/learning'
import type { ObservationCreate, StudyCreate, ModelCreate, ModelReview } from '../lib/api/generated/types.gen'
import { Choice, LearningTable, Field, Section, JsonDetails } from './learningComponents'
import { LearningLifecycle } from './LearningLifecycle'
import './learning.css'

const values = (event: FormEvent<HTMLFormElement>) => new FormData(event.currentTarget)
const text = (data: FormData, key: string) => String(data.get(key) ?? '').trim()
const numeric = (data: FormData, key: string) => Number(text(data, key))
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(object) : []
const newest = <T extends { created_at: string }>(items: T[]) => [...items].sort((a, b) => b.created_at.localeCompare(a.created_at))
const numberLabel = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(4) : '—'

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
  const [algorithm, setAlgorithm] = useState<ModelCreate['algorithm']>('knn')
  const [validation, setValidation] = useState<ModelCreate['validation']>('sequence')
  const [calibrate, setCalibrate] = useState(false)
  const [assayTemplate, setAssayTemplate] = useState('custom')
  const [retests, setRetests] = useState<string[]>([])
  const [measurementStatus, setMeasurementStatus] = useState<ObservationCreate['status']>('measured')
  const access = useQuery({ queryKey: ['project-access', projectId], queryFn: () => getProjectAccess(projectId) })
  const query = useQuery({ queryKey: ['learning-workspace', projectId], queryFn: async () => {
    const [assays, studies, datasets, models, decisions, results, candidates, artifacts, goals, evidence, batches, workflows] = await Promise.all([
      learning.listLearning(projectId, 'assays'), learning.listLearning(projectId, 'studies'),
      learning.listLearning(projectId, 'datasets'), learning.listLearning(projectId, 'models'),
      learning.listLearning(projectId, 'decisions'), learning.listLearningResults(projectId),
      listAllCandidates(projectId, { limit: 200 }), listProjectArtifacts(projectId), listResearchGoals(projectId),
      learning.listLearning(projectId, 'evidence'), learning.listLearning(projectId, 'batches'), listProjectWorkflowRuns(projectId),
    ])
    return { assays, studies: newest(studies), datasets: newest(datasets), models: newest(models), decisions: newest(decisions), results: newest(results), candidates: candidates.items, artifacts, goals, evidence: newest(evidence), batches: newest(batches).reverse(), workflows }
  } })
  const writable = !demo && access.data?.permissions.write === true
  const experimentWritable = !demo && access.data?.permissions.experiment === true
  const data = query.data
  const study = data?.studies.find((row) => row.id === studyId) ?? data?.studies.find((s) => !data.studies.some((revision) => revision.supersedes_id === s.id)) ?? data?.studies[0]
  const assay = data?.assays.find((row) => row.id === study?.assay_id)
  const datasets = data?.datasets.filter((row) => row.study_id === study?.id) ?? []
  const models = data?.models.filter((row) => row.study_id === study?.id) ?? []
  const decisions = data?.decisions.filter((row) => row.study_id === study?.id) ?? []
  const observations = data?.results.filter((row) => object(row.result_metadata.learning).assay_id === assay?.id) ?? []
  const measuredValue = !['failed', 'missing'].includes(measurementStatus)
  const evidenceLoaded = Boolean(data) && !query.isError && !access.isError

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
    const url = URL.createObjectURL(new Blob([evidence], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url; link.download = `learning-evidence-${decisionId}.json`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <div className="learning-workbench" data-tour-id="learning-page">
    <header className="learning-header">
      <div className="learning-heading">
        <div className="learning-eyebrow"><span>ITERAVIA</span><span className="learning-version">2.6 PREVIEW</span></div>
        <h1>{copy('项目学习工作台', 'Project learning workbench')}</h1>
        <p>{copy('把每轮实验变成下一轮决策的依据。', 'Turn each experimental round into evidence for the next decision.')}</p>
        <p className="learning-limit">{copy('从实验契约、模型验证到下一轮实验与学习交付。模型提升通过回顾性检查；实际实验增益仍需前瞻验证。', 'From assay contracts and model validation to the next experimental round and learning delivery. Promotion passes retrospective checks; experimental benefit needs prospective validation.')}</p>
      </div>
      <dl className="learning-overview" aria-label={copy('当前学习目标的数据概况', 'Current study evidence summary')}>
        {[
          [copy('实验记录', 'Observations'), observations.length],
          [copy('冻结数据集', 'Frozen datasets'), datasets.length],
          [copy('项目模型', 'Project models'), models.length],
          [copy('批次建议', 'Batch proposals'), decisions.length],
        ].map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{evidenceLoaded ? count : '—'}</dd></div>)}
      </dl>
    </header>
    <ol className="learning-steps" aria-label={copy('跳转到工作步骤', 'Jump to a work step')}>{[copy('目标契约', 'Goal & assay'), copy('实验数据', 'Observations'), copy('模型验证', 'Model validation'), copy('批次决策', 'Batch decisions'), copy('交接回流', 'Handoff & results'), copy('学习记录', 'Learning record'), copy('项目交付', 'Delivery')].map((label, index) => <li key={label}><Button type="button" variant="ghost" disabled={!data || (index > 0 && !study)} onClick={() => { const heading = document.getElementById(`learning-step-${String(index + 1).padStart(2, '0')}`); heading?.scrollIntoView({ block: 'start' }); heading?.focus({ preventScroll: true }) }}><span>{index + 1}</span>{label}</Button></li>)}</ol>
    {(query.isPending || access.isPending) && <p role="status">{copy('正在读取项目证据…', 'Loading project evidence…')}</p>}
    {(query.isError || access.isError) && <div role="alert"><p>{copy('项目数据加载失败，操作已暂停。', 'Project data could not be loaded. Actions are paused.')}</p><Button type="button" variant="outline" onClick={() => { void query.refetch(); void access.refetch() }}>{copy('重试', 'Retry')}</Button></div>}
    {failure && <div role="alert" className="learning-message">{failure}<Button type="button" variant="outline" onClick={() => void query.refetch()}>{copy('刷新数据', 'Refresh data')}</Button></div>}
    {notice && <p role="status" className="learning-message">{notice}</p>}
    {data && !query.isError && !access.isError && <>
      {!writable && <p>{copy('当前为只读模式。', 'You have read-only access.')}</p>}
      <Section title={copy('01 · 目标与测定契约', '01 · Goal and assay contract')}>
        <div className="learning-grid">
          <Disclosure defaultOpen={!data.assays.length} title={copy('新建测定方法', 'Define an assay')}>
            <Field label={copy('应用模板', 'Assay template')}><Choice value={assayTemplate} onChange={(event) => setAssayTemplate(event.target.value)}><option value="custom">{copy('自定义测定', 'Custom assay')}</option><option value="enzyme">{copy('酶活性优化', 'Enzyme activity')}</option><option value="binder">{copy('结合蛋白亲和力', 'Binder affinity')}</option></Choice></Field>
            <form key={assayTemplate} onSubmit={(event) => submit(event, (form) => learning.createAssay(projectId, { name: text(form, 'name'), method: text(form, 'method'), unit: text(form, 'unit'), conditions: { context: text(form, 'conditions') } }))}>
              <fieldset disabled={!experimentWritable || busy}>
                <Field label={copy('测定名称', 'Assay name')}><Input name="name" required maxLength={200} defaultValue={assayTemplate === 'enzyme' ? copy('酶比活性', 'Enzyme specific activity') : assayTemplate === 'binder' ? copy('结合亲和力 KD', 'Binding affinity KD') : ''} /></Field>
                <Field label={copy('方法、仪器与处理方式', 'Method, instrument and processing')}><Textarea name="method" required maxLength={4000} defaultValue={assayTemplate === 'enzyme' ? copy('填写底物、检测波长、温度和初始速率拟合方法。', 'Specify substrate, readout, temperature and initial-rate fitting method.') : assayTemplate === 'binder' ? copy('填写 BLI/SPR 仪器、固定化方式、浓度梯度与结合/解离拟合方法。', 'Specify BLI/SPR instrument, immobilization, concentration series and kinetic fitting.') : ''} /></Field>
                <Field label={copy('单位（例如 nM）', 'Unit (for example nM)')}><Input name="unit" required maxLength={40} defaultValue={assayTemplate === 'enzyme' ? 'U/mg' : assayTemplate === 'binder' ? 'nM' : ''} /></Field>
                <Field label={copy('条件与对照', 'Conditions and controls')}><Textarea name="conditions" required maxLength={3000} /></Field>
                <Button type="submit">{copy('保存测定', 'Save assay')}</Button>
              </fieldset>
            </form>
          </Disclosure>
          <Disclosure defaultOpen={!data.studies.length} title={copy('新建学习目标', 'Create a learning study')}>
            {!data.goals.length && <p><Link to={`/research?project=${projectId}`}>{copy('先在研究页面建立项目目标', 'Create a project goal in Research first')}</Link></p>}
            <form onSubmit={(event) => submit(event, async (form) => {
              const created = await learning.createStudy(projectId, { name: text(form, 'name'), assay_id: text(form, 'assay'), research_goal_id: text(form, 'goal'), direction: text(form, 'direction') as StudyCreate['direction'], threshold: text(form, 'threshold') ? numeric(form, 'threshold') : null, currency: text(form, 'currency') as StudyCreate['currency'], batch_budget_cents: Math.round(numeric(form, 'budget') * 100), max_batch_size: numeric(form, 'size'), max_rounds: numeric(form, 'rounds'), stop_on_threshold: form.get('stop') === 'on', supersedes_id: text(form, 'previous') === 'new' ? null : text(form, 'previous'), selection_constraints: { min_length: numeric(form, 'minLength'), max_length: numeric(form, 'maxLength'), forbidden_motifs: text(form, 'motifs').toUpperCase().split(/[\s,]+/).filter(Boolean), allow_out_of_domain: form.get('noOod') !== 'on' } })
              setStudyId(created.id); setSelectedResults([]); setSelectedCandidates({}); setRetests([]); setMeasurementStatus('measured')
            })}>
              <fieldset disabled={!writable || busy || !data.assays.length || !data.goals.length}>
                <Field label={copy('学习目标名称', 'Study name')}><Input name="name" required maxLength={200} /></Field>
                <Field label={copy('研究目标', 'Research goal')}><Choice name="goal" required>{data.goals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}</Choice></Field>
                <Field label={copy('测定契约', 'Assay contract')}><Choice name="assay" required>{data.assays.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.unit}</option>)}</Choice></Field>
                <Field label={copy('优化方向', 'Optimization direction')}><Choice name="direction"><option value="maximize">{copy('越大越好', 'Maximize')}</option><option value="minimize">{copy('越小越好', 'Minimize')}</option></Choice></Field>
                <Field label={copy('目标阈值（可选）', 'Target threshold (optional)')}><Input name="threshold" type="number" step="any" /></Field>
                <div className="learning-grid"><Field label={copy('每批预算', 'Budget per batch')}><Input name="budget" type="number" min="0.01" max="1000000" step="0.01" required /></Field><Field label={copy('币种', 'Currency')}><Choice name="currency">{['USD', 'EUR', 'GBP', 'CNY'].map((c) => <option key={c}>{c}</option>)}</Choice></Field></div>
                <Field label={copy('每批最多候选数', 'Maximum candidates per batch')}><Input name="size" type="number" min="1" max="96" defaultValue="12" required /></Field>
                <div className="learning-grid"><Field label={copy('最短序列长度', 'Minimum sequence length')}><Input name="minLength" type="number" min="1" max="10000" defaultValue="1" required /></Field><Field label={copy('最长序列长度', 'Maximum sequence length')}><Input name="maxLength" type="number" min="1" max="10000" defaultValue="10000" required /></Field></div>
                <Field label={copy('排除的氨基酸片段（空格分隔，可选）', 'Forbidden amino acid motifs (space separated, optional)')}><Input name="motifs" maxLength={2019} /></Field>
                <label className="learning-check"><Checkbox name="noOod" />{copy('禁止选择训练域外候选', 'Exclude candidates outside the model domain')}</label>
                <Field label={copy('最多实验轮数', 'Maximum experimental rounds')}><Input name="rounds" type="number" min="1" max="100" defaultValue="12" required /></Field>
                <Field label={copy('目标版本', 'Study revision')}><Choice name="previous"><option value="new">{copy('独立新目标', 'New study')}</option>{data.studies.map((s) => <option key={s.id} value={s.id}>{copy('修订', 'Revise')} · {s.name}</option>)}</Choice></Field>
                <label className="learning-check"><Checkbox name="stop" />{copy('已有合格测量达到目标阈值时建议停止', 'Recommend stopping when accepted measurements reach the target')}</label>
                <Button type="submit">{copy('冻结目标与预算', 'Freeze goal and budget')}</Button>
              </fieldset>
            </form>
          </Disclosure>
        </div>
        {study && <Field label={copy('当前学习目标', 'Current study')}><Choice value={study.id} disabled={busy} onChange={(event) => { setStudyId(event.target.value); setSelectedResults([]); setSelectedCandidates({}); setRetests([]); setMeasurementStatus('measured') }}>{data.studies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Choice></Field>}
        {study && <p>{assay?.name} · {assay?.unit} · {study.direction === 'maximize' ? copy('最大化', 'Maximize') : copy('最小化', 'Minimize')} · {study.currency} {(study.batch_budget_cents / 100).toFixed(2)} / {copy('批', 'batch')} · ≤ {study.max_batch_size} {copy('个候选', 'candidates')}</p>}
        {study && <JsonDetails label={copy('查看冻结目标与测定依据', 'Inspect frozen goal and assay')} data={{ study, assay }} />}
      </Section>
      {study && assay && <Fragment key={study.id}>
        <Section title={copy('02 · 实验结果与冻结数据集', '02 · Observations and frozen datasets')}>
          <Disclosure title={copy('上传原始实验文件', 'Upload source experimental data')}>
            <ArtifactUploadDropzone projectId={projectId} disabled={busy} readOnly={demo || access.data?.permissions.artifact !== true} onUploaded={() => { void cache.invalidateQueries({ queryKey: ['learning-workspace', projectId] }) }} />
          </Disclosure>
          <Disclosure title={copy('录入实验结果', 'Record an observation')}>
            <p>{copy('先把原始文件上传至项目；方法或条件变化时建立新测定。重复编号表示同一次生物学重复，技术重复使用相同编号。', 'Upload the source file to the project first. Use a new assay when methods or conditions change. Replicate keys identify a biological replicate; technical repeats share that key.')}</p>
            <form onSubmit={(event) => submit(event, (form) => learning.createObservation(projectId, { assay_id: assay.id, candidate_id: text(form, 'candidate'), source_artifact_id: text(form, 'artifact'), batch_key: text(form, 'batch'), replicate_key: text(form, 'replicate'), replicate_type: text(form, 'replicateType') as ObservationCreate['replicate_type'], status: measurementStatus, value: measuredValue ? numeric(form, 'value') : null, unit: assay.unit, qc_accepted: form.get('qc') === 'on', note: text(form, 'note'), family_key: text(form, 'family') || null, measurement_key: text(form, 'measurementKey') || null, observed_at: text(form, 'observed') ? new Date(text(form, 'observed')).toISOString() : null, sample_role: text(form, 'role') as ObservationCreate['sample_role'] }))}>
              <fieldset disabled={!experimentWritable || busy || !data.candidates.length || !data.artifacts.some((a) => a.status === 'available')}>
                <div className="learning-grid">
                  <Field label={copy('候选', 'Candidate')}><Choice name="candidate" required>{data.candidates.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Choice></Field>
                  <Field label={copy('原始证据文件', 'Source artifact')}><Choice name="artifact" required>{data.artifacts.filter((a) => a.status === 'available').map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}</Choice></Field>
                  <Field label={copy('实验批次', 'Batch')}><Input name="batch" required maxLength={200} /></Field>
                  <Field label={copy('测量编号 / 孔位（可选，文件内唯一）', 'Measurement key / well (optional, unique within source file)')}><Input name="measurementKey" maxLength={120} /></Field><Field label={copy('生物学重复编号', 'Biological replicate key')}><Input name="replicate" required maxLength={120} /></Field>
                  <Field label={copy('重复类型', 'Replicate type')}><Choice name="replicateType"><option value="biological">{copy('生物学重复', 'Biological')}</option><option value="technical">{copy('技术重复', 'Technical')}</option></Choice></Field>
                  <Field label={copy('序列家族（用于家族隔离验证）', 'Sequence family (for held-out family validation)')}><Input name="family" maxLength={120} /></Field>
                  <Field label={copy('实验观测时间（本地时区）', 'Observation time (local timezone)')}><Input name="observed" type="datetime-local" /></Field>
                  <Field label={copy('样本角色', 'Sample role')}><Choice name="role"><option value="candidate">{copy('候选样本', 'Candidate')}</option><option value="positive_control">{copy('阳性对照', 'Positive control')}</option><option value="negative_control">{copy('阴性对照', 'Negative control')}</option></Choice></Field>
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
            <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('纳入', 'Include'), copy('候选', 'Candidate'), copy('结果', 'Result'), copy('批次 / 重复', 'Batch / replicate'), 'QC', copy('审阅', 'Review')]} cells={observations.map((r) => {
 const meta = object(r.result_metadata.learning)
 return [<><Checkbox aria-label={`${copy('选择结果', 'Select result')} ${r.id}`} checked={selectedResults.includes(r.id)} disabled={busy || !writable || (selectedResults.length >= 256 && !selectedResults.includes(r.id))} onCheckedChange={(checked) => setSelectedResults((current) => checked ? [...current, r.id] : current.filter((id) => id !== r.id))} /></>, <>{data.candidates.find((c) => c.id === r.candidate_id)?.name ?? r.candidate_ref ?? '—'}</>, <>{numberLabel(r.value)} {r.unit} · {String(meta.status)}</>, <>{r.batch_key} / {String(meta.replicate_key)}</>, <>{r.result_metadata.learning_withdrawal ? copy('已撤回', 'Withdrawn') : meta.qc_accepted === true ? '✓' : '—'}</>, <>{!r.result_metadata.learning_withdrawal && <Disclosure title={copy('撤回结果', 'Withdraw result')}><form onSubmit={(event) => submit(event, (form) => learning.withdrawObservation(projectId, r, text(form, 'reason')))}><fieldset disabled={!experimentWritable || busy}><Field label={copy('撤回测量的理由', 'Measurement withdrawal reason')}><Input name="reason" required maxLength={2000} /></Field><Button type="submit" variant="outline">{copy('确认撤回', 'Withdraw measurement')}</Button></fieldset></form></Disclosure>}</>]
 })} /></div>
            <Button type="button" disabled={!writable || busy || !selectedResults.length} onClick={() => void perform(() => learning.freezeDataset(projectId, study.id, selectedResults))}>{copy('冻结所选数据', 'Freeze selected data')} ({selectedResults.length})</Button>
          </>}
          <div className="learning-grid"><Field label={copy('预先选择模型', 'Predeclared model')}><Choice value={algorithm} onChange={(event) => setAlgorithm(event.target.value as ModelCreate['algorithm'])}><option value="knn">KNN</option><option value="ridge">{copy('岭回归', 'Ridge regression')}</option></Choice></Field><Field label={copy('验证划分', 'Validation split')}><Choice value={validation} onChange={(event) => setValidation(event.target.value as ModelCreate['validation'])}><option value="sequence">{copy('留出序列', 'Leave sequences out')}</option><option value="family">{copy('留出家族', 'Leave families out')}</option><option value="batch">{copy('留出批次', 'Leave batches out')}</option><option value="time">{copy('按时间前后划分', 'Forward temporal holdout')}</option></Choice></Field></div>
          <label className="learning-check"><Checkbox checked={calibrate && ['sequence', 'family'].includes(validation || '')} disabled={!['sequence', 'family'].includes(validation || '')} onCheckedChange={(checked) => setCalibrate(checked === true)} />{copy('保留独立校准集，计算名义 90% 区间（至少 20 个独立组；分布变化时不保证覆盖率）', 'Reserve independent calibration groups for nominal 90% intervals (20+ groups; distribution shift can invalidate coverage)')}</label>
          {datasets.map((d) => <article className="learning-record" key={d.id}><p><strong>{copy('冻结数据集', 'Frozen dataset')} · {d.digest.slice(0, 12)}</strong> · {rows(d.manifest.included).length} {copy('纳入', 'included')} / {rows(d.manifest.excluded).length} {copy('排除', 'excluded')}</p><JsonDetails label={copy('查看来源与排除原因', 'Inspect sources and exclusions')} data={d.manifest} /><Button type="button" variant="outline" disabled={!writable || busy} onClick={() => void perform(() => learning.trainLearningModel(projectId, d.id, { algorithm, validation, calibrate: calibrate && ['sequence', 'family'].includes(validation || '') }))}>{copy('训练并评估基线', 'Train and evaluate baseline')}</Button></article>)}
        </Section>
        <Section title={copy('03 · 项目模型与验证', '03 · Project models and validation')}>
          {!models.length && <p>{copy('冻结至少四组不同序列的有效结果后，训练项目基线。', 'Train a project baseline after freezing valid measurements for at least four distinct sequences.')}</p>}
          {models.map((m) => <article className="learning-record" key={m.id}>
            <h3>{m.algorithm} · {m.status} · {m.id.slice(0, 8)}</h3>
            <dl className="learning-metrics"><div><dt>{copy('独立序列组', 'Sequence groups')}</dt><dd>{String(m.evaluation.groups)}</dd></div><div><dt>RMSE</dt><dd>{numberLabel(m.evaluation.rmse)}</dd></div><div><dt>{copy('均值基线 RMSE', 'Mean baseline RMSE')}</dt><dd>{numberLabel(m.evaluation.mean_baseline_rmse)}</dd></div></dl>
            <p>{copy('验证划分和模型在训练前指定；每折排除测试序列在训练集中的重复。家族标签与实验时间需要准确填写。', 'Model and validation split are declared before training. Test sequences are purged from each training fold; family labels and timestamps must be accurate.')}</p>
            <JsonDetails label={copy('查看验证记录与限制', 'Inspect evaluation and limits')} data={m.evaluation} />
            {(m.status !== 'retired' || rows(m.evaluation.reviews).some((r) => r.action === 'promote' || r.action === 'rollback')) && <form onSubmit={(event) => submit(event, (form) => learning.reviewLearningModel(projectId, m, text(form, 'action') as ModelReview['action'], text(form, 'reason')))}><fieldset disabled={!writable || busy}><Field label={copy('模型审阅理由', 'Model review rationale')}><Input name="reason" required maxLength={2000} /></Field><Field label={copy('处理方式', 'Review action')}><Choice name="action">{m.status === 'retired' && <option value="rollback">{copy('回滚至此模型', 'Roll back to this model')}</option>}{m.status === 'shadow' && m.evaluation.eligible_for_promotion === true && <option value="promote">{copy('提升为项目模型', 'Promote to project model')}</option>}<option value="retire">{copy('停用模型', 'Retire model')}</option></Choice></Field><Button type="submit" variant="outline">{copy('保存模型审阅', 'Save model review')}</Button></fieldset></form>}
          </article>)}
        </Section>
        <Section title={copy('04 · 下一轮候选与决策', '04 · Next batch and decision')}>
          <p>{copy('预算为本批估算上限；当前建议采用贪心探索与利用策略。审阅建议不会预订预算或提交实验。', 'The budget caps estimated batch cost. Selection uses a greedy exploration/exploitation policy. Reviewing a proposal does not reserve budget or submit experiments.')}</p>
          <form onSubmit={(event) => submit(event, (form) => learning.createLearningDecision(projectId, { study_id: study.id, model_id: text(form, 'model'), exploration_fraction: numeric(form, 'explore') / 100, retest_candidates: retests.filter((id) => id in selectedCandidates), secondary_model_id: text(form, 'secondary') === 'none' ? null : text(form, 'secondary'), candidates: Object.entries(selectedCandidates).map(([candidate_id, cost]) => ({ candidate_id, cost_cents: Math.round(Number(cost) * 100) })) }))}>
            <fieldset disabled={!writable || busy || !models.some((m) => m.status !== 'retired')}>
              <Field label={copy('使用模型', 'Model')}><Choice name="model" required>{models.filter((m) => m.status !== 'retired').map((m) => <option key={m.id} value={m.id}>{m.algorithm} · {m.status} · {m.id.slice(0, 8)}</option>)}</Choice></Field>
              <Field label={copy('第二测定目标（可选，按 Pareto 前沿选择）', 'Secondary assay (optional Pareto selection)')}><Choice name="secondary"><option value="none">{copy('仅当前测定', 'Primary assay only')}</option>{data.models.filter((m) => m.status === 'promoted' && m.study_id !== study.id && data.studies.find((s) => s.id === m.study_id)?.assay_id !== study.assay_id).map((m) => <option key={m.id} value={m.id}>{data.studies.find((s) => s.id === m.study_id)?.name} · {m.algorithm}</option>)}</Choice></Field>
              <Field label={copy('探索比例（%）', 'Exploration share (%)')}><Input name="explore" type="number" min="0" max="100" defaultValue="25" required /></Field>
              <p>{copy('选择候选并填写完整实验估价。已测序列默认排除；需要重复确认时，明确勾选复测。复测优先计入预算，第二目标采用预测 Pareto 排序。', 'Select candidates and enter complete estimates. Measured sequences are excluded unless marked for retest. Retests receive budget priority; a secondary objective uses predicted Pareto ranking.')}</p>
              <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('选择', 'Select'), copy('候选', 'Candidate'), `${copy('实验估价', 'Experiment estimate')} (${study.currency})`]} cells={data.candidates.map((c) => [<><Checkbox aria-label={`${copy('选择候选', 'Select candidate')} ${c.name}`} checked={c.id in selectedCandidates} disabled={Object.keys(selectedCandidates).length >= 256 && !(c.id in selectedCandidates)} onCheckedChange={(checked) => setSelectedCandidates((current) => { const next = { ...current }; if (checked) next[c.id] = ''; else delete next[c.id]; return next })} /></>, <>{c.name}</>, <>{c.id in selectedCandidates && <Input aria-label={`${copy('实验估价', 'Estimate')} ${c.name}`} type="number" min="0.01" max="1000000" step="0.01" value={selectedCandidates[c.id]} required onChange={(event) => setSelectedCandidates((current) => ({ ...current, [c.id]: event.target.value }))} />}</>])} /></div>
              <Disclosure title={copy('指定优先复测候选', 'Prioritize candidates for retesting')}><div className="learning-source-list">{data.candidates.filter((c) => c.id in selectedCandidates).map((c) => <label key={c.id} className="learning-check"><Checkbox checked={retests.includes(c.id)} onCheckedChange={(checked) => setRetests((current) => checked ? [...current, c.id] : current.filter((id) => id !== c.id))} />{c.name}</label>)}</div></Disclosure>
              <Button type="submit" disabled={!Object.keys(selectedCandidates).length}>{copy('生成批次建议', 'Generate batch proposal')}</Button>
            </fieldset>
          </form>
          {decisions.map((d) => <article className="learning-record" key={d.id}>
            <h3>{String(d.proposal.action).startsWith('stop_') ? copy('停止建议', 'Stop recommendation') : copy('候选批次建议', 'Candidate batch proposal')} · {d.review_status}</h3>
            {String(d.proposal.action).startsWith('stop_') && <p>{d.proposal.action === 'stop_round_limit' ? copy('已达到冻结的实验轮次上限。继续前请修订目标契约。', 'The frozen round limit has been reached. Revise the study contract before continuing.') : d.proposal.action === 'stop_target_reached' ? copy('实测结果已达到目标阈值，当前契约要求停止。', 'Measured results reached the target threshold; this contract requires stopping.') : copy('当前候选池、约束和预算下没有可选批次。', 'No batch is feasible within the current candidate pool, constraints and budget.')}</p>}
            <p>{String(d.proposal.currency)} {(Number(d.proposal.estimated_cost_cents) / 100).toFixed(2)} · {copy('模型状态', 'Model state')}: {String(d.proposal.model_status)}</p>
            <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('可滚动数据表', 'Scrollable data table')}><LearningTable headings={[copy('候选', 'Candidate'), copy('预测', 'Prediction'), copy('名义 90% 区间', 'Nominal 90% interval'), copy('选择理由', 'Selection reason'), copy('训练域外', 'Out of domain')]} cells={rows(d.proposal.selected).map((r) => [<>{String(r.candidate_name)}</>, <>{numberLabel(r.prediction)} {assay.unit}</>, <>{Array.isArray(r.nominal_interval) ? `${numberLabel(r.nominal_interval[0])} – ${numberLabel(r.nominal_interval[1])} ${assay.unit}` : copy('未校准或域外', 'Uncalibrated / out of domain')}</>, <>{String(r.selection_reason)}</>, <>{r.out_of_domain ? copy('是', 'Yes') : copy('否', 'No')}</>])} /></div>
            <JsonDetails label={copy('审查所有评分、排除原因与限制', 'Inspect all scores, exclusions and limits')} data={d.proposal} />
            {d.review_status === 'pending' && <form onSubmit={(event) => submit(event, (form) => learning.reviewLearningDecision(projectId, d, text(form, 'review') === 'approve', text(form, 'reason')))}><fieldset disabled={!writable || busy}><Field label={copy('决策理由', 'Decision rationale')}><Textarea name="reason" required maxLength={2000} /></Field><Field label={copy('决策', 'Decision')}><Choice name="review"><option value="reject">{copy('拒绝，补充证据', 'Reject; gather more evidence')}</option>{d.proposal.model_status === 'promoted' && <option value="approve">{copy('同意建议', 'Approve proposal')}</option>}</Choice></Field><Button type="submit" variant="outline">{copy('记录决策', 'Record decision')}</Button></fieldset></form>}
            {d.review_note && <p>{d.review_note}</p>}
            <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(() => download(d.id))}>{copy('下载证据包', 'Download evidence package')}</Button>
            {d.timeline_entry_id && <Link to={`/timeline?project=${projectId}`}>{copy('查看项目决策时间线', 'Open decision timeline')}</Link>}
          </article>)}
        </Section>
        <LearningLifecycle key={study.id} projectId={projectId} study={study} assay={assay} evidence={data.evidence.filter((e) => e.study_id === study.id)} batches={data.batches.filter((b) => b.study_id === study.id)} decisions={decisions} results={observations} artifacts={data.artifacts} workflows={data.workflows} writable={writable} experimentWritable={experimentWritable} busy={busy} perform={perform} copy={copy} />
      </Fragment>}
    </>}
  </div>
}
