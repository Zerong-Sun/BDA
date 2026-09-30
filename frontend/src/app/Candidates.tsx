import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select'
import { FOLD_CONFIDENCE_FLOOR, canonicalFoldConfidence, screenByFoldConfidence } from '../features/candidates/foldConfidence'
import { candidatesCsv } from '../features/candidates/candidatesCsv'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { DownloadSimpleIcon } from '@phosphor-icons/react'
import { downloadCandidateStructures, listAllCandidates } from '../lib/api/candidates'
import { getCandidateFunnel } from '../lib/api/projects'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useToastStore } from '../components/ui/toastStore'
import { useI18n } from '../lib/i18n'
import { PageHead } from '../components/ui/PageHead'
import { ApiState } from '../components/ui/ApiState'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../components/ui/AppFrame'
import { CandidateFilters } from '../features/candidates/CandidateFilters'
import { CandidateTable } from '../features/candidates/CandidateTable'
import { CandidateDetail } from '../features/candidates/CandidateDetail'
import { ComputeStatusStrip } from '../features/workflow/ComputeStatusStrip'
import { candidateScore, candidateText, resolveActiveCandidate, type Candidate } from '../lib/schemas/candidate'
import { NextStep } from '../components/ui/NextStep'
import { GlossaryTooltip } from '../components/ui/GlossaryTooltip'

const funnelStageKeys = ['generated', 'designed', 'folded', 'scored', 'ordered'] as const
const priorityDecisions = new Set(['anchor', 'order', 'retest'])

function CandidateGridSkeleton({ label }: { label: string }) {
  return (
    <AppFrame panelClassName="space-y-3 p-4" aria-label={label}>
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-9 w-full" />
      ))}
    </AppFrame>
  )
}

export function CandidatesPage() {
  const { t, format, language } = useI18n()
  const zh = language === 'zh'
  const { projectId } = useProjectContext()
  const showToast = useToastStore((s) => s.show)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('All')
  const [priorityOnly, setPriorityOnly] = useState(false)
  const [confidenceFilter, setConfidenceFilter] = useState({ scope: '', enabled: false })
  const [searchParams, setSearchParams] = useSearchParams()
  const linkedCandidateId = searchParams.get('candidate')?.trim() || null
  const [selected, setSelected] = useState<Candidate | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [isDownloading, setIsDownloading] = useState(false)

  const {
    data,
    isLoading,
    isError,
    error: candidatesError,
    refetch,
  } = useQuery({
    queryKey: ['candidates', projectId],
    queryFn: () => listAllCandidates(projectId, { limit: 100 }),
    enabled: Boolean(projectId),
  })

  const { data: funnel } = useQuery({
    queryKey: ['candidate-funnel', projectId],
    queryFn: () => getCandidateFunnel(projectId),
    enabled: Boolean(projectId),
  })

  const allCandidates = useMemo(() => data?.items ?? [], [data])
  const sources = [...new Set(allCandidates.map((c) => String(c.properties.source_dataset ?? '')).filter(Boolean))].sort()
  const linkedSource = linkedCandidateId ? String(allCandidates.find((c) => c.id === linkedCandidateId)?.properties.source_dataset ?? 'all') : null
  const requestedSource = searchParams.get('dataset') ?? linkedSource ?? sources[0] ?? 'all'
  const activeSource = sources.includes(requestedSource) ? requestedSource : 'all'
  const normalizedSearch = search.trim().toLocaleLowerCase()
  const normalizedStatus = status.toLocaleLowerCase()
  const matching = allCandidates.filter((candidate) => {
      const matchesSearch =
        !normalizedSearch ||
        [
          candidate.id,
          candidate.candidate_key,
          candidate.name,
          candidateText(candidate, 'family'),
        ].some((value) => value?.toLocaleLowerCase().includes(normalizedSearch))
      const matchesStatus =
        status === 'All' || candidate.status.toLocaleLowerCase() === normalizedStatus
      const matchesPriority =
        !priorityOnly ||
        priorityDecisions.has((candidateText(candidate, 'decision') ?? '').toLocaleLowerCase())
      const matchesSource = activeSource === 'all' || candidate.properties.source_dataset === activeSource
      return matchesSearch && matchesStatus && matchesPriority && matchesSource
  })

  const confidenceScope = `${projectId}:${activeSource}`
  const foldScreen = confidenceFilter.scope === confidenceScope && confidenceFilter.enabled
  const confidenceScreen = screenByFoldConfidence(matching)
  const candidates = foldScreen
    ? matching.filter(candidate => !confidenceScreen.screenedOut.includes(candidate) || candidate.id === linkedCandidateId)
    : matching
  const hiddenCount = matching.length - candidates.length

  useEffect(() => {
    const resetSelection = window.setTimeout(() => {
      setSelected(null)
      setSelectedIds(new Set())
    }, 0)
    return () => window.clearTimeout(resetSelection)
  }, [projectId])

  // A construct on the bench links back here by candidate id. Derive the selection from
  // it rather than writing it into state on load: an explicit pick still wins, and the
  // link keeps working after a refetch without an effect that re-selects on every render.
  const linkedCandidate = linkedCandidateId
    ? candidates.find((candidate) => candidate.id === linkedCandidateId) ?? null
    : null
  const activeCandidate = resolveActiveCandidate(candidates, selected ?? linkedCandidate)
  const selectedCount = selectedIds.size

  const exportCsv = () => {
    if (!candidates.length) return
    const blob = new Blob([candidatesCsv(candidates)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bda_candidates.csv'
    a.click()
    URL.revokeObjectURL(url)
    showToast(t.candidatesExt.toasts.csvExported, 'success')
  }

  const toggleCandidate = (candidateId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(candidateId)) {
        next.delete(candidateId)
      } else {
        next.add(candidateId)
      }
      return next
    })
  }

  const togglePage = (candidateIds: string[]) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      const allSelected =
        candidateIds.length > 0 && candidateIds.every((candidateId) => next.has(candidateId))
      for (const candidateId of candidateIds) {
        if (allSelected) {
          next.delete(candidateId)
        } else {
          next.add(candidateId)
        }
      }
      return next
    })
  }

  const downloadSelected = async () => {
    const ids = [...selectedIds]
    if (!ids.length) return
    setIsDownloading(true)
    try {
      await downloadCandidateStructures(projectId, ids, `${projectId}_selected_candidates.zip`)
      showToast(
        format(ids.length === 1 ? t.candidatesExt.toasts.downloadedStructures : t.candidatesExt.toasts.downloadedStructuresPlural, {
          count: ids.length,
        }),
        'success',
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : t.candidatesExt.toasts.downloadFailed
      showToast(message, 'error')
    } finally {
      setIsDownloading(false)
    }
  }

  const downloadPage = async (candidateIds: string[], pageIndex: number) => {
    if (!candidateIds.length) return
    setIsDownloading(true)
    try {
      await downloadCandidateStructures(
        projectId,
        candidateIds,
        `${projectId}_page_${pageIndex + 1}_candidates.zip`,
      )
      showToast(format(t.candidatesExt.toasts.downloadedPage, { count: candidateIds.length }), 'success')
    } catch (err) {
      const message = err instanceof Error ? err.message : t.candidatesExt.toasts.downloadFailed
      showToast(message, 'error')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <section>
      <PageHead
        eyebrow={t.candidates.eyebrow}
        title={t.candidates.title}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={exportCsv}
            >
              <DownloadSimpleIcon aria-hidden="true" />
              {t.candidates.exportCsv}
            </Button>
            <Button
              type="button"
              disabled={!selectedCount || isDownloading}
              onClick={() => void downloadSelected()}
            >
              <DownloadSimpleIcon aria-hidden="true" />
              {selectedCount
                ? format(t.candidatesExt.pagination.downloadSelectedCount, { count: selectedCount })
                : t.candidatesExt.pagination.downloadSelected}
            </Button>
          </div>
        }
      />
      <ComputeStatusStrip />

      {activeSource !== 'all' ? <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4" data-tour-id="candidate-funnel">
        {[
          [zh ? '计算候选' : 'Candidates', candidates.length],
          [zh ? '可用三维结构' : 'Structures', candidates.filter(c => c.complex_artifact_id || c.structure_artifact_id).length],
          [zh ? '平均 pLDDT（已确认 0–100）' : 'Mean pLDDT (confirmed 0–100)', (() => { const values = candidates.map(canonicalFoldConfidence).filter((v): v is number => v !== null); return values.length ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2) : '—' })()],
          [zh ? '界面预测覆盖' : 'Interface metrics', candidates.filter(c => candidateScore(c, 'iptm') !== null).length],
        ].map(([label, value]) => <AppFrame key={label} panelClassName="p-4"><span className="text-xs text-text-secondary">{label}</span><strong className="mt-2 block text-2xl">{value}</strong></AppFrame>)}
      </div> : (
      <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5" data-tour-id="candidate-funnel">
        {funnelStageKeys.map((stageKey) => {
          const label = t.candidatesExt.funnel[stageKey]
          const value = funnel?.[stageKey] ?? '—'
          return (
            <AppFrame key={stageKey} panelClassName="p-3">
              <span className="text-xs text-text-secondary">
                <GlossaryTooltip label={label} description={t.candidatesExt.funnelHelp[stageKey]} />
              </span>
              <strong className="mt-1 block text-xl">
                {typeof value === 'number' ? value.toLocaleString() : value}
              </strong>
            </AppFrame>
          )
        })}
      </div>
      )}

      {sources.length ? <label className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        {zh ? '候选数据集' : 'Candidate dataset'}
        <Select value={activeSource}
          onValueChange={(value) => {
            if (!value) return
            const next = new URLSearchParams(searchParams); next.set('dataset', String(value)); next.delete('candidate')
            setSearchParams(next); setSelected(null); setSelectedIds(new Set())
          }}>
          <SelectTrigger aria-label={zh ? '候选数据集' : 'Candidate dataset'} className="max-w-full"><SelectValue>{activeSource === 'all' ? (zh ? '全部项目记录' : 'All project records') : activeSource}</SelectValue></SelectTrigger>
          <SelectContent>{sources.map((source) => <SelectItem key={source} value={source}>{source}</SelectItem>)}
          <SelectItem value="all">{zh ? '全部项目记录' : 'All project records'}</SelectItem></SelectContent>
        </Select>
        <span className="text-text-secondary">{zh ? '按来源数据集查看候选、结构与预测指标。' : 'Filters the candidate table; workflow counts above cover the whole project.'}</span>
      </label> : null}
      <div data-tour-id="candidate-filters">
      <CandidateFilters
        search={search}
        status={status}
        priorityOnly={priorityOnly}
        onSearchChange={setSearch}
        onStatusChange={setStatus}
        onPriorityOnlyChange={setPriorityOnly}
      />
      </div>

      {(confidenceScreen.screenedOut.length > 0 || confidenceScreen.uncertain.length > 0) ? (
        <AppFrame className="mb-4" panelClassName="flex flex-wrap items-center justify-between gap-3 p-3">
          <div className="text-sm text-text-secondary" role="status">
            {confidenceScreen.screenedOut.length > 0 ? <p>{format(
              foldScreen ? t.candidatesExt.foldScreen.withheld : t.candidatesExt.foldScreen.included,
              { count: foldScreen ? hiddenCount : confidenceScreen.screenedOut.length, floor: FOLD_CONFIDENCE_FLOOR },
            )}</p> : null}
            {confidenceScreen.uncertain.length > 0 ? <p>{format(t.candidatesExt.foldScreen.uncertain, { count: confidenceScreen.uncertain.length })}</p> : null}
          </div>
          {confidenceScreen.screenedOut.length > 0 ? <Button type="button" variant="outline" onClick={() => {
            setConfidenceFilter({ scope: confidenceScope, enabled: !foldScreen })
            setSelected(null)
            setSelectedIds(new Set())
          }}>{foldScreen ? t.candidatesExt.foldScreen.show : t.candidatesExt.foldScreen.hide}</Button> : null}
        </AppFrame>
      ) : null}

      <ApiState
        isLoading={isLoading}
        isError={isError}
        error={candidatesError}
        onRetry={() => void refetch()}
        loadingSkeleton={<CandidateGridSkeleton label={t.candidatesExt.table.loadingAriaLabel} />}
      >
        <div className="grid min-h-0 gap-4 xl:h-[calc(100vh-22rem)] xl:min-h-[34rem] xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.9fr)]" data-tour-id="candidate-table">
          <div className="flex min-h-[34rem] flex-col overflow-hidden xl:min-h-0">
            <AppFrame className="min-h-0 flex-1" panelClassName="min-h-0 overflow-hidden">
              <CandidateTable
                key={`${projectId}:${activeSource}:${search}:${status}:${priorityOnly}:${foldScreen}`}
                data={candidates}
                selectedId={activeCandidate?.id}
                selectedIds={selectedIds}
                onSelect={setSelected}
                onToggleCandidate={toggleCandidate}
                onTogglePage={togglePage}
                onClearSelection={() => setSelectedIds(new Set())}
                onDownloadPage={(candidateIds, pageIndex) => {
                  void downloadPage(candidateIds, pageIndex)
                }}
                isDownloading={isDownloading}
              />
            </AppFrame>
          </div>
          <CandidateDetail candidate={activeCandidate} projectId={projectId} />
        </div>
      </ApiState>

      <NextStep stage="candidates" />
    </section>
  )
}
