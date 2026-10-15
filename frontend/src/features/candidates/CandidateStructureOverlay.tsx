import { Link } from 'react-router'
import { candidateScore, candidateStrings, candidateText, type Candidate } from '../../lib/schemas/candidate'
import type { StructureMetadataResponse } from '../pdb-viewer/types'
import { useI18n } from '../../lib/i18n'

interface CandidateStructureOverlayProps {
  candidate: Candidate
  metadata?: StructureMetadataResponse | null
  structureMode: 'monomer' | 'complex'
  projectId: string
}

function chainRole(index: number, mode: 'monomer' | 'complex', labels: {
  candidateChain: string
  additionalCandidateChain: string
  inferredBinderChain: string
  inferredTargetChain: string
}) {
  if (mode === 'monomer') return index === 0 ? labels.candidateChain : labels.additionalCandidateChain
  return index === 0 ? labels.inferredBinderChain : labels.inferredTargetChain
}

function metricRows(candidate: Candidate, labels: {
  metricInterfaceScore: string
  metricPlddt: string
  metricInterfacePae: string
  metricRosetta: string
  metricSourceCandidateRanking: string
  metricSourceFoldingConfidence: string
  metricSourceInterfaceConfidence: string
  metricSourceRosetta: string
}) {
  return [
    {
      label: labels.metricInterfaceScore,
      value: candidateScore(candidate, 'interface_score') ?? candidate.score,
      source: labels.metricSourceCandidateRanking,
    },
    {
      label: labels.metricPlddt,
      value: candidateScore(candidate, 'plddt'),
      source: labels.metricSourceFoldingConfidence,
    },
    {
      label: labels.metricInterfacePae,
      value: candidateScore(candidate, 'interface_pae') ?? candidateScore(candidate, 'pae_interaction'),
      source: labels.metricSourceInterfaceConfidence,
    },
    {
      label: labels.metricRosetta,
      value: candidateScore(candidate, 'rosetta_interface_dg') ?? candidateScore(candidate, 'rosetta_score') ?? candidateScore(candidate, 'interface_energy'),
      source: labels.metricSourceRosetta,
    },
  ].filter((row) => row.value !== null && row.value !== undefined)
}

export function CandidateStructureOverlay({
  candidate,
  metadata,
  structureMode,
  projectId,
}: CandidateStructureOverlayProps) {
  const { t, language } = useI18n()
  const detail = t.candidatesExt.detail
  const declaredChains = candidateStrings(candidate, 'chains')
  const mappedChains = [candidateText(candidate, 'fixed_partner_chain'), candidateText(candidate, 'design_chain')].filter((c): c is string => Boolean(c))
  const chains = metadata?.chains?.length ? metadata.chains : declaredChains.length ? declaredChains : mappedChains
  const rows = metricRows(candidate, detail)

  return (
    <section className="mb-4 rounded-lg border border-border-soft bg-bg-app p-3 text-xs text-text-secondary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-text-primary">{detail.structureOverlayTitle}</h3>
        <span className="rounded-full border border-border-soft px-2 py-0.5">
          {structureMode === 'complex' ? detail.complex : detail.monomer}
        </span>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="font-medium text-text-primary">{detail.chainRoleLegend}</p>
          {chains.length ? (
            <dl className="mt-2 grid gap-1">
              {chains.map((chainId, index) => (
                <div key={`${chainId}-${index}`} className="flex items-center justify-between gap-2">
                  <dt className="rounded bg-surface-2 px-2 py-0.5 font-mono text-text-primary">
                    {chainId}
                  </dt>
                  <dd className="text-right">{chainId === candidateText(candidate, 'design_chain') ? (language === 'zh' ? '设计链（来源已核验）' : 'Design chain (source verified)') : chainId === candidateText(candidate, 'fixed_partner_chain') ? (language === 'zh' ? '固定伙伴链（来源已核验）' : 'Fixed partner (source verified)') : chainRole(index, structureMode, detail)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2">{detail.noChainMetadata}</p>
          )}
        </div>

        <div>
          <p className="font-medium text-text-primary">{detail.confirmedHotspots}</p>
          <p className="mt-2">{detail.noConfirmedHotspots}</p>
          <Link
            to={`/research?project=${encodeURIComponent(projectId)}&tab=structures`}
            className="mt-2 inline-flex text-accent hover:underline"
          >
            {detail.reviewHotspots}
          </Link>
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="font-medium text-text-primary">{detail.interfaceContacts}</p>
          <p className="mt-2">{detail.interfaceContactsUnavailable}</p>
        </div>
        <div>
          <p className="font-medium text-text-primary">{detail.metricProvenance}</p>
          {rows.length ? (
            <dl className="mt-2 grid gap-1">
              {rows.map((row) => (
                <div key={row.label} className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                  <dt className="truncate text-text-primary">{row.label}</dt>
                  <dd className="text-right">
                    <span>{typeof row.value === 'number' ? row.value.toFixed(3) : row.value}</span>
                    <span className="block text-[10px] text-text-muted">{row.source}</span>
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2">{detail.noMetricProvenance}</p>
          )}
          {candidate.source_job_id ? (
            <Link
              to={`/workflow?project=${encodeURIComponent(projectId)}`}
              className="mt-2 inline-flex text-accent hover:underline"
            >
              {detail.openWorkflowRun}
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  )
}
