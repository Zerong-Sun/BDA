import { z } from 'zod'

export const LocalizedTextSchema = z.union([
  z.string(),
  z.object({ zh: z.string(), en: z.string() }),
])

export type LocalizedText = z.infer<typeof LocalizedTextSchema>

export function localizedResearchText(value: LocalizedText, language: 'en' | 'zh'): string {
  return typeof value === 'string' ? value : value[language]
}

const canonicalId = /^[A-Za-z][A-Za-z0-9_-]*$/
export const BundledProjectIdSchema = z.string().regex(canonicalId)
const canonicalPdbId = /^[A-Za-z0-9][A-Za-z0-9_-]*$/
const pmidPattern = /^[1-9]\d{0,8}$/
const doiPattern = /^10\.\d{4,9}\/\S+$/i
const trustedVerificationStatuses = new Set(['verified_europe_pmc'])

const trustedReferenceHosts = new Set([
  'doi.org',
  'dx.doi.org',
  'europepmc.org',
  'www.ebi.ac.uk',
  'pubmed.ncbi.nlm.nih.gov',
  'pmc.ncbi.nlm.nih.gov',
])

function isTrustedReferenceUrl(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || !trustedReferenceHosts.has(url.hostname)) return false
    const path = decodeURIComponent(url.pathname).replace(/^\/+|\/+$/g, '')
    if (!path) return false
    if (url.hostname === 'doi.org' || url.hostname === 'dx.doi.org') return doiPattern.test(path)
    if (url.hostname === 'pubmed.ncbi.nlm.nih.gov') return pmidPattern.test(path.split('/', 1)[0])
    return true
  } catch {
    return false
  }
}

export const BundledStructureSchema = z.object({
  pdb_id: z.string().regex(canonicalPdbId),
  name: LocalizedTextSchema,
  method: z.string(),
  resolution: z.number().nullable(),
  role: LocalizedTextSchema,
  reference_id: z.string().regex(canonicalId),
  url: z.string().url(),
  rcsb_url: z.string().url(),
})

export const BundledProjectSchema = z.object({
  id: BundledProjectIdSchema,
  name: LocalizedTextSchema,
  project_type: z.string(),
  summary: LocalizedTextSchema,
  project_review: LocalizedTextSchema,
  primary_target: z.object({
    name: LocalizedTextSchema,
    gene: z.string(),
    uniprot: z.string(),
    organism: z.string(),
    pdb_id: z.string().nullable(),
  }),
  structures: z.array(BundledStructureSchema),
  // Optional per-project override of the package-level methods entry. Must stay
  // declared here: unknown keys are stripped before the bundle is imported.
  methods: LocalizedTextSchema.optional(),
})

export const BundledReferenceSchema = z.object({
  ref_id: z.string().regex(canonicalId),
  role: z.string(),
  title: z.string(),
  authors: z.string().optional().default(''),
  journal: z.string().optional().default(''),
  year: z.string().optional().default(''),
  doi: z.string().optional().default(''),
  pmid: z.string().optional().default(''),
  pmcid: z.string().optional().default(''),
  doi_url: z.string().optional().default(''),
  pubmed_url: z.string().optional().default(''),
  pmc_url: z.string().optional().default(''),
  url: z.string().optional().default(''),
  source_url: z.string().optional().default(''),
  verification_status: z.string(),
  is_open_access: z.string().optional().default('N'),
  project_ids: z.array(BundledProjectIdSchema).min(1).refine(
    (projectIds) => new Set(projectIds).size === projectIds.length,
    'Reference project IDs must be unique',
  ),
}).passthrough().refine(
  (reference) => Boolean(
    (reference.pmid && pmidPattern.test(reference.pmid))
    || (reference.doi && doiPattern.test(reference.doi))
    || [
      reference.url,
      reference.pubmed_url,
      reference.doi_url,
      reference.pmc_url,
      reference.source_url,
    ].some(isTrustedReferenceUrl),
  ),
  'Reference must provide a valid PMID, DOI, or trusted HTTPS source URL',
).refine(
  (reference) => trustedVerificationStatuses.has(reference.verification_status.toLowerCase()),
  'Reference must have a trusted verification status',
)

export const BundledEdgeSchema = z.object({
  claim_id: z.string().regex(canonicalId),
  project: BundledProjectIdSchema,
  subject: z.string(),
  predicate: z.string(),
  object: z.string(),
  context: LocalizedTextSchema,
  assertion: z.string(),
  grade: z.string(),
  ref_id: z.string().regex(canonicalId),
  summary: LocalizedTextSchema,
  source_url: z.string(),
  metadata_verification: z.string(),
}).passthrough()

export const BundledCandidateSchema = z.object({
  candidate_id: z.string().regex(canonicalId),
  project_id: BundledProjectIdSchema,
  group: LocalizedTextSchema.optional().default(''),
  target: LocalizedTextSchema,
  gene: z.string(),
  protein_type: LocalizedTextSchema,
  localization: LocalizedTextSchema,
  axis: LocalizedTextSchema,
  weighted_score: z.number(),
  evidence: z.number(),
  novelty: z.number(),
  tractability: z.number(),
  human: z.number(),
  specificity: z.number(),
  safety: z.number(),
  reference_ids: z.string().min(1),
}).passthrough().refine((candidate) => {
  const ids = candidate.reference_ids.split(';')
  return ids.every((id) => canonicalId.test(id)) && new Set(ids).size === ids.length
}, 'Candidate reference IDs must be canonical and unique')

export const BundledResearchPackageSchema = z.object({
  package_id: z.string(),
  schema_version: z.literal('1.1'),
  version: z.string(),
  as_of: z.string(),
  license: z.literal('CC-BY-4.0'),
  synthetic_demo: z.literal(true),
  disclaimer: LocalizedTextSchema,
  title: LocalizedTextSchema,
  description: LocalizedTextSchema,
  projects: z.array(BundledProjectSchema).min(1),
  methods: LocalizedTextSchema,
  search_strategy: LocalizedTextSchema,
  database_schema: LocalizedTextSchema,
  references: z.array(BundledReferenceSchema).min(1),
  edges: z.array(BundledEdgeSchema),
  candidates: z.array(BundledCandidateSchema),
  bibliometrics: z.array(z.object({
    id: z.string(), target: z.string(), historical_count: z.number(), recent_5y_count: z.number(),
    review_count: z.number(), clinical_trial_count: z.number(), as_of: z.string(),
  }).passthrough()),
  identifiers: z.array(z.object({
    gene: z.string(), uniprot_accession: z.string(), uniprot_entry: z.string(), protein_name: z.string(),
    ncbi_gene_ids: z.string(), ensembl_ids: z.string(), uniprot_url: z.string(), verification_status: z.string(),
  }).passthrough()),
  search_log: z.array(z.record(z.string(), z.string())),
  field_dictionary: z.array(z.record(z.string(), z.string())),
  ontology_relations: z.array(z.record(z.string(), z.string())),
  display_data: z.record(z.string(), z.array(z.record(z.string(), LocalizedTextSchema))).default({}),
  validation_report: LocalizedTextSchema,
  generation_template: z.object({
    system_role: z.string(),
    required_outputs: z.array(z.string()),
    quality_gates: z.array(z.string()),
  }),
}).superRefine((bundle, context) => {
  const projectIds = bundle.projects.map((project) => project.id)
  if (new Set(projectIds).size !== projectIds.length) {
    context.addIssue({ code: 'custom', path: ['projects'], message: 'Project IDs must be unique' })
  }

  const referencesById = new Map<string, z.infer<typeof BundledReferenceSchema>>()
  bundle.references.forEach((reference, index) => {
    if (referencesById.has(reference.ref_id)) {
      context.addIssue({
        code: 'custom',
        path: ['references', index, 'ref_id'],
        message: 'Reference IDs must be unique',
      })
    }
    referencesById.set(reference.ref_id, reference)
  })

  const claimIds = new Set<string>()
  bundle.edges.forEach((edge, index) => {
    if (claimIds.has(edge.claim_id)) {
      context.addIssue({
        code: 'custom',
        path: ['edges', index, 'claim_id'],
        message: 'Claim IDs must be unique',
      })
    }
    claimIds.add(edge.claim_id)
    if (!referencesById.get(edge.ref_id)?.project_ids.includes(edge.project)) {
      context.addIssue({
        code: 'custom',
        path: ['edges', index, 'ref_id'],
        message: `Reference ${edge.ref_id} is not visible in project ${edge.project}`,
      })
    }
  })

  bundle.projects.forEach((project, projectIndex) => {
    const visible = new Set(
      bundle.references
        .filter((reference) => reference.project_ids.includes(project.id))
        .map((reference) => reference.ref_id),
    )
    if (!visible.size) {
      context.addIssue({
        code: 'custom',
        path: ['projects', projectIndex],
        message: `Project ${project.id} must have at least one visible reference`,
      })
    }
    const pdbIds = new Set<string>()
    project.structures.forEach((structure, structureIndex) => {
      const pdbId = structure.pdb_id.toUpperCase()
      if (pdbIds.has(pdbId)) {
        context.addIssue({
          code: 'custom',
          path: ['projects', projectIndex, 'structures', structureIndex, 'pdb_id'],
          message: 'Project structure PDB IDs must be unique',
        })
      }
      pdbIds.add(pdbId)
      if (!visible.has(structure.reference_id)) {
        context.addIssue({
          code: 'custom',
          path: ['projects', projectIndex, 'structures', structureIndex, 'reference_id'],
          message: `Reference ${structure.reference_id} is not visible in project ${project.id}`,
        })
      }
    })
    if (project.primary_target.pdb_id
      && !pdbIds.has(project.primary_target.pdb_id.toUpperCase())) {
      context.addIssue({
        code: 'custom',
        path: ['projects', projectIndex, 'primary_target', 'pdb_id'],
        message: `Project ${project.id} primary target PDB ID must exist in project structures`,
      })
    }

    for (const [language, heading] of [['zh', '## 参考文献'], ['en', '## References']] as const) {
      const review = localizedResearchText(project.project_review, language)
      const lines = review.split(/\r?\n/)
      if (lines.filter((line) => line === heading).length !== 1) {
        context.addIssue({
          code: 'custom',
          path: ['projects', projectIndex, 'project_review'],
          message: `${project.id} ${language} review must contain exactly one ${heading} heading`,
        })
        continue
      }
      const section = lines.slice(lines.indexOf(heading) + 1).join('\n').split(/^##\s+/m, 1)[0]
      const ids = [...section.matchAll(/^([A-Za-z][A-Za-z0-9_-]*)\.\s/gm)].map((match) => match[1])
      if (ids.length !== visible.size || new Set(ids).size !== ids.length
        || ids.some((id) => !visible.has(id))) {
        context.addIssue({
          code: 'custom',
          path: ['projects', projectIndex, 'project_review'],
          message: `${project.id} ${language} bibliography must list every visible reference exactly once`,
        })
      }
    }
  })

  const candidateIds = new Set<string>()
  bundle.candidates.forEach((candidate, index) => {
    if (candidateIds.has(candidate.candidate_id)) {
      context.addIssue({
        code: 'custom',
        path: ['candidates', index, 'candidate_id'],
        message: 'Candidate IDs must be unique',
      })
    }
    candidateIds.add(candidate.candidate_id)
    if (!projectIds.includes(candidate.project_id)) {
      context.addIssue({
        code: 'custom',
        path: ['candidates', index, 'project_id'],
        message: `Candidate ${candidate.candidate_id} references unknown project ${candidate.project_id}`,
      })
      return
    }
    for (const refId of candidate.reference_ids.split(';')) {
      if (!referencesById.get(refId)?.project_ids.includes(candidate.project_id)) {
        context.addIssue({
          code: 'custom',
          path: ['candidates', index, 'reference_ids'],
          message: `Reference ${refId} is not visible in project ${candidate.project_id}`,
        })
      }
    }
  })
})

export type BundledResearchPackage = z.infer<typeof BundledResearchPackageSchema>
export type BundledProject = z.infer<typeof BundledProjectSchema>
export type BundledStructure = z.infer<typeof BundledStructureSchema>
