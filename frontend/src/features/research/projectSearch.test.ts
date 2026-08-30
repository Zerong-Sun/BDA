import { describe, expect, it } from 'vitest'
import type { Project } from '../../lib/schemas/project'
import type { ProjectResearchSummary } from '../../lib/schemas/research'
import { projectKnowledgeQuery, projectLiteratureQuery } from './projectSearch'

const botrytisProject: Project = {
  id: 'proj_botrytis',
  organization_id: 'org_test',
  owner_id: 'user_test',
  name: 'Botrytis_cinerea_antifungal_protein_20260705',
  project_type: 'protein_design',
  status: 'draft',
  summary: 'Design an antifungal protein workflow for Botrytis cinerea.',
  prompt: null,
  primary_target_id: null,
  version: 1,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

describe('projectSearch', () => {
  it('builds knowledge search from the active project instead of canned workflow terms', () => {
    const query = projectKnowledgeQuery(botrytisProject)

    expect(query).toContain('Botrytis')
    expect(query).toContain('cinerea')
    expect(query).not.toContain('ProteinMPNN')
    expect(query).not.toContain('RFdiffusion')
  })

  it('builds literature search from project research context instead of unrelated defaults', () => {
    const research: ProjectResearchSummary = {
      brief: {
        id: 'brief_botrytis',
        project_id: 'proj_botrytis',
        title: 'Botrytis cinerea antifungal protein target discovery',
        content: 'Compare cutinase, chitin synthase, CYP51, DHODH, and BcBet4 as design targets.',
        scope: {}, status: 'active', version: 1,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      },
      findings: [{
        id: 'finding_botrytis', project_id: 'proj_botrytis', brief_id: 'brief_botrytis',
        title: 'BcBet4 target evidence',
        content: 'Perillyl alcohol was reported to bind BcBet4.',
        finding_type: 'target', evidence: {}, version: 1,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        outcome: 'unspecified', supersedes_id: null, provenance: {},
      }],
      literature_document_count: 0, intelligence_run_count: 0, knowledge_entry_count: 0,
    }

    const query = projectLiteratureQuery(botrytisProject, research)

    expect(query).toContain('Botrytis')
    expect(query).toContain('cinerea')
    expect(query).toContain('antifungal')
    expect(query).not.toContain('unrelated receptor')
  })

  it('falls back to project context when a partial research summary omits findings', () => {
    const partialResearch = {
      brief: {
        title: 'Botrytis target discovery',
        content: 'Compare antifungal targets.',
      },
    } as ProjectResearchSummary

    expect(projectLiteratureQuery(botrytisProject, partialResearch)).toContain('Botrytis')
  })
})
