import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Project } from '../../lib/api/projects'
import { RepresentativeStructurePreview } from './RepresentativeStructurePreview'

function project(name: string, projectType = 'protein_design', sourceProjectKey: string | null = null): Project {
  return {
    id: name,
    organization_id: 'org',
    owner_id: 'user',
    name,
    project_type: projectType,
    summary: null,
    prompt: null,
    status: 'draft',
    source_package_id: null,
    source_project_key: sourceProjectKey,
    localized_content: {},
    primary_target_id: null,
    version: 1,
    created_at: '2026-08-03T00:00:00Z',
    updated_at: '2026-08-03T00:00:00Z',
  }
}

describe('RepresentativeStructurePreview', () => {
  it('uses project types without inferring private research identities from names', () => {
    render(
      <>
        <RepresentativeStructurePreview project={project('Project A', 'binder_design')} />
        <RepresentativeStructurePreview project={project('Project B', 'enzyme_design')} />
        <RepresentativeStructurePreview project={project('Project C', 'sweet_protein_design')} />
      </>,
    )

    expect(screen.getByRole('img', { name: /Binder · target/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Enzyme · substrate/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Sweet-protein design/ })).toBeInTheDocument()
  })

  it('uses the matching RCSB structure image when a verified PDB example exists', () => {
    const { container } = render(
      <RepresentativeStructurePreview project={project('PD-1/PD-L1 binding and regulatory network')} />,
    )
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'https://cdn.rcsb.org/images/structures/6jbt_assembly-1.jpeg',
    )
  })
})
