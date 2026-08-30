import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import type { DeliveryPackageData } from '../../lib/api/projects'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'

interface DeliveryPackageProps {
  packageData: DeliveryPackageData | null
  loading?: boolean
}

function candidateIds(packageData: DeliveryPackageData): string[] {
  const value = packageData.selection.candidate_ids
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

export function DeliveryPackage({ packageData, loading }: DeliveryPackageProps) {
  const { t, format } = useI18n()
  const d = t.resultsExt.deliveryPackage
  const showToast = useToastStore((state) => state.show)

  const download = async (artifactId: string) => {
    try {
      await downloadArtifact(await getArtifact(artifactId))
    } catch {
      showToast(t.resultsExt.toasts.downloadGenericFailed, 'error')
    }
  }

  return (
    <AppFrame
      className="h-full min-h-[24rem] xl:min-h-0"
      panelClassName="overflow-y-auto p-4"
      heading={d.title}
    >
      {loading ? (
        <p className="text-sm text-text-secondary">{d.loading}</p>
      ) : !packageData ? (
        <div className="rounded-md border border-dashed border-border-soft bg-bg-app p-4 text-sm text-text-secondary">
          {d.notReady}
        </div>
      ) : (
        <>
          <p className="text-sm text-text-primary">{packageData.name}</p>
          <p className="mt-1 text-xs text-text-secondary">{packageData.status}</p>
          {packageData.error ? <p className="mt-2 text-sm text-danger">{packageData.error}</p> : null}
          {candidateIds(packageData).length ? (
            <p className="mt-3 text-xs text-text-secondary">
              {d.candidates} {candidateIds(packageData).join(', ')}
            </p>
          ) : null}
          {packageData.artifact_id ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => void download(packageData.artifact_id!)}
            >
              {format(d.downloadLabel, { label: d.structureBundle })}
            </Button>
          ) : null}
        </>
      )}
    </AppFrame>
  )
}
