import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Disclosure } from '../../components/ui/Disclosure'
import { Choice } from '../../app/learningComponents'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { useI18n } from '../../lib/i18n'
import { listProjects } from '../../lib/api/projects'
import * as memory from '../../lib/api/designMemory'

type Copy = (zh: string, en: string) => string
function Field({ title, children }: { title: string; children: ReactNode }) { return <label className="flex flex-col gap-1 text-sm"><span>{title}</span>{children}</label> }
function read(form: FormData, key: string) { return String(form.get(key) ?? '').trim() }
const outcomes = [['hypothesis', '待验证假说', 'Hypothesis'], ['supported', '支持', 'Supported'], ['refuted', '反证', 'Refuted'], ['inconclusive', '不确定', 'Inconclusive'], ['method_invalid', '方法无效', 'Method invalid'], ['execution_blocked', '执行受阻（未检验假说）', 'Execution blocked (hypothesis untested)']]
function outcomeLabel(value: string, copy: Copy) { const row = outcomes.find(r => r[0] === value); return row ? copy(row[1], row[2]) : value }
const planFields = [['hypothesis', '本轮假说或问题', 'Hypothesis or question'], ['action', '设计动作 / 改变的因素', 'Design action / changed factor'], ['comparison', '比较组与匹配对照', 'Comparison and matched controls'], ['readout', '读出、单位与证据记录', 'Readout, units and evidence record'], ['decision_rule', '预先约定的通过 / 否定 / 无效条件', 'Predefined support / refutation / invalidity criteria']]

function useAction(projectId: string) {
  const cache = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  async function perform(action: () => Promise<unknown>) {
    if (busy) return
    setBusy(true); setError(''); setSaved(false)
    try {
      await action()
      await Promise.all([
        cache.invalidateQueries({ queryKey: ['design-lessons', projectId] }),
        cache.invalidateQueries({ queryKey: ['design-learning'] }),
        cache.invalidateQueries({ queryKey: ['workflow-preflight'] }),
        cache.invalidateQueries({ queryKey: ['workflow-graph'] }),
      ])
      setSaved(true)
    } catch (err) { setError(err instanceof Error ? err.message : String(err)) }
    finally { setBusy(false) }
  }
  return { busy, error, saved, perform }
}
function Notice({ action, copy }: { action: ReturnType<typeof useAction>; copy: Copy }) { return <>{action.error && <p role="alert">{action.error}</p>}{action.saved && <p role="status">{copy('已保存，后续设计将检查更新后的记录。', 'Saved. Future designs will review the updated record.')}</p>}</> }

function LessonCard({ lesson, copy }: { lesson: memory.Lesson; copy: Copy }) {
  const p = lesson.payload
  return <Disclosure className="rounded-md border border-border p-3" title={<>{p.title} · {outcomeLabel(p.outcome, copy)}</>}>
    <dl className="mt-3 grid gap-2 text-sm">
      {[[copy('结论/假说', 'Statement / hypothesis'), p.statement], [copy('适用条件', 'Conditions'), p.conditions], [copy('局限与不确定性', 'Limits and uncertainty'), p.limitations], [copy('下一轮改变', 'Next design change'), p.next_design_change]].map(([k, v]) => <div key={k}><dt className="font-medium">{k}</dt><dd className="whitespace-pre-wrap text-text-secondary">{v}</dd></div>)}
      <div><dt className="font-medium">{copy('证据来源', 'Evidence sources')}</dt><dd>{p.evidence.map((ref, i) => <p key={i} className="break-all">{ref}</p>)}</dd></div>
      <div><dt>{copy('记录', 'Record')}</dt><dd className="break-all text-text-secondary">{lesson.id} · {new Date(lesson.created_at).toLocaleString()}</dd></div>
      {p.origin && <p>{copy('从其他项目引入的证据快照，需重新评估适用性。', 'Imported evidence snapshot; applicability must be reassessed.')}</p>}
    </dl>
  </Disclosure>
}

function LessonFields({ copy, feedback = false, initial }: { copy: Copy; feedback?: boolean; initial?: memory.Lesson['payload'] }) {
  return <>
    <Field title={copy('经验标题', 'Lesson title')}><Input name="title" required maxLength={200} defaultValue={initial?.title} /></Field>
    {([['statement', '结论或待验证假说', 'Conclusion or hypothesis'], ['conditions', '适用条件（对象、状态、方法、环境）', 'Conditions (object, state, method, environment)'], ['limitations', '局限与不确定性', 'Limits and uncertainty'], ['next_design_change', '对下一轮设计的具体改变', 'Specific change for the next design']] as const).map(([key, zh, en]) => <Field key={key} title={copy(zh, en)}><Textarea name={key} required maxLength={6000} defaultValue={initial?.[key]} /></Field>)}
    <Field title={copy('证据引用（每行一个链接、文献号或记录标识）', 'Evidence references (one URL, citation or record ID per line)')}><Textarea name="evidence" required maxLength={18000} defaultValue={initial?.evidence.join('\n')} /></Field>
    <Field title={copy('证据判断', 'Evidence assessment')}><Choice name="outcome" required defaultValue={initial?.outcome ?? ''}><option value="">{copy('请选择', 'Select')}</option>{outcomes.filter(r => !feedback || r[0] !== 'hypothesis').map(r => <option key={r[0]} value={r[0]}>{copy(r[1], r[2])}</option>)}</Choice></Field>
  </>
}
function lessonBody(form: FormData): memory.LessonCreate {
  return { title: read(form, 'title'), statement: read(form, 'statement'), conditions: read(form, 'conditions'), limitations: read(form, 'limitations'), evidence: read(form, 'evidence').split('\n').map(v => v.trim()).filter(Boolean), outcome: read(form, 'outcome') as memory.LessonCreate['outcome'], next_design_change: read(form, 'next_design_change') }
}

export function DesignLessonLibrary({ projectId, writable }: { projectId: string; writable: boolean }) {
  const { language } = useI18n()
  const copy: Copy = (zh, en) => language === 'zh' ? zh : en
  const query = useQuery({ queryKey: ['design-lessons', projectId], queryFn: () => memory.listDesignLessons(projectId) })
  const [sourceProject, setSourceProject] = useState('')
  const [revision, setRevision] = useState('')
  const [showForm, setShowForm] = useState(false)
  const action = useAction(projectId)
  const projects = useQuery({ queryKey: ['design-memory-projects'], queryFn: listProjects, enabled: writable })
  const source = useQuery({ queryKey: ['design-lessons', sourceProject], queryFn: () => memory.listDesignLessons(sourceProject), enabled: Boolean(sourceProject) })
  const items = query.data ?? []
  const active = items.filter(r => !items.some(other => other.supersedes_id === r.id))
  const previous = active.find(r => r.id === revision)
  return <section className="mb-4 space-y-3 rounded-lg border border-border p-4" aria-label={copy('设计经验库', 'Design lesson library')}>
    <h2 className="font-semibold">{copy('设计经验库 · 所有项目通用', 'Design lesson library · available in every project')}</h2>
    <p className="text-sm text-text-secondary">{copy('先查已有经验与适用条件，再定义本轮要学什么。结果回写后，下一轮会自动读到；证据判断由研究者确认。', 'Review experience and conditions, then define what to learn. Recorded outcomes enter the next review; researchers assess the evidence.')}</p>
    {query.isPending && <p role="status">{copy('正在读取经验…', 'Loading lessons…')}</p>}
    {query.isError && <p role="alert">{query.error.message}<Button variant="outline" onClick={() => void query.refetch()}>{copy('重试', 'Retry')}</Button></p>}
    {query.isSuccess && !active.length && <p className="text-sm">{copy('暂无已记录经验。新设计仍需完成六项通用检查，并明确待验证的问题。', 'No lessons recorded yet. New designs still review six core questions and define uncertainties.')}</p>}
    {active.map(lesson => <LessonCard key={lesson.id} lesson={lesson} copy={copy} />)}
    {items.length > active.length && <Disclosure title={<>{copy('历史版本', 'Previous versions')} ({items.length - active.length})</>}>{items.filter(r => !active.includes(r)).map(lesson => <LessonCard key={lesson.id} lesson={lesson} copy={copy} />)}</Disclosure>}
    {writable && query.isSuccess && <>
      <Button variant="outline" onClick={() => setShowForm(v => !v)}>{copy('记录经验 / 修订结论', 'Record / revise a lesson')}</Button>
      {showForm && <form className="space-y-3" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); void action.perform(() => memory.createDesignLesson(projectId, { ...lessonBody(form), ...(revision ? { supersedes_id: revision } : {}) })) }}>
        <fieldset disabled={action.busy} className="grid gap-3 md:grid-cols-2">
          <Field title={copy('新增或追加修订（原记录保留）', 'New lesson or appended revision (history retained)')}><Choice value={revision} onChange={e => setRevision(e.target.value)}><option value="">{copy('新增经验', 'New lesson')}</option>{active.map(r => <option key={r.id} value={r.id}>{r.payload.title}</option>)}</Choice></Field><div />
          <LessonFields key={revision} copy={copy} initial={previous?.payload} /><Button type="submit">{copy('保存经验', 'Save lesson')}</Button>
        </fieldset>
      </form>}
      <Disclosure title={copy('从有权访问的其他项目引入经验', 'Import experience from another accessible project')}>
        <div className="mt-3 space-y-3"><Field title={copy('来源项目', 'Source project')}><Choice value={sourceProject} onChange={e => setSourceProject(e.target.value)}><option value="">{copy('选择项目', 'Select project')}</option>{projects.data?.filter(p => p.id !== projectId).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Choice></Field>
          {(projects.isError || source.isError) && <p role="alert">{copy('来源加载失败，请重试。', 'Source could not be loaded; retry.')}<Button variant="outline" onClick={() => { void projects.refetch(); if (sourceProject) void source.refetch() }}>{copy('重试', 'Retry')}</Button></p>}
          {source.isFetching && sourceProject && <p role="status">{copy('正在读取来源…', 'Loading source…')}</p>}
          {source.data?.filter(r => !source.data.some(other => other.supersedes_id === r.id)).map(r => <div className="space-y-2" key={r.id}><LessonCard lesson={r} copy={copy} /><Button variant="outline" disabled={action.busy || items.some(i => i.payload.origin?.lesson_id === r.id)} onClick={() => void action.perform(() => memory.importDesignLesson(projectId, r.id))}>{copy('引入并在本项目重新评估', 'Import for reassessment in this project')}</Button></div>)}
        </div>
      </Disclosure>
    </>}
    <Notice action={action} copy={copy} />
  </section>
}

function ReviewQuestion({ itemKey, title, prompt, prior, copy }: { itemKey: string; title: string; prompt?: string; prior?: memory.ReviewItem; copy: Copy }) {
  const [choice, setChoice] = useState('')
  const name = (key: string) => `${itemKey}/${key}`
  return <section className="rounded-md border border-border p-3">
    <h3 className="font-medium">{title} · {choice ? copy('已填写判断', 'Assessment entered') : copy('待检查', 'Review needed')}</h3>
    <div className="mt-3 grid gap-3 md:grid-cols-2">
      {prompt && <p className="whitespace-pre-wrap text-sm text-text-secondary md:col-span-2">{prompt}</p>}
      <Field title={copy('本轮适用性（每次重新确认）', 'Applicability (reconfirm for this design)')}><Choice name={name('disposition')} value={choice} onChange={e => setChoice(e.target.value)} required><option value="">{copy('请选择', 'Select')}</option><option value="apply">{copy('适用，纳入设计', 'Apply to this design')}</option><option value="test">{copy('不确定，设置验证', 'Uncertain; test it')}</option><option value="not_applicable">{copy('不适用，说明原因', 'Not applicable; explain why')}</option></Choice></Field>
      <Field title={copy('适用 / 不适用的理由与条件', 'Rationale and conditions')}><Textarea name={name('rationale')} required maxLength={6000} defaultValue={prior?.rationale} /></Field>
      {choice && choice !== 'not_applicable' && planFields.map(([key, zh, en]) => <Field key={key} title={copy(zh, en)}><Textarea name={name(key)} required maxLength={6000} defaultValue={prior?.[key as keyof memory.ReviewItem] ?? ''} /></Field>)}
    </div>
  </section>
}

function ReviewEditor({ state, workflowId, projectId, writable, copy }: { state: memory.DesignLearning; workflowId: string; projectId: string; writable: boolean; copy: Copy }) {
  const action = useAction(projectId)
  const [extra, setExtra] = useState<string[]>(state.review?.payload.items.filter(i => i.key.startsWith('question:')).map(i => i.key) ?? [])
  const questions = [...state.checklist.map(i => ({ key: i.key, title: copy(i.title, i.title_en), prompt: copy(i.prompt, i.prompt_en) })), ...state.lessons.map(l => ({ key: `lesson:${l.id}`, title: l.payload.title, prompt: `${l.payload.statement}\n${copy('适用条件', 'Conditions')}: ${l.payload.conditions}\n${copy('证据判断', 'Assessment')}: ${outcomeLabel(l.payload.outcome, copy)}\n${copy('局限', 'Limits')}: ${l.payload.limitations}\n${copy('证据', 'Evidence')}: ${l.payload.evidence.join('; ')}` })), ...extra.map(key => ({ key, title: copy('本设计新增学习问题', 'Additional learning question'), prompt: '' }))]
  return <form className="space-y-3" onSubmit={event => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const items = questions.map(q => ({ key: q.key, disposition: read(form, `${q.key}/disposition`) as memory.ReviewItem['disposition'], rationale: read(form, `${q.key}/rationale`), ...Object.fromEntries(planFields.map(([k]) => [k, read(form, `${q.key}/${k}`)])) }))
    void action.perform(() => memory.saveDesignReview(workflowId, state.workflow_version, { fingerprint: state.fingerprint, memory_digest: state.memory_digest, objective: read(form, 'objective'), context: read(form, 'context'), items }))
  }}>
    <fieldset disabled={!writable || action.busy} className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2"><Field title={copy('本轮设计目标（指标及方向）', 'Design objective (metric and direction)')}><Textarea name="objective" required maxLength={6000} defaultValue={state.review?.payload.objective} /></Field><Field title={copy('本轮上下文与适用范围', 'Context and scope')}><Textarea name="context" required maxLength={6000} defaultValue={state.review?.payload.context} /></Field></div>
      {questions.map(q => <ReviewQuestion key={q.key} itemKey={q.key} title={q.title} prompt={q.prompt} prior={state.review?.payload.items.find(i => i.key === q.key)} copy={copy} />)}
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={() => setExtra(keys => [...keys, `question:${crypto.randomUUID()}`])}>{copy('增加本设计要学习的问题', 'Add a learning question')}</Button><Button type="submit">{copy('保存设计前评审', 'Save pre-design review')}</Button></div>
    </fieldset>
    <Notice action={action} copy={copy} />
  </form>
}

export function DesignLearningPanel({ workflowId, projectId, workflowVersion, draft, writable }: { workflowId: string; projectId: string; workflowVersion: number; draft: boolean; writable: boolean }) {
  const { language } = useI18n()
  const copy: Copy = (zh, en) => language === 'zh' ? zh : en
  const query = useQuery({ queryKey: ['design-learning', workflowId, workflowVersion], queryFn: () => memory.getDesignLearning(workflowId), refetchOnWindowFocus: false })
  const state = query.data
  const action = useAction(projectId)
  const labels = { missing: copy('待完成设计前评审', 'Pre-design review needed'), stale: copy('设计或经验已变化，需要重新评审', 'Design or lessons changed; review again'), ready: copy('设计前评审已通过', 'Pre-design review complete'), frozen: copy('原设计评审已冻结', 'Original design review frozen') }
  return <section className="mb-4 space-y-3 rounded-lg border border-border p-4" aria-label={copy('设计学习闭环', 'Design learning loop')}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">{copy('设计学习闭环', 'Design learning loop')}</h2><Link className="text-sm underline" to={`/learning?project=${projectId}`}>{copy('打开项目经验库', 'Open project lesson library')}</Link></div>
    <ol className="flex flex-wrap gap-3 text-sm text-text-secondary"><li>{copy('1 查经验与适用条件', '1 Review experience and conditions')}</li><li>→ {copy('2 冻结假说与门控', '2 Freeze hypotheses and criteria')}</li><li>→ {copy('3 执行与读出', '3 Execute and measure')}</li><li>→ {copy('4 回写并用于下一轮', '4 Record outcomes for the next design')}</li></ol>
    {query.isPending && <p role="status">{copy('正在检查已有经验…', 'Checking prior experience…')}</p>}
    {query.isError && <p role="alert">{query.error.message}<Button variant="outline" onClick={() => void query.refetch()}>{copy('重试', 'Retry')}</Button></p>}
    {state && !query.isError && <>
      <p role="status" className="text-sm font-medium">{labels[state.state]} · {copy('经验条目', 'Prior lessons')} {state.lessons.length}</p>
      {!state.required && <p className="text-sm text-text-secondary">{copy('历史路线尚未启用此门控。草稿保存评审后启用；所有新建路线自动要求评审。', 'This historical route has no learning gate. Saving a draft review enables it; new routes require it automatically.')}</p>}
      {draft && <Disclosure key={`${state.state}:${state.required}`} defaultOpen={state.state !== 'ready' && state.required} title={copy('设计前学习清单', 'Pre-design learning checklist')}><div className="mt-3"><ReviewEditor key={`${workflowId}:${state.fingerprint}:${state.memory_digest}:${state.review?.id ?? ''}`} state={state} workflowId={workflowId} projectId={projectId} writable={writable} copy={copy} /></div></Disclosure>}
      {state.review && <>
        <Disclosure title={<>{copy('查看冻结评审与版本历史', 'View frozen review and version history')} ({state.history.length})</>}>{state.history.map(review => <article className="mt-3 space-y-2 border-t border-border pt-3 text-sm" key={review.id}><p>{new Date(review.created_at).toLocaleString()} · {review.payload.objective}</p><p className="text-text-secondary">{review.payload.context}</p>{review.payload.items.map(item => <Disclosure key={item.key} title={<>{item.hypothesis || item.key} · {item.disposition}</>}><p>{item.rationale}</p>{planFields.filter(([k]) => k !== 'hypothesis').map(([k, zh, en]) => <p key={k}>{copy(zh, en)}: {item[k as keyof memory.ReviewItem]}</p>)}</Disclosure>)}</article>)}</Disclosure>
        {!draft && <Disclosure defaultOpen={state.pending_feedback.length > 0} title={<>{copy('结果回流', 'Result feedback')} · {state.pending_feedback.length ? `${state.pending_feedback.length} ${copy('项待记录', 'items pending')}` : copy('已记录全部适用项', 'All applicable items recorded')}</>}>
          <p className="my-3 text-sm text-text-secondary">{copy('运行成功不等于假说成立。逐项关联结果证据、适用条件、不确定性与下一轮改变；失败和无效方法也需要留下记录。', 'A successful run does not prove a hypothesis. Record evidence, conditions, uncertainty and next changes for each item, including failures and invalid methods.')}</p>
          {state.feedback.map(lesson => <LessonCard key={lesson.id} lesson={lesson} copy={copy} />)}
          <form className="mt-3" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); void action.perform(() => memory.saveDesignFeedback(workflowId, { ...lessonBody(form), outcome: read(form, 'outcome') as memory.FeedbackCreate['outcome'], review_id: state.review!.id, item_key: read(form, 'item_key') })) }}>
            <fieldset disabled={!writable || action.busy} className="grid gap-3 md:grid-cols-2"><Field title={copy('对应原设计问题', 'Question from the original review')}><Choice name="item_key" required defaultValue=""><option value="">{copy('请选择', 'Select')}</option>{state.review.payload.items.filter(i => i.disposition !== 'not_applicable').map(i => <option key={i.key} value={i.key}>{state.pending_feedback.includes(i.key) ? '○ ' : '✓ '}{i.hypothesis || i.key}</option>)}</Choice></Field><div /><LessonFields copy={copy} feedback /><Button type="submit">{copy('保存结果并回写经验库', 'Save outcome to the lesson library')}</Button></fieldset>
          </form>
        </Disclosure>}
      </>}
    </>}
    <Notice action={action} copy={copy} />
  </section>
}
