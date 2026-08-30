export function getThemeColor(varName: string): string {
  const name = varName.startsWith('--') ? varName : `--${varName}`
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
