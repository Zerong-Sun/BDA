export function interpolate(template: string, vars: Record<string, string | number | undefined | null>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = vars[key]
    return value === undefined || value === null ? `{${key}}` : String(value)
  })
}
