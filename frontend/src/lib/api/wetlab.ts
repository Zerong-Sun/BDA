import './generatedTransport'
import {
  getConcentrationApiV2ProjectsProjectIdWetlabConcentrationGet,
  getDilutionSeriesApiV2WetlabDilutionSeriesGet,
  getUnitConversionApiV2WetlabUnitConversionGet,
  listProteinsApiV2ProjectsProjectIdProteinsGet,
  patchProteinApiV2ProteinsProteinIdPatch,
  postAktaAnalysisApiV2ProjectsProjectIdWetlabAktaAnalysesPost,
  postBliAnalysisApiV2ProjectsProjectIdWetlabBliAnalysesPost,
  postEnzymeAnalysisApiV2ProjectsProjectIdWetlabEnzymeAnalysesPost,
  postFastaImportApiV2ProjectsProjectIdProteinsImportFastaPost,
  postProteinApiV2ProjectsProjectIdProteinsPost,
  postPromoteCandidateApiV2ProjectsProjectIdCandidatesCandidateIdPromoteToBenchPost,
} from './generated/sdk.gen'
import {
  AktaSummarySchema,
  BliSummarySchema,
  EnzymeSummarySchema,
} from '../schemas/instrumentAnalysis'

/**
 * Wet-lab bench transport.
 *
 * Note what is absent: there is no way to read a sequence back. The server
 * projects constructs without one and identifies them by a 12-character
 * fingerprint, so no client code can accidentally render or forward plaintext.
 */

export interface ProteinQuery {
  search?: string
  tag?: string
  limit?: number
  cursor?: string
}

export async function listProteins(projectId: string, query: ProteinQuery = {}) {
  const page = await listProteinsApiV2ProjectsProjectIdProteinsGet<true>({
    path: { project_id: projectId },
    query: {
      cursor: query.cursor,
      limit: query.limit ?? 50,
      search: query.search || undefined,
      tag: query.tag || undefined,
    },
    throwOnError: true,
  })
  return page.data
}

export async function createProtein(
  projectId: string,
  body: { name: string; sequence: string; tags?: string[]; notes?: string; candidate_id?: string },
) {
  const created = await postProteinApiV2ProjectsProjectIdProteinsPost<true>({
    path: { project_id: projectId },
    body: { tags: [], notes: '', ...body },
    throwOnError: true,
  })
  return created.data
}

/**
 * Make a designed candidate into a construct on the bench.
 *
 * The construct keeps `candidate_id`, which is the whole point: a measurement taken
 * against it later finds its way back to the design that predicted it. Promoting the
 * same candidate twice returns the construct that already exists rather than failing -
 * the server treats a repeated click as a repeated click.
 */
export async function promoteCandidateToBench(projectId: string, candidateId: string) {
  const created =
    await postPromoteCandidateApiV2ProjectsProjectIdCandidatesCandidateIdPromoteToBenchPost<true>({
      path: { project_id: projectId, candidate_id: candidateId },
      throwOnError: true,
    })
  return created.data
}

export async function importFasta(projectId: string, content: string, tags: string[] = []) {
  const result = await postFastaImportApiV2ProjectsProjectIdProteinsImportFastaPost<true>({
    path: { project_id: projectId },
    body: { content, tags },
    throwOnError: true,
  })
  return result.data
}

export async function updateProtein(
  proteinId: string,
  version: number,
  body: { name?: string; tags?: string[]; notes?: string },
) {
  const updated = await patchProteinApiV2ProteinsProteinIdPatch<true>({
    path: { protein_id: proteinId },
    // Mutations carry the version as an ETag; 412 means reload, never overwrite.
    headers: { 'If-Match': `W/"${version}"` },
    body,
    throwOnError: true,
  })
  return updated.data
}

export interface ConcentrationQuery {
  a280: number
  protein_id?: string
  ext_coeff?: number
  molecular_weight?: number
  path_length_cm?: number
  cystines?: 'reduced' | 'oxidized'
}

export async function computeConcentration(projectId: string, query: ConcentrationQuery) {
  const result = await getConcentrationApiV2ProjectsProjectIdWetlabConcentrationGet<true>({
    path: { project_id: projectId },
    query: {
      a280: query.a280,
      protein_id: query.protein_id,
      ext_coeff: query.ext_coeff,
      molecular_weight: query.molecular_weight,
      path_length_cm: query.path_length_cm ?? 1,
      cystines: query.cystines ?? 'reduced',
    },
    throwOnError: true,
  })
  return result.data
}

export async function convertUnits(query: {
  value: number
  from_unit: string
  to_unit: string
  molecular_weight?: number
}) {
  const result = await getUnitConversionApiV2WetlabUnitConversionGet<true>({
    query,
    throwOnError: true,
  })
  return result.data
}

export async function planDilutionSeries(query: {
  stock_conc_uM: number
  start_conc_uM: number
  dilution_factor: number
  n_steps: number
  vol_per_well_uL: number
  extra_dead_vol_uL?: number
}) {
  const result = await getDilutionSeriesApiV2WetlabDilutionSeriesGet<true>({
    query: { extra_dead_vol_uL: 0, ...query },
    throwOnError: true,
  })
  return result.data
}

// --- Instrument analysis -----------------------------------------------------
//
// POST, unlike the calculators above: each of these records an ExperimentResult
// against the artifact it read. The body carries an artifact id rather than a
// file, because uploads go browser-direct to object storage (see
// `artifacts.ts`) and the API never receives a multipart body.
//
// `summary` is `dict` on the wire, so each of these parses it through the Zod
// schema for that instrument. An unvalidated curve that arrives as `undefined`
// draws an empty chart instead of raising, which is the worst way for a plot of
// a measurement to fail.

export interface AnalysisRecord {
  experiment_result_id: string
  experiment_type: string
  analysis_version: string
  value: number | null
  unit: string | null
  source_artifact_id: string
}

function record(data: {
  experiment_result_id: string
  experiment_type: string
  analysis_version: string
  value: number | null
  unit: string | null
  source_artifact_id: string
}): AnalysisRecord {
  return {
    experiment_result_id: data.experiment_result_id,
    experiment_type: data.experiment_type,
    analysis_version: data.analysis_version,
    value: data.value,
    unit: data.unit,
    source_artifact_id: data.source_artifact_id,
  }
}

export async function analyseBli(
  projectId: string,
  body: {
    artifact_id: string
    sample_id?: string | null
    t_assoc?: number | null
    t_dissoc?: number | null
    candidate_id?: string | null
  },
) {
  const result = await postBliAnalysisApiV2ProjectsProjectIdWetlabBliAnalysesPost<true>({
    path: { project_id: projectId },
    body,
    throwOnError: true,
  })
  return { ...record(result.data), summary: BliSummarySchema.parse(result.data.summary) }
}

export async function analyseAkta(
  projectId: string,
  body: { artifact_id: string; channel?: string | null; candidate_id?: string | null },
) {
  const result = await postAktaAnalysisApiV2ProjectsProjectIdWetlabAktaAnalysesPost<true>({
    path: { project_id: projectId },
    body,
    throwOnError: true,
  })
  return { ...record(result.data), summary: AktaSummarySchema.parse(result.data.summary) }
}

export async function analyseEnzyme(
  projectId: string,
  body: { artifact_id: string; subtract_background?: boolean; candidate_id?: string | null },
) {
  const result = await postEnzymeAnalysisApiV2ProjectsProjectIdWetlabEnzymeAnalysesPost<true>({
    path: { project_id: projectId },
    body: { subtract_background: true, ...body },
    throwOnError: true,
  })
  return { ...record(result.data), summary: EnzymeSummarySchema.parse(result.data.summary) }
}
