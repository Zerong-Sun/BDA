import { useRef } from 'react'
import { Link, NavLink, useLocation } from 'react-router'
import { CaretDownIcon } from '@phosphor-icons/react'
import { APP_ROUTES, PRIMARY_ROUTES, routeLabel, workbenchGroups } from '../../lib/nav/routes'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { Button } from './Button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from './dropdown-menu'

/** One route hierarchy for the fixed desktop navigator and compact page menu. */
export function WorkspaceNavigation() {
  const { t, language } = useI18n()
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const { projectId } = useProjectContext()
  const location = useLocation()
  const zh = language === 'zh'
  const query = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
  const label = (key: (typeof APP_ROUTES)[number]['key']) => routeLabel(key, zh, (item) => t.nav[item])
  const groups = [
    {
      key: 'workspace',
      label: zh ? '工作空间' : 'Workspace',
      routes: APP_ROUTES.filter((route) => PRIMARY_ROUTES.includes(route.to)),
    },
    ...workbenchGroups(zh),
  ]
  const current = APP_ROUTES.find((route) =>
    location.pathname === route.to || location.pathname.startsWith(`${route.to}/`),
  )
  const hrefFor = (path: string) => path === location.pathname
    && new URLSearchParams(location.search).get('project') === projectId
    ? `${path}${location.search}` : `${path}${query}`

  return (
    <nav className="workspace-navigation" data-tour-id="main-navigation" aria-label={t.shared.mainNavigation}>
      <div className="workspace-navigation-desktop">
        {groups.map((group) => (
          <div key={group.key} role="group" aria-label={group.label}>
            <h2>{group.label}</h2>
            {group.routes.map((route) => (
              <NavLink key={route.to} data-nav-route={route.to} to={hrefFor(route.to)}>
                {label(route.key)}
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <div className="workspace-navigation-mobile">
        <DropdownMenu>
          <DropdownMenuTrigger
            ref={menuTrigger}
            render={<Button type="button" variant="ghost" className="w-full justify-between" />}
            aria-label={zh ? '切换页面' : 'Switch page'}
          >
            <span>{current ? label(current.key) : (zh ? '切换页面' : 'Switch page')}</span>
            <CaretDownIcon aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72" finalFocus={menuTrigger}>
            {groups.map((group) => (
              <DropdownMenuGroup key={group.key}>
                <DropdownMenuLabel>{group.label}</DropdownMenuLabel>
                {group.routes.map((route) => (
                  <DropdownMenuItem
                    key={route.to}
                    aria-current={current?.to === route.to ? 'page' : undefined}
                    render={<Link to={hrefFor(route.to)} />}
                  >
                    {label(route.key)}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuGroup>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  )
}
