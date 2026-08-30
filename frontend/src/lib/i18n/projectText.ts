import type { Project } from '../schemas/project'
import { resolveStoredText } from './localizedText'

export function projectText(project: Project, key: 'name' | 'summary', language: 'en' | 'zh'): string {
  const value = project.localized_content?.[key]
  return resolveStoredText(value, language, key === 'name' ? project.name : project.summary ?? '')
}
