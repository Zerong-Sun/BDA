import { FAQAccordion, FAQAccordionShell } from '../../components/ui/FAQAccordion'
import { useI18n } from '../../lib/i18n'
import { getGuideFaqSections } from './guideFAQData'

export function WorkflowFAQ() {
  const { t, language } = useI18n()

  return (
    <section className="guide-faq py-16 md:py-24" aria-labelledby="guide-faq-heading">
      <div className="mb-10 text-center">
        <span className="inline-flex rounded-full border border-accent-border bg-accent-bg px-3 py-1 font-mono text-fine font-semibold uppercase tracking-wider text-accent">
          {t.guide.faq.eyebrow}
        </span>
        <h2 id="guide-faq-heading" className="mt-3 text-2xl font-bold text-text-primary sm:text-3xl">
          {t.guide.faq.title}
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-text-secondary">{t.guide.faq.subtitle}</p>
      </div>

      <FAQAccordionShell>
        <FAQAccordion sections={getGuideFaqSections(language)} emptyMessage={t.guide.faq.empty} />
      </FAQAccordionShell>
    </section>
  )
}
