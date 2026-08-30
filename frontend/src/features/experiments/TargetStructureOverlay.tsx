import { Link } from 'react-router'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/statusBadge'
import type { ProjectTargetStructure, TargetReadiness } from '../../lib/schemas/target'
import { useI18n } from '../../lib/i18n'

interface TargetStructureOverlayProps {
  target: ProjectTargetStructure
  readiness?: TargetReadiness | null
  projectId: string
}

function targetChainRole(index: number, labels: {
  targetChain: string
  additionalTargetChain: string
}) {
  return index === 0 ? labels.targetChain : labels.additionalTargetChain
}

export function TargetStructureOverlay({
  target,
  readiness,
  projectId,
}: TargetStructureOverlayProps) {
  const { t } = useI18n()
  const labels = t.projects.activeProjectPanel
  const lineageChains = target.artifact?.lineage.chains
  const chains = Array.isArray(lineageChains)
    ? lineageChains.filter((item): item is string => typeof item === 'string')
    : []
  const provenanceRows = [
    { label: labels.targetPdbId, value: target.artifact?.lineage.pdb_id },
    { label: labels.targetStructureFile, value: target.artifact?.filename },
    { label: labels.targetAtomCount, value: target.artifact?.lineage.atom_count },
  ].filter((row) => row.value !== null && row.value !== undefined && row.value !== '')

  return (
    <AppFrame className="mt-3" panelClassName="p-3 text-xs text-text-secondary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-text-primary">{labels.targetOverlayTitle}</h3>
        {readiness ? (
          <StatusBadge
            status={readiness.ready_for_workflow ? 'success' : 'warning'}
            label={readiness.ready_for_workflow ? labels.targetReady : labels.targetBlocked}
          />
        ) : null}
      </div>

      {readiness?.next_action ? (
        <p className="mt-2">
          <span className="font-medium text-text-primary">{labels.targetReadinessStatus}: </span>
          {readiness.next_action}
        </p>
      ) : null}

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="font-medium text-text-primary">{labels.targetChainRoleLegend}</p>
          {chains.length ? (
            <dl className="mt-2 grid gap-1">
              {chains.map((chainId, index) => (
                <div key={`${chainId}-${index}`} className="flex items-center justify-between gap-2">
                  <dt className="rounded bg-surface-2 px-2 py-0.5 font-mono text-text-primary">
                    {chainId}
                  </dt>
                  <dd className="text-right">{targetChainRole(index, labels)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2">{labels.noTargetChainMetadata}</p>
          )}
        </div>

        <div>
          <p className="font-medium text-text-primary">{labels.targetHotspots}</p>
          <p className="mt-2">{labels.targetNoConfirmedHotspots}</p>
          <Button
            render={<Link to={`/research?project=${encodeURIComponent(projectId)}&tab=structures`} />}
            variant="ghost"
            size="sm"
            className="mt-2"
          >
            {labels.targetReviewHotspots}
          </Button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="font-medium text-text-primary">{labels.targetInterfaceContacts}</p>
          <p className="mt-2">{labels.targetInterfaceContactsUnavailable}</p>
        </div>
        <div>
          <p className="font-medium text-text-primary">{labels.targetProvenance}</p>
          {provenanceRows.length ? (
            <dl className="mt-2 grid gap-1">
              {provenanceRows.map((row) => (
                <div key={row.label} className="grid grid-cols-[auto_minmax(0,1fr)] gap-2">
                  <dt className="text-text-primary">{row.label}</dt>
                  <dd className="truncate text-right">{String(row.value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-2">{labels.targetStructureEmpty}</p>
          )}
        </div>
      </div>
    </AppFrame>
  )
}
