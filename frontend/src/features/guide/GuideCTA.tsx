import { Link } from 'react-router'
import { ArrowRight } from '@phosphor-icons/react'
import { AppFrame } from '@/components/ui/AppFrame'
import { Button } from '@/components/ui/Button'
import { useI18n } from '../../lib/i18n'

export function GuideCTA() {
  const { t } = useI18n()
  const isAuthenticated = Boolean(sessionStorage.getItem('bda_token'))

  return (
    <AppFrame
      className="guide-cta relative overflow-hidden"
      panelClassName="px-6 py-12 text-center md:px-12 md:py-16"
      aria-labelledby="guide-cta-heading"
    >
      <div className="guide-campus-mist pointer-events-none absolute inset-0 opacity-50" aria-hidden="true" />

      <div className="relative z-10 mx-auto max-w-2xl">
        <h2 id="guide-cta-heading" className="text-2xl font-bold text-text-primary sm:text-3xl">
          {t.guide.cta.title}
        </h2>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary sm:text-base">{t.guide.cta.body}</p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {isAuthenticated ? (
            <Button nativeButton={false} render={<Link to="/projects" />} className="gap-2">
              {t.guide.cta.startProject}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          ) : (
            <Button nativeButton={false} render={<Link to="/login" />} className="gap-2">
              {t.guide.cta.signIn}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          )}
          <Button nativeButton={false} render={<Link to="/login" />} variant="outline">{t.guide.cta.backToLogin}</Button>
        </div>
      </div>
    </AppFrame>
  )
}
