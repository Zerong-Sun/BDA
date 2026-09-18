import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import { WorkflowEvidence } from './WorkflowEvidence'
vi.mock('../../lib/api/candidates', () => ({ getCandidate: vi.fn(async (id: string) => ({ id, project_id: id === 'archived' ? 'history-project' : 'p1' })) }))
afterEach(cleanup)
const node = { id: 'n1', node_key: 'bli', parameters: { display_name: 'BLI 历史实验记录', evidence_summary: '来源待核验', evidence_records: [{ label: 'binder1', candidate_id: 'c1', values: { value: 0.6, unit: 'nM', missing: null } }] } } as unknown as WorkflowNode
it('opens evidence nodes while preserving provenance and record counts', () => {
 const select = vi.fn()
 renderWithProviders(<WorkflowEvidence nodes={[node]} artifacts={[]} projectId="p1" onSelect={select} />)
 expect(screen.getByText('来源待核验')).toBeInTheDocument()
 expect(screen.getByText('1 条记录 · 0 个文件')).toBeInTheDocument()
 fireEvent.click(screen.getByRole('button', { name: 'BLI 历史实验记录' }))
 expect(select).toHaveBeenCalledWith('n1')
})
it('shows linked values without inventing missing readings', async () => {
 renderWithProviders(<WorkflowEvidence nodes={[node]} artifacts={[]} projectId="p1" expanded />)
 expect(screen.getByText('0.6')).toBeInTheDocument()
 expect(screen.getByText('nM')).toBeInTheDocument()
 expect(screen.getByText('—')).toBeInTheDocument()
 expect(await screen.findByRole('link', { name: 'binder1' })).toHaveAttribute('href', '#/candidates?project=p1&candidate=c1')
})

it('resolves moved candidates to their historical project', async () => {
 const moved = { ...node, parameters: { ...node.parameters, evidence_records: [{ label: 'old binder', candidate_id: 'archived', values: {} }] } }
 renderWithProviders(<WorkflowEvidence nodes={[moved]} artifacts={[]} projectId="p1" expanded />)
 expect(await screen.findByRole('link', { name: 'old binder' })).toHaveAttribute('href', '#/candidates?project=history-project&candidate=archived&history=history-project')
})
