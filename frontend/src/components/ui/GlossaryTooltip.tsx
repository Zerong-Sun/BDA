import { QuestionIcon } from '@phosphor-icons/react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip'

interface GlossaryTooltipProps {
  label: string
  description: string
  good?: string
}

export function GlossaryTooltip({ label, description, good }: GlossaryTooltipProps) {
  const tooltip = good ? `${description} ${good}` : description

  return (
    <TooltipProvider>
    <Tooltip>
      <span className="inline-flex min-w-0 items-center gap-1 align-middle">
      <span>{label}</span>
      <TooltipTrigger
        aria-label={`${label}: ${tooltip}`}
        className="inline-flex h-4 w-4 items-center justify-center text-muted-foreground hover:text-primary"
      >
        <QuestionIcon className="h-3.5 w-3.5" aria-hidden="true" />
      </TooltipTrigger>
      </span>
      <TooltipContent className="block w-64 p-3 text-left font-normal leading-relaxed">
        <span className="block text-text-secondary">{description}</span>
        {good ? <span className="mt-1 block text-accent">{good}</span> : null}
      </TooltipContent>
    </Tooltip>
    </TooltipProvider>
  )
}
