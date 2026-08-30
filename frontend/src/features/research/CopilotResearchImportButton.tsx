import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CheckCircleIcon, DownloadSimpleIcon, SpinnerGapIcon, WarningIcon } from '@phosphor-icons/react'
import { Alert, AlertDescription, AlertTitle } from '../../components/reui/alert'
import { Button } from '../../components/ui/Button'
import {
  copilotResearchIssues,
  importCopilotResearchResult,
  type CopilotResearchImportResponse,
} from '../../lib/api/copilotResearch'
import { useI18n } from '../../lib/i18n'

export function CopilotResearchImportButton({
  organizationId,
  content,
  onImported,
}: {
  organizationId: string
  content: string
  onImported: (result: CopilotResearchImportResponse) => void | Promise<void>
}) {
  const { t, format } = useI18n()
  const copy = t.research.copilotImport
  const [result, setResult] = useState<CopilotResearchImportResponse | null>(null)
  const mutation = useMutation({
    mutationFn: () => importCopilotResearchResult(organizationId, content),
    onSuccess: async (next) => {
      setResult(next)
      await onImported(next)
    },
  })
  const issues = copilotResearchIssues(mutation.error)

  return (
    <div className="mt-3 border-t border-border-soft pt-3" data-testid="copilot-research-import">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={mutation.isPending || Boolean(result)}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? <SpinnerGapIcon className="animate-spin" aria-hidden="true" /> : <DownloadSimpleIcon aria-hidden="true" />}
        {mutation.isPending ? copy.pending : copy.action}
      </Button>

      {result ? (
        <Alert className="mt-2" variant="success" role="status">
          <CheckCircleIcon aria-hidden="true" />
          <AlertTitle>{result.status === 'created' ? copy.createdTitle : copy.openedTitle}</AlertTitle>
          <AlertDescription>{format(
            result.status === 'created' ? copy.createdBody : copy.openedBody,
            { project: result.project_name },
          )}</AlertDescription>
        </Alert>
      ) : null}

      {mutation.isError ? (
        <Alert className="mt-2" variant="destructive" role="alert">
          <WarningIcon aria-hidden="true" />
          <AlertTitle>{copy.failedTitle}</AlertTitle>
          <AlertDescription>
          {issues.length ? (
            <ul className="mt-2 grid gap-1 font-mono">
              {issues.map((issue, index) => (
                <li key={`${issue.path}-${issue.reference ?? ''}-${index}`}>
                  {issue.path}{issue.reference ? ` (${issue.reference})` : ''}: {issue.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1">{mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}</p>
          )}
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
