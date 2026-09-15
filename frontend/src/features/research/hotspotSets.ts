import { useQuery } from '@tanstack/react-query'
import {
  confirmHotspotSetApiV2HotspotSetsHotspotSetIdConfirmationsPost,
  createHotspotSetApiV2TargetsTargetIdHotspotSetsPost,
  listHotspotSetsApiV2ProjectsProjectIdHotspotSetsGet,
  rejectHotspotSetApiV2HotspotSetsHotspotSetIdRejectionsPost,
} from '../../lib/api/generated'
import type { HotspotResidue, HotspotSetResponse } from '../../lib/api/generated'

/**
 * Which residues a design should target.
 *
 * A set carries who chose it: `agent` is a proposal and can reach nothing,
 * `human` is a person's own choice, and `agent_proposed_human_confirmed` is a
 * proposal somebody accepted. The workflow form reads only confirmed sets,
 * which is the whole reason the distinction is kept in the data rather than in
 * a sentence next to it.
 */

export const hotspotSetsQueryKey = (projectId: string | null, status?: string) =>
  ['hotspot-sets', projectId, status ?? 'all'] as const

export function useHotspotSets(
  projectId: string | null,
  status?: 'proposed' | 'confirmed' | 'rejected',
) {
  return useQuery({
    queryKey: hotspotSetsQueryKey(projectId, status),
    enabled: Boolean(projectId),
    queryFn: async () => {
      const { data } = await listHotspotSetsApiV2ProjectsProjectIdHotspotSetsGet<true>({
        throwOnError: true,
        path: { project_id: projectId as string },
        query: status ? { status } : {},
      })
      return data.items
    },
  })
}

/** A set the person picked themselves, confirmed on arrival. */
export async function createHotspotSet(
  targetId: string,
  body: {
    label: string
    residues: HotspotResidue[]
    structure_artifact_id?: string | null
    rationale?: string
    evidence_refs?: string[]
  },
): Promise<HotspotSetResponse> {
  const { data } = await createHotspotSetApiV2TargetsTargetIdHotspotSetsPost<true>({
    path: { target_id: targetId },
    body,
    throwOnError: true,
  })
  return data
}

/**
 * Take responsibility for a proposed set.
 *
 * Carries the version as an ETag: a 412 means somebody else already ruled on
 * it, and the list reloads rather than overwriting their call.
 */
export async function confirmHotspotSet(id: string, version: number): Promise<HotspotSetResponse> {
  const { data } = await confirmHotspotSetApiV2HotspotSetsHotspotSetIdConfirmationsPost<true>({
    path: { hotspot_set_id: id },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return data
}

/** Refuse a proposal, keeping it and the reason in the record. */
export async function rejectHotspotSet(
  id: string,
  version: number,
  reason = '',
): Promise<HotspotSetResponse> {
  const { data } = await rejectHotspotSetApiV2HotspotSetsHotspotSetIdRejectionsPost<true>({
    path: { hotspot_set_id: id },
    body: { reason },
    headers: { 'If-Match': `W/"${version}"` },
    throwOnError: true,
  })
  return data
}

/** `A164,A168,A171` - the shape both RFdiffusion and BindCraft take. */
export function residueArgument(residues: readonly HotspotResidue[]): string {
  return residues.map((residue) => `${residue.chain}${residue.seq}`).join(',')
}
