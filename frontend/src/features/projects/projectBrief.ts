import type { Project } from '../../lib/api/projects'
import { projectText } from '../../lib/i18n/projectText'

export interface ProjectBrief {
  objective: string
  questions: string[]
  deliverables: string[]
  source: 'public-package' | 'project'
}

/** Editorial presentation of the approved public package, not experimental data.
 * Source: pd1-demo-v1 / projects.PD1.project_review, objective and boundary sections.
 * Never apply this copy to private projects merely because their title contains PD1.
 */
export function projectBrief(project: Project, language: 'zh' | 'en'): ProjectBrief {
  const zh = language === 'zh'
  const prompt = project.prompt?.trim() ?? ''
  // Import initializes the prompt from the source summary. A later authored
  // prompt takes precedence over the editorial package fallback.
  const summaries = [project.summary, projectText(project, 'summary', 'en'), projectText(project, 'summary', 'zh')]
  const authoredPrompt = prompt && !summaries.some((summary) => summary?.trim() === prompt)
  if (!authoredPrompt && project.source_package_id === 'pd1-demo-v1' && project.source_project_key === 'PD1') {
    return {
      source: 'public-package',
      objective: zh
        ? '梳理 PD-1 的结合与调控证据，区分已知机制、推断与争议，形成可追溯的研究简报。'
        : 'Map the evidence for PD-1 binding and regulation, separating established mechanisms, inferences and open questions.',
      questions: zh ? [
        '哪些结构与文献支持 PD-1 的配体识别及抗体结合？',
        '糖基化和细胞背景如何影响对已有证据的解释？',
        '神经感觉相关结论有哪些冲突，哪些仍需验证？',
      ] : [
        'Which structures and sources support ligand recognition and antibody binding?',
        'How do glycosylation and cellular context affect interpretation?',
        'Where does the sensory-neuron evidence conflict or remain unverified?',
      ],
      deliverables: zh ? ['带来源的证据综述', '结构对照与可追溯引用', '待验证问题与决策记录']
        : ['Cited evidence brief', 'Structure comparison with provenance', 'Open questions and decision record'],
    }
  }
  return {
    source: 'project',
    objective: prompt || projectText(project, 'summary', language).trim(),
    questions: [],
    deliverables: [],
  }
}
