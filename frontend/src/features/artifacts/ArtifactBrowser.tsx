import { useState } from 'react'
import {
  DatabaseIcon,
  DownloadSimpleIcon,
  FileTextIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import type { Artifact } from '../../lib/schemas/artifact'
import { formatBytes } from '../../lib/schemas/artifact'
import { downloadArtifact } from '../../lib/api/artifacts'
import { Button } from '../../components/ui/Button'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { useI18n } from '../../lib/i18n'

interface ArtifactBrowserProps {
  artifacts: Artifact[]
  selectedArtifactId?: string
  onSelect: (artifact: Artifact) => void
}

export function ArtifactBrowser({
  artifacts,
  selectedArtifactId,
  onSelect,
}: ArtifactBrowserProps) {
  const { t, format } = useI18n()
  const labels = t.artifacts
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const download = async (artifact: Artifact) => {
    setDownloadError(null)
    setDownloadingId(artifact.id)
    try {
      await downloadArtifact(artifact)
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : labels.downloadFailed)
    } finally {
      setDownloadingId(null)
    }
  }

  if (artifacts.length === 0) {
    return (
      <Frame variant="ghost" spacing="sm">
        <FramePanel>
          <p className="text-center text-xs text-muted-foreground">{labels.empty}</p>
        </FramePanel>
      </Frame>
    )
  }

  return (
    <div className="grid gap-2">
      {downloadError ? (
        <Alert variant="destructive">
          <WarningIcon aria-hidden="true" />
          <AlertDescription>{downloadError}</AlertDescription>
        </Alert>
      ) : null}
      <Frame stacked dense>
        {artifacts.map((artifact) => {
          const hasDownload = Boolean(artifact.download_url)
          const selected = selectedArtifactId === artifact.id
          const badges = [
            artifact.lineage?.route ? String(artifact.lineage.route) : null,
            artifact.lineage?.sequence_count != null
              ? format(labels.sequences, { count: Number(artifact.lineage.sequence_count) })
              : null,
            artifact.lineage?.row_count != null
              ? format(labels.rows, { count: Number(artifact.lineage.row_count) })
              : null,
            artifact.lineage?.backbone_count != null
              ? format(labels.backbones, { count: Number(artifact.lineage.backbone_count) })
              : null,
            artifact.lineage?.source_lsf_job_id
              ? `LSF ${artifact.lineage.source_lsf_job_id}`
              : null,
          ].filter(Boolean) as string[]

          return (
            <FramePanel key={artifact.id} fit className="p-2">
              <div className="flex min-w-0 items-stretch gap-2">
                <Button
                  type="button"
                  variant={selected ? 'secondary' : 'ghost'}
                  className="h-auto min-w-0 flex-1 justify-start whitespace-normal p-2 text-left"
                  aria-label={format(labels.selectAriaLabel, { name: artifact.filename })}
                  aria-pressed={selected}
                  onClick={() => onSelect(artifact)}
                >
                  {artifact.status === 'available' ? (
                    <DatabaseIcon className="shrink-0 text-success" aria-hidden="true" />
                  ) : (
                    <FileTextIcon className="shrink-0 text-primary" aria-hidden="true" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="flex min-w-0 items-center justify-between gap-2">
                      <strong className="truncate text-xs text-foreground">
                        {artifact.filename}
                      </strong>
                      <Badge variant="outline" size="xs">
                        {artifact.content_type}
                      </Badge>
                    </span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">
                      {artifact.artifact_type} · {formatBytes(artifact.size_bytes)}
                    </span>
                    {badges.length > 0 ? (
                      <span className="mt-2 flex flex-wrap gap-1">
                        {badges.slice(0, 3).map((badge) => (
                          <Badge key={badge} variant="secondary" size="xs">
                            {badge}
                          </Badge>
                        ))}
                      </span>
                    ) : null}
                  </span>
                </Button>
                {hasDownload ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    className="self-center"
                    aria-label={format(labels.downloadAriaLabel, { name: artifact.filename })}
                    disabled={downloadingId === artifact.id}
                    onClick={() => void download(artifact)}
                  >
                    <DownloadSimpleIcon aria-hidden="true" />
                  </Button>
                ) : null}
              </div>
            </FramePanel>
          )
        })}
      </Frame>
    </div>
  )
}
