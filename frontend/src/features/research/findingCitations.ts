import { jsonArray, text } from './jsonHelpers'

export function findingCitationSources(evidence: Record<string, unknown>): string[] {
  return Array.from(new Set(
    [...jsonArray(evidence.sources), ...jsonArray(evidence.source_refs)]
      .map((source) => text(source).trim())
      .filter(Boolean),
  ))
}
