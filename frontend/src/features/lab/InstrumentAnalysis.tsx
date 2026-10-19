"use no memo"

import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useI18n } from '../../lib/i18n'
import { uploadArtifact } from '../../lib/api/artifacts'
import { previewInstrumentAnalysis, analyseAkta, analyseBli, analyseEnzyme } from '../../lib/api/wetlab'
import type { InstrumentAnalysisData } from '../../lib/schemas/instrumentAnalysis'
import { Frame, FrameHeader, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/checkbox'
import { Disclosure } from '../../components/ui/Disclosure'
import { Textarea } from '../../components/ui/textarea'
import { Input } from '../../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import { AnalysisResult } from './InstrumentResult'
import { SavedInstrumentReviews } from './SavedInstrumentReviews'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useAppStore } from '../../lib/store/appStore'
import { isPublicVisitor } from '../../lib/auth/publicWorkspace'

type Instrument = 'bli' | 'akta' | 'enzyme'

type InstrumentAnalysisProps = { projectId?: string; previewOnly?: boolean; instrument?: Instrument }
type DisplayAnalysis = InstrumentAnalysisData & { savedProjectId: string }

//: What each kernel can read. The picker narrows the file dialog rather than
//: relying on the 422 that a Unicorn zip handed to the BLI parser would produce.
const ACCEPT: Record<Instrument, string> = {
  bli: '.csv,text/csv',
  akta: '.zip',
  enzyme: '.xlsx',
}

function optionalNumber(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

/**
 * Upload an instrument export, analyse it, and look at what was fitted.
 *
 * The three kernels and their endpoints already existed and the Copilot could
 * already call them; what was missing was the way a person does it. The order
 * here is the platform's upload contract, not a choice: the file goes
 * browser-direct to object storage, and only its artifact id is posted to the
 * analysis endpoint. Standalone previews use the bounded ephemeral preview API;
 * saving a preview returns to the same artifact upload and analysis path.
 *
 * The plots are drawn from the series the response carries, because the backend
 * has no plotting library on purpose. Numbers that did not converge are shown as
 * such rather than hidden: a KD that four methods agree on means something quite
 * different from one that only a single method produced.
 */
export function InstrumentAnalysis({ projectId = '', previewOnly = false, instrument }: InstrumentAnalysisProps) {
  return <InstrumentAnalysisPanel key={`${instrument ?? 'all'}:${previewOnly ? 'preview' : projectId}`} projectId={projectId} previewOnly={previewOnly} instrument={instrument} />
}

function InstrumentAnalysisPanel({ projectId = '', previewOnly = false, instrument: fixedInstrument }: InstrumentAnalysisProps) {
  const { t, language } = useI18n()
  const copy = t.lab.instruments
  const access = useProjectAccess(projectId)
  const demo = useAppStore((state) => state.appMode === 'demo')
  const canSave = !demo && access.data?.permissions.experiment === true
  const canRun = previewOnly ? !isPublicVisitor() : canSave
  const accessMessage = language === 'zh'
    ? '当前为只读浏览，可查看已保存的分析。上传、分析和保存新版本需要项目实验权限。'
    : 'You can browse saved analyses. Uploading, analyzing and saving new versions requires project experiment access.'

  const [instrument, setInstrument] = useState<Instrument>(fixedInstrument ?? 'bli')
  const [file, setFile] = useState<File | null>(null)
  const [source, setSource] = useState<{ artifactId: string; resultId: string; label: string } | null>(null)
  const [mapping, setMapping] = useState('')
  const [excluded, setExcluded] = useState('')
  const [reference, setReference] = useState('')
  const [method, setMethod] = useState<'measured_global' | 'instrument_kobs'>('measured_global')
  const [correction, setCorrection] = useState('')
  const [baseline, setBaseline] = useState<'initial_point' | 'fitted_offset'>('initial_point')
  const [candidate, setCandidate] = useState({ projectId, value: '' })
  const candidateId = candidate.projectId === projectId ? candidate.value : ''
  const [sampleId, setSampleId] = useState('')
  const [channel, setChannel] = useState('')
  const [tAssoc, setTAssoc] = useState('')
  const [tDissoc, setTDissoc] = useState('')
  const [subtractBackground, setSubtractBackground] = useState(true)
  const [analysed, setAnalysed] = useState<DisplayAnalysis | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const run = useMutation({
    mutationFn: async (save: boolean): Promise<DisplayAnalysis> => {
      if (!canRun || (save && !canSave)) throw new Error(accessMessage)
      if (!file && !source) throw new Error(copy.file)
      const sample_mapping: Record<string, string> = {}
      for (const line of mapping.split('\n').map((line) => line.trim()).filter(Boolean)) {
        const [label, ...sample] = line.split('=')
        if (!label.trim() || !sample.join('=').trim()) throw new Error(language === 'zh' ? '映射格式为标签=样品，每行一条。' : 'Use label=sample for each mapping line.')
        sample_mapping[label.trim()] = sample.join('=').trim()
      }
      const processing = { baseline_mode: baseline, sample_mapping, excluded_labels: excluded.split(/[,\s]+/).filter(Boolean), reference_label: reference.trim() || null, analysis_method: method, correction_note: correction.trim() || null }

      if (previewOnly && !save) return { ...await previewInstrumentAnalysis(file!, {
        ...processing,
        instrument, sample_id: sampleId.trim() || null, channel: channel.trim() || null,
        t_assoc: optionalNumber(tAssoc), t_dissoc: optionalNumber(tDissoc), subtract_background: subtractBackground,
      }), savedProjectId: '' }
      if (!projectId) throw new Error(language === 'zh' ? '请先选择保存到哪个项目' : 'Choose a project before saving')
      const artifact = source ? { id: source.artifactId } : await uploadArtifact(file!, projectId)
      const candidate = candidateId.trim() || null
      if (instrument === 'bli') {
        const result = await analyseBli(projectId, {
          artifact_id: artifact.id,
          ...processing,
          supersedes_result_id: source?.resultId ?? null,
          sample_id: sampleId.trim() || null,
          t_assoc: optionalNumber(tAssoc),
          t_dissoc: optionalNumber(tDissoc),
          candidate_id: candidate,
        })
        return { instrument: 'bli', record: result, summary: result.summary, savedProjectId: projectId }
      }
      if (instrument === 'akta') {
        const result = await analyseAkta(projectId, {
          artifact_id: artifact.id,
          channel: channel.trim() || null,
          candidate_id: candidate,
        })
        return { instrument: 'akta', record: result, summary: result.summary, savedProjectId: projectId }
      }
      const result = await analyseEnzyme(projectId, {
        artifact_id: artifact.id,
        subtract_background: subtractBackground,
        candidate_id: candidate,
      })
      return { instrument: 'enzyme', record: result, summary: result.summary, savedProjectId: projectId }
    },
    onSuccess: (result) => setAnalysed(result),
  })

  return (
    <Frame dense>
      <FrameHeader>
        <FrameTitle>{fixedInstrument ? copy[fixedInstrument] : copy.title}</FrameTitle>
      </FrameHeader>

      <div className="space-y-5 p-4">
        <p className="max-w-3xl text-sm text-text-secondary">{previewOnly ? (language === 'zh' ? '先预览仪器导出文件与拟合结果。只有选择项目并点击保存后，才记录原始文件、分析结果及后续人工质控。' : 'Preview an instrument export and its fitted results. The source file and analysis are recorded only after you select a project and save; you can then record a human quality review.') : copy.intro}</p>

        {!canRun ? <p role="status" className="text-sm text-muted-foreground">{accessMessage}</p> : null}
        {access.isError ? <Button type="button" variant="outline" onClick={() => void access.refetch()}>{language === 'zh' ? '重新检查实验权限' : 'Retry experiment access'}</Button> : null}
        <fieldset disabled={run.isPending || !canRun}>
        <form
          onChange={() => { setAnalysed(null); run.reset() }}
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            run.mutate(false)
          }}
        >
          {!fixedInstrument ? <label className="flex flex-col gap-1 text-sm">
            <span>{copy.instrument}</span>
            <Select
              value={instrument}
              onValueChange={(next) => {
                setInstrument((next as Instrument) ?? instrument)
                setAnalysed(null)
                // The chosen file belongs to the instrument it was picked for;
                // a Unicorn zip handed to the BLI parser only produces a
                // confusing 422.
                setFile(null); setSource(null)
                if (fileInput.current) fileInput.current.value = ''
              }}
            >
              <SelectTrigger aria-label={copy.instrument} className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="bli">{copy.bli}</SelectItem>
                <SelectItem value="akta">{copy.akta}</SelectItem>
                <SelectItem value="enzyme">{copy.enzyme}</SelectItem>
              </SelectContent>
            </Select>
          </label> : null}

          {/* The picker is a hidden native input behind a registry Button, the
              same shape every other upload here uses: the browser's own file
              control cannot be styled or labelled consistently. */}
          <div className="flex flex-col gap-1 text-sm">
            <span>{copy.file}</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInput.current?.click()}
              >
                {copy.choose}
              </Button>
              <span className="max-w-48 truncate text-text-secondary">{file?.name ?? source?.label ?? '—'}</span>
            </div>
            <input
              ref={fileInput}
              type="file"
              aria-label={copy.file}
              accept={ACCEPT[instrument]}
              className="hidden"
              onChange={(event) => { setFile(event.target.files?.[0] ?? null); setSource(null) }}
            />
          </div>

          {instrument === 'bli' ? (
            <>
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.sample}</span>
                <Input
                  className="w-32"
                  value={sampleId}
                  onChange={(event) => setSampleId(event.target.value)}
                />
              </label>
              {/* Worth passing whenever the run declares them: without a
                  boundary the kernel reads one off the smoothed curve, which is
                  fine for a look and not what belongs behind a recorded KD. */}
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.tAssoc}</span>
                <Input
                  type="number"
                  step="any"
                  className="w-32 tabular-nums"
                  value={tAssoc}
                  onChange={(event) => setTAssoc(event.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span>{copy.tDissoc}</span>
                <Input
                  type="number"
                  step="any"
                  className="w-32 tabular-nums"
                  value={tDissoc}
                  onChange={(event) => setTDissoc(event.target.value)}
                />
              </label>
            </>
          ) : null}

          {instrument === 'akta' ? (
            <label className="flex flex-col gap-1 text-sm">
              <span>{copy.channel}</span>
              <Input
                className="w-40"
                value={channel}
                onChange={(event) => setChannel(event.target.value)}
              />
            </label>
          ) : null}

          {instrument === 'enzyme' ? (
            <label className="flex items-center gap-2 pb-2 text-sm">
              <Checkbox
                checked={subtractBackground}
                onCheckedChange={(next) => setSubtractBackground(next === true)}
              />
              {copy.subtractBackground}
            </label>
          ) : null}

          {!previewOnly || projectId ? <label className="flex flex-col gap-1 text-sm">
            <span>{copy.candidate}</span>
            <Input
              className="w-72"
              placeholder={copy.candidateHint}
              value={candidateId}
              onChange={(event) => setCandidate({ projectId, value: event.target.value })}
            />
          </label> : null}

          <Button type="submit" disabled={(!file && !source) || run.isPending}>
            {run.isPending ? copy.analysing : previewOnly ? (language === 'zh' ? '预览分析（不保存）' : 'Preview without saving') : source ? (language === 'zh' ? '保存新分析版本' : 'Save new analysis version') : copy.analyse}
          </Button>
          {instrument === 'bli' ? <Disclosure className="basis-full" title={language === 'zh' ? '样品映射、参考扣除与处理参数' : 'Sample mapping, reference subtraction and processing'}>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-sm"><span>{language === 'zh' ? '样品映射（标签=样品，每行一条）' : 'Sample mapping (label=sample, one per line)'}</span><Textarea value={mapping} onChange={(event) => setMapping(event.target.value)} placeholder="A1=sample-1" /></label>
              <label className="space-y-1 text-sm"><span>{language === 'zh' ? '排除标签（逗号分隔）' : 'Excluded labels (comma separated)'}</span><Input value={excluded} onChange={(event) => setExcluded(event.target.value)} /></label>
              <label className="space-y-1 text-sm"><span>{language === 'zh' ? '参考传感器标签' : 'Reference sensor label'}</span><Input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
              <label className="space-y-1 text-sm"><span>{language === 'zh' ? '分析方法' : 'Analysis method'}</span><Select value={method} onValueChange={(value) => { setMethod(value === 'instrument_kobs' ? 'instrument_kobs' : 'measured_global'); setAnalysed(null) }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="measured_global">{language === 'zh' ? '实测数据全局拟合' : 'Measured data global fit'}</SelectItem><SelectItem value="instrument_kobs">{language === 'zh' ? '仪器 Kobs 回归' : 'Instrument Kobs regression'}</SelectItem></SelectContent></Select></label>
              <label className="space-y-1 text-sm"><span>{language === 'zh' ? '基线处理' : 'Baseline processing'}</span><Select value={baseline} onValueChange={(value) => { setBaseline(value === 'fitted_offset' ? 'fitted_offset' : 'initial_point'); setAnalysed(null) }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="initial_point">{language === 'zh' ? '首个实测结合点' : 'First measured association point'}</SelectItem><SelectItem value="fitted_offset">{language === 'zh' ? '自由拟合偏移（敏感性分析）' : 'Fitted offset (sensitivity analysis)'}</SelectItem></SelectContent></Select></label>
              <label className="space-y-1 text-sm sm:col-span-2"><span>{language === 'zh' ? '更正与处理说明' : 'Correction and processing note'}</span><Textarea required={Boolean(source)} value={correction} onChange={(event) => setCorrection(event.target.value)} /></label>
            </div>
            <p className="mt-2 text-xs text-text-secondary">{language === 'zh' ? '样品标识须明确映射；采集结束时间不等于解离开始时间。保留原始文件，参数修改另存新版本。' : 'Map sample identities explicitly. Acquisition stop time is not the dissociation start. The raw source is preserved; parameter changes create a new version.'}</p>
          </Disclosure> : null}
        </form>
        </fieldset>
        {source ? <p className="break-all text-xs text-text-secondary">{language === 'zh' ? '新版本基于原始文件；替代分析记录' : 'New version from the preserved raw source; supersedes analysis'}: {source.resultId}</p> : null}
        {previewOnly && analysed && !analysed.record.experiment_result_id ? <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-text-secondary">{language === 'zh' ? '预览未保存。选择项目后可保存原始文件和分析结果。' : 'Unsaved preview. Choose a project to save the source file and analysis.'}</p>
          <Button type="button" disabled={!canSave || run.isPending} onClick={() => run.mutate(true)}>{language === 'zh' ? '保存到所选项目' : 'Save to selected project'}</Button>
        </div> : null}

        {run.error ? (
          <p role="alert" className="text-sm text-destructive">
            {(run.error as Error).message}
          </p>
        ) : null}

        {projectId && !previewOnly ? <SavedInstrumentReviews key={projectId} projectId={projectId} onReanalyse={canSave ? (saved, label) => {
          if (!canSave) return
          setCandidate({ projectId, value: saved.record.candidate_id ?? '' }); setInstrument(saved.instrument); setFile(null); setSource({ artifactId: saved.record.source_artifact_id, resultId: saved.record.experiment_result_id, label }); setAnalysed(null); run.reset()
          if (saved.instrument === 'bli') {
            setSampleId(saved.summary.sample_id); setTAssoc(String(saved.summary.phase?.t_assoc ?? '')); setTDissoc(String(saved.summary.phase?.t_dissoc ?? ''))
            const settings = saved.summary.processing ?? {}
            const mapping = settings.sample_mapping && typeof settings.sample_mapping === 'object' ? settings.sample_mapping as Record<string, unknown> : {}
            setMapping(Object.entries(mapping).map(([label, sample]) => `${label}=${String(sample)}`).join('\n'))
            setExcluded(Array.isArray(settings.excluded_labels) ? settings.excluded_labels.join(', ') : '')
            setBaseline(settings.baseline_mode === 'fitted_offset' ? 'fitted_offset' : 'initial_point')
            setReference(String(settings.reference_label ?? '')); setMethod(saved.summary.selected_method === 'instrument_kobs' ? 'instrument_kobs' : 'measured_global'); setCorrection('')
          }
          if (saved.instrument === 'akta') setChannel(saved.summary.channel)
          if (saved.instrument === 'enzyme') setSubtractBackground(saved.summary.background_subtracted)
          fileInput.current?.closest('section')?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
        } : undefined} /> : null}
        {analysed ? <AnalysisResult analysed={analysed} projectId={analysed.savedProjectId} onReviewed={(record) => setAnalysed((current) => current?.record.experiment_result_id === record.experiment_result_id ? { ...current, record } : current)} /> : null}
      </div>
    </Frame>
  )
}
