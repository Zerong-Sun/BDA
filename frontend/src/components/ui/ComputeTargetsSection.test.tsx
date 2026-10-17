import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { ComputeTargetsSection } from './ComputeTargetsSection'
import { awaitOperation } from '../../lib/api/operations'
import { listComputeNodes } from '../../lib/api/registry'
vi.mock('../../features/research/jsonHelpers', () => ({currentRole: () => 'admin'}))
vi.mock('../../lib/api/operations', () => ({awaitOperation: vi.fn()}))
vi.mock('../../lib/api/registry', () => ({listComputeNodes: vi.fn(),checkComputeNodeHealth: vi.fn().mockResolvedValue({operation_id:'op'}),createComputeNode: vi.fn(),disableComputeNode: vi.fn()}))
afterEach(cleanup)
describe('compute target checks', () => {
 it('waits for the operation and refreshes the visible result', async () => {
  useAppStore.setState({language:'en'})
  const node={id:'node',name:'qm-test',backend:'lsf',queue:'test',enabled:true,health_status:'unknown',labels:{},version:1,health_checked_at:null,health_error:null,server_id:null,created_at:'',updated_at:''}
  vi.mocked(listComputeNodes).mockResolvedValue([node])
  let complete!: (value: never) => void
  vi.mocked(awaitOperation).mockImplementation(() => new Promise(resolve => {complete=resolve}))
  renderWithProviders(<ComputeTargetsSection />)
  fireEvent.click(await screen.findByRole('button',{name:'Run a health check on qm-test'}))
  expect(await screen.findByText('Checking…')).toBeDisabled()
  expect(listComputeNodes).toHaveBeenCalledTimes(1)
  vi.mocked(listComputeNodes).mockResolvedValue([{...node,health_status:'unhealthy',health_error:'Queue is closed'}])
  complete({status:'succeeded'} as never)
  await waitFor(() => expect(screen.getByText('Queue is closed')).toBeInTheDocument())
  expect(screen.getByText('unhealthy')).toBeInTheDocument()
 })
})
