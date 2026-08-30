import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { PackageIcon } from '@phosphor-icons/react'
import { listExperimentResults } from '../lib/api/experiments'
import { getDeliveryPackageOrNull, getResultsSummary } from '../lib/api/projects'
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
import { Alert, AlertDescription } from '@/components/reui/alert'
import { isDemoProject } from '../features/tour'

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
  const { t } = useI18n()
  const { projectId, activeProject } = useProjectContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const [interpretation, setInterpretation] = useState<InterpretationReasoning | null>(null)
  const candidateParam = searchParams.get('candidate')?.trim() || null
  const isDemoReferenceProject = Boolean(activeProject && isDemoProject(activeProject))

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
        <AlphaFoldResults
          candidates={candidates}
          artifacts={artifacts}
          onDownload={(artifact) => void handleArtifactDownload(artifact.id)}
        />
        <RosettaResults
          candidates={candidates}
          artifacts={artifacts}
          onDownload={(artifact) => void handleArtifactDownload(artifact.id)}
        />
      </ApiState>

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
          ? `${summary.experiment_result_count} results · ${summary.passed_result_count} pass · ${summary.failed_result_count} fail`
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
            loading={packageLoading}
          />
          </ApiState>
        </div>
      </div>

      <NextStep stage="results" />
    </section>
  )
}
