import type { AnalysisRecord } from '../api/wetlab'
import { z } from 'zod'

/**
 * What an instrument analysis hands back.
 *
 * The recorded row is typed by the generated SDK, but `summary` is `dict` on the
 * wire — it holds a fit, and the shape of a fit differs per instrument. So it is
 * validated here, at the boundary, the same way Literature and Intelligence JSON
 * is: a curve that silently arrives as `undefined` would draw an empty chart
 * rather than an error, which is the worst possible failure for a plot of a
 * measurement.
 *
 * Every fit field is nullable on purpose. The kernels return `null` for a method
 * that did not converge, and "did not converge" is a result worth showing — a
 * KD from four methods that agree means something different from one method that
 * happened to fit.
 */

/** Ordered [x, y] observations. Rendering connects supplied points without smoothing. */
export const SeriesSchema = z.array(z.tuple([z.number(), z.number()]))

export const InstrumentQCSchema = z.object({
  version: z.string(),
  review_required: z.boolean(),
  checks: z.array(z.object({ code: z.string(), status: z.enum(['review', 'information']), message: z.string(), details: z.record(z.string(), z.unknown()).default({}) })),
  metrics: z.record(z.string(), z.unknown()).default({}),
  interpretation: z.string(),
})

const FitSchema = z
  .object({
    kd: z.number().nullable().optional(),
    ka: z.number().nullable().optional(),
    kdis: z.number().nullable().optional(),
    rmax: z.number().nullable().optional(),
    r2: z.number().nullable().optional(),
  })
  .loose()
  .nullable()

const ProvenanceSchema = {
  source_format: z.string().optional(),
  evidence_kind: z.string().optional(),
  source_artifact_id: z.string().optional(),
  source_checksum_sha256: z.string().optional(),
  supersedes_result_id: z.string().nullable().optional(),
  selected_method: z.string().optional(),
  processing: z.record(z.string(), z.unknown()).optional(),
  uncertainty: z.unknown().optional(),
}

export const BliSummarySchema = z.object({
  ...ProvenanceSchema,
  quality_control: InstrumentQCSchema.nullable().default(null),
  sample_id: z.string(),
  samples_available: z.array(z.string()).default([]),
  kd_nM: z.number().nullable().default(null),
  methods: z.object({
    standard: FitSchema.default(null),
    split: FitSchema.default(null),
    joint: FitSchema.default(null),
    steady: FitSchema.default(null),
    mixed: FitSchema.default(null),
    instrument_kobs: FitSchema.optional(),
  }),
  phase: z
    .object({ t_assoc: z.number().nullable(), t_dissoc: z.number().nullable() }).loose()
    .nullable()
    .default(null),
  curves: z
    .array(z.object({ label: z.string(), conc_nM: z.number(), points: SeriesSchema, instrument_fit_points: SeriesSchema.optional(), analysis_fit_points: SeriesSchema.optional(), evidence_kind: z.string().optional(), excluded: z.boolean().optional(), sample_id: z.string().optional(), processed_points: SeriesSchema.optional(), analysis_fit_basis: z.string().optional() }))
    .default([]),
})

export const AktaSummarySchema = z.object({
  ...ProvenanceSchema,
  quality_control: InstrumentQCSchema.nullable().default(null),
  channel: z.string(),
  channels_available: z.array(z.string()).default([]),
  peak_count: z.number(),
  unit: z.string().nullable().default(null),
  peaks: z
    .array(
      z.object({
        apex_vol: z.number(),
        apex_amp: z.number(),
        start_vol: z.number(),
        end_vol: z.number(),
        height: z.number(),
        area: z.number(),
        half_width: z.number(),
      }),
    )
    .default([]),
  trace: SeriesSchema.default([]),
  fractions: z
    .array(z.object({ start: z.number(), end: z.number(), label: z.string() }))
    .default([]),
})

export const EnzymeSummarySchema = z.object({
  ...ProvenanceSchema,
  quality_control: InstrumentQCSchema.nullable().default(null),
  well_count: z.number(),
  background_subtracted: z.boolean().default(false),
  fits: z.record(
    z.string(),
    z.object({
      slope: z.number().nullable(),
      intercept: z.number().nullable(),
      r2: z.number().nullable(),
      n: z.number(),
      diagnostics: z.record(z.string(), z.unknown()).optional(),
    }),
  ),
  wells: z.array(z.object({ well: z.string(), points: SeriesSchema })).default([]),
})

export type Series = z.infer<typeof SeriesSchema>
export type BliSummary = z.infer<typeof BliSummarySchema>
export type AktaSummary = z.infer<typeof AktaSummarySchema>
export type EnzymeSummary = z.infer<typeof EnzymeSummarySchema>

export type InstrumentAnalysisData =
  | { instrument: 'bli'; record: AnalysisRecord; summary: BliSummary }
  | { instrument: 'akta'; record: AnalysisRecord; summary: AktaSummary }
  | { instrument: 'enzyme'; record: AnalysisRecord; summary: EnzymeSummary }
