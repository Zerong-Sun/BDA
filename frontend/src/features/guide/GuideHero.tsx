import { CaretDown } from '@phosphor-icons/react'
import { AppFrame } from '@/components/ui/AppFrame'
import { useI18n } from '../../lib/i18n'

export function GuideHero() {
  const { t } = useI18n()

  return (
    <header className="guide-hero relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden px-4 py-20 text-center">
      {/* Isometric world background */}
      <div className="guide-hero-world pointer-events-none absolute inset-0" aria-hidden="true">
        <div className="guide-hero-grid absolute inset-0" />
        <div className="guide-hero-mist absolute inset-0" />
        <div className="guide-hero-beam absolute left-1/4 top-1/3 h-px w-1/2 rotate-[-8deg] bg-gradient-to-r from-transparent via-accent to-transparent opacity-40" />
        <div className="guide-hero-beam absolute right-1/4 top-2/3 h-px w-1/3 rotate-[12deg] bg-gradient-to-r from-transparent via-danger to-transparent opacity-25" />
        {/* Miniature building silhouettes */}
        <div className="guide-hero-buildings absolute bottom-[15%] left-1/2 flex -translate-x-1/2 gap-6 opacity-30">
          {[40, 56, 32, 48, 36].map((h, i) => (
            <div
              key={i}
              className="w-8 rounded-t-sm bg-surface-2/40"
              style={{ height: `${h}px` }}
            />
          ))}
        </div>
      </div>

      <AppFrame className="relative z-10 mx-auto max-w-3xl" panelClassName="p-8 text-center sm:p-10">
        <span className="inline-flex rounded-full border border-accent-border bg-accent-bg px-4 py-1.5 font-mono text-fine font-semibold uppercase tracking-widest text-accent">
          {t.guide.hero.pill}
        </span>

        <h1 className="mt-6 text-3xl font-bold leading-tight tracking-tight text-text-primary sm:text-4xl md:text-5xl">
          {t.guide.hero.title}
        </h1>

        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-lg">
          {t.guide.hero.subtitle}
        </p>

        <p className="mt-3 text-caption text-text-muted">{t.guide.hero.disclaimer}</p>

        <div className="mt-10 flex flex-col items-center gap-2 motion-reduce:hidden">
          <span className="font-mono text-caption uppercase tracking-widest text-accent">{t.guide.hero.scrollPrompt}</span>
          <CaretDown className="h-5 w-5 animate-bounce text-accent motion-reduce:animate-none" aria-hidden="true" />
        </div>
      </AppFrame>
    </header>
  )
}
