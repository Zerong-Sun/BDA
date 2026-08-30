import { useNavigate } from 'react-router'
import { CaretDownIcon, SignOutIcon, UserIcon } from '@phosphor-icons/react'
import { useAppStore, type Language, type ThemePreference } from '../../lib/store/appStore'
import { applyTheme, resolveTheme } from '../../lib/theme/initTheme'
import { useI18n } from '../../lib/i18n'
import { Button } from './Button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './dropdown-menu'

function currentUserLabel(): string | null {
  try {
    const raw = sessionStorage.getItem('bda_user')
    if (!raw) return null
    const user = JSON.parse(raw) as { display_name?: string; username?: string }
    return user.display_name || user.username || null
  } catch {
    return null
  }
}

const THEME_LABELS: Record<ThemePreference, (t: ReturnType<typeof useI18n>['t']) => string> = {
  light: (t) => t.settings.theme.light,
  dark: (t) => t.settings.theme.dark,
  system: (t) => t.settings.theme.system,
}

export function UserMenu() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const {
    language,
    setLanguage,
    uiDensity,
    setUiDensity,
    themePreference,
    setThemePreference,
  } = useAppStore()
  const userLabel = currentUserLabel()

  const logout = () => {
    sessionStorage.removeItem('bda_token')
    sessionStorage.removeItem('bda_user')
    navigate('/login', { replace: true })
  }

  const setTheme = (pref: ThemePreference) => {
    setThemePreference(pref)
    applyTheme(resolveTheme(pref))
  }

  if (!userLabel) {
    return (
      <Button type="button" variant="outline" size="sm" onClick={() => navigate('/login')}>
        {t.shared.userMenu.login}
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="inline-flex h-8 items-center gap-1.5 border border-border px-2.5 text-sm hover:bg-muted">
        <UserIcon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="hidden max-w-28 truncate sm:inline">{userLabel}</span>
        <CaretDownIcon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{userLabel}</DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t.shared.userMenu.language}</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={language} onValueChange={(value) => setLanguage(value as Language)}>
            <DropdownMenuRadioItem value="en">{t.shared.userMenu.english}</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="zh">{t.shared.userMenu.chinese}</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t.shared.userMenu.appearance}</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={themePreference} onValueChange={(value) => setTheme(value as ThemePreference)}>
            {(['light', 'dark', 'system'] as const).map((pref) => (
              <DropdownMenuRadioItem key={pref} value={pref}>
                {THEME_LABELS[pref](t)}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t.shared.userMenu.view}</DropdownMenuLabel>
          <DropdownMenuItem
            onClick={() => setUiDensity(uiDensity === 'guided' ? 'advanced' : 'guided')}
          >
            {uiDensity === 'guided' ? t.shared.userMenu.switchToAdvanced : t.shared.userMenu.switchToGuided}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem variant="destructive" onClick={logout}>
            <SignOutIcon aria-hidden="true" />
            {t.shared.userMenu.logout}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
