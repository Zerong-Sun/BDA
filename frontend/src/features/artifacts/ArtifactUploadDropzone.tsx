import { useCallback, useId, useRef, useState } from 'react'
import { SpinnerGapIcon, UploadSimpleIcon, WarningIcon } from '@phosphor-icons/react'
import { uploadArtifact } from '../../lib/api/artifacts'
import type { Artifact } from '../../lib/schemas/artifact'
import { Button } from '../../components/ui/Button'
import { Progress, ProgressLabel } from '../../components/ui/progress'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FramePanel } from '../../components/reui/frame'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'

const ACCEPTED = '.pdb,.cif,.mmcif,.fasta,.fa,.faa,.csv,.tsv,.json,.zip'

interface ArtifactUploadDropzoneProps {
  projectId?: string
  onUploaded: (artifact: Artifact, file: File) => void
  disabled?: boolean
  readOnly?: boolean
}

export function ArtifactUploadDropzone({
  projectId,
  onUploaded,
  disabled = false,
  readOnly = false,
}: ArtifactUploadDropzoneProps) {
  const { t, format } = useI18n()
  const labels = t.artifacts
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const showToast = useToastStore((state) => state.show)
  const blocked = disabled || readOnly || uploading

  const handleFiles = useCallback(
    async (files: FileList | File[] | null) => {
      if (disabled || readOnly || uploading) return
      const file = files?.[0]
      if (!file) return
      setUploadError(null)
      setUploading(true)
      try {
        const artifact = await uploadArtifact(file, projectId)
        onUploaded(artifact, file)
        showToast(format(labels.uploaded, { name: artifact.filename }), 'success')
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : labels.uploadFailed)
      } finally {
        setUploading(false)
        if (inputRef.current) inputRef.current.value = ''
      }
    },
    [
      disabled,
      format,
      labels.uploadFailed,
      labels.uploaded,
      onUploaded,
      projectId,
      readOnly,
      showToast,
      uploading,
    ],
  )

  return (
    <div className="grid gap-2">
      <Frame
        data-testid="artifact-dropzone"
        variant={dragging ? 'inverse' : 'default'}
        spacing="sm"
        onDragOver={(event) => {
          event.preventDefault()
          if (!blocked) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          void handleFiles(event.dataTransfer.files)
        }}
      >
        <FramePanel className="flex flex-col items-center justify-center gap-2 text-center">
          {uploading ? (
            <SpinnerGapIcon
              className="size-5 animate-spin text-primary motion-reduce:animate-none"
              aria-hidden="true"
            />
          ) : (
            <UploadSimpleIcon className="size-5 text-primary" aria-hidden="true" />
          )}
          <span className="text-sm font-medium text-foreground">
            {uploading ? labels.uploading : labels.dropFiles}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={blocked}
            onClick={() => inputRef.current?.click()}
          >
            {labels.browseButton}
          </Button>
          <span className="text-xs leading-relaxed text-muted-foreground">
            {labels.acceptedFormats}
          </span>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            aria-label={labels.fileInputLabel}
            disabled={blocked}
            onChange={(event) => void handleFiles(event.target.files)}
          />
          {uploading ? (
            <Progress value={null} className="w-full" aria-label={labels.uploadProgressLabel}>
              <ProgressLabel>{labels.uploadProgressLabel}</ProgressLabel>
            </Progress>
          ) : null}
        </FramePanel>
      </Frame>
      {uploadError ? (
        <Alert variant="destructive">
          <WarningIcon aria-hidden="true" />
          <AlertDescription>{uploadError}</AlertDescription>
        </Alert>
      ) : null}
      {!uploading && !uploadError ? (
        <span className="sr-only">{format(labels.uploadReady, { projectId: projectId ?? '' })}</span>
      ) : null}
    </div>
  )
}
