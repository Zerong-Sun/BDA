import type { ReactNode } from 'react'
import { AppFrame } from './AppFrame'

interface PageHeadProps {
  eyebrow: string
  title: string
  actions?: ReactNode
}

export function PageHead({ eyebrow, title, actions }: PageHeadProps) {
  return (
    <AppFrame className="mb-5" panelClassName="flex flex-wrap items-start justify-between gap-4 p-4">
      <div>
        <p className="font-mono text-fine font-medium uppercase tracking-wider text-text-muted">{eyebrow}</p>
        <h1 className="mt-1 text-page-title font-bold leading-tight text-text-primary">{title}</h1>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </AppFrame>
  )
}
