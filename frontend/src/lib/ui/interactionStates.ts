/** Shared interaction state class fragments for consistent hover/active/selected styling. */
export const interactionStates = {
  hoverSurface: 'hover:bg-surface-2',
  selectedRing: 'ring-2 ring-accent ring-offset-1 ring-offset-bg-canvas',
  disabled: 'disabled:cursor-not-allowed disabled:opacity-50',
  loading: 'animate-pulse',
  empty: 'text-text-muted',
  error: 'text-danger',
} as const
