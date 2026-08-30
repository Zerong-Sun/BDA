import { useNavigate } from 'react-router'
import { BookOpenIcon, LifebuoyIcon, QuestionIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from './dropdown-menu'

export function HelpMenu() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { projectId } = useProjectContext()
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t.pipeline.help}
        title={t.pipeline.help}
        className="inline-flex h-8 w-8 items-center justify-center border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <QuestionIcon className="h-4 w-4" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t.pipeline.help}</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => navigate(`/guide${projectQuery}`)}>
            <BookOpenIcon aria-hidden="true" />
            {t.pipeline.workflowGuide}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate(`/faq${projectQuery}`)}>
            <LifebuoyIcon aria-hidden="true" />
            {t.nav.faq}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
