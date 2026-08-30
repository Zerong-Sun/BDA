const REVIEW_INTENT_PATTERNS = [
  /完善项目/,
  /研究综述/,
  /综述章节/,
  /写回.*review/i,
  /complete.*review/i,
  /research review/i,
  /review section/i,
  /project research review/i,
  /完善.*综述/,
]

export function detectReviewIntent(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return false
  return REVIEW_INTENT_PATTERNS.some((pattern) => pattern.test(trimmed))
}

export function isResearchPageContext(pageContext?: string): boolean {
  if (!pageContext) return false
  return pageContext.includes('route=/research')
}
