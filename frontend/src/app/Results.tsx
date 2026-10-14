import { ModelResultGuideLibrary } from '../features/results/ModelResultGuide'
import { lazy, Suspense, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { PackageIcon } from '@phosphor-icons/react'
import { listExperimentResults } from '../lib/api/experiments'
import { createDeliveryPackage, getDeliveryPackageOrNull, getResultsSummary } from '../lib/api/projects'
import { interpretResults, type InterpretationReasoning } from '../lib/api/copilot'
import { InterpretationCard } from '../components/ui/InterpretationCard'
import { downloadArtifact, getArtifact } from '../lib/api/artifacts'
import { listProjectArtifacts } from '../lib/api/artifacts'
import { listAllCandidates } from '../lib/api/candidates'
import { PageHead } from '../components/ui/PageHead'
import { ResultsMetrics } from '../features/results/ResultsMetrics'
import { ValidationTable } from '../features/results/ValidationTable'
import { ExperimentUpload } from '../features/results/ExperimentUpload'
import { DeliveryPackage } from '../features/results/DeliveryPackage'
import { AlphaFoldResults } from '../features/results/AlphaFoldResults'
import { RosettaResults } from '../features/results/RosettaResults'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useToastStore } from '../components/ui/toastStore'
import { useI18n } from '../lib/i18n'
import { NextStep } from '../components/ui/NextStep'
import { ApiState } from '../components/ui/ApiState'
import { Skeleton } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../components/ui/AppFrame'
import { Disclosure } from '../components/ui/Disclosure'
import { Alert, AlertDescription } from '@/components/reui/alert'
import { isDemoProject } from '../features/tour'
import { useProjectAccess } from '../lib/hooks/useProjectAccess'
import { useAppStore } from '../lib/store/appStore'

const ArtifactEvidence = lazy(() => import('../features/results/ArtifactEvidence').then((module) => ({ default: module.ArtifactEvidence })))
const SavedInstrumentReviews = lazy(() => import('../features/lab/SavedInstrumentReviews').then((module) => ({ default: module.SavedInstrumentReviews })))

function ResultsMetricsSkeleton() {
  return (
    <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }, (_, index) => (
        <AppFrame key={index} panelClassName="space-y-3 p-4">
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-7 w-1/2" />
          <Skeleton className="h-3 w-3/4" />
        </AppFrame>
      ))}
    </div>
  )
}

export function ResultsPage() {
  const { t, language } = useI18n()
  const zh = language === 'zh'
  const { projectId, activeProject } = useProjectContext()
  const access = useProjectAccess(projectId)
  const demoMode = useAppStore((state) => state.appMode === 'demo')
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const [interpretation, setInterpretation] = useState<InterpretationReasoning | null>(null)
  const candidateParam = searchParams.get('candidate')?.trim() || null
  const isDemoReferenceProject = Boolean(activeProject && isDemoProject(activeProject))
  const createPackage = useMutation({
    mutationFn: () => createDeliveryPackage(projectId, `${activeProject?.name || 'Research'} · ${new Date().toISOString().slice(0, 10)}`),
    onSuccess: (data) => { queryClient.setQueryData(['delivery-package', data.project_id], data) },
    onError: (error) => showToast(error instanceof Error ? error.message : (zh ? '创建失败' : 'Could not create delivery'), 'error'),
  })

  const {
    data: results = [],
    isLoading: resultsLoading,
    isError: resultsError,
    error: resultsQueryError,
    refetch: refetchResults,
  } = useQuery({
    queryKey: ['experiment-results', projectId],
    queryFn: () => listExperimentResults(projectId),
    enabled: Boolean(projectId),
  })

  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    error: summaryQueryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ['results-summary', projectId],
    queryFn: () => getResultsSummary(projectId),
    enabled: Boolean(projectId),
  })

  const {
    data: deliveryPackage,
    isLoading: packageLoading,
    isError: packageError,
    error: packageQueryError,
    refetch: refetchPackage,
  } = useQuery({
    queryKey: ['delivery-package', projectId],
    queryFn: () => getDeliveryPackageOrNull(projectId),
    enabled: Boolean(projectId),
    refetchInterval: (query) => query.state.data?.status === 'pending' ? 2000 : false,
  })

  const {
    data: candidatePage,
    isLoading: candidatesLoading,
    isError: candidatesError,
    error: candidatesQueryError,
    refetch: refetchCandidates,
  } = useQuery({
    queryKey: ['all-candidates', projectId],
    queryFn: () => listAllCandidates(projectId),
    enabled: Boolean(projectId),
  })
  const candidates = candidatePage?.items ?? []
  const sourceGroups = new Map<string, typeof candidates>()
  for (const candidate of candidates) {
    const source = typeof candidate.properties.source_dataset === 'string' ? candidate.properties.source_dataset : ''
    sourceGroups.set(source, [...(sourceGroups.get(source) ?? []), candidate])
  }
  const nativeCandidates = candidates.filter((c) => Boolean(c.properties.source_dataset))
  const nativeIds = new Set(nativeCandidates.flatMap((c) => [c.id, c.candidate_key]))
  const nativeReadouts = results.filter((r) => nativeIds.has(r.candidate_id ?? '') || nativeIds.has(r.candidate_ref ?? ''))
  const hasImported = nativeCandidates.length > 0

  const {
    data: artifacts = [],
    isLoading: artifactsLoading,
    isError: artifactsError,
    error: artifactsQueryError,
    refetch: refetchArtifacts,
  } = useQuery({
    queryKey: ['project-artifacts', projectId],
    queryFn: () => listProjectArtifacts(projectId),
    enabled: Boolean(projectId),
  })

  const invalidateResults = () => {
    queryClient.invalidateQueries({ queryKey: ['experiment-results', projectId] })
    queryClient.invalidateQueries({ queryKey: ['results-summary', projectId] })
    queryClient.invalidateQueries({ queryKey: ['project-overview', projectId] })
  }

  const preparePackage = async () => {
    if (!deliveryPackage) {
      showToast(t.resultsExt.toasts.packageNotReady, 'error')
      return
    }
    try {
      if (!deliveryPackage.artifact_id) throw new Error('Delivery artifact is not available')
      await downloadArtifact(await getArtifact(deliveryPackage.artifact_id))
      showToast(t.resultsExt.toasts.downloadStarted, 'success')
    } catch {
      showToast(t.resultsExt.toasts.downloadFailed, 'error')
    }
  }

  const handleInterpret = async () => {
    try {
      const response = await interpretResults(projectId)
      setInterpretation(response)
    } catch {
      showToast(t.resultsExt.toasts.interpretFailed, 'error')
    }
  }

  const handleArtifactDownload = async (artifactId: string) => {
    try {
      await downloadArtifact(await getArtifact(artifactId))
    } catch {
      showToast(t.resultsExt.toasts.downloadGenericFailed, 'error')
    }
  }

  const clearCandidateFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('candidate')
    setSearchParams(next, { replace: true })
  }

  const showEmptyPrompt =
    !resultsLoading && !resultsError && results.length === 0 && Boolean(projectId)

  return (
    <section>
      <PageHead
        eyebrow={t.results.eyebrow}
        title={t.results.title}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleInterpret()}
            >
              {t.results.interpret}
            </Button>
            <Button
              type="button"
              onClick={() => void preparePackage()}
              disabled={!deliveryPackage?.artifact_id || packageLoading || packageError}
            >
              <PackageIcon aria-hidden="true" />
              {t.results.preparePackage}
            </Button>
          </div>
        }
      />

      {searchParams.get('artifact') ? <Suspense fallback={null}><ArtifactEvidence projectId={projectId} artifactId={searchParams.get('artifact')!} residues={searchParams.get('residues')} /></Suspense> : null}
      <AppFrame className="mb-5" panelClassName="space-y-3 p-4">
        <p className="text-sm text-text-secondary">{zh ? '在此审阅实测证据、计算证据与分析结论。候选页负责设计、筛选和选择。' : 'Review measured evidence, computational evidence and conclusions here. Use Candidates to manage designs, filtering and selection.'}</p>
        <div className="flex flex-wrap gap-2">
          <Button render={<Link to={`/lab?project=${encodeURIComponent(projectId)}&section=analysis`} />}>{zh ? '上传原始实验文件并分析' : 'Upload raw experiment and analyse'}</Button>
          <Button variant="outline" render={<Link to={`/candidates?project=${encodeURIComponent(projectId)}${candidateParam ? `&candidate=${encodeURIComponent(candidateParam)}` : ''}`} />}>{zh ? '管理候选与选择' : 'Manage candidates and selection'}</Button>
          <Button variant="outline" render={<Link to={`/research?project=${encodeURIComponent(projectId)}&tab=methods`} />}>{zh ? '阅读已保存的讨论报告' : 'Read saved discussion reports'}</Button>
          <Button variant="outline" render={<Link to={`/research?project=${encodeURIComponent(projectId)}&tab=timeline`} />}>{zh ? '查看决策记录' : 'Review decision record'}</Button>
        </div>
      </AppFrame>
      <AppFrame className="mb-5" panelClassName="p-4">
        <Suspense fallback={<p>{zh ? '加载分析视图…' : 'Loading analyses…'}</p>}><SavedInstrumentReviews key={projectId} projectId={projectId} autoLoad /></Suspense>
      </AppFrame>
      <Disclosure className="mb-5" title={zh ? '计算指标释义' : 'Computational metric guide'}><ModelResultGuideLibrary /></Disclosure>

      {isDemoReferenceProject ? (
        <div className="mb-5">
          <Alert variant="warning">
            <AlertDescription>{t.results.disclaimer}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      {interpretation ? (
        <AppFrame
          className="mb-5"
          panelClassName="p-4"
          heading={t.resultsExt.page.aiInterpretation}
          actions={
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setInterpretation(null)}
            >
              {t.resultsExt.page.dismiss}
            </Button>
          }
        >
          <InterpretationCard reasoning={interpretation} />
        </AppFrame>
      ) : null}

      <ApiState
        isLoading={candidatesLoading || artifactsLoading}
        isError={candidatesError || artifactsError}
        error={candidatesQueryError ?? artifactsQueryError}
        onRetry={() => {
          void refetchCandidates()
          void refetchArtifacts()
        }}
      >
        {[...sourceGroups].sort(([a], [b]) => Number(!a) - Number(!b) || a.localeCompare(b)).map(([source, group]) => {
          const keys = new Set(group.map((c) => c.candidate_key))
          const groupArtifacts = artifacts.filter((a) => source
            ? a.lineage.package_id === source || keys.has(String(a.lineage.candidate_key ?? ''))
            : !a.lineage.package_id || keys.has(String(a.lineage.candidate_key ?? '')))
          const panel = <AlphaFoldResults summaryOnly candidates={group} artifacts={groupArtifacts} onDownload={(a) => void handleArtifactDownload(a.id)} />
          return source ? <div key={source}>
            <h2 className="mb-2 text-sm font-semibold">{zh ? '导入数据集' : 'Imported dataset'} · {source}</h2>
            <p className="mb-3 text-sm text-text-secondary">{zh ? '上游已筛选子集；以下统计仅包含该数据集，不能推断总体通过率。' : 'An upstream-selected subset; statistics cover this dataset only, not population success rates.'}</p>
            {panel}
          </div> : hasImported ? <Disclosure key="legacy" className="mb-5 rounded-lg border border-border-soft p-4" title={zh ? '其他项目记录（不计入导入数据统计）' : 'Other project records (excluded from imported statistics)'}>
            <div className="mt-3">{panel}</div>
          </Disclosure> : <div key="legacy">{panel}</div>
        })}
        <Disclosure className="mb-5" title={zh ? 'Rosetta 计算证据与原始结果' : 'Rosetta computational evidence and source results'}>
        <RosettaResults
          candidates={candidates}
          artifacts={artifacts}
          onDownload={(artifact) => void handleArtifactDownload(artifact.id)}
        />
        </Disclosure>
      </ApiState>

      {hasImported ? <p className="mb-4 rounded-lg border border-border-soft bg-surface-2 p-4 text-sm">
        {zh ? `导入的 ${nativeCandidates.length} 条候选关联实验读数：${nativeReadouts.length} 条。项目历史实验与交付记录在下方单独查看。` : `${nativeCandidates.length} imported candidates have ${nativeReadouts.length} linked experimental readouts. Project history is shown separately below.`}
      </p> : null}
      <div data-tour-id="results-history">
      <Disclosure key={`experiment-history-${projectId}-${hasImported}`} defaultOpen className="mb-5" title={zh ? '项目实验与交付记录' : 'Project experiments and deliveries'}>
      <div data-tour-id="results-metrics">
      <ApiState
        isLoading={summaryLoading}
        isError={summaryError}
        error={summaryQueryError}
        onRetry={() => void refetchSummary()}
        loadingSkeleton={<ResultsMetricsSkeleton />}
      >
        <ResultsMetrics summary={summary ?? null} />
      </ApiState>
      </div>

      <AppFrame className="mb-5" panelClassName="p-4 text-sm text-text-secondary break-words">
        {summary
          ? zh
            ? `${summary.experiment_result_count} 条结果 · ${summary.passed_result_count} 条通过 · ${summary.failed_result_count} 条未通过`
            : `${summary.experiment_result_count} results · ${summary.passed_result_count} pass · ${summary.failed_result_count} fail`
          : t.resultsExt.page.experimentSummaryEmpty}
      </AppFrame>

      {showEmptyPrompt ? (
        <div className="mb-5">
          <Alert variant="info">
            <AlertDescription>{t.resultsExt.page.noReadoutsYet}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      <div className="mb-5">
        <ExperimentUpload projectId={projectId} onUploaded={invalidateResults} />
      </div>

      <div className="grid min-h-0 gap-4 xl:h-[calc(100vh-28rem)] xl:min-h-[28rem] xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.9fr)]">
        <div className="min-h-0" data-tour-id="results-validation">
          <ValidationTable
            results={results}
            loading={resultsLoading}
            isError={resultsError}
            error={resultsQueryError}
            candidateId={candidateParam}
            onClearCandidate={clearCandidateFilter}
            onRetry={() => void refetchResults()}
          />
        </div>
        <div className="min-h-0" data-tour-id="results-delivery">
          <ApiState
            isLoading={false}
            isError={packageError}
            error={packageQueryError}
            onRetry={() => void refetchPackage()}
          >
          <DeliveryPackage
            packageData={deliveryPackage ?? null}
            onCreate={() => createPackage.mutate()}
            creating={createPackage.isPending}
            writable={!demoMode && access.data?.permissions.write === true}
            loading={packageLoading}
          />
          </ApiState>
        </div>
      </div>

      </Disclosure>
      </div>
      <NextStep stage="results" />
    </section>
  )
}
