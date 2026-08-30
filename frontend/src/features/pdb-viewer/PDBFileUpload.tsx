import { useCallback, useId, useRef, useState } from 'react'
import { FileText, UploadSimple, WarningCircle } from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '@/components/reui/alert'
import { Frame, FramePanel } from '@/components/reui/frame'
import { Button } from '@/components/ui/Button'
import { Progress, ProgressLabel } from '@/components/ui/progress'
import { uploadPdb } from '../../lib/api/targets'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'

interface PDBFileUploadProps {
  projectId?: string
  selectedFile?: File | null
  onFileSelected: (file: File) => void
  onUploaded?: (previewUrl: string) => void
  readOnly?: boolean
}

async function countStructureAtoms(file: File): Promise<number> {
  const text = await file.text()
  return text
    .split(/\r?\n/)
    .filter((line) => /^(?:ATOM|HETATM)(?:\s|$)/.test(line.trimStart()))
    .length
}

export function PDBFileUpload({
  projectId,
  selectedFile = null,
  onFileSelected,
  onUploaded,
  readOnly = false,
}: PDBFileUploadProps) {
  const { t, format } = useI18n()
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const showToast = useToastStore((s) => s.show)

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (readOnly || uploading) return
      const file = files?.[0]
      if (!file) return
      const lower = file.name.toLowerCase()
      if (!lower.endsWith('.pdb') && !lower.endsWith('.cif') && !lower.endsWith('.mmcif')) {
        showToast(t.pdbUpload.invalidFile, 'error')
        setUploadError(t.pdbUpload.invalidFile)
        return
      }
      setUploadError(null)
      onFileSelected(file)
      setUploading(true)
      try {
        const [result, atomCount] = await Promise.all([
          uploadPdb(file, projectId),
          countStructureAtoms(file),
        ])
        if (!result.artifact.download_url) throw new Error('Artifact download URL is unavailable')
        onUploaded?.(result.artifact.download_url)
        showToast(
          t.pdbUpload.uploadSuccess
            .replace('{filename}', result.artifact.filename)
            .replace('{atomCount}', String(atomCount)),
          'success',
        )
      } catch {
        setUploadError(t.pdbUpload.uploadError)
        showToast(t.pdbUpload.uploadFallback, 'info')
      } finally {
        setUploading(false)
        if (inputRef.current) inputRef.current.value = ''
      }
    },
    [onFileSelected, onUploaded, projectId, readOnly, showToast, t, uploading],
  )

  if (selectedFile) {
    return (
      <div className="grid gap-2">
        <Frame role="group" aria-label={t.pdbUpload.uploadGroup} spacing="sm">
          <FramePanel className="flex min-w-0 items-center gap-2">
            <FileText className="size-5 shrink-0 text-primary" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate text-sm">{selectedFile.name}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => inputRef.current?.click()}
              disabled={readOnly || uploading}
              title={t.pdbUpload.replaceHint}
              aria-label={format(t.pdbUpload.replaceButton, { filename: selectedFile.name })}
            >
              <UploadSimple aria-hidden="true" />
              {uploading ? t.pdbUpload.uploading : t.pdbUpload.replace}
            </Button>
            <input
              ref={inputRef}
              id={inputId}
              type="file"
              accept=".pdb,.cif,.mmcif"
              className="hidden"
              disabled={readOnly || uploading}
              aria-label={t.pdbUpload.fileInputLabel}
              onChange={(event) => void handleFiles(event.target.files)}
            />
          </FramePanel>
        </Frame>
        {uploading ? (
          <Progress value={null} aria-label={t.pdbUpload.uploading}>
            <ProgressLabel>{t.pdbUpload.uploading}</ProgressLabel>
          </Progress>
        ) : null}
        {readOnly ? (
          <Alert variant="info">
            <AlertDescription>{t.pdbUpload.readOnly}</AlertDescription>
          </Alert>
        ) : null}
        {uploadError ? <UploadError message={uploadError} /> : null}
      </div>
    )
  }

  return (
    <div className="grid gap-2">
      <Frame
        role="group"
        aria-label={t.pdbUpload.uploadGroup}
        spacing="sm"
        className={dragging ? 'ring-2 ring-primary/40' : undefined}
      >
        <FramePanel
          className="flex flex-col items-center justify-center gap-3 border-dashed py-8 text-center"
          onDragOver={(event) => {
            event.preventDefault()
            if (!readOnly && !uploading) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            void handleFiles(event.dataTransfer.files)
          }}
        >
          <UploadSimple className="size-6 text-primary" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium">
              {uploading ? t.pdbUpload.uploading : t.pdbUpload.dropzone}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{t.pdbUpload.hint}</p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={readOnly || uploading}
            onClick={() => inputRef.current?.click()}
          >
            {t.pdbUpload.browseButton}
          </Button>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept=".pdb,.cif,.mmcif"
            className="hidden"
            disabled={readOnly || uploading}
            aria-label={t.pdbUpload.fileInputLabel}
            onChange={(event) => void handleFiles(event.target.files)}
          />
        </FramePanel>
      </Frame>
      {uploading ? (
        <Progress value={null} aria-label={t.pdbUpload.uploading}>
          <ProgressLabel>{t.pdbUpload.uploading}</ProgressLabel>
        </Progress>
      ) : null}
      {readOnly ? (
        <Alert variant="info">
          <AlertDescription>{t.pdbUpload.readOnly}</AlertDescription>
        </Alert>
      ) : null}
      {uploadError ? <UploadError message={uploadError} /> : null}
    </div>
  )
}

function UploadError({ message }: { message: string }) {
  const { t } = useI18n()
  return (
    <Alert variant="destructive">
      <WarningCircle aria-hidden="true" />
      <AlertTitle>{t.pdbUpload.uploadErrorTitle}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
