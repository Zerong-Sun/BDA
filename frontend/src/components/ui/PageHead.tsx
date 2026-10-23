import type { ReactNode } from 'react'

interface PageHeadProps {
  eyebrow: string
  title: string
  actions?: ReactNode
}

export function PageHead({ title, actions }: PageHeadProps) {
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
      <h1 className="min-w-0 text-page-title font-bold leading-tight text-text-primary">{title}</h1>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  )
}
