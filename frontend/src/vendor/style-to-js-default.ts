function camelCase(property: string): string {
  return property
    .trim()
    .replace(/^-ms-/, 'ms-')
    .replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase())
}

export default function styleToJS(style: string | null | undefined): Record<string, string> {
  if (!style) return {}
  const output: Record<string, string> = {}
  for (const declaration of style.split(';')) {
    const separator = declaration.indexOf(':')
    if (separator === -1) continue
    const property = declaration.slice(0, separator).trim()
    const value = declaration.slice(separator + 1).trim()
    if (!property || !value) continue
    output[camelCase(property)] = value
  }
  return output
}
