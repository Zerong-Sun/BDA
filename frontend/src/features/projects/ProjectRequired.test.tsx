import { fireEvent, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, expect, it } from 'vitest'
import { ProjectRequired } from './ProjectRequired'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/mocks/handlers'
import { useAppStore } from '../../lib/store/appStore'

afterEach(() => { window.location.hash = ''; useAppStore.setState({ activeProjectId: '' }) })

it('distinguishes a failed project request from an empty workspace and retries', async () => {
  let failed = true
  useAppStore.setState({ activeProjectId: '', language: 'en' })
  server.use(http.get('/api/v2/projects', () => failed
    ? HttpResponse.json({ detail: 'Project service unavailable' }, { status: 503 })
    : HttpResponse.json({ items: [], next_cursor: null })))
  renderWithProviders(<ProjectRequired><p>Project content</p></ProjectRequired>)
  expect(await screen.findByRole('alert')).toHaveTextContent('Project service unavailable')
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  failed = false
  fireEvent.click(screen.getByRole('button', { name: /Retry/i }))
  expect(await screen.findByRole('combobox')).toBeVisible()
  expect(screen.queryByText('Project content')).not.toBeInTheDocument()
})
