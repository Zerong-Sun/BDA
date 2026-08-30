import { describe, expect, it } from 'vitest'
import type { Project } from '../../lib/schemas/project'
import { findDemoProject, isDemoProject } from './demoProject'

const project = (overrides: Partial<Project>): Project => ({
  id: 'project',
  organization_id: 'org',
  name: 'Project',
  project_type: 'research',
  status: 'active',
  owner_id: 'user',
  summary: '',
  prompt: null,
  primary_target_id: null,
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

describe('findDemoProject', () => {
  it('selects the packaged PD-1 project instead of a running ordinary project', () => {
    const running = project({ id: 'running', name: 'Running', status: 'running' })
    const pd1 = project({ id: 'pd1', name: 'PD-1', source_project_key: 'PD1' })
    expect(findDemoProject([running, pd1])).toBe(pd1)
  })

  it('supports the legacy demo id', () => {
    expect(findDemoProject([project({ id: 'proj_pd1_0423' })])?.id).toBe('proj_pd1_0423')
  })

  it('does not substitute an arbitrary project', () => {
    expect(findDemoProject([project({ id: 'ordinary', status: 'running' })])).toBeUndefined()
  })

  it('does not treat a real project opened by URL as a demo', () => {
    expect(
      isDemoProject(
        project({
          id: 'dc5cbf4f-4283-5366-bac0-690f30158a4d',
          name: 'SweetProtein_RFdiffusion_100x2_20260626',
        }),
      ),
    ).toBe(false)
  })
})
