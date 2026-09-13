import { afterEach, expect, it } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { requireCopilotWrite } from './commandAccess'

afterEach(() => { sessionStorage.clear(); useAppStore.setState({ appMode: 'application' }) })

it.each(['viewer', 'demo'])('rejects a command even if a disabled control is bypassed in %s mode', (mode) => {
  useAppStore.setState({ appMode: mode === 'demo' ? 'demo' : 'application', language: 'en' })
  sessionStorage.setItem('bda_user', JSON.stringify({ role: mode === 'viewer' ? 'viewer' : 'researcher' }))
  expect(() => requireCopilotWrite()).toThrow('This workspace is read-only.')
})
