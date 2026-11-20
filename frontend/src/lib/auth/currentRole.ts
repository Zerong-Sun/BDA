/** Display state only; the server derives the caller's role from the access token. */
export function currentRole(): string {
  try {
    const raw = sessionStorage.getItem('bda_user')
    const role = raw ? (JSON.parse(raw) as { role?: unknown }).role : undefined
    return typeof role === 'string' ? role : ''
  } catch {
    return ''
  }
}
