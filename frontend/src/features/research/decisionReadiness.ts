import type { ResearchDecisionContract } from '../../lib/api/generated/types.gen'
import type { ResearchGoal } from '../../lib/api/researchGoals'
import type { EvidenceNote } from './evidenceNotes'

export const emptyDecisionContract = (): Required<ResearchDecisionContract> => ({
  hypothesis: '', alternatives: [], success_criteria: [], falsification_criteria: [], next_decision: '', evidence_note_ids: [],
})

export function goalContract(goal: ResearchGoal): Required<ResearchDecisionContract> {
  return { ...emptyDecisionContract(), ...goal.decision_contract }
}

/** These are documentation checks, never a scientific truth or automatic go/no-go score. */
export function decisionReadiness(goal: ResearchGoal, notes: EvidenceNote[], evidenceComplete: boolean) {
  const contract = goalContract(goal)
  const linked = notes.filter((note) => contract.evidence_note_ids.includes(note.id))
  const missing = contract.evidence_note_ids.filter((id) => !linked.some((note) => note.id === id))
  const criteria = [
    { key: 'hypothesis', satisfied: Boolean(contract.hypothesis.trim()) },
    { key: 'alternatives', satisfied: contract.alternatives.length >= 2 },
    { key: 'success', satisfied: contract.success_criteria.length > 0 },
    { key: 'falsification', satisfied: contract.falsification_criteria.length > 0 },
    { key: 'next', satisfied: Boolean(contract.next_decision.trim()) },
    { key: 'sources', satisfied: linked.length > 0 && missing.length === 0 },
    { key: 'review', satisfied: linked.length > 0 && missing.length === 0 && linked.every((note) => note.review_status === 'accepted' && note.anchor_status === 'matched') },
  ] as const
  return { contract, linked, missing, criteria, definitionComplete: criteria.slice(0, 5).every((item) => item.satisfied),
    evidenceComplete, readyForReview: evidenceComplete && criteria.every((item) => item.satisfied) }
}
