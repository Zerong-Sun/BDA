import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import type { DeliveryPackageData } from '../../lib/api/projects'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'
import { Disclosure } from '../../components/ui/Disclosure'

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
      className="h-full"
      panelClassName="overflow-y-auto p-4"
      heading={d.title}
    >
      {onCreate ? <div className="mb-4 space-y-2">
        <p className="text-xs text-text-secondary">{zh ? '导出当前候选、结果及源文件。单包上限 100 MiB。' : 'Export current candidates, results and source files. Limit: 100 MiB per package.'}</p>
        <Button type="button" variant="outline" size="sm" disabled={!writable || creating || packageData?.status === 'pending'} onClick={onCreate}>
          {creating ? (zh ? '正在创建…' : 'Creating…') : (zh ? '生成新的研究交付包' : 'Create research delivery package')}
        </Button>
      </div> : null}
      {loading ? (
        <p className="text-sm text-text-secondary">{d.loading}</p>
      ) : !packageData ? (
        <p className="text-sm text-text-secondary">
          {d.notReady}
        </p>
      ) : (
        <>
          <p className="text-sm text-text-primary">{packageData.name}</p>
          <p className="mt-1 text-xs text-text-secondary">{packageData.status}</p>
          {packageData.error ? <p className="mt-2 text-sm text-danger">{packageData.error}</p> : null}
          {candidateIds(packageData).length ? (
            <p className="mt-3 text-xs text-text-secondary">
              {d.candidates} {candidateIds(packageData).length}
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
          <Disclosure title={zh ? '打包详情' : 'Package details'}>
            {packageData.selection.format === 'ro-crate-1.1' ? <div className="space-y-1 text-xs text-text-secondary">
              <p>{zh ? '标准：RO-Crate 1.1 · 保留指标证据类型与实验来源' : 'RO-Crate 1.1 · metric evidence types and experiment sources retained'}</p>
              <p>{zh ? '冻结时间：' : 'Frozen at: '}{String(packageData.selection.frozen_at ?? '')}</p>
            </div> : null}
            {candidateIds(packageData).length ? <p className="mt-2 break-all text-xs">{d.candidates} {candidateIds(packageData).join(', ')}</p> : null}
          </Disclosure>
        </>
      )}
    </AppFrame>
  )
}
