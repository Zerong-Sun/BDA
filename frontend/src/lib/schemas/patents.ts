import { z } from 'zod'

const Member = z.object({
  document_id: z.string(), publication_number: z.string().nullable(), title: z.string(),
})
export const PatentLandscapeSchema = z.object({
  records_matched: z.number(), documents_truncated: z.boolean(), records_listed: z.number(),
  families: z.object({
    distinct: z.number(), publications_without_family_id: z.number(), groups_truncated: z.boolean(),
    groups: z.array(z.object({
      family_id: z.string(), publications: z.number(), jurisdictions: z.array(z.string()),
      applicants: z.array(z.string()), members: z.array(Member), members_truncated: z.boolean(),
    })),
  }),
  records: z.array(Member.extend({ family_id: z.string().nullable() })),
})
export const PatentClaimsPageSchema = z.object({
  items: z.array(z.object({
    claim_id: z.string(), document_id: z.string(), title: z.string(), excerpt: z.string(),
    claim_number: z.string(), language: z.string(), retrieval_trace_id: z.string(),
  })),
  next_cursor: z.string().nullable(),
})
