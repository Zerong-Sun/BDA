type DebugFn = ((...args: unknown[]) => void) & {
  enabled: boolean
  extend: (namespace: string) => DebugFn
}

function createDebug(): DebugFn {
  const debug = (() => undefined) as DebugFn
  debug.enabled = false
  debug.extend = () => createDebug()
  return debug
}

const debugFactory = Object.assign(
  (namespace: string) => {
    void namespace
    return createDebug()
  },
  {
    coerce: (value: unknown) => value,
    disable: () => '',
    enable: (namespaces: string) => {
      void namespaces
      return undefined
    },
    enabled: (namespace: string) => {
      void namespace
      return false
    },
    formatArgs: (args: unknown[]) => {
      void args
      return undefined
    },
    humanize: (value: unknown) => String(value),
    log: (...args: unknown[]) => {
      void args
      return undefined
    },
  },
)

export default debugFactory
