import type { ReactNode } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './accordion'

export function Disclosure({ title, children, className, defaultOpen = false }: {
  title: ReactNode
  children: ReactNode
  className?: string
  defaultOpen?: boolean
}) {
  return <Accordion className={className} defaultValue={defaultOpen ? ['content'] : []}>
    <AccordionItem value="content" className="border-0">
      <AccordionTrigger>{title}</AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  </Accordion>
}
