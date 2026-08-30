import { resolveLegacyIdApiV2LegacyIdsEntityTypeLegacyIdGet } from './generated/sdk.gen'
import './generatedTransport'

export type LegacyEntity = 'artifacts' | 'candidates' | 'projects' | 'targets' | 'workflow-runs'

export async function resolveLegacyId(entityType: LegacyEntity, legacyId: string): Promise<string> {
  const { data } = await resolveLegacyIdApiV2LegacyIdsEntityTypeLegacyIdGet<true>({
    path: { entity_type: entityType, legacy_id: legacyId }, throwOnError: true,
  })
  return data.id
}
