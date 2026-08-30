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

/** A decimated trace, as [x, y] pairs. The server thins it; the browser draws it. */
export const SeriesSchema = z.array(z.tuple([z.number(), z.number()]))

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

export const BliSummarySchema = z.object({
  sample_id: z.string(),
  samples_available: z.array(z.string()).default([]),
  kd_nM: z.number().nullable().default(null),
  methods: z.object({
    standard: FitSchema.default(null),
    split: FitSchema.default(null),
    joint: FitSchema.default(null),
    steady: FitSchema.default(null),
    mixed: FitSchema.default(null),
  }),
  phase: z
    .object({ t_assoc: z.number().nullable(), t_dissoc: z.number().nullable() })
    .nullable()
    .default(null),
  curves: z
    .array(z.object({ label: z.string(), conc_nM: z.number(), points: SeriesSchema }))
    .default([]),
})

export const AktaSummarySchema = z.object({
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
  well_count: z.number(),
  background_subtracted: z.boolean().default(false),
  fits: z.record(
    z.string(),
    z.object({
      slope: z.number().nullable(),
      intercept: z.number().nullable(),
      r2: z.number().nullable(),
      n: z.number(),
    }),
  ),
  wells: z.array(z.object({ well: z.string(), points: SeriesSchema })).default([]),
})

export type Series = z.infer<typeof SeriesSchema>
export type BliSummary = z.infer<typeof BliSummarySchema>
export type AktaSummary = z.infer<typeof AktaSummarySchema>
export type EnzymeSummary = z.infer<typeof EnzymeSummarySchema>
