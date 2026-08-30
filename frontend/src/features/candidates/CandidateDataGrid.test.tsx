import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bundleZh } from '../../lib/i18n/locales/zh.bundle'
import { resolveActiveCandidate, type Candidate } from '../../lib/schemas/candidate'
import { useAppStore } from '../../lib/store/appStore'
import { renderWithProviders } from '../../test/renderWithProviders'
import { CandidateFilters } from './CandidateFilters'
import { CandidateTable } from './CandidateTable'

const candidates: Candidate[] = [
  {
    id: 'cand_b',
    project_id: 'proj_test',
    candidate_key: 'cand_b',
    name: 'family_b',
    status: 'Validated',
    rank: 2,
    score: 72,
    scores: { interface_score: 72, plddt: 81 },
    properties: { decision: 'Review' },
    structure_artifact_id: null,
    complex_artifact_id: null,
    source_job_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'cand_a',
    project_id: 'proj_test',
    candidate_key: 'cand_a',
    name: 'family_a',
    status: 'Reserve',
    rank: 1,
    score: 91,
    scores: { interface_score: 91, plddt: 89 },
    properties: { decision: 'Anchor' },
    structure_artifact_id: null,
    complex_artifact_id: null,
    source_job_id: null,
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
]

describe('candidate detail selection', () => {
  it('falls back to a visible candidate when filters hide the selected row', () => {
    expect(resolveActiveCandidate([candidates[1]], candidates[0])).toMatchObject({ id: 'cand_a' })
    expect(resolveActiveCandidate([], candidates[0])).toBeNull()
  })
})

describe('CandidateTable ReUI data grid', () => {
  beforeEach(() => {
    useAppStore.setState({ language: 'en' })
  })

  afterEach(() => cleanup())

  it('uses the ReUI grid and registry selection controls with stable candidate activation', () => {
    const onSelect = vi.fn()
    const onToggleCandidate = vi.fn()
    renderWithProviders(
      <CandidateTable
        data={candidates}
        selectedIds={new Set()}
        onSelect={onSelect}
        onToggleCandidate={onToggleCandidate}
        onTogglePage={vi.fn()}
      />,
    )

    expect(screen.getByRole('table')).toHaveAttribute('data-slot', 'data-grid-table')
    expect(screen.getAllByRole('checkbox')[0]).toHaveAttribute('data-slot', 'checkbox')

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select candidate cand_a' }))
    expect(onToggleCandidate).toHaveBeenCalledWith('cand_a')

    fireEvent.click(screen.getByRole('button', { name: 'View details for candidate cand_a' }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'cand_a' }))
  })

  it('keeps the ReUI table inside its localized named scroll region with usage instructions', () => {
    renderWithProviders(
      <CandidateTable
        data={candidates}
        selectedIds={new Set()}
        onSelect={vi.fn()}
        onToggleCandidate={vi.fn()}
        onTogglePage={vi.fn()}
      />,
    )

    const table = screen.getByRole('table')
    const region = screen.getByRole('region', { name: 'Candidate results table (scrollable)' })
    expect(region).toContainElement(table)
    expect(region).toHaveAccessibleDescription(
      'Ranked candidates. Activate a column header to sort; activate a row to view candidate details.',
    )
    const gridContainer = region.querySelector('[data-slot="data-grid"]')
    expect(gridContainer).toHaveClass('[&>div]:h-full', '[&>div]:min-h-0')
    expect(region.querySelector('[data-slot="data-grid-scroll-area"]')).toHaveClass('h-full', 'min-h-0')
  })

  it('maps ReUI filter changes back to the existing query callbacks', () => {
    const onSearchChange = vi.fn()
    const onStatusChange = vi.fn()
    const onPriorityOnlyChange = vi.fn()
    renderWithProviders(
      <CandidateFilters
        search="alpha"
        status="Validated"
        priorityOnly
        onSearchChange={onSearchChange}
        onStatusChange={onStatusChange}
        onPriorityOnlyChange={onPriorityOnlyChange}
      />,
    )

    expect(screen.getByTestId('candidate-filters')).toHaveAttribute('data-slot', 'filters')
    fireEvent.click(screen.getByRole('button', { name: 'Clear candidate filters' }))
    expect(onSearchChange).toHaveBeenCalledWith('')
    expect(onStatusChange).toHaveBeenCalledWith('All')
    expect(onPriorityOnlyChange).toHaveBeenCalledWith(false)
  })

  it('keeps a newly added empty search filter mounted so its value can update the query', async () => {
    const onSearchChange = vi.fn()
    renderWithProviders(
      <CandidateFilters
        search=""
        status="All"
        priorityOnly={false}
        onSearchChange={onSearchChange}
        onStatusChange={vi.fn()}
        onPriorityOnlyChange={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Add candidate filter' }))
    fireEvent.click(await screen.findByRole('option', { name: 'Candidate or family' }))

    const searchInput = await screen.findByPlaceholderText('Search candidate or family')
    expect(searchInput).toBeInTheDocument()
    fireEvent.change(searchInput, { target: { value: 'kinase' } })

    await waitFor(() => expect(onSearchChange).toHaveBeenLastCalledWith('kinase'))
    expect(screen.getByPlaceholderText('Search candidate or family')).toHaveValue('kinase')
  })

  it('only exposes filter operators that map to candidate API query semantics', async () => {
    renderWithProviders(
      <CandidateFilters
        search="kinase"
        status="Validated"
        priorityOnly
        onSearchChange={vi.fn()}
        onStatusChange={vi.fn()}
        onPriorityOnlyChange={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'contains' }))
    expect(await screen.findByRole('menuitem', { name: 'contains' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'does not contain' })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'starts with' })).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'is' })[0])
    expect(await screen.findByRole('menuitem', { name: 'is' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'is not' })).not.toBeInTheDocument()
  })

  it('localizes per-row selection and candidate loading accessible names in Chinese', () => {
    useAppStore.setState({ language: 'zh' })
    renderWithProviders(
      <CandidateTable
        data={candidates}
        selectedIds={new Set()}
        onSelect={vi.fn()}
        onToggleCandidate={vi.fn()}
        onTogglePage={vi.fn()}
      />,
    )

    expect(screen.getByRole('checkbox', { name: '选择候选物 cand_a' })).toBeInTheDocument()
    const tableLabels = bundleZh.candidatesExt.table as unknown as Record<string, string>
    expect(tableLabels.loadingAriaLabel).toBe('正在加载候选物')
  })

  it('retains localized metric help when expert grid columns are shown', () => {
    renderWithProviders(
      <CandidateTable
        data={candidates}
        selectedIds={new Set()}
        onSelect={vi.fn()}
        onToggleCandidate={vi.fn()}
        onTogglePage={vi.fn()}
      />,
    )

    expect(screen.queryByText('Model-derived interface quality score. Higher is better; this is not measured affinity.')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expert columns' }))
    expect(
      screen.getByText('Model-derived interface quality score. Higher is better; this is not measured affinity.'),
    ).toBeInTheDocument()
    expect(screen.getByTitle('Predicted local distance difference test. Higher means greater structure confidence.')).toBeInTheDocument()
  })

  it('paginates the complete collection through ReUI and resets to the first page when sorting changes', () => {
    const paginatedCandidates = Array.from({ length: 12 }, (_, index): Candidate => ({
      ...candidates[index % candidates.length],
      id: `cand_${String(index + 1).padStart(2, '0')}`,
      candidate_key: `cand_${String(index + 1).padStart(2, '0')}`,
      name: `family_${String(12 - index).padStart(2, '0')}`,
      score: 12 - index,
      scores: { interface_score: 12 - index, plddt: 80 + index },
    }))

    const onDownloadPage = vi.fn()
    renderWithProviders(
      <CandidateTable
        data={paginatedCandidates}
        selectedIds={new Set()}
        onSelect={vi.fn()}
        onToggleCandidate={vi.fn()}
        onTogglePage={vi.fn()}
        onDownloadPage={onDownloadPage}
      />,
    )

    const pagination = screen.getByTestId('candidate-pagination')
    expect(pagination.querySelector('[data-slot="data-grid-pagination"]')).toBeInTheDocument()
    expect(screen.getByText('1 - 10 of 12')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View details for candidate cand_11' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    expect(screen.getByText('11 - 12 of 12')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View details for candidate cand_11' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Family' }))
    expect(screen.getByRole('columnheader', { name: /Family/ })).toHaveAttribute('aria-sort', 'ascending')
    expect(screen.getByText('1 - 10 of 12')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View details for candidate cand_12' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    fireEvent.click(screen.getByRole('button', { name: 'Download page' }))
    expect(onDownloadPage).toHaveBeenCalledWith(['cand_02', 'cand_01'], 1)
  })

  it('keeps selected candidates stable while page selection targets only the visible page', () => {
    const paginatedCandidates = Array.from({ length: 12 }, (_, index): Candidate => ({
      ...candidates[index % candidates.length],
      id: `cand_${String(index + 1).padStart(2, '0')}`,
      candidate_key: `cand_${String(index + 1).padStart(2, '0')}`,
      name: `family_${String(index + 1).padStart(2, '0')}`,
      score: 12 - index,
      scores: { interface_score: 12 - index },
    }))
    function SelectionHarness() {
      const [selectedIds, setSelectedIds] = useState(() => new Set(['cand_01']))
      const togglePage = (candidateIds: string[]) => {
        setSelectedIds((current) => {
          const next = new Set(current)
          const allSelected = candidateIds.every((candidateId) => next.has(candidateId))
          for (const candidateId of candidateIds) {
            if (allSelected) next.delete(candidateId)
            else next.add(candidateId)
          }
          return next
        })
      }

      return (
        <CandidateTable
          data={paginatedCandidates}
          selectedIds={selectedIds}
          onSelect={vi.fn()}
          onToggleCandidate={vi.fn()}
          onTogglePage={togglePage}
        />
      )
    }

    renderWithProviders(<SelectionHarness />)

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    expect(screen.queryByRole('checkbox', { name: 'Select candidate cand_01' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Select page' }))
    expect(screen.getByText('3 selected')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Select candidate cand_11' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Select candidate cand_12' })).toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: 'Go to previous page' }))
    expect(screen.getByRole('checkbox', { name: 'Select candidate cand_01' })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    expect(screen.getByRole('checkbox', { name: 'Select candidate cand_11' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Select candidate cand_12' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Clear page' })).toBeInTheDocument()
  })

  it('localizes ReUI pagination controls in Chinese', () => {
    useAppStore.setState({ language: 'zh' })
    const paginatedCandidates = Array.from({ length: 12 }, (_, index): Candidate => ({
      ...candidates[index % candidates.length],
      id: `cand_${index + 1}`,
      candidate_key: `cand_${index + 1}`,
    }))

    renderWithProviders(
      <CandidateTable
        data={paginatedCandidates}
        selectedIds={new Set()}
        onSelect={vi.fn()}
        onToggleCandidate={vi.fn()}
        onTogglePage={vi.fn()}
      />,
    )

    expect(screen.getByText('每页行数')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '转到下一页' })).toBeInTheDocument()
    expect(screen.getByText('显示 1–10，共 12')).toBeInTheDocument()
  })
})
