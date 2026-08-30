import { useMemo } from 'react'
import { AppFrame } from '@/components/ui/AppFrame'
import { FAQAccordion, FAQAccordionShell } from '../components/ui/FAQAccordion'
import { resolveFaqSections, type FAQSectionBundle } from '../lib/data/faqContent'
import { useI18n } from '../lib/i18n'

export function FAQPage() {
  const { t } = useI18n()

  const sections = useMemo(
    () => resolveFaqSections(t.faq?.sections as Record<string, FAQSectionBundle> | undefined),
    [t],
  )

  return (
    <div className="pb-10">
      <AppFrame
        className="mx-auto mb-8 max-w-2xl"
        heading={<h1>{t.faq.page.title}</h1>}
        description={t.faq.page.eyebrow}
        panelClassName="p-5 text-center"
      />

      <div data-tour-id="faq-content">
      <FAQAccordionShell>
        <FAQAccordion sections={sections} emptyMessage={t.faq.page.empty} />
      </FAQAccordionShell>
      </div>
    </div>
  )
}
