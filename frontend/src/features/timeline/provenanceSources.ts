import './../../lib/api/generatedTransport'
import {
  listFindingsApiV2ProjectsProjectIdResearchFindingsGet,
  listJobsApiV2JobsGet,
  listWorkflowsApiV2ProjectsProjectIdWorkflowRunsGet,
} from '../../lib/api/generated/sdk.gen'
import { listProjectArtifacts } from '../../lib/api/artifacts'
import { listCandidates } from '../../lib/api/candidates'
import { listExperimentResults } from '../../lib/api/experiments'
import { listProteins } from '../../lib/api/wetlab'
import type { ProvenanceKey } from '../../lib/schemas/timeline'

/**
 * Where each provenance key's options come from.
 *
 * The table `project_timeline_entries` was created with six provenance keys and the
 * seeders between them filled `job_ids` once; 49 entries went into `external_refs` as LSF
 * job-number *strings*, which nothing can resolve. The field was not the problem. The
 * editor was: it offered eight free-text boxes, and a free-text box is answered with
 * whatever the writer has to hand, which is a number from a terminal.
 *
 * So a key that names something the platform owns is answered by choosing that thing.
 * There is no text box to type an id into, which is the whole mechanism - not a
 * convenience, and not validation that can be skipped by pasting.
 *
 * Three kinds, and the split is the honest part:
 *
 * - `pick`   - the platform can list these; choose from real rows.
 * - `id`     - the platform owns them but has no project-scoped listing to offer. Typed,
 *              but checked to be a UUID, so at least it addresses something.
 * - `free`   - `external_refs` only. It exists for things the platform does *not* own, an
 *              LSF job id being the case that motivated it, so demanding a UUID would be
 *              wrong. This is the one box where a bare number is the correct answer.
 */

export interface ProvenanceOption {
  id: string
  label: string
  /** Shown under the label: enough to tell two similar rows apart. */
  detail?: string
}

export type ProvenanceSourceKind = 'pick' | 'id' | 'free'

export interface ProvenanceSource {
  kind: ProvenanceSourceKind
  /** Only for `pick`. */
  load?: (projectId: string) => Promise<ProvenanceOption[]>
}

const first = (value: unknown, fallback: string): string =>
  typeof value === 'string' && value.trim() ? value : fallback

export const PROVENANCE_SOURCES: Record<ProvenanceKey, ProvenanceSource> = {
  job_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const page = await listJobsApiV2JobsGet<true>({
        query: { project_id: projectId, limit: 200 },
        throwOnError: true,
      })
      return page.data.items.map((job) => ({
        id: job.id,
        label: first(job.external_id, job.id.slice(0, 8)),
        detail: job.status,
      }))
    },
  },
  candidate_ids: {
    kind: 'pick',
    load: async (projectId) => {
      // One page, not every page. A chooser is read, and a list longer than a screen
      // is not read - the same reasoning `core/review.py` states for approval batches.
      const page = await listCandidates(projectId, { limit: 200 })
      return page.items.map((item) => ({ id: item.id, label: item.name, detail: item.status }))
    },
  },
  artifact_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const items = await listProjectArtifacts(projectId)
      return items.map((item) => ({
        id: item.id,
        label: first(item.filename, item.id.slice(0, 8)),
        detail: item.artifact_type,
      }))
    },
  },
  workflow_run_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const page = await listWorkflowsApiV2ProjectsProjectIdWorkflowRunsGet<true>({
        path: { project_id: projectId },
        query: { limit: 200 },
        throwOnError: true,
      })
      return page.data.items.map((run) => ({
        id: run.id,
        label: first(run.name, run.id.slice(0, 8)),
        detail: run.status,
      }))
    },
  },
  finding_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const page = await listFindingsApiV2ProjectsProjectIdResearchFindingsGet<true>({
        path: { project_id: projectId },
        query: { limit: 200 },
        throwOnError: true,
      })
      return page.data.items.map((finding) => ({
        id: finding.id,
        label: finding.title,
        detail: finding.outcome ?? undefined,
      }))
    },
  },
  experiment_result_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const items = await listExperimentResults(projectId)
      return items.map((item) => ({
        id: item.id,
        label: first(item.experiment_type, item.id.slice(0, 8)),
        detail: item.pass_status,
      }))
    },
  },
  protein_ids: {
    kind: 'pick',
    load: async (projectId) => {
      const page = await listProteins(projectId, { limit: 200 })
      return page.items.map((protein) => ({
        id: protein.id,
        label: protein.name,
        // The fingerprint, not the sequence: two constructs with the same name are
        // told apart by what they actually are, and sequences never leave the server.
        detail: protein.fingerprint ?? undefined,
      }))
    },
  },
  // No project-scoped listing exists, and the rows that matter here are written by the
  // confirm service rather than typed, so a picker would be scaffolding for a case that
  // does not arise. Checked as a UUID so a hand-entered value still addresses a row.
  autopilot_campaign_ids: { kind: 'id' },
  // The exception, and the reason the rule can be strict everywhere else.
  external_refs: { kind: 'free' },
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Which entries of an `id`-kind field do not address anything. */
export function unresolvableIds(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !UUID.test(item))
}
