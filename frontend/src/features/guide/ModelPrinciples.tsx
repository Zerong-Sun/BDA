import { ArrowRight, ArrowsOut } from '@phosphor-icons/react'
import { AppFrame } from '@/components/ui/AppFrame'
import alphaFold3Diagram from '../../assets/guide-models/alphafold3.png'
import proteinMpnnDiagram from '../../assets/guide-models/proteinmpnn.png'
import rfDiffusionDiagram from '../../assets/guide-models/rfdiffusion.png'
import { useI18n } from '../../lib/i18n'

export function ModelPrinciples() {
  const { t } = useI18n()
  const models = [
    {
      id: 'rfdiffusion',
      name: 'RFdiffusion',
      role: t.guide.models.rfdiffusion.role,
      summary: t.guide.models.rfdiffusion.summary,
      input: t.guide.models.rfdiffusion.input,
      mechanism: t.guide.models.rfdiffusion.mechanism,
      output: t.guide.models.rfdiffusion.output,
      image: rfDiffusionDiagram,
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
      image: proteinMpnnDiagram,
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
      image: alphaFold3Diagram,
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

            <figure className="bg-background">
              <a
                href={model.image}
                target="_blank"
                rel="noopener noreferrer"
                className="group relative block aspect-video focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
                aria-label={`${t.guide.models.enlarge}: ${model.name}`}
              >
                <img
                  src={model.image}
                  alt={model.alt}
                  className="h-full w-full object-contain"
                  loading="lazy"
                  decoding="async"
                />
                <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-border bg-background/90 px-2.5 py-1 text-xs font-medium text-foreground opacity-0 shadow-sm backdrop-blur transition-opacity motion-reduce:transition-none group-hover:opacity-100 group-focus-visible:opacity-100">
                  <ArrowsOut className="h-3.5 w-3.5" aria-hidden="true" />
                  {t.guide.models.enlarge}
                </span>
              </a>
              <figcaption className="sr-only">{model.alt}</figcaption>
            </figure>

            <div className="grid gap-4 border-t border-border-soft px-5 py-5 sm:grid-cols-[1fr_auto_1.35fr_auto_1fr] sm:items-start sm:px-7">
              <PrincipleStep label={t.guide.models.inputLabel} text={model.input} />
              <ArrowRight className="mt-6 hidden h-4 w-4 text-border-strong sm:block" aria-hidden="true" />
              <PrincipleStep label={t.guide.models.mechanismLabel} text={model.mechanism} emphasized />
              <ArrowRight className="mt-6 hidden h-4 w-4 text-border-strong sm:block" aria-hidden="true" />
              <PrincipleStep label={t.guide.models.outputLabel} text={model.output} />
            </div>
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
