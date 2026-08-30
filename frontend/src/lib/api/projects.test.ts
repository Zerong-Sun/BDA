import { describe, expect, it } from 'vitest'
import {
  deleteProject,
  getCurrentWorkflowRun,
  hasWorkflowNodes,
  listProjectWorkflowRuns,
  sortWorkflowRunsNewestFirst,
} from './projects'
import { http, HttpResponse } from 'msw'
import { WorkflowRunSchema } from '../schemas/workflow'
import { server } from '../../test/mocks/handlers'

describe('project api', () => {
  it('soft deletes a project with the configured retention period', async () => {
    const result = await deleteProject('proj_delete_test')

    expect(result).toMatchObject({
      id: 'proj_delete_test',
      deleted: true,
      retention_days: 30,
    })
  })

  it('orders workflow runs by creation time instead of UUID', () => {
    const workflow = (id: string, createdAt: string) =>
      WorkflowRunSchema.parse({
        id,
        project_id: 'project',
        name: id,
        status: 'running',
        graph: {},
        version: 1,
        created_by: 'user',
        created_at: createdAt,
        updated_at: createdAt,
      })

    expect(
      sortWorkflowRunsNewestFirst([
        workflow('0000-newer-looking-uuid', '2026-07-01T00:00:00Z'),
        workflow('ffff-older-looking-uuid', '2026-07-02T00:00:00Z'),
      ]).map((item) => item.id),
    ).toEqual(['ffff-older-looking-uuid', '0000-newer-looking-uuid'])
  })

  it('does not treat an empty draft as a drawable run', () => {
    const run = (graph: unknown) =>
      WorkflowRunSchema.parse({
        id: 'run',
        project_id: 'project',
        name: 'New workflow',
        status: 'draft',
        graph,
        version: 1,
        created_by: 'user',
        created_at: '2026-08-04T12:15:49Z',
        updated_at: '2026-08-04T12:15:49Z',
      })

    // The toolbar's "new route" button persists {nodes: [], edges: []} immediately, so an
    // empty draft is always the newest run in the project. Selecting it by recency alone
    // blanks the canvas of a project whose real runs are older - which is what happened to
    // manuka: two stray drafts from 2026-08-04 hid a 19-node run.
    expect(hasWorkflowNodes(run({ nodes: [], edges: [] }))).toBe(false)
    expect(hasWorkflowNodes(run({}))).toBe(false)
    expect(hasWorkflowNodes(run({ nodes: [{ id: 'monellin_rfdiffusion' }] }))).toBe(true)
  })

  it('hides archived runs from the route list', async () => {
    server.use(
      http.get('/api/v2/projects/manuka/workflow-runs', () =>
        HttpResponse.json({
          items: [
            {
              id: 'merged',
              project_id: 'manuka',
              name: 'Sweet-protein design workflow: routes 1-3',
              status: 'running',
              graph: {
                nodes: [{ id: 'n1' }],
                archived: { reason: 'split into one run per route', replaced_by: 'route-1' },
              },
              version: 1,
              created_by: 'script',
              created_at: '2026-08-01T18:32:21Z',
              updated_at: '2026-08-01T18:32:21Z',
            },
            {
              id: 'route-2',
              project_id: 'manuka',
              name: '设计路线 2 · 天然 Brazzein',
              status: 'running',
              graph: { nodes: [{ id: 'n1' }], edges: [] },
              version: 1,
              created_by: 'script',
              created_at: '2026-08-11T15:00:00Z',
              updated_at: '2026-08-11T15:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      ),
    )

    const runs = await listProjectWorkflowRuns('manuka')

    // A route is a run, so a superseded run is a second way to open the same route.
    expect(runs.map((run) => run.id)).toEqual(['route-2'])
  })

  it('selects the started run with nodes, not the newest draft', async () => {
    const item = (name: string, status: string, createdAt: string, nodeCount: number) => ({
      id: name,
      project_id: 'manuka',
      name,
      status,
      graph: { nodes: Array.from({ length: nodeCount }, (_, i) => ({ id: `n${i}` })), edges: [] },
      version: 1,
      created_by: 'script',
      created_at: createdAt,
      updated_at: createdAt,
    })

    server.use(
      http.get('/api/v2/projects/manuka/workflow-runs', () =>
        HttpResponse.json({
          items: [
            // Newest first is also the order the API returns; both of the leading entries
            // are wrong answers for different reasons.
            item('Route 0 calibration', 'draft', '2026-08-11T14:00:00Z', 4),
            item('New workflow', 'draft', '2026-08-04T12:15:49Z', 0),
            item('observed results', 'running', '2026-08-01T18:32:21Z', 19),
          ],
          next_cursor: null,
        }),
      ),
    )

    const current = await getCurrentWorkflowRun('manuka')
    expect(current.name).toBe('observed results')
  })
})
