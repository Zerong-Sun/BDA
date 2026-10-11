import { useState } from 'react'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { getProceduralSkill, listProceduralSkills, type ProceduralSkillSummary } from '../../lib/api/copilot'
import { AppliedProceduralSkills, ProceduralSkillCatalog, ProceduralSkillSelector } from './ProceduralSkills'

vi.mock('../../lib/api/copilot', () => ({ listProceduralSkills: vi.fn(), getProceduralSkill: vi.fn() }))

const skill = (id: string, title: string, defaults: string[] = []): ProceduralSkillSummary => ({
  id, title, title_zh: title, description: `${title} method`, description_zh: `${title} method`,
  version: '1.0.0', checksum_sha256: 'a'.repeat(64), instruction_sha256: 'b'.repeat(64),
  license: 'Apache-2.0', author: 'BDA contributors', default_for: defaults,
  tool_requests: ['research_overview'], optional_write_tools: [], data_policy: 'Current project only',
  provenance: [{ title: 'Reviewed reference', url: 'https://github.com/agentskills/agentskills', relation: 'format', note: 'Format only' }],
  input_schema: { type: 'object' }, output_schema: { type: 'object' },
})
const methods = [skill('evidence', 'Evidence', ['literature']), skill('design', 'Design', ['planning']), skill('statistics', 'Statistics'), skill('structure', 'Structure')]

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  vi.mocked(listProceduralSkills).mockResolvedValue(methods)
  vi.mocked(getProceduralSkill).mockImplementation(async (id) => ({ ...methods.find((entry) => entry.id === id)!, instructions: '# Frozen reviewed instructions\nVerify actual sources.' }))
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('Scientific method selection and audit', () => {
  it('discovers methods and loads instructions only on demand', async () => {
    renderWithProviders(<ProceduralSkillCatalog />)
    expect(await screen.findByRole('heading', { name: 'Evidence' })).toBeInTheDocument()
    expect(getProceduralSkill).not.toHaveBeenCalled()
    fireEvent.change(screen.getByRole('textbox', { name: 'Search scientific methods' }), { target: { value: 'Statistics' } })
    expect(screen.queryByRole('heading', { name: 'Evidence' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Method & provenance' }))
    expect(await screen.findByText(/Frozen reviewed instructions/)).toBeInTheDocument()
    expect(getProceduralSkill).toHaveBeenCalledWith('statistics')
    expect(screen.getByRole('link', { name: 'Reviewed reference' })).toHaveAttribute('href', 'https://github.com/agentskills/agentskills')
  })

  it('distinguishes recommendations from explicit opt out and caps at three', async () => {
    const changed = vi.fn()
    function Selection() {
      const [value, setValue] = useState<string[] | null>(null)
      return <ProceduralSkillSelector serviceKind="literature" value={value} onChange={(next) => { changed(next); setValue(next) }} />
    }
    renderWithProviders(<Selection />)
    expect(await screen.findByRole('checkbox', { name: /Evidence/ })).toBeChecked()
    fireEvent.click(screen.getByRole('checkbox', { name: /Design/ }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Statistics/ }))
    expect(changed).toHaveBeenLastCalledWith(['evidence', 'design', 'statistics'])
    expect(screen.getByRole('checkbox', { name: /Structure/ })).toHaveAttribute('aria-disabled', 'true')
    changed.mockClear()
    fireEvent.click(screen.getByRole('checkbox', { name: /Structure/ }))
    expect(changed).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'No method packages' }))
    expect(changed).toHaveBeenLastCalledWith([])
    expect(screen.getByRole('checkbox', { name: /Evidence/ })).not.toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Use recommended' }))
    expect(changed).toHaveBeenLastCalledWith(null)
    expect(screen.getByRole('checkbox', { name: /Evidence/ })).toBeChecked()
  })

  it('does not allow changes while read only', async () => {
    const changed = vi.fn()
    renderWithProviders(<ProceduralSkillSelector serviceKind="literature" value={null} onChange={changed} disabled />)
    expect(await screen.findByRole('checkbox', { name: /Evidence/ })).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(screen.getByRole('checkbox', { name: /Evidence/ }))
    expect(changed).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'No method packages' })).toBeDisabled()
  })

  it('shows failed loading without pretending an empty catalog is loaded', async () => {
    vi.mocked(listProceduralSkills).mockRejectedValue(new Error('Offline'))
    renderWithProviders(<ProceduralSkillCatalog />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unavailable')
    vi.mocked(listProceduralSkills).mockResolvedValue(methods)
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
    expect(await screen.findByRole('heading', { name: 'Evidence' })).toBeInTheDocument()
  })

  it('displays the frozen run snapshot and validated output without refetching current methods', async () => {
    const snapshot = { ...methods[0], version: '0.9.0', instructions: 'Exact older method.' }
    renderWithProviders(<AppliedProceduralSkills contract={{ procedural_skills: [snapshot] }} outcome={{ skill_outputs: { evidence: { project_claim: 'The actual project claim', evidence_call_ids: ['call-1'], limitations: ['Small sample'] } } }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Scientific methods and delivery for this run' }))
    expect(await screen.findByText('Evidence · v0.9.0')).toBeInTheDocument()
    expect(screen.getByText('The actual project claim')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Inspect frozen instructions' }))
    await waitFor(() => expect(screen.getByText('Exact older method.')).toBeInTheDocument())
    expect(getProceduralSkill).not.toHaveBeenCalled()
    expect(listProceduralSkills).not.toHaveBeenCalled()
  })
})
