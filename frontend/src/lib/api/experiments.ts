import { ExperimentResultSchema } from '../schemas/candidate'
import { z } from 'zod'
import { uploadArtifact } from './artifacts'
import './generatedTransport'
import { awaitOperation, OperationTimeout } from './operations'
import {
  importResultsApiV2ProjectsProjectIdExperimentResultsImportsPost,
  listResultsApiV2ProjectsProjectIdExperimentResultsGet,
} from './generated/sdk.gen'

/** Row-level outcome of an import, produced by the backend import task. */
export const ImportReportSchema = z.object({
  imported: z.number().default(0),
  skipped: z.number().default(0),
  unlinked: z.number().default(0),
  ignored_columns: z.array(z.string()).default([]),
  errors: z.array(z.object({
    row: z.number(),
    column: z.string().optional(),
    message: z.string(),
    severity: z.string().optional(),
  })).default([]),
}).passthrough()

export type ImportReport = z.infer<typeof ImportReportSchema>

export async function listExperimentResults(projectId: string) {
  const page = await listResultsApiV2ProjectsProjectIdExperimentResultsGet<true>({
    path: { project_id: projectId }, query: { limit: 200 }, throwOnError: true,
  })
  return z.array(ExperimentResultSchema).parse(page.data.items)
}

export function uploadExperimentResults(file: File, projectId: string, options: { dryRun?: boolean } = {}) {
  return uploadArtifact(file, projectId).then((artifact) =>
    importResultsApiV2ProjectsProjectIdExperimentResultsImportsPost<true>({
      path: { project_id: projectId }, body: { artifact_id: artifact.id, dry_run: options.dryRun ?? false },
      throwOnError: true,
    }).then(async (accepted) => {
      const operationId = accepted.data.operation_id
      const operation = await awaitOperation(operationId, { timeoutMs: 30_000, intervalMs: 500 })
      const imported = operation.result.imported
      return { imported: typeof imported === 'number' ? imported : 0, batch_id: operationId }
    }),
  )
}

/**
 * Wait for an import operation and return its row-level report.
 *
 * The import is asynchronous, so the uploader would otherwise only learn that "something
 * was queued" - not which rows failed or which candidate references went unmatched. A
 * failed import still has a report worth rendering, so failure settles here rather than
 * throwing.
 */
export async function awaitImportReport(
  operationId: string,
  { timeoutMs = 30_000, intervalMs = 1000 }: { timeoutMs?: number; intervalMs?: number } = {},
): Promise<{ status: string; report: ImportReport | null; error: string | null }> {
  try {
    const operation = await awaitOperation(operationId, { timeoutMs, intervalMs, settleOnFailure: true })
    const parsed = ImportReportSchema.safeParse(operation.result)
    return {
      status: operation.status,
      report: parsed.success ? parsed.data : null,
      error: operation.error_message ?? null,
    }
  } catch (error) {
    if (error instanceof OperationTimeout) return { status: 'pending', report: null, error: null }
    throw error
  }
}
