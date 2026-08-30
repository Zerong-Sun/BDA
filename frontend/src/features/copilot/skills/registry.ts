import type { CopilotSkill } from './types'

/**
 * Mirrors the canonical backend capability IDs returned by /copilot/skills.
 * Matching is only a routing hint; backend configuration and permissions are
 * authoritative.
 */
export const copilotSkills: CopilotSkill[] = [
  {
    name: 'literature-search',
    description: 'Search and ingest auditable Europe PMC literature',
    trigger: ['paper', 'literature', 'citation', 'PubMed', 'Europe PMC', '论文', '文献', '引用'],
    systemPrompt: 'Use saved scientific literature and preserve provenance.',
  },
  {
    name: 'research-gap-repair',
    description: 'Repair retrievable Research gaps',
    trigger: ['gap', 'gaps', '缺口', '补齐', '修复'],
    systemPrompt: 'Repair only automatable gaps for exact Research target IDs.',
  },
  {
    name: 'target-intelligence',
    description: 'Run or explain target intelligence',
    trigger: ['target intelligence', 'target profile', '靶点情报', '靶点档案'],
    systemPrompt: 'Use exact project Target IDs and report queued work as pending.',
  },
  {
    name: 'compute-drafting',
    description: 'Create reviewable compute drafts',
    trigger: ['LSF', 'compute draft', 'cluster job', '计算草稿', '集群作业', '任务草稿'],
    systemPrompt: 'Create drafts only; never confirm or submit compute.',
  },
  {
    name: 'workflow-planning',
    description: 'Plan routes and inspect workflow state',
    trigger: ['workflow', 'route', 'threshold', '工作流', '路线', '阈值'],
    systemPrompt: 'Inspect and plan workflows without silently applying or submitting them.',
  },
  {
    name: 'result-interpretation',
    description: 'Interpret recorded candidate and experiment results',
    trigger: ['BLI', 'SEC', 'experiment', 'result', 'assay', '实验', '结果', '测定'],
    systemPrompt: 'Interpret recorded results without inventing measurements.',
  },
  {
    name: 'knowledge-authoring',
    description: 'Search knowledge and create pending-review notes',
    trigger: ['knowledge', 'note', 'save this', '知识', '笔记', '保存'],
    systemPrompt: 'Treat Copilot-authored notes as pending review.',
  },
  {
    name: 'research-read',
    description: 'Read Research workspace evidence and datasets',
    trigger: ['research', 'dataset', 'reference', '研究', '数据集', '参考文献'],
    systemPrompt: 'Use only canonical Research workspace evidence.',
  },
  {
    name: 'project-read',
    description: 'Read project targets, candidates, workflows, compute, and experiments',
    trigger: [
      'candidate',
      'rank',
      'protein',
      'peptide',
      'binder',
      'structure',
      'PDB',
      'AlphaFold',
      'Rosetta',
      '候选',
      '排序',
      '蛋白',
      '多肽',
      '结合蛋白',
      '结构',
    ],
    systemPrompt: 'Read current-project operational data before answering.',
  },
]

export function matchSkill(input: string): CopilotSkill | undefined {
  const lower = input.toLowerCase()
  const matches = copilotSkills.filter((skill) =>
    skill.trigger.some((token) => lower.includes(token.toLowerCase())),
  )
  const focused = matches.filter(
    (skill) => !['project-read', 'research-read'].includes(skill.name),
  )
  if (focused.length > 0) {
    return focused.length === 1 ? focused[0] : undefined
  }
  return matches.length === 1 ? matches[0] : undefined
}
