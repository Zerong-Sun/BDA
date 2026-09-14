import type { ReactNode } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './accordion'

// Stable references: Base UI treats a new `defaultValue` array on re-render as a
// changed default and warns, even when its contents are the same.
const OPEN = ['content']
const CLOSED: string[] = []

export function Disclosure({ title, children, className, defaultOpen = false }: {
  title: ReactNode
  children: ReactNode
  className?: string
  defaultOpen?: boolean
}) {
  return <Accordion className={className} defaultValue={defaultOpen ? OPEN : CLOSED}>
    <AccordionItem value="content" className="border-0">
      <AccordionTrigger>{title}</AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  </Accordion>
}
