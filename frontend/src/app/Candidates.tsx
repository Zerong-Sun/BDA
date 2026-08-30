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
import { candidateText, resolveActiveCandidate, type Candidate } from '../lib/schemas/candidate'
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
  const { t, format } = useI18n()
  const { projectId } = useProjectContext()
  const showToast = useToastStore((s) => s.show)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('All')
  const [priorityOnly, setPriorityOnly] = useState(false)
  const [searchParams] = useSearchParams()
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
  const candidates = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase()
    const normalizedStatus = status.toLocaleLowerCase()

    return allCandidates.filter((candidate) => {
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
      return matchesSearch && matchesStatus && matchesPriority
    })
  }, [allCandidates, priorityOnly, search, status])

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
    const header = [
      'candidate_id', 'family', 'interface_score', 'pred_kd', 'plddt',
      'solubility_score', 'clash_count', 'buried_sasa', 'status', 'decision',
    ]
    const rows = candidates.map((c) =>
      header.map((h) => (c as Record<string, unknown>)[h] ?? '').join(','),
    )
    const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv' })
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
                key={`${projectId}:${search}:${status}:${priorityOnly}`}
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
