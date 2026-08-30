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
  it('uses distinct, project-specific proteins instead of one project-type thumbnail', () => {
    render(
      <>
        <RepresentativeStructurePreview project={project('Cannabinoid_specific_binding_protein_20260706')} />
        <RepresentativeStructurePreview project={project('Botrytis_cinerea_antifungal_protein_20260705')} />
        <RepresentativeStructurePreview project={project('Novel_Aroma_Flavor_Proteins_20260724')} />
        <RepresentativeStructurePreview project={project('Nanocage_delivery_0518', 'multimer_design')} />
        <RepresentativeStructurePreview project={project('manuka', 'sweet_protein_design')} />
      </>,
    )

    expect(screen.getByRole('img', { name: /Anti-THC Fab · THC/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /BcChs chitin synthase/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Flavor-molecule binding protein/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Self-assembling protein nanocage/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Single-chain monellin/ })).toBeInTheDocument()
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
