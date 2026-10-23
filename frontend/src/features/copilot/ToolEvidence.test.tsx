import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'
import { ToolEvidence } from './ToolEvidence'
import { useAppStore } from '../../lib/store/appStore'
afterEach(cleanup)
it('links structure selections to Results with exact insertion codes and project context', () => {
  useAppStore.setState({ language: 'en' })
  const residues = [{ chain: 'A', seq: 52, insertion_code: 'A', name: 'LYS' }]
  render(<MemoryRouter><ToolEvidence projectId="project-1" calls={[{ name: 'list_structure_residues', result: { filename: 'target.pdb', viewer_selection: { artifact_id: 'artifact-1', residues }, checksum_sha256: 'abc' } }]} /></MemoryRouter>)
  const link = screen.getByRole('link', { name: 'Open structure and residues in Results' })
  const url = new URL(link.getAttribute('href')!, 'https://example.test')
  expect(url.pathname).toBe('/results')
  expect(url.searchParams.get('project')).toBe('project-1')
  expect(url.searchParams.get('artifact')).toBe('artifact-1')
  expect(JSON.parse(url.searchParams.get('residues')!)).toEqual(residues)
  expect(screen.getByText('A:52A LYS')).toBeInTheDocument()
  expect(screen.queryByText(/"checksum_sha256"/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Complete tool output and provenance' }))
  expect(screen.getByText(/"checksum_sha256": "abc"/)).toBeVisible()
})
it.each([undefined, 'A', null])('preserves render_structure_view highlighted residues and insertion code %s without viewer_selection', (insertionCode) => {
  const highlighted = [{ chain: 'B', seq: 46, name: 'LYS' }, { chain: 'B', seq: 54, name: 'ARG', ...(insertionCode !== undefined ? { insertion_code: insertionCode } : {}) }]
  render(<MemoryRouter><ToolEvidence projectId="p" calls={[{ name: 'render_structure_view', result: { artifact_id: 'structure', highlighted, scene_format: 'molviewspec/1' } }]} /></MemoryRouter>)
  const link = screen.getByRole('link', { name: 'Open structure and residues in Results' })
  const url = new URL(link.getAttribute('href')!, 'https://example.test')
  expect(url.searchParams.get('artifact')).toBe('structure')
  expect(JSON.parse(url.searchParams.get('residues')!)).toEqual(highlighted)
})
it.each([
  ['analyse_structure', [{ chain: 'B', seq: 46 }]],
  ['render_structure_view', [{ chain: 'B', seq: '46' }]],
  ['render_structure_view', [{ chain: 'B', seq: 46, insertionCode: 'A' }]],
  ['render_structure_view', Array.from({ length: 201 }, (_, seq) => ({ chain: 'B', seq }))],
])('does not apply an unrecognized or invalid highlighted fallback for %s', (name, highlighted) => {
  render(<MemoryRouter><ToolEvidence projectId="p" calls={[{ name, result: { artifact_id: 'structure', highlighted } }]} /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Open source in Results' })).toHaveAttribute('href', '/results?project=p&artifact=structure')
  expect(screen.queryByRole('link', { name: 'Open structure and residues in Results' })).not.toBeInTheDocument()
})
it('renders durable tool JSON as actionable analysis evidence without following arbitrary URLs', () => {
  render(<MemoryRouter><ToolEvidence projectId="p" content={JSON.stringify({ experiment_result_id: 'r', source_artifact_id: 'a', candidate_id: 'c', url: 'javascript:bad' })} /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Review saved analysis and QC' })).toHaveAttribute('href', '/lab?project=p&section=analysis')
  expect(screen.getByRole('link', { name: 'Open candidate' })).toHaveAttribute('href', '/candidates?project=p&candidate=c')
  expect(screen.getAllByRole('link').every((link) => link.getAttribute('href')?.startsWith('/'))).toBe(true)
})

it('retains list-shaped tool outputs for inspection even without a destination ID', () => {
  render(<MemoryRouter><ToolEvidence projectId="p" calls={[{ name: 'list_proteins', result: [{ name: 'Construct A' }] }]} /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Complete tool output and provenance' }))
  expect(screen.getByText(/Construct A/)).toBeInTheDocument()
})

it('opens the exact saved discussion report in the existing research view with review status', () => {
  render(<MemoryRouter><ToolEvidence projectId="project-one" calls={[{ name: 'create_knowledge_draft', result: { knowledge_entry_id: 'report-one', status: 'pending_review', entry_type: 'copilot_draft' } }]} /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Open saved discussion report' })).toHaveAttribute('href', '/research?project=project-one&tab=methods&knowledge=report-one')
  expect(screen.getByText('Recorded status: pending review')).toBeInTheDocument()
})
