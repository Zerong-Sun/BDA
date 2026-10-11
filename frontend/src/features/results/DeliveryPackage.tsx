import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import type { DeliveryPackageData } from '../../lib/api/projects'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'

interface DeliveryPackageProps {
  packageData: DeliveryPackageData | null
  loading?: boolean
  onCreate?: () => void
  creating?: boolean
  writable?: boolean
}

function candidateIds(packageData: DeliveryPackageData): string[] {
  const value = packageData.selection.candidate_ids
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

export function DeliveryPackage({ packageData, loading, onCreate, creating, writable }: DeliveryPackageProps) {
  const { t, format, language } = useI18n()
  const zh = language === 'zh'
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
      {onCreate ? <div className="mb-4 space-y-2">
        <p className="text-xs text-text-secondary">{zh ? '冻结当前候选、分类指标、实验结果和可用源文件；打包时逐项校验。单包上限 100 MiB。' : 'Freeze candidates, typed metrics, experiment results and available source files, then verify each file. Limit: 100 MiB per package.'}</p>
        <Button type="button" variant="outline" size="sm" disabled={!writable || creating || packageData?.status === 'pending'} onClick={onCreate}>
          {creating ? (zh ? '正在创建…' : 'Creating…') : (zh ? '生成新的研究交付包' : 'Create research delivery package')}
        </Button>
      </div> : null}
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
          {packageData.selection.format === 'ro-crate-1.1' ? <div className="mt-2 space-y-1 text-xs text-text-secondary">
            <p>{zh ? '标准：RO-Crate 1.1 · 保留指标证据类型与实验来源' : 'RO-Crate 1.1 · metric evidence types and experiment sources retained'}</p>
            <p>{zh ? '冻结时间：' : 'Frozen at: '}{String(packageData.selection.frozen_at ?? '')}</p>
          </div> : null}
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
