/** Display state only; the server independently enforces anonymous read access. */
export function isPublicVisitor(): boolean {
  if (sessionStorage.getItem('bda_token')) return false
  try { return JSON.parse(sessionStorage.getItem('bda_user') ?? '{}').public_visitor === true }
  catch { return false }
}
