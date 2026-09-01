import type { ResearchGoal } from '../../lib/api/researchGoals'
import type { TimelineEntry } from '../../lib/schemas/timeline'

/**
 * Joining the goal tree to the decisions hung off it.
 *
 * The vertical structure is the goal tree (`research_goals.parent_id`); the decisions
 * attach to it many-to-many through `research_goal_links` with `resource_type` of
 * `timeline_entry`. That split is deliberate and load-bearing: a judgement routinely
 * constrains more than one goal - the sweet-protein D109 used dry re-analysis to revoke
 * a *wet* expression authorisation, so it belongs under both "produce an expressible
 * candidate" and "safety" - and a single parent pointer would force one of those
 * relationships into prose, which is where the project already loses things.
 *
 * `supersedes_id` and `caused_by_id` stay horizontal for the same reason. They are edges
 * between decisions, not a second hierarchy competing with the goals.
 *
 * Pure functions, no React: the joins are the part worth testing, and the component
 * should not be where "which decisions are unattached" is decided.
 */

export interface DecisionNode {
  entry: TimelineEntry
  /** Entries this one replaced. Shown collapsed - overturned reasoning is evidence. */
  superseded: TimelineEntry[]
}

export interface GoalNode {
  goal: ResearchGoal
  children: GoalNode[]
  decisions: DecisionNode[]
  depth: number
}

export interface DecisionTree {
  roots: GoalNode[]
  /** Decisions attached to no goal. Not hidden: an unattached decision still binds the
   *  project, and burying it is how the tree drifts away from the record. */
  unattached: DecisionNode[]
}

function decisionNodes(entries: TimelineEntry[], byId: Map<string, TimelineEntry>): DecisionNode[] {
  const superseded = new Map<string, TimelineEntry[]>()
  for (const entry of entries) {
    if (!entry.supersedes_id) continue
    const list = superseded.get(entry.id) ?? []
    const older = byId.get(entry.supersedes_id)
    if (older) list.push(older)
    superseded.set(entry.id, list)
  }
  return entries.map((entry) => ({ entry, superseded: superseded.get(entry.id) ?? [] }))
}

/**
 * Build the tree. `goals` is the flat, parent-first list the API returns, each carrying
 * its own links; `entries` is the project's whole timeline.
 */
export function buildDecisionTree(goals: ResearchGoal[], entries: TimelineEntry[]): DecisionTree {
  const byId = new Map(entries.map((entry) => [entry.id, entry]))
  // An entry that some later entry replaced is shown folded into its replacement rather
  // than as a peer, so the tree reads as the current state with its history attached.
  const replaced = new Set(
    entries.map((entry) => entry.supersedes_id).filter((id): id is string => Boolean(id)),
  )

  const nodes = new Map<string, GoalNode>()
  for (const goal of goals) nodes.set(goal.id, { goal, children: [], decisions: [], depth: 0 })

  const attached = new Set<string>()
  for (const goal of goals) {
    const node = nodes.get(goal.id)
    if (!node) continue
    const linked: TimelineEntry[] = []
    for (const link of goal.links ?? []) {
      if (link.resource_type !== 'timeline_entry') continue
      const entry = byId.get(link.resource_id)
      // A link whose target is gone reads as a dangling reference rather than an error;
      // that is the trade the link table was designed around.
      if (!entry) continue
      attached.add(entry.id)
      if (replaced.has(entry.id)) continue
      linked.push(entry)
    }
    linked.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
    node.decisions = decisionNodes(linked, byId)
  }

  const roots: GoalNode[] = []
  for (const goal of goals) {
    const node = nodes.get(goal.id)
    if (!node) continue
    const parent = goal.parent_id ? nodes.get(goal.parent_id) : undefined
    if (parent) {
      node.depth = parent.depth + 1
      parent.children.push(node)
    } else {
      // Also catches a child whose parent is missing from the response: showing it at
      // the root beats dropping it, since a goal nobody can see cannot be corrected.
      roots.push(node)
    }
  }

  const loose = entries.filter(
    (entry) => entry.entry_type === 'decision' && !attached.has(entry.id) && !replaced.has(entry.id),
  )
  loose.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))

  return { roots, unattached: decisionNodes(loose, byId) }
}

/** Depth-first in reading order, so a flat renderer produces the same shape. */
export function flattenGoalNodes(nodes: GoalNode[]): GoalNode[] {
  return nodes.flatMap((node) => [node, ...flattenGoalNodes(node.children)])
}

/** How many decisions sit under a goal and everything below it. */
export function subtreeDecisionCount(node: GoalNode): number {
  return node.decisions.length + node.children.reduce((sum, child) => sum + subtreeDecisionCount(child), 0)
}
