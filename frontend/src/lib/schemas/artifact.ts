import { z } from 'zod'

export const ArtifactSchema = z.object({
  id: z.string(), project_id: z.string(), artifact_type: z.string(), filename: z.string(),
  content_type: z.string(), status: z.string(), size_bytes: z.number(), checksum_sha256: z.string(),
  lineage: z.record(z.string(), z.unknown()), version: z.number(), created_at: z.string(), updated_at: z.string(),
  download_url: z.string().nullable().optional(),
})

export type Artifact = z.infer<typeof ArtifactSchema>

export function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** index
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}
