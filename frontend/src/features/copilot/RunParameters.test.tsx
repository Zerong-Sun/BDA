import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import type { AgentRun } from '../../lib/api/agentRuns'
import { RunParameters } from './RunParameters'

afterEach(cleanup)

describe('RunParameters', () => {
  it('separates recorded tool messages from the configured processing limit', () => {
    useAppStore.setState({ language: 'en' })
    renderWithProviders(<RunParameters run={{
      id: 'run', project_id: 'project', version: 1, turn_count: 9, max_turns: 6,
      max_cost_usd_cents: null, allowed_tools: ['research_overview'],
      task_contract: { service_kind: 'brief', authorized_writes: [] },
    } as unknown as AgentRun} />)
    expect(screen.queryByText('Configured turn limit')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Technical details' }))
    const region = within(screen.getByRole('region', { name: 'Technical details' }))
    expect(region.getByText('Recorded messages').nextElementSibling).toHaveTextContent('9')
    expect(region.getByText('Configured turn limit').nextElementSibling).toHaveTextContent('6')
    expect(region.queryByText('9 / 6')).not.toBeInTheDocument()
    expect(region.getByText(/Platform call and cost limits also apply/)).toBeInTheDocument()
    expect(region.getByText('Not set')).toBeInTheDocument()
  })
})
