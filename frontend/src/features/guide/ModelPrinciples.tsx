import { ArrowRight, ArrowSquareOut } from '@phosphor-icons/react'
import { AppFrame } from '@/components/ui/AppFrame'
import { useI18n } from '../../lib/i18n'

export function ModelPrinciples() {
  const { t, language } = useI18n()
  const models = [
    {
      id: 'rfdiffusion',
      name: 'RFdiffusion',
      role: t.guide.models.rfdiffusion.role,
      summary: t.guide.models.rfdiffusion.summary,
      input: t.guide.models.rfdiffusion.input,
      mechanism: t.guide.models.rfdiffusion.mechanism,
      output: t.guide.models.rfdiffusion.output,
      source: 'https://doi.org/10.1038/s41586-023-06415-8',
      reference: 'Watson et al., Nature (2023)',
      alt: t.guide.models.rfdiffusion.alt,
    },
    {
      id: 'proteinmpnn',
      name: 'ProteinMPNN',
      role: t.guide.models.proteinmpnn.role,
      summary: t.guide.models.proteinmpnn.summary,
      input: t.guide.models.proteinmpnn.input,
      mechanism: t.guide.models.proteinmpnn.mechanism,
      output: t.guide.models.proteinmpnn.output,
      source: 'https://doi.org/10.1126/science.add2187',
      reference: 'Dauparas et al., Science (2022)',
      alt: t.guide.models.proteinmpnn.alt,
    },
    {
      id: 'alphafold3',
      name: 'AlphaFold 3',
      role: t.guide.models.alphafold3.role,
      summary: t.guide.models.alphafold3.summary,
      input: t.guide.models.alphafold3.input,
      mechanism: t.guide.models.alphafold3.mechanism,
      output: t.guide.models.alphafold3.output,
      source: 'https://doi.org/10.1038/s41586-024-07487-w',
      reference: 'Abramson et al., Nature (2024)',
      alt: t.guide.models.alphafold3.alt,
    },
  ]

  return (
    <section className="guide-model-principles py-16 md:py-24" aria-labelledby="guide-model-principles-heading">
      <div className="mb-10 text-center">
        <span className="inline-flex rounded-full border border-accent-border bg-accent-bg px-3 py-1 font-mono text-fine font-semibold uppercase tracking-wider text-accent">
          {t.guide.models.eyebrow}
        </span>
        <h2 id="guide-model-principles-heading" className="mt-3 text-2xl font-bold text-text-primary sm:text-3xl">
          {t.guide.models.title}
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-text-secondary">
          {t.guide.models.subtitle}
        </p>
      </div>

      <div className="space-y-8">
        {models.map((model, index) => (
          <AppFrame
            key={model.id}
            className="guide-model-card overflow-hidden"
            panelClassName="p-0"
            aria-labelledby={`guide-model-${model.id}`}
          >
            <div className="flex flex-col gap-4 border-b border-border-soft px-5 py-5 sm:flex-row sm:items-start sm:justify-between sm:px-7">
              <div className="flex items-start gap-4">
                <span className="mt-0.5 font-mono text-sm font-semibold text-accent">0{index + 1}</span>
                <div>
                  <h3 id={`guide-model-${model.id}`} className="text-xl font-semibold text-text-primary">
                    {model.name}
                  </h3>
                  <p className="mt-1 font-mono text-xs uppercase tracking-wider text-accent">{model.role}</p>
                </div>
              </div>
              <p className="max-w-xl text-sm leading-relaxed text-text-secondary sm:text-right">{model.summary}</p>
            </div>

            <div className="grid gap-4 border-t border-border-soft px-5 py-5 sm:grid-cols-[1fr_auto_1.35fr_auto_1fr] sm:items-start sm:px-7">
              <PrincipleStep label={t.guide.models.inputLabel} text={model.input} />
              <ArrowRight className="mt-6 hidden h-4 w-4 text-border-strong sm:block" aria-hidden="true" />
              <PrincipleStep label={t.guide.models.mechanismLabel} text={model.mechanism} emphasized />
              <ArrowRight className="mt-6 hidden h-4 w-4 text-border-strong sm:block" aria-hidden="true" />
              <PrincipleStep label={t.guide.models.outputLabel} text={model.output} />
            </div>
            <p className="border-t border-border-soft px-5 py-3 text-xs text-text-secondary sm:px-7">
              {language === 'zh' ? '方法依据：' : 'Method reference: '}
              <a href={model.source} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-4">
                {model.reference}<ArrowSquareOut aria-hidden="true" />
              </a>
            </p>
          </AppFrame>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-sm text-text-secondary" aria-label={t.guide.models.chainLabel}>
        <span className="rounded-full border border-border-soft bg-surface-1 px-3 py-1.5">RFdiffusion</span>
        <ArrowRight className="h-4 w-4 text-accent" aria-hidden="true" />
        <span className="rounded-full border border-border-soft bg-surface-1 px-3 py-1.5">ProteinMPNN</span>
        <ArrowRight className="h-4 w-4 text-accent" aria-hidden="true" />
        <span className="rounded-full border border-border-soft bg-surface-1 px-3 py-1.5">AlphaFold 3</span>
        <span className="ml-1 text-text-muted">— {t.guide.models.chainCaption}</span>
      </div>
    </section>
  )
}

function PrincipleStep({
  label,
  text,
  emphasized = false,
}: {
  label: string
  text: string
  emphasized?: boolean
}) {
  return (
    <div className={emphasized ? 'rounded-xl bg-accent-bg/60 p-3 sm:-m-3' : undefined}>
      <p className="font-mono text-fine font-semibold uppercase tracking-wider text-accent">{label}</p>
      <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{text}</p>
    </div>
  )
}
