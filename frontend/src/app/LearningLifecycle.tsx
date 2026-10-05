import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/textarea'
import { Disclosure } from '../components/ui/Disclosure'
import { Checkbox } from '../components/ui/checkbox'
import * as learning from '../lib/api/learning'
import type { ArtifactResponse, EvidenceCreate, ExperimentResultResponse, ObservationImportResult } from '../lib/api/generated/types.gen'
import { Choice, Field, Section, JsonDetails } from './learningComponents'

const str = (form: FormData, key: string) => String(form.get(key) ?? '').trim()
const meta = (result: ExperimentResultResponse): Record<string, unknown> => {
  const value = result.result_metadata.learning
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function downloadLearningFile(name: string, content: unknown, mime = 'application/json') {
  const url = URL.createObjectURL(new Blob([typeof content === 'string' ? content : JSON.stringify(content, null, 2)], { type: mime }))
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

type Props = {
  projectId: string; study: learning.StudyResponse; assay: learning.AssayResponse;
  evidence: learning.EvidenceResponse[]; batches: learning.BatchResponse[]; decisions: learning.LearningDecisionResponse[];
  results: ExperimentResultResponse[]; artifacts: ArtifactResponse[]; workflows: { id: string; name: string }[];
  writable: boolean; experimentWritable: boolean; busy: boolean;
  perform: (action: () => Promise<unknown>) => Promise<void>;
  copy: (cn: string, en: string) => string;
}

export function LearningLifecycle({ projectId, study, assay, evidence, batches, decisions, results, artifacts, workflows, writable, experimentWritable, busy, perform, copy }: Props) {
  const [artifactId, setArtifactId] = useState('')
  const [preview, setPreview] = useState<ObservationImportResult | null>(null)
  const [sources, setSources] = useState<string[]>([])
  const availableFiles = artifacts.filter((a) => a.status === 'available' && a.filename.toLowerCase().endsWith('.csv'))
  const fileId = artifactId || availableFiles[0]?.id || ''
  function needsSourceReview(entry: learning.EvidenceResponse) {
    const linkedResults = Array.isArray(entry.sources.results) ? entry.sources.results as { id: string; version: number }[] : []
    const linkedArtifacts = Array.isArray(entry.sources.artifacts) ? entry.sources.artifacts as { id: string; version: number }[] : []
    return linkedResults.some((source) => {
      const current = results.find((r) => r.id === source.id)
      return !current || current.version !== source.version || Boolean(current.result_metadata.learning_withdrawal)
    }) || linkedArtifacts.some((source) => {
      const current = artifacts.find((a) => a.id === source.id)
      return !current || current.version !== source.version || current.status !== 'available'
    })
  }
  function submit(event: FormEvent<HTMLFormElement>, action: (form: FormData) => Promise<unknown>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    void perform(() => action(form))
  }
  return <>
    <Section title={copy('05 · 批量导入与实验交接', '05 · Import and experimental handoff')}>
      <p>{copy('CSV 先验证再导入，使用原始文件的哈希核验内容。单位必须与测定一致；不推测单位、不把失败填成零。', 'Validate CSV before importing. Content is checked against its artifact hash. Units must match the assay; failed samples keep explicit status.')}</p>
      <div className="learning-actions">
        <Button type="button" variant="outline" onClick={() => downloadLearningFile('learning-observations.csv', 'candidate_id,batch_key,replicate_key,replicate_type,status,value,unit,qc_accepted,note,family_key,observed_at,sample_role,measurement_key\n', 'text/csv')}>{copy('下载 CSV 空模板', 'Download blank CSV template')}</Button>
      </div>
      <form onSubmit={(event) => submit(event, async () => { setPreview(null); setPreview(await learning.importObservations(projectId, { assay_id: assay.id, artifact_id: fileId, dry_run: true })) })}>
        <fieldset disabled={!experimentWritable || busy || !fileId}>
          <Field label={copy('已上传的 CSV 原始文件', 'Uploaded CSV source artifact')}><Choice value={fileId} onChange={(event) => { setArtifactId(event.target.value); setPreview(null) }}>{availableFiles.map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}</Choice></Field>
          <Button type="submit" variant="outline">{copy('验证文件', 'Validate file')}</Button>
        </fieldset>
      </form>
      {preview && <div className="learning-record"><p>{copy('契约验证通过，待导入记录：', 'Contract validation passed. Rows to import: ')}{preview.row_count}</p><JsonDetails label={copy('查看解析结果', 'Inspect parsed results')} data={preview.observations} /><Button type="button" disabled={!experimentWritable || busy} onClick={() => void perform(async () => { await learning.importObservations(projectId, { assay_id: assay.id, artifact_id: fileId, dry_run: false }); setPreview(null) })}>{copy('确认导入实验记录', 'Import validated observations')}</Button></div>}
      <p>{copy('交接单关联已有研究轮次；创建交接单不会向供应商下单。每个候选都要有结果状态，失败和缺失同样计入成本。', 'Handoffs link to research campaign rounds. Creating a handoff does not place a supplier order. Every candidate needs a result status, including failed and missing samples.')}</p>
      {decisions.filter((d) => d.review_status === 'approved' && d.proposal.action === 'review_batch' && !batches.some((b) => b.decision_id === d.id)).map((d) => <form className="learning-record" key={d.id} onSubmit={(event) => submit(event, (form) => learning.createLearningBatch(projectId, d, str(form, 'rationale'), str(form, 'workflow') === 'none' ? undefined : str(form, 'workflow')))}>
        <fieldset disabled={!writable || !experimentWritable || busy}><h3>{copy('已审阅建议', 'Reviewed proposal')} · {d.id.slice(0, 8)}</h3><Field label={copy('本轮实验目的与交接说明', 'Round purpose and handoff instructions')}><Textarea name="rationale" required maxLength={2000} /></Field><Field label={copy('关联计算工作流（可选）', 'Linked compute workflow (optional)')}><Choice name="workflow"><option value="none">{copy('仅实验交接', 'Experimental handoff only')}</option>{workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</Choice></Field><Button type="submit">{copy('建立实验轮次与交接单', 'Create round and handoff')}</Button></fieldset>
      </form>)}
      {batches.map((batch) => {
        const batchResults = results.filter((r) => r.batch_key === batch.manifest.batch_key && !r.result_metadata.learning_withdrawal)
        return <article key={batch.id} className="learning-record">
          <h3>{copy('实验轮次', 'Experimental round')} {String(batch.manifest.round_number)} · {batch.receipt ? copy('结果已回流', 'Results received') : copy('等待结果', 'Awaiting results')}</h3>
          <p>{copy('录入或导入时填写批次编号：', 'Use this batch key when recording or importing results: ')}<code>{String(batch.manifest.batch_key)}</code></p>
          <div className="learning-actions"><Button type="button" variant="outline" disabled={busy} onClick={() => void perform(async () => downloadLearningFile(`learning-handoff-${batch.id}.json`, await learning.exportLearningBatch(projectId, batch.id)))}>{copy('下载交接单', 'Download handoff')}</Button><Link to={`/projects?view=campaigns&project=${projectId}`}>{copy('查看研究轮次', 'Open campaigns')}</Link>{typeof batch.manifest.workflow_run_id === 'string' && <Link to={`/workflow?project=${projectId}&run=${encodeURIComponent(batch.manifest.workflow_run_id)}`}>{copy('打开计算工作流', 'Open compute workflow')}</Link>}</div>
          <JsonDetails label={copy('查看实验清单', 'Inspect experimental manifest')} data={batch.manifest} />
          {batch.receipt ? <JsonDetails label={copy('查看回流结果与实际成本', 'Inspect receipt and reported costs')} data={batch.receipt} /> : <form onSubmit={(event) => submit(event, (form) => learning.receiveLearningBatch(projectId, batch, { result_ids: batchResults.map((r) => r.id), actual_cost_cents: Math.round(Number(str(form, 'cost')) * 100), note: str(form, 'note') }))}>
            <fieldset disabled={!experimentWritable || busy || !batchResults.length}>
              <p>{copy('已找到本批结果：', 'Results found for this batch: ')}{batchResults.length}</p>
              <Field label={`${copy('报告的实际实验总成本（含失败）', 'Reported total experimental cost (including failures)')} · ${study.currency}`}><Input name="cost" type="number" min="0" max="1000000" step="0.01" required /></Field>
              <Field label={copy('本轮结论与偏差说明', 'Round conclusions and deviations')}><Textarea name="note" required maxLength={2000} /></Field>
              <Button type="submit">{copy('确认结果回流', 'Receive results')}</Button>
            </fieldset>
          </form>}
        </article>
      })}
      {!batches.length && <p>{copy('审阅建议后建立第一轮实验交接单。', 'Review a proposal, then create the first experimental handoff.')}</p>}
    </Section>
    <Section title={copy('06 · 项目学习记录', '06 · Project learning record')}>
      <p>{copy('把已知事实、假设、冲突和未知问题分开记录。新增或撤回证据后，旧建议必须重新计算才能交接。', 'Record facts, hypotheses, conflicts and unknowns separately. Adding or withdrawing evidence requires a new proposal before handoff.')}</p>
      <Disclosure title={copy('记录本轮学到了什么', 'Record what this round taught us')}>
        <form onSubmit={(event) => submit(event, async (form) => { await learning.createEvidence(projectId, { study_id: study.id, kind: str(form, 'kind') as EvidenceCreate['kind'], statement: str(form, 'statement'), result_ids: sources }); setSources([]) })}>
          <fieldset disabled={!writable || busy}>
            <Field label={copy('记录类型', 'Record type')}><Choice name="kind"><option value="hypothesis">{copy('假设', 'Hypothesis')}</option><option value="fact">{copy('事实', 'Fact')}</option><option value="conflict">{copy('冲突', 'Conflict')}</option><option value="unknown">{copy('未知', 'Unknown')}</option></Choice></Field>
            <Field label={copy('发现与下一步问题', 'Finding and next question')}><Textarea name="statement" required maxLength={4000} /></Field>
            <fieldset><legend>{copy('关联实验依据（事实必须有来源）', 'Link experimental evidence (required for facts)')}</legend><div className="learning-source-list">{results.map((r) => <label key={r.id} className="learning-check"><Checkbox checked={sources.includes(r.id)} onCheckedChange={(checked) => setSources((current) => checked ? [...current, r.id] : current.filter((id) => id !== r.id))} disabled={!sources.includes(r.id) && sources.length >= 256} />{r.result_metadata.learning_withdrawal ? copy('已撤回 · ', 'Withdrawn · ') : ''}{r.candidate_ref || r.candidate_id?.slice(0, 8)} · {r.value ?? String(meta(r).status)} {r.unit} · {r.batch_key}</label>)}</div></fieldset>
            <Button type="submit">{copy('保存学习记录', 'Save learning record')}</Button>
          </fieldset>
        </form>
      </Disclosure>
      {evidence.map((entry) => <article key={entry.id} className="learning-record"><h3>{entry.kind} · {entry.withdrawal ? copy('已撤回', 'Withdrawn') : needsSourceReview(entry) ? copy('来源已变化，需复核', 'Sources changed; review required') : copy('有效', 'Active')}</h3><p>{entry.statement}</p><JsonDetails label={copy('查看来源与历史', 'Inspect sources and history')} data={{ sources: entry.sources, withdrawal: entry.withdrawal }} />{!entry.withdrawal && <Disclosure title={copy('撤回这条记录', 'Withdraw this record')}><form onSubmit={(event) => submit(event, (form) => learning.withdrawEvidence(projectId, entry, str(form, 'reason')))}><fieldset disabled={!writable || busy}><Field label={copy('撤回原因（原记录仍保留）', 'Reason (the original record is retained)')}><Input name="reason" required maxLength={2000} /></Field><Button type="submit" variant="outline">{copy('记录撤回', 'Record withdrawal')}</Button></fieldset></form></Disclosure>}</article>)}
    </Section>
    <Section title={copy('07 · LAAS 交付', '07 · Learning service delivery')}>
      <p>{copy('导出目标版本、测定契约、实验结果、数据快照、模型验证、决策、学习记录、批次及成本。包内带校验摘要，原始文件可从项目文件中另行下载。', 'Export goal and assay contracts, observations, snapshots, model evaluations, decisions, learning records, batches and costs with an integrity digest. Download raw source files separately from project artifacts.')}</p>
      <Button type="button" variant="outline" disabled={busy} onClick={() => void perform(async () => downloadLearningFile(`learning-delivery-${study.id}.json`, await learning.exportLearningDelivery(projectId, study.id)))}>{copy('下载完整学习交付包', 'Download learning delivery package')}</Button>
    </Section>
  </>
}
