import type { ReactNode } from 'react'

interface PageHeadProps {
  eyebrow: string
  title: string
  actions?: ReactNode
}

export function PageHead({ eyebrow, title, actions }: PageHeadProps) {
  return (
    <header className="science-page-header workspace-page-head">
      <div>
        <p className="science-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      {actions ? <div className="workspace-page-actions">{actions}</div> : null}
    </header>
  )
}
