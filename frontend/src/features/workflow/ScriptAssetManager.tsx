import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowsClockwise,
  DotsSixVertical,
  FileText,
  SpinnerGap,
  UploadSimple,
} from '@phosphor-icons/react'
import { listScriptAssets, uploadScriptAsset } from '../../lib/api/registry'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import {
  Sortable,
  SortableItem,
  SortableItemHandle,
} from '../../components/reui/sortable'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

export function ScriptAssetManager() {
  const { t, format } = useI18n()
  const [relativePath, setRelativePath] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [lastResult, setLastResult] = useState<string>('')
  const [scriptOrder, setScriptOrder] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const showToast = useToastStore((s) => s.show)
  const { projectId } = useProjectContext()

  const {
    data: scripts = [],
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['script-assets'],
    queryFn: () => listScriptAssets(),
  })

  const visibleScripts = useMemo(() => {
    const order = new Map(scriptOrder.map((id, index) => [id, index]))
    return scripts
      .slice()
      .sort(
        (left, right) =>
          (order.get(left.id) ?? Number.MAX_SAFE_INTEGER) -
          (order.get(right.id) ?? Number.MAX_SAFE_INTEGER),
      )
  }, [scriptOrder, scripts])

  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error(t.workflowExt.scriptAssets.selectFileFirst)
      return uploadScriptAsset(file, {
        relativePath: relativePath.trim() || undefined,
        projectId: projectId || undefined,
      })
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['script-assets'] })
      setFile(null)
      setLastResult(
        format(t.workflowExt.scriptAssets.successResult, {
          path: result.item.name,
        }),
      )
      showToast(t.workflowExt.scriptAssets.importSuccess, 'success')
    },
    onError: (error) => {
      setLastResult(
        error instanceof Error
          ? `${t.workflowExt.scriptAssets.failedPrefix} ${error.message}`
          : `${t.workflowExt.scriptAssets.failedPrefix} ${t.workflowExt.scriptAssets.importFailed}`,
      )
      showToast(error instanceof Error ? error.message : t.workflowExt.scriptAssets.importFailed, 'error')
    },
  })

  return (
    <Frame variant="inverse" spacing="sm">
      <FrameHeader className="flex-row items-center gap-2">
        <FileText className="h-4 w-4 text-accent" />
        <div>
          <p className="text-xs uppercase tracking-wide text-accent">{t.workflowExt.scriptAssets.eyebrow}</p>
          <FrameTitle>{t.workflowExt.scriptAssets.title}</FrameTitle>
        </div>
      </FrameHeader>

      <FramePanel>
        <div className="grid gap-2">
        <Alert variant="info">
          <AlertDescription>{t.workflowExt.scriptAssets.importHint}</AlertDescription>
        </Alert>
        <label className="grid gap-1 text-xs text-text-secondary">
          {t.workflowExt.scriptAssets.archivePath}
          <Input
            value={relativePath}
            onChange={(event) => setRelativePath(event.target.value)}
            placeholder={t.workflowExt.scriptAssets.archivePathExample}
          />
        </label>

        <div className="grid gap-1 text-xs text-text-secondary">
          <span>{t.workflowExt.scriptAssets.scriptFile}</span>
          <Input
            ref={fileInputRef}
            aria-label={t.workflowExt.scriptAssets.scriptFile}
            type="file"
            className="hidden"
            accept=".lsf,.sh,.py,.xml"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <Button
            type="button"
            variant="outline"
            className="w-fit"
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadSimple className="h-3.5 w-3.5" />
            {file?.name ?? t.workflowExt.scriptAssets.chooseScriptFile}
          </Button>
        </div>

        <div className="flex gap-2">
          <Button type="button"
            className="flex-1"
            disabled={!projectId || !file || upload.isPending}
            onClick={() => upload.mutate()}
          >
            {upload.isPending ? (
              <SpinnerGap className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <UploadSimple className="h-3.5 w-3.5" />
            )}
            {upload.isPending ? t.workflowExt.scriptAssets.importing : t.workflowExt.scriptAssets.uploadImport}
          </Button>
          <Button type="button"
            variant="outline"
            size="icon"
            title={t.workflowExt.scriptAssets.refreshTitle}
            disabled={isFetching}
            onClick={() => void refetch()}
          >
            <ArrowsClockwise className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {lastResult ? (
        <Alert
          className="mt-3"
          variant={
            lastResult.startsWith(t.workflowExt.scriptAssets.failedPrefix) ? 'destructive' : 'success'
          }
        >
          <AlertDescription>{lastResult}</AlertDescription>
        </Alert>
      ) : null}

      <div className="mt-3 space-y-2">
        {isLoading ? <p className="text-xs text-text-secondary">{t.workflowExt.scriptAssets.loadingRegistry}</p> : null}
        {!isLoading && scripts.length === 0 ? (
          <p className="rounded border border-dashed border-border-soft px-3 py-4 text-center text-xs text-text-secondary">
            {t.workflowExt.scriptAssets.empty}
          </p>
        ) : null}
        <Sortable
          value={visibleScripts}
          onValueChange={(nextScripts) => setScriptOrder(nextScripts.map((script) => script.id))}
          getItemValue={(script) => script.id}
          strategy="vertical"
          className="space-y-2"
        >
        {visibleScripts.map((script) => (
          <SortableItem key={script.id} value={script.id}>
          <article className="rounded-md border border-border-soft bg-bg-app p-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1">
                <SortableItemHandle
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      aria-label={t.workflowExt.scriptAssets.reorderScript}
                    />
                  }
                >
                  <DotsSixVertical className="h-4 w-4" />
                </SortableItemHandle>
                <strong className="truncate text-xs">{script.name}</strong>
              </div>
              <Badge variant="outline">{script.runtime}</Badge>
            </div>
            <p className="mt-1 truncate text-[11px] text-text-secondary">
              {t.workflowExt.scriptAssets.archiveOnly}
            </p>
            <p className="mt-1 truncate font-mono text-[10px] text-text-secondary">{script.checksum_sha256}</p>
          </article>
          </SortableItem>
        ))}
        </Sortable>
      </div>
      </FramePanel>
    </Frame>
  )
}
