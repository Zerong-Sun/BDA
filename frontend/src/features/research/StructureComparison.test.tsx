import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { ResearchWorkspaceStructure } from '../../lib/api/generated/types.gen'
import { StructureComparison } from './StructureComparison'

vi.mock('../pdb-viewer/StructureViewerLazy', () => ({ StructureViewerLazy: ({ source }: { source: { artifactId: string } }) => <div data-testid="comparison-viewer">{source.artifactId}</div> }))
const structures: ResearchWorkspaceStructure[] = [1, 2].map((id) => ({
  artifact_id: `artifact-${id}`, pdb_id: `DEMO${id}`, name: { en: `Synthetic structure ${id}` }, role: { en: 'Synthetic QA data' }, method: { en: 'Synthetic' }, status: 'available', download_url: `https://example.test/demo-${id}.pdb`,
}))

beforeEach(() => {
  useAppStore.setState({ language: 'en', activeProjectId: 'project-one', copilotDraft: '', copilotSelectedEntityIds: [] })
  window.location.hash = '/research?project=project-one&tab=structures'
})
afterEach(cleanup)

describe('structure comparison', () => {
  it('mounts one viewer by default, adds an independent second view on request and releases it on collapse', () => {
    renderWithProviders(<StructureComparison projectId="project-one" structures={structures} />)
    expect(screen.getAllByTestId('comparison-viewer')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Compare side by side' }))
    expect(screen.getAllByTestId('comparison-viewer')).toHaveLength(2)
    expect(screen.getByRole('combobox', { name: 'Structure B' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Single structure' }))
    expect(screen.getAllByTestId('comparison-viewer')).toHaveLength(1)
  })

  it('passes both selected artifact IDs to an unsent project-scoped Bot draft', () => {
    renderWithProviders(<StructureComparison projectId="project-one" structures={structures} />)
    fireEvent.click(screen.getByRole('button', { name: 'Compare side by side' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discuss with a Bot' }))
    expect(useAppStore.getState().copilotSelectedEntityIds).toEqual(['artifact-1', 'artifact-2'])
    expect(useAppStore.getState().copilotDraft).toContain('DEMO1')
    expect(useAppStore.getState().copilotDraft).toContain('DEMO2')
    expect(window.location.hash).toBe('#/bots?project=project-one&view=chat')
  })

  it('explains missing files and disables comparison when only one structure exists', () => {
    renderWithProviders(<StructureComparison projectId="project-one" structures={[{ ...structures[0], download_url: null, status: 'pending' }]} />)
    expect(screen.getByText('Structure file unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compare side by side' })).toBeDisabled()
    expect(screen.queryByTestId('comparison-viewer')).not.toBeInTheDocument()
  })
})
