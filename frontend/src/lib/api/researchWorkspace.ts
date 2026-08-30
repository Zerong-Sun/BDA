import './generatedTransport'
import { getResearchWorkspaceApiV2ProjectsProjectIdResearchWorkspaceGet } from './generated/sdk.gen'
import type {
  LocalizedResearchText,
  ResearchWorkspaceResponse,
} from './generated/types.gen'
import { resolveStoredText } from '../i18n/localizedText'

export type ResearchLanguage = 'en' | 'zh'

export type NormalizedResearchWorkspace = ResearchWorkspaceResponse & {
  review_sections: NonNullable<ResearchWorkspaceResponse['review_sections']>
  graph_nodes: NonNullable<ResearchWorkspaceResponse['graph_nodes']>
  graph_edges: NonNullable<ResearchWorkspaceResponse['graph_edges']>
  references: NonNullable<ResearchWorkspaceResponse['references']>
  structures: NonNullable<ResearchWorkspaceResponse['structures']>
  research_targets: NonNullable<ResearchWorkspaceResponse['research_targets']>
  methods: NonNullable<ResearchWorkspaceResponse['methods']>
  datasets: NonNullable<ResearchWorkspaceResponse['datasets']>
  counts: NonNullable<ResearchWorkspaceResponse['counts']>
}

export function resolveWorkspaceText(value: LocalizedResearchText, language: ResearchLanguage) {
  const selected = value[language]?.trim()
  return {
    text: resolveStoredText(value, language),
    usedFallback: !selected,
  }
}

export function workspaceText(value: LocalizedResearchText, language: ResearchLanguage): string {
  return resolveWorkspaceText(value, language).text
}

export async function getResearchWorkspace(projectId: string): Promise<NormalizedResearchWorkspace> {
  const response = await getResearchWorkspaceApiV2ProjectsProjectIdResearchWorkspaceGet<true>({
    path: { project_id: projectId },
    throwOnError: true,
  })
  const data = response.data
  return {
    ...data,
    review_sections: data.review_sections ?? [],
    graph_nodes: data.graph_nodes ?? [],
    graph_edges: data.graph_edges ?? [],
    references: data.references ?? [],
    structures: data.structures ?? [],
    research_targets: data.research_targets ?? [],
    methods: data.methods ?? [],
    datasets: data.datasets ?? [],
    counts: data.counts ?? {},
  }
}
