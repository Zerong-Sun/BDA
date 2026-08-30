/** Default LSF queue names; override via Vite env (see repo `.env.example`). */
export const DEFAULT_GPU_QUEUE =
  import.meta.env.VITE_LSF_DEFAULT_GPU_QUEUE?.trim() || 'gpu-bme-liz'

export const DEFAULT_CPU_QUEUE =
  import.meta.env.VITE_LSF_DEFAULT_CPU_QUEUE?.trim() || 'v3-64'
