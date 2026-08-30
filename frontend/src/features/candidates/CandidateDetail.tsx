import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { DownloadSimpleIcon, FlaskIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import { structureSourceFromCandidate } from '../pdb-viewer/types'
import { downloadCandidateStructures } from '../../lib/api/candidates'
import { getArtifact } from '../../lib/api/artifacts'
import { promoteCandidateToBench } from '../../lib/api/wetlab'
import { explainCandidate, type InterpretationReasoning } from '../../lib/api/copilot'
import { candidateScore, candidateText, type Candidate } from '../../lib/schemas/candidate'
import { ScoreBars } from './ScoreBars'
import { StatusPill } from '../../components/ui/StatusPill'
import { InterpretationCard } from '../../components/ui/InterpretationCard'
import { statusTone } from '../../components/ui/statusTone'
import { useI18n } from '../../lib/i18n'
import { useToastStore } from '../../components/ui/toastStore'
import { useAppStore } from '../../lib/store/appStore'
import { GlossaryTooltip } from '../../components/ui/GlossaryTooltip'
import { CandidateStructureOverlay } from './CandidateStructureOverlay'
import { CandidateConditionMetrics } from './CandidateConditionMetrics'
import { AttachToGoalButton } from '../research/AttachToGoalButton'

interface CandidateDetailProps {
  candidate: Candidate | null
  projectId: string
}

const metricGuideKeys = [
  ['metricInterfaceScore', 'metricInterfaceScoreHelp'],
  ['metricPlddt', 'metricPlddtHelp'],
  ['metricInterfacePae', 'metricInterfacePaeHelp'],
  ['metricRosetta', 'metricRosettaHelp'],
] as const

export function CandidateDetail({ candidate, projectId }: CandidateDetailProps) {
  const { t, format } = useI18n()
  const showToast = useToastStore((s) => s.show)
  const uiDensity = useAppStore((s) => s.uiDensity)
  const advanced = uiDensity === 'advanced'
  const [structureMode, setStructureMode] = useState<'monomer' | 'complex'>('monomer')
  const [explanation, setExplanation] = useState<InterpretationReasoning | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const queryClient = useQueryClient()

  const hasMonomer = Boolean(candidate?.structure_artifact_id)
  const hasComplex = Boolean(candidate?.complex_artifact_id)
  const hasStructure = hasMonomer || hasComplex
  const selectedArtifactId = structureMode === 'complex'
    ? candidate?.complex_artifact_id
    : candidate?.structure_artifact_id ?? candidate?.complex_artifact_id
  const artifactQuery = useQuery({
    queryKey: ['artifact', selectedArtifactId],
    queryFn: () => getArtifact(selectedArtifactId!),
    enabled: Boolean(selectedArtifactId),
    staleTime: 60_000,
  })

  if (!candidate) {
    return (
      <AppFrame className="min-h-[18rem] xl:min-h-0" panelClassName="p-4 text-sm text-text-secondary">
          {t.candidatesExt.detail.selectHint}
      </AppFrame>
    )
  }

  const decision = candidateText(candidate, 'decision')
  const nextAction = candidateText(candidate, 'next_action')

  const structureSource = structureSourceFromCandidate(candidate, {
    structureMode,
    downloadUrl: artifactQuery.data?.download_url ?? undefined,
  })

  const explain = async () => {
    try {
      const result = await explainCandidate(candidate.id)
      setExplanation(result)
    } catch {
      showToast(t.candidatesExt.toasts.explainFailed, 'error')
    }
  }

  /** Whether there is a sequence to make. Presence only - it is never rendered. */
  const sequence = candidate?.properties?.sequence
  const hasSequence = typeof sequence === 'string' && sequence.trim().length > 0

  const promoteToBench = async () => {
    if (!candidate) return
    setIsPromoting(true)
    try {
      const construct = await promoteCandidateToBench(candidate.project_id, candidate.id)
      showToast(format(t.candidatesExt.toasts.promoted, { name: construct.name }), 'success')
      // The construct is now in the library, and it carries this candidate's id.
      void queryClient.invalidateQueries({ queryKey: ['proteins', candidate.project_id] })
    } catch (err) {
      const message = err instanceof Error ? err.message : t.candidatesExt.toasts.promoteFailed
      showToast(message, 'error')
    } finally {
      setIsPromoting(false)
    }
  }

  const downloadStructure = async () => {
    setIsDownloading(true)
    try {
      await downloadCandidateStructures(
        candidate.project_id,
        [candidate.id],
        `${candidate.id}_structure.zip`,
      )
      showToast(t.candidatesExt.toasts.structureDownloaded, 'success')
    } catch (err) {
      const message = err instanceof Error ? err.message : t.candidatesExt.toasts.downloadFailed
      showToast(message, 'error')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <AppFrame className="min-h-[32rem] xl:min-h-0" panelClassName="h-full overflow-y-auto p-4">
      {hasStructure ? (
        <>
          {hasMonomer && hasComplex ? (
            <div className="mb-2 flex gap-2">
              <Button
                type="button"
                variant={structureMode === 'monomer' ? 'secondary' : 'outline'}
                size="sm"
                aria-pressed={structureMode === 'monomer'}
                onClick={() => setStructureMode('monomer')}
              >
                {t.candidatesExt.detail.monomer}
              </Button>
              <Button
                type="button"
                variant={structureMode === 'complex' ? 'secondary' : 'outline'}
                size="sm"
                aria-pressed={structureMode === 'complex'}
                onClick={() => setStructureMode('complex')}
              >
                {t.candidatesExt.detail.complex}
              </Button>
            </div>
          ) : null}
          <StructureViewerLazy source={structureSource} height={280} className="mb-4" showMetadata />
          <CandidateStructureOverlay
            candidate={candidate}
            metadata={null}
            structureMode={structureMode}
            projectId={projectId}
          />
        </>
      ) : (
        <div className="mb-4 flex h-[280px] items-center justify-center rounded-lg border border-dashed border-border-soft bg-bg-app text-sm text-text-secondary">
          {t.candidatesExt.detail.noStructure}
        </div>
      )}
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{candidate.id}</h2>
        <StatusPill label={decision ?? '—'} tone={statusTone(decision ?? '')} />
      </div>
      <p className="mb-4 text-sm text-text-secondary">
        {format(t.candidatesExt.detail.familyLine, {
          family: candidate.name,
          nextAction,
        })}
      </p>
      {explanation && explanation.subject_id === candidate.id ? (
        <div className="mb-4">
          <InterpretationCard reasoning={explanation} />
        </div>
      ) : null}
      <ScoreBars
        affinity={candidateScore(candidate, 'interface_score') ?? candidate.score}
        stability={candidateScore(candidate, 'plddt')}
        solubility={candidateScore(candidate, 'solubility_score')}
        rosettaScore={candidateScore(candidate, 'rosetta_score')}
      />
      {!advanced ? (
        <p className="mt-4 rounded-md border border-border-soft bg-bg-app p-3 text-xs text-text-secondary">
          {format(t.candidatesExt.detail.simplifiedView, {
            advanced: t.candidatesExt.detail.advancedLabel,
          })}
        </p>
      ) : null}
      <div className={`mt-4 grid-cols-2 gap-2 text-xs text-text-secondary ${advanced ? 'grid' : 'hidden'}`}>
        <div>
          <GlossaryTooltip
            label={t.candidates.predKd}
            description={t.candidatesExt.detail.predKdHelp}
            good={t.candidatesExt.detail.predKdGood}
          />
          : <span className="text-text-primary">{candidateText(candidate, 'pred_kd') ?? t.candidatesExt.table.notScored}</span>
        </div>
        <div>
          <GlossaryTooltip
            label={t.candidatesExt.table.interfacePae}
            description={t.candidatesExt.detail.interfacePaeHelp}
            good={t.candidatesExt.detail.interfacePaeGood}
          />
          : <span className="text-text-primary">{candidateScore(candidate, 'interface_pae') != null ? `${candidateScore(candidate, 'interface_pae')} Å` : t.candidatesExt.table.notScored}</span>
        </div>
        <div>
          <GlossaryTooltip
            label={t.candidatesExt.table.rosettaEnergy}
            description={t.candidatesExt.detail.rosettaHelp}
            good={t.candidatesExt.detail.rosettaGood}
          />
          : <span className="text-text-primary">{candidateScore(candidate, 'rosetta_score') ?? t.candidatesExt.table.notScored}</span>
        </div>
        <div>
          {t.candidatesExt.detail.expressionRisk}:{' '}
          <span className="text-text-primary">{candidateText(candidate, 'expression_risk') ?? t.candidatesExt.table.notScored}</span>
        </div>
        {candidateScore(candidate, 'clash_count') != null ? (
          <div>
            {t.candidatesExt.detail.clashCount}: <span className="text-text-primary">{candidateScore(candidate, 'clash_count')}</span>
          </div>
        ) : null}
        {candidateScore(candidate, 'buried_sasa') != null ? (
          <div>
            <GlossaryTooltip
              label={t.candidatesExt.table.buriedSasa}
              description={t.candidatesExt.detail.buriedSasaHelp}
              good={t.candidatesExt.detail.buriedSasaGood}
            />
            : <span className="text-text-primary">{candidateScore(candidate, 'buried_sasa')} Å²</span>
          </div>
        ) : null}
      </div>
      {advanced ? <CandidateConditionMetrics candidateId={candidate.id} /> : null}
      {advanced ? (
        <div className="mt-4 rounded-md border border-border-soft bg-bg-app p-3 text-xs text-text-secondary">
          <p className="uppercase tracking-wide text-accent">{t.candidatesExt.detail.metricGuideTitle}</p>
          <dl className="mt-2 grid gap-2">
            {metricGuideKeys.map(([termKey, meaningKey]) => (
              <div key={termKey}>
                <dt className="font-semibold text-text-primary">{t.candidatesExt.detail[termKey]}</dt>
                <dd>{t.candidatesExt.detail[meaningKey]}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void explain()}
        >
          {t.candidates.explain}
        </Button>
        <Button
          variant="outline"
          size="sm"
          render={<Link to={`/results?project=${encodeURIComponent(projectId)}&candidate=${encodeURIComponent(candidate.id)}`} />}
        >
          {t.candidates.viewLabResults}
        </Button>
        <AttachToGoalButton
          projectId={candidate.project_id}
          resourceType="candidate"
          resourceId={candidate.id}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasSequence || isPromoting}
          title={hasSequence ? undefined : t.candidatesExt.detail.promoteNeedsSequence}
          onClick={() => void promoteToBench()}
        >
          <FlaskIcon aria-hidden="true" />
          {isPromoting ? t.candidatesExt.detail.promoting : t.candidatesExt.detail.promoteToBench}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasStructure || isDownloading}
          onClick={() => void downloadStructure()}
        >
          <DownloadSimpleIcon aria-hidden="true" />
          {isDownloading ? t.candidatesExt.detail.downloading : t.candidatesExt.detail.downloadStructure}
        </Button>
      </div>
      <div className="mt-4 rounded-md border border-border-soft bg-bg-app p-3 text-sm">
        <span className="text-xs uppercase text-text-secondary">{t.candidatesExt.detail.nextAction}</span>
        <p className="mt-1 text-text-primary">{nextAction ?? '—'}</p>
      </div>
    </AppFrame>
  )
}
