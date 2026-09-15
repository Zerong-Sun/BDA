import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { MagnifyingGlassIcon } from '@phosphor-icons/react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from './command'
import { Button } from './Button'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useCopilotBots } from '../../features/copilot/bots/registry'
import { APP_ROUTES, routeLabel } from '../../lib/nav/routes'

/**
 * Go anywhere, by typing its name.
 *
 * The workbench has twenty-one pages, and reaching any of them meant finding
 * the right control: a nav link, a menu behind a wrench icon, a project
 * selector, a roster rail. That is the shape of a records system - every
 * destination has exactly one door, and you must know where the door is. A
 * person who already knows they want "Runner" or the PD-1 project should be
 * able to say so.
 *
 * Three deliberate limits:
 *
 * **It navigates; it does not act.** No "start a task", no "confirm draft".
 * Those spend money or change the record, and a fuzzy-matched list is the
 * wrong place to land on one by pressing Enter a moment too early. The palette
 * takes you to where the action is, with its own confirmation intact.
 *
 * **It indexes only what is already loaded.** Projects and the roster are
 * queries the shell holds anyway, so opening the palette issues no request and
 * cannot fail. A palette that fetched on open would be a loading spinner in
 * front of a search box.
 *
 * **The keyboard is a shortcut, not the only door.** Cmd/Ctrl-K opens it and a
 * visible button does too: a feature only reachable by an unlisted chord is a
 * feature most people never learn exists.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { t, language } = useI18n()
  const zh = language === 'zh'
  const { visibleProjects, projectId, setProjectId } = useProjectContext()
  const bots = useCopilotBots()
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'k' || !(event.metaKey || event.ctrlKey)) return
      event.preventDefault()
      setOpen((current) => !current)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const go = (to: string) => {
    setOpen(false)
    navigate(to)
  }

  const routes = useMemo(
    () => APP_ROUTES.map((route) => ({
      ...route,
      label: routeLabel(route.key, zh, (key) => t.nav[key]),
    })),
    [zh, t],
  )

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="command-palette-trigger"
        onClick={() => setOpen(true)}
        aria-label={zh ? '搜索与跳转' : 'Search and jump'}
      >
        <MagnifyingGlassIcon aria-hidden="true" />
        <span className="hidden lg:inline">{zh ? '跳转…' : 'Jump to…'}</span>
        <CommandShortcut className="hidden lg:inline">⌘K</CommandShortcut>
      </Button>

      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title={zh ? '跳转' : 'Jump to'}
        description={zh ? '搜索页面、项目与研究团队成员' : 'Search pages, projects and research team members'}
      >
        <CommandInput placeholder={zh ? '输入页面、项目或成员名称…' : 'Type a page, project or member…'} />
        <CommandList>
          <CommandEmpty>{zh ? '没有匹配项。' : 'Nothing matches.'}</CommandEmpty>

          <CommandGroup heading={zh ? '页面' : 'Pages'}>
            {routes.map((route) => (
              <CommandItem
                key={route.to}
                value={`${route.label} ${route.to}`}
                onSelect={() => go(`${route.to}${projectQuery}`)}
              >
                {route.label}
              </CommandItem>
            ))}
          </CommandGroup>

          {visibleProjects.length ? (
            <CommandGroup heading={zh ? '项目' : 'Projects'}>
              {visibleProjects.slice(0, 20).map((project) => (
                <CommandItem
                  key={project.id}
                  value={`${project.name} ${project.id}`}
                  onSelect={() => {
                    // Switching project is the one state change the palette
                    // makes, and it is the same one the top bar's selector
                    // makes - it changes what you are looking at, not the record.
                    setProjectId(project.id)
                    go(`/projects?project=${encodeURIComponent(project.id)}`)
                  }}
                >
                  {project.name}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}

          {bots.data?.length ? (
            <CommandGroup heading={zh ? '团队成员' : 'Team members'}>
              {bots.data.map((bot) => (
                <CommandItem
                  key={bot.id}
                  value={`${bot.title} ${bot.title_zh} ${bot.id}`}
                  onSelect={() => go(`/bots/${encodeURIComponent(bot.id)}${projectQuery}`)}
                >
                  {zh ? bot.title_zh : bot.title}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
        </CommandList>
      </CommandDialog>
    </>
  )
}
