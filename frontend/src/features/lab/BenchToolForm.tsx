import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select'
import { calculateBench, type BenchRequest, type BenchResult } from '../../lib/api/bench'
import { useI18n } from '../../lib/i18n'
import { ApiError } from '../../lib/api/client'
import { calculationPayload, initialToolValues, type BenchTool, type ToolId } from './toolCatalog'

function numericText(value: number): string {
  if (value === 0) return '0'
  if (Math.abs(value) < 0.001 || Math.abs(value) >= 1e7) return value.toExponential(5)
  return Number(value.toPrecision(7)).toString()
}

function ResultPanel({ result, onUse, current, title }: { result: BenchResult; onUse: (tool: ToolId, values: Record<string, string>) => void; current: boolean; title: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(false)
  const assumptions = zh ? result.assumptions_zh : result.assumptions
  const warnings = (zh ? result.warnings_zh : result.warnings) ?? []
  const valueFor = (key: string) => result.values.find((value) => value.key === key)?.value
  const molecularWeight = valueFor('molecular_weight_g_mol')
  const reducedEpsilon = valueFor('epsilon_reduced')
  async function copyResult() {
    try {
      await navigator.clipboard.writeText([title, ...result.values.map((value) => `${zh ? value.label_zh : value.label}: ${numericText(value.value)} ${value.unit}`), result.formula, ...assumptions, ...warnings, ...result.references.map((reference) => reference.url)].join('\n'))
      setCopied(true)
      setCopyError(false)
    } catch { setCopyError(true) }
  }
  return <section className="space-y-4 border-t pt-5" aria-label={zh ? '计算结果' : 'Calculation result'}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{zh ? '计算结果' : 'Calculation result'}</h3><Button type="button" variant="outline" size="sm" onClick={copyResult} disabled={!current}>{copied ? (zh ? '已复制' : 'Copied') : (zh ? '复制结果与依据' : 'Copy result & method')}</Button></div>
    {!current ? <p role="status" className="border-l-2 border-warning pl-3 text-sm">{zh ? '输入已修改。以下是上次计算的结果，请重新计算后使用。' : 'Inputs changed. These are the previous results; calculate again before using them.'}</p> : null}
    {copyError ? <p role="alert" className="text-sm text-destructive">{zh ? '浏览器不允许复制，请选择结果文本手动复制。' : 'Clipboard access is unavailable. Select and copy the result text.'}</p> : null}
    <dl className={`grid gap-3 sm:grid-cols-2 ${current ? '' : 'opacity-60'}`}>{result.values.map((value) => <div key={value.key} className="min-w-0 border bg-muted/20 p-4"><dt className="text-xs leading-5 text-muted-foreground">{zh ? value.label_zh : value.label}</dt><dd className="mt-2 break-words font-mono text-xl tabular-nums">{numericText(value.value)} <span className="text-sm text-muted-foreground">{value.unit}</span></dd></div>)}</dl>
    {current && molecularWeight !== undefined ? <div className="flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => onUse('concentration', { molecular_weight_g_mol: String(molecularWeight) })}>{zh ? '用于浓度换算' : 'Use for concentration conversion'}</Button>
      {reducedEpsilon !== undefined && reducedEpsilon > 0 ? <Button type="button" size="sm" variant="outline" onClick={() => onUse('protein-a280', { molecular_weight_g_mol: String(molecularWeight), epsilon_M_inv_cm_inv: String(reducedEpsilon) })}>{zh ? '用还原态 ε 计算 A280 浓度' : 'Use reduced ε for A280 concentration'}</Button> : null}
      {result.kind === 'nucleic-properties' ? <Button type="button" size="sm" variant="outline" onClick={() => onUse('copy-number', { molecular_weight_g_mol: String(molecularWeight), _mass_basis: 'known' })}>{zh ? '用于拷贝数计算' : 'Use for copy number'}</Button> : null}
    </div> : null}
    <div className="space-y-2 text-sm"><h4 className="font-medium">{zh ? '公式与适用条件' : 'Formula & assumptions'}</h4><p className="overflow-x-auto border bg-muted/20 p-3 font-mono text-xs leading-6">{result.formula}</p><ul className="list-disc space-y-1 pl-5 leading-6">{assumptions.map((text) => <li key={text}>{text}</li>)}</ul></div>
    {warnings.length ? <ul className="list-disc space-y-1 border-l-2 border-warning pl-6 text-sm leading-6">{warnings.map((text) => <li key={text}>{text}</li>)}</ul> : null}
    <div className="border-t pt-3 text-xs leading-6 text-muted-foreground"><span>{zh ? '方法参考：' : 'Method references: '}</span>{result.references.map((reference) => <a key={reference.url} className="mr-3 underline underline-offset-2" href={reference.url} target="_blank" rel="noopener noreferrer">{reference.title}</a>)}</div>
  </section>
}

export type BenchDraft = { values: Record<string, string>; result: { value: BenchResult; input: string } | null }

export function BenchToolForm({ tool, prefill = {}, draft, onDraft, onUse }: { tool: BenchTool; prefill?: Record<string, string>; draft?: BenchDraft; onDraft?: (draft: BenchDraft) => void; onUse: (tool: ToolId, values: Record<string, string>) => void }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [values, setValues] = useState(() => draft?.values ?? initialToolValues(tool, prefill))
  const [error, setError] = useState('')
  const [result, setResult] = useState<BenchDraft['result']>(draft?.result ?? null)
  const inputFingerprint = JSON.stringify(values)
  const calculate = useMutation({ mutationFn: calculateBench, onSuccess: (value) => { const next = { value, input: inputFingerprint }; setResult(next); onDraft?.({ values, result: next }); setError('') } })
  function change(name: string, value: string) {
    const next = { ...values, [name]: value }
    setValues(next)
    onDraft?.({ values: next, result })
    setError('')
    calculate.reset()
  }
  function submit(event: React.FormEvent) {
    event.preventDefault()
    let body: Record<string, unknown>
    try { body = calculationPayload(tool, values) } catch (issue) { setError(`${zh ? '请检查输入：' : 'Check input: '}${(issue as Error).message}`); return }
    setError('')
    calculate.mutate(body as BenchRequest)
  }
  function reset() { const next = initialToolValues(tool); setValues(next); setResult(null); onDraft?.({ values: next, result: null }); setError(''); calculate.reset() }
  const problem = calculate.error instanceof ApiError ? calculate.error.payload as { errors?: { msg?: string; message?: string }[] } | undefined : undefined
  const detail = problem?.errors?.map((issue) => issue.msg ?? issue.message).filter(Boolean).slice(0, 3).join('; ')
  const backendError = calculate.error instanceof ApiError ? detail || calculate.error.message : calculate.error ? (zh ? '计算失败，请检查输入后重试。' : 'Calculation failed. Check your inputs and retry.') : ''
  return <div className="space-y-6">
    <form aria-label={tool.title[language]} onSubmit={submit} className="space-y-4">
      <fieldset disabled={calculate.isPending} className="grid gap-x-5 gap-y-4 sm:grid-cols-2 disabled:opacity-60">
        {tool.fields.filter((field) => !field.visible || field.visible(values)).map((field) => <label key={field.name} className={`grid content-start gap-2 text-sm ${field.type === 'sequence' ? 'sm:col-span-2' : ''}`}>
          <span className="font-medium">{field.label[language]}{field.optional ? (zh ? '（可选）' : ' (optional)') : ''}</span>
          {field.type === 'select' ? <Select disabled={calculate.isPending} items={field.options?.map((option) => ({ value: option.value, label: option.label[language] }))} value={values[field.name]} onValueChange={(value) => { if (value !== null) change(field.name, value) }}>
            <SelectTrigger aria-label={field.label[language]} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{field.options?.map((option) => <SelectItem key={option.value} value={option.value}>{option.label[language]}</SelectItem>)}</SelectContent>
          </Select> : field.type === 'sequence' ? <Textarea aria-label={field.label[language]} required maxLength={200_000} rows={6} spellCheck={false} autoComplete="off" className="w-full resize-y rounded border bg-background p-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-ring" value={values[field.name]} onChange={(event) => change(field.name, event.target.value)} /> :
            <Input type="number" required={!field.optional} min={field.min} step={field.step ?? 'any'} aria-label={field.label[language]} value={values[field.name]} onChange={(event) => change(field.name, event.target.value)} className="w-full font-mono" />}
          {field.help ? <span className="text-xs leading-5 text-muted-foreground">{field.help[language]}</span> : null}
        </label>)}
      </fieldset>
      {error || backendError ? <p role="alert" className="text-sm text-destructive">{error || backendError}</p> : null}
      <div className="flex items-center gap-3"><Button type="submit" disabled={calculate.isPending}>{calculate.isPending ? (zh ? '正在计算…' : 'Calculating…') : (zh ? '计算' : 'Calculate')}</Button><Button type="button" variant="ghost" disabled={calculate.isPending} onClick={reset}>{zh ? '清空并重置' : 'Clear & reset'}</Button></div>
    </form>
    {result ? <ResultPanel key={result.input} result={result.value} current={result.input === inputFingerprint} title={tool.title[language]} onUse={onUse} /> : <p className="border-t pt-5 text-sm text-muted-foreground">{zh ? '填写输入后计算。结果会同时显示单位、公式与适用条件。' : 'Enter inputs to calculate. Results include units, formulas and assumptions.'}</p>}
  </div>
}
