import './generatedTransport'
import {
  deleteResearchGoalApiV2ResearchGoalsGoalIdDelete,
  deleteResearchGoalLinkApiV2ResearchGoalsGoalIdLinksLinkIdDelete,
  getResearchGoalsApiV2ProjectsProjectIdResearchGoalsGet,
  patchResearchGoalApiV2ResearchGoalsGoalIdPatch,
  postResearchGoalApiV2ProjectsProjectIdResearchGoalsPost,
  postResearchGoalLinkApiV2ResearchGoalsGoalIdLinksPost,
} from './generated/sdk.gen'
import type { ResearchGoalResponse } from './generated/types.gen'

/**
 * The research goal tree: what we are trying to find out, and what has been hung on it.
 *
 * The server returns the tree flat, parent-first, already ordered. Nesting is rebuilt
 * here rather than asked for, because a flat list is what paginates and what a cycle
 * guard can reason about - the server refuses a re-parent that would close a loop.
 */

export type ResearchGoal = ResearchGoalResponse

export interface ResearchGoalNode {
  goal: ResearchGoal
  children: ResearchGoalNode[]
  depth: number
}

export async function listResearchGoals(projectId: string): Promise<ResearchGoal[]> {
  const page = await getResearchGoalsApiV2ProjectsProjectIdResearchGoalsGet<true>({
    path: { project_id: projectId },
    throwOnError: true,
  })
  return page.data.items
}

/** Rebuild the parent/child nesting from the flat, parent-first list. */
export function buildGoalTree(goals: ResearchGoal[]): ResearchGoalNode[] {
  const nodes = new Map<string, ResearchGoalNode>()
  for (const goal of goals) nodes.set(goal.id, { goal, children: [], depth: 0 })

  const roots: ResearchGoalNode[] = []
  for (const goal of goals) {
    const node = nodes.get(goal.id)!
    const parent = goal.parent_id ? nodes.get(goal.parent_id) : undefined
    if (parent) {
      node.depth = parent.depth + 1
      parent.children.push(node)
    } else {
      // Also covers a child whose parent is not in this page: showing it at the root is
      // better than dropping it, since a goal nobody can see cannot be corrected.
      roots.push(node)
    }
  }
  return roots
}

/** Depth-first, in the order the tree reads on screen. */
export function flattenGoalTree(nodes: ResearchGoalNode[]): ResearchGoalNode[] {
  return nodes.flatMap((node) => [node, ...flattenGoalTree(node.children)])
}

export async function createResearchGoal(
  projectId: string,
  body: { title: string; detail?: string; parent_id?: string | null; tags?: string[] },
) {
  const created = await postResearchGoalApiV2ProjectsProjectIdResearchGoalsPost<true>({
    path: { project_id: projectId },
    body: { detail: '', tags: [], ...body },
    throwOnError: true,
  })
  return created.data
}

export async function updateResearchGoal(
  goalId: string,
  version: number,
  body: { title?: string; detail?: string; status?: string; tags?: string[] },
) {
  const updated = await patchResearchGoalApiV2ResearchGoalsGoalIdPatch<true>({
    path: { goal_id: goalId },
    // 412 here means someone else moved the goal; reload, never overwrite.
    headers: { 'If-Match': `W/"${version}"` },
    body,
    throwOnError: true,
  })
  return updated.data
}

/** Deletes the goal and everything under it; the response says how many went. */
export async function deleteResearchGoal(goalId: string) {
  const deleted = await deleteResearchGoalApiV2ResearchGoalsGoalIdDelete<true>({
    path: { goal_id: goalId },
    throwOnError: true,
  })
  return deleted.data
}

export async function attachToResearchGoal(
  goalId: string,
  body: { resource_type: string; resource_id: string; note?: string },
) {
  const created = await postResearchGoalLinkApiV2ResearchGoalsGoalIdLinksPost<true>({
    path: { goal_id: goalId },
    body: { note: '', ...body },
    throwOnError: true,
  })
  return created.data
}

export async function detachFromResearchGoal(goalId: string, linkId: string) {
  await deleteResearchGoalLinkApiV2ResearchGoalsGoalIdLinksLinkIdDelete<true>({
    path: { goal_id: goalId, link_id: linkId },
    throwOnError: true,
  })
}
