import type { TranslationDict } from './types'
import type { Project } from '../schemas/project'
import { resolveStoredText } from './localizedText'

export function projectText(project: Project, key: 'name' | 'summary', language: 'en' | 'zh'): string {
  const value = project.localized_content?.[key]
  return resolveStoredText(value, language, key === 'name' ? project.name : project.summary ?? '')
}

/** Display known API action codes without rewriting server-authored explanations. */
export function projectActionText(action: string, t: TranslationDict): string {
  const actions: Record<string, string> = {
    create_workflow: t.research.targetIntelligence.createWorkflow,
    edit_workflow: t.projects.activeProjectPanel.continueWorkflow,
    review_candidates: t.jobs.reviewCandidates,
    review_results: t.experiments.interpretResults,
    primary_target_missing: t.workflowExt.routePlanner.resolveTarget,
    target_identity_unconfirmed: t.research.targetIntelligence.confirmIdentity,
    target_structure_unavailable: t.projects.activeProjectPanel.prepareStructure,
  }
  return Object.hasOwn(actions, action) ? actions[action] : action
}
