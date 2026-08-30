import { useRef, useState } from 'react'
import { UploadSimpleIcon } from '@phosphor-icons/react'
import { awaitImportReport, uploadExperimentResults, type ImportReport } from '../../lib/api/experiments'
import { useToastStore } from '../../components/ui/toastStore'
import { useI18n } from '../../lib/i18n'
import { Button } from '@/components/ui/Button'
import { AppFrame } from '../../components/ui/AppFrame'

interface ExperimentUploadProps {
  projectId: string
  onUploaded?: () => void
}

export function ExperimentUpload({ projectId, onUploaded }: ExperimentUploadProps) {
  const { t, format } = useI18n()
  const u = t.resultsExt.experimentUpload
  const [uploading, setUploading] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const showToast = useToastStore((s) => s.show)

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setUploading(true)
    setReport(null)
    try {
      const result = await uploadExperimentResults(file, projectId)
      // The import runs asynchronously; without waiting for its report the uploader
      // would never learn which rows failed or which candidate refs went unmatched.
      const outcome = await awaitImportReport(result.batch_id)
      setReport(outcome.report)
      if (outcome.status === 'failed') {
        showToast(outcome.error ?? t.resultsExt.toasts.uploadFailed, 'error')
      } else {
        showToast(
          format(t.resultsExt.toasts.importedResults, { count: outcome.report?.imported ?? 0 }),
          'success',
        )
      }
      onUploaded?.()
    } catch {
      showToast(t.resultsExt.toasts.uploadFailed, 'error')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="grid gap-2">
      <AppFrame panelClassName="flex items-center gap-3 border border-dashed border-border p-4">
        <UploadSimpleIcon className="size-5 text-primary" aria-hidden="true" />
        <div>
          <p className="text-sm text-text-primary">
            {uploading ? u.uploading : u.label}
          </p>
          <p className="text-xs text-text-secondary">{u.hint}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="ms-auto"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? u.uploading : u.chooseFile}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.json,.xlsx"
          className="hidden"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
      </AppFrame>
      {report ? <ImportReportPanel report={report} /> : null}
    </div>
  )
}

function ImportReportPanel({ report }: { report: ImportReport }) {
  const { t } = useI18n()
  const r = t.resultsExt.importReport
  return (
    <div data-testid="import-report" className="rounded-lg border border-border-soft bg-bg-app p-3 text-xs">
      <dl className="flex flex-wrap gap-x-4 gap-y-1">
        <Stat label={r.imported} value={report.imported} />
        <Stat label={r.skipped} value={report.skipped} tone={report.skipped > 0 ? 'warn' : undefined} />
        <Stat label={r.unlinked} value={report.unlinked} tone={report.unlinked > 0 ? 'warn' : undefined} />
      </dl>

      {report.ignored_columns.length > 0 ? (
        <p className="mt-2 text-text-secondary">
          {r.ignoredColumns}: {report.ignored_columns.join(', ')}
        </p>
      ) : null}

      {report.errors.length > 0 ? (
        <ul className="mt-2 grid max-h-48 gap-1 overflow-auto rounded border border-border-soft p-2">
          {report.errors.map((error, index) => (
            <li
              key={`${error.row}-${index}`}
              className="grid grid-cols-[auto_auto_1fr] gap-2 border-b border-border-soft py-1 last:border-0"
            >
              <span className="font-medium text-text-primary">{r.row} {error.row}</span>
              <span className="text-text-secondary">{r.column}: {error.column ?? '—'}</span>
              <span className="text-text-secondary">
                <span className="sr-only">{r.message}: </span>
                {error.message}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'warn' }) {
  return (
    <div className="flex items-baseline gap-1">
      <dt className="text-text-secondary">{label}</dt>
      <dd className={tone === 'warn' ? 'font-medium text-status-warning' : 'font-medium text-text-primary'}>
        {value}
      </dd>
    </div>
  )
}
