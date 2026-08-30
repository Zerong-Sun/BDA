import type { Project } from '../../lib/schemas/project'

const LEGACY_PD1_IDS = new Set(['proj_pd1_0423'])
const LEGACY_PD1_NAMES = new Set(['PD1Binder_validation_0423'])

export function isDemoProject(project: Project): boolean {
  return project.source_project_key?.toUpperCase() === 'PD1'
    || LEGACY_PD1_IDS.has(project.id)
    || LEGACY_PD1_NAMES.has(project.name)
}

export function findDemoProject(projects: Project[]): Project | undefined {
  return projects.find(isDemoProject)
}
