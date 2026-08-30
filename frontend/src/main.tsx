import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { bootstrapHashRouterProjectParam } from './lib/bootstrapHashRouter'
import { initTheme } from './lib/theme/initTheme'
import type { ThemePreference } from './lib/store/appStore'

bootstrapHashRouterProjectParam()

function readPersistedThemePreference(): ThemePreference {
  try {
    const raw = localStorage.getItem('bda-app-store')
    if (!raw) return 'system'
    const parsed = JSON.parse(raw) as { state?: { themePreference?: ThemePreference } }
    const pref = parsed.state?.themePreference
    if (pref === 'light' || pref === 'dark' || pref === 'system') return pref
  } catch {
    /* ignore */
  }
  return 'system'
}

initTheme(readPersistedThemePreference())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
