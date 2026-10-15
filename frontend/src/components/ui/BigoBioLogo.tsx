import clsx from 'clsx'

/** Display the supplied wordmark without changing its source pixels. */
export function BigoBioLogo({ className }: { className?: string }) {
  return (
    <svg
      className={clsx('bigobio-logo', className)}
      viewBox="150 270 1470 445"
      role="img"
      aria-label="BigoBio"
      focusable="false"
    >
      <image href="/brand/bigobio-logo.png" width="1774" height="887" />
    </svg>
  )
}
