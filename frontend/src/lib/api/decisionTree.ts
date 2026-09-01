import './generatedTransport'
import {
  getDecisionTreeDraftApiV2DecisionTreeDraftsDraftIdGet,
  postDecisionTreeApiV2ProjectsProjectIdDecisionTreePost,
  postDecisionTreeDraftApiV2ProjectsProjectIdDecisionTreeDraftsPost,
} from './generated/sdk.gen'
import { ApiError } from './client'

/**
 * The decision-tree bootstrap: a project's prompt becomes a proposed tree, a person
 * reviews it item by item, and only what they submit is written.
 *
 * There is deliberately no `importDraft(draftId)` here, mirroring the server: the draft
 * is a waiting room, and the only write takes the reviewed proposal. Adding a shortcut
 * on this side would hand goal-setting back to the model.
 */

export interface DraftGoal {
  title: string
  detail: string
  children: DraftGoal[]
}

export interface DraftAlternative {
  option: string
  rejected_because: string
}

export type DraftLane = 'dry' | 'wet' | 'both'

export interface DraftBranch {
  title: string
  summary: string
  lane: DraftLane
  goal_title: string
  alternatives: DraftAlternative[]
}

export interface DecisionTreeProposal {
  goals: DraftGoal[]
  branches: DraftBranch[]
}

export interface DecisionTreeDraft {
  id: string
  project_id: string
  status: string
  draft: DecisionTreeProposal
  error: string | null
}

export async function createDecisionTreeDraft(projectId: string): Promise<{ draft_id: string }> {
  const accepted = await postDecisionTreeDraftApiV2ProjectsProjectIdDecisionTreeDraftsPost<true>({
    path: { project_id: projectId },
    body: {},
    throwOnError: true,
  })
  return accepted.data
}

export async function getDecisionTreeDraft(draftId: string): Promise<DecisionTreeDraft> {
  const draft = await getDecisionTreeDraftApiV2DecisionTreeDraftsDraftIdGet<true>({
    path: { draft_id: draftId },
    throwOnError: true,
  })
  return draft.data as unknown as DecisionTreeDraft
}

/** Same polling shape as `waitForProjectPromptDraft`; the work runs on the research queue. */
export async function waitForDecisionTreeDraft(draftId: string): Promise<DecisionTreeDraft> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const draft = await getDecisionTreeDraft(draftId)
    if (draft.status !== 'pending') return draft
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
  }
  throw new ApiError('Decision tree drafting did not finish within two minutes.', 408)
}

export async function importDecisionTree(projectId: string, proposal: DecisionTreeProposal) {
  const created = await postDecisionTreeApiV2ProjectsProjectIdDecisionTreePost<true>({
    path: { project_id: projectId },
    body: proposal,
    throwOnError: true,
  })
  return created.data
}

/** Drop a goal and everything under it, and every branch that pointed at any of them.
 *
 *  Rejecting a goal has to take its branches with it, or the submitted proposal fails
 *  server-side validation on an unmatched `goal_title` - the reviewer would see a 422
 *  about a goal they deliberately removed. */
export function removeGoal(proposal: DecisionTreeProposal, title: string): DecisionTreeProposal {
  const removed = new Set<string>()

  function collect(goal: DraftGoal): void {
    removed.add(goal.title)
    goal.children.forEach(collect)
  }

  function prune(goals: DraftGoal[]): DraftGoal[] {
    return goals
      .filter((goal) => {
        if (goal.title !== title) return true
        collect(goal)
        return false
      })
      .map((goal) => ({ ...goal, children: prune(goal.children) }))
  }

  const goals = prune(proposal.goals)
  return { goals, branches: proposal.branches.filter((branch) => !removed.has(branch.goal_title)) }
}

/** Rename a goal, carrying every branch that referenced it by the old title. */
export function renameGoal(
  proposal: DecisionTreeProposal,
  from: string,
  to: string,
): DecisionTreeProposal {
  function walk(goals: DraftGoal[]): DraftGoal[] {
    return goals.map((goal) => ({
      ...goal,
      title: goal.title === from ? to : goal.title,
      children: walk(goal.children),
    }))
  }
  return {
    goals: walk(proposal.goals),
    branches: proposal.branches.map((branch) =>
      branch.goal_title === from ? { ...branch, goal_title: to } : branch,
    ),
  }
}

export function flattenDraftGoals(goals: DraftGoal[], depth = 0): Array<{ goal: DraftGoal; depth: number }> {
  return goals.flatMap((goal) => [{ goal, depth }, ...flattenDraftGoals(goal.children, depth + 1)])
}
