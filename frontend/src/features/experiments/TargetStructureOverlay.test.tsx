import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { ProjectTargetStructure, TargetReadiness } from '../../lib/schemas/target'
import { TargetStructureOverlay } from './TargetStructureOverlay'

const target: ProjectTargetStructure = {
  target: { id: 'target_a', project_id: 'proj_test', name: 'Example target', sequence: null,
    uniprot_accession: null, organism: null, identity_status: 'confirmed',
    structure_artifact_id: 'artifact_target', structure_status: 'approved', version: 1,
    target_kind: 'protein' as const, chemical_identity: {},
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z' },
  structure: { target_id: 'target_a', structure_status: 'approved', current_artifact_id: 'artifact_target',
    approved_revision_id: null, latest_revision: null },
  artifact: { id: 'artifact_target', project_id: 'proj_test', artifact_type: 'target_structure',
    filename: 'targets-prepared.pdb', content_type: 'chemical/x-pdb', status: 'available', size_bytes: 2048,
    checksum_sha256: 'a'.repeat(64), lineage: { pdb_id: '1ABC', atom_count: 2048, chains: ['A', 'B'] },
    version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
    download_url: '/api/v2/artifacts/artifact_target/content' },
}

const readiness: TargetReadiness = {
  stage: 'target_confirmed',
  ready_for_workflow: false,
  blockers: ['approve_prepared_structure'],
  next_action: 'Approve the prepared structure.',
  target_id: 'target_a', structure_artifact_id: 'artifact_target',
  identity_status: 'confirmed', structure_status: 'approved',
}

describe('TargetStructureOverlay', () => {
  it('shows target chain roles, readiness, missing contact evidence, and provenance', () => {
    renderWithProviders(
      <TargetStructureOverlay target={target} readiness={readiness} projectId="proj_test" />,
    )

    expect(screen.getByText('Target structure interpretation overlay')).toBeInTheDocument()
    expect(screen.getByText('Target chain')).toBeInTheDocument()
    expect(screen.getByText('Additional target chain')).toBeInTheDocument()
    expect(screen.getByText(/Approve the prepared structure/i)).toBeInTheDocument()
    expect(screen.getByText(/No confirmed hotspot rows are linked/i)).toBeInTheDocument()
    expect(screen.getByText(/No computed residue-contact table is attached/i)).toBeInTheDocument()
    expect(screen.getByText('1ABC')).toBeInTheDocument()
    expect(screen.getByText('targets-prepared.pdb')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review target hotspots' })).toHaveAttribute(
      'href',
      '#/research?project=proj_test&tab=structures',
    )
  })
})
