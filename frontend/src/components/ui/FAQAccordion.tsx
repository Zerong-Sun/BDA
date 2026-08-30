import { useState, type ReactNode } from 'react'
import type { FAQAccordionItemData, FAQAccordionSectionData } from '../../lib/data/faqContent'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './accordion'
import { AppFrame } from './AppFrame'
import { StatusBadge } from './statusBadge'
import { Button } from './Button'

export type { FAQAccordionItemData, FAQAccordionSectionData }

interface FAQAccordionProps {
  sections: FAQAccordionSectionData[]
  emptyMessage?: string
}

export function FAQAccordion({ sections, emptyMessage }: FAQAccordionProps) {
  const [openSectionIds, setOpenSectionIds] = useState<string[]>([])
  const [openItemIds, setOpenItemIds] = useState<string[]>([])

  if (!sections.length) {
    return (
      <AppFrame panelClassName="px-5 py-8 text-center">
        <p role="status" className="text-sm text-muted-foreground">
          {emptyMessage ?? 'No FAQ content is available yet.'}
        </p>
      </AppFrame>
    )
  }

  return (
    <Accordion
      multiple
      keepMounted
      value={openSectionIds}
      onValueChange={setOpenSectionIds}
      className="gap-3"
    >
      {sections.filter((section) => section.items.length > 0).map((section) => {
        const sectionOpen = openSectionIds.includes(section.id)
        return (
          <section key={section.id}>
            <AppFrame dense>
              <AccordionItem value={section.id} className="border-0">
                <AccordionTrigger
                  className="px-5 py-4 no-underline hover:no-underline"
                  onKeyDown={(event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return
                    event.preventDefault()
                    setOpenSectionIds((current) =>
                      current.includes(section.id)
                        ? current.filter((id) => id !== section.id)
                        : [...current, section.id],
                    )
                  }}
                >
                  <div className="min-w-0">
                    <StatusBadge status="info" label={section.label} />
                    <h2 className="mt-2 text-base font-semibold leading-snug text-foreground">
                      {section.title}
                    </h2>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="p-0" keepMounted>
                  <Accordion
                    multiple
                    value={openItemIds}
                    onValueChange={setOpenItemIds}
                    className="border-t"
                  >
                    {section.items.map((item) => {
                      const itemValue = `${section.id}:${item.id}`
                      return (
                        <AccordionItem
                          key={itemValue}
                          value={itemValue}
                          disabled={!sectionOpen}
                          className="px-4"
                        >
                          <AccordionTrigger
                            render={<Button type="button" disabled={!sectionOpen} />}
                            className="py-3.5 text-sm"
                            onKeyDown={(event) => {
                              if (event.key !== 'Enter' && event.key !== ' ') return
                              event.preventDefault()
                              setOpenItemIds((current) =>
                                current.includes(itemValue)
                                  ? current.filter((id) => id !== itemValue)
                                  : [...current, itemValue],
                              )
                            }}
                          >
                            {item.question}
                          </AccordionTrigger>
                          <AccordionContent className="pl-5 text-sm leading-relaxed text-muted-foreground">
                            {item.answer}
                          </AccordionContent>
                        </AccordionItem>
                      )
                    })}
                  </Accordion>
                </AccordionContent>
              </AccordionItem>
            </AppFrame>
          </section>
        )
      })}
    </Accordion>
  )
}

export function FAQAccordionShell({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-2xl">{children}</div>
}
