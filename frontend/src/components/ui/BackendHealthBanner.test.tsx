import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { ApiError } from '../../lib/api/client'
import { getHealth } from '../../lib/api/health'
import { BackendHealthBanner } from './BackendHealthBanner'

vi.mock('../../lib/api/health', () => ({ getHealth: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

describe('BackendHealthBanner', () => {
  it('describes a scheduling pause and clears the banner after a successful retry', async () => {
    useAppStore.setState({ language: 'zh' })
    vi.mocked(getHealth).mockRejectedValueOnce(new ApiError('Unavailable', 503, {
      checks: { scheduler_dispatch: 'paused', postgresql: 'ok', worker_heartbeats: 'ok' },
    })).mockResolvedValue({ status: 'ok' })
    renderWithProviders(<BackendHealthBanner />)
    expect(await screen.findByRole('alert')).toHaveTextContent('自动调度已暂停')
    expect(screen.getByRole('alert')).not.toHaveTextContent('8100')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('does not hide another service failure behind the scheduling pause', async () => {
    useAppStore.setState({ language: 'zh' })
    vi.mocked(getHealth).mockRejectedValue(new ApiError('Unavailable', 503, {
      checks: { scheduler_dispatch: 'paused', postgresql: 'failed' },
    }))
    renderWithProviders(<BackendHealthBanner />)
    expect(await screen.findByRole('alert')).toHaveTextContent('部分服务暂未就绪')
  })

  it('preserves the separate compute-service warning', async () => {
    useAppStore.setState({ language: 'zh' })
    vi.mocked(getHealth).mockRejectedValue(new ApiError('Unavailable', 503, {
      checks: { worker_heartbeats: 'missing', schema_revision: 'ok', postgresql: 'ok', redis: 'ok', minio: 'ok' },
    }))
    renderWithProviders(<BackendHealthBanner />)
    expect(await screen.findByRole('alert')).toHaveTextContent('计算服务暂不可用')
  })

  it('shows plain connection guidance for a network failure', async () => {
    useAppStore.setState({ language: 'en' })
    vi.mocked(getHealth).mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<BackendHealthBanner />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot connect to the service')
    expect(screen.getByRole('alert')).not.toHaveTextContent('uvicorn')
  })
})
