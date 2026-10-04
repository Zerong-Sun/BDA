import { defaultWorkflowEdges, defaultWorkflowNodes, type BdaWorkflowNode } from './workflowTypes'

export interface DemoWorkflowStep {
  node: BdaWorkflowNode
  inputs: string
  outputs: string
  checks: string
}

type StepCopy = { label: string; description: string; inputs: string; outputs: string; checks: string }
const copy: Record<string, { en: StepCopy; zh: StepCopy }> = {
  target: {
    en: { label: 'Target protein', description: 'Prepare the target before choosing a design route.', inputs: 'Target identity, sequence and source structure.', outputs: 'A reviewed target structure and design region.', checks: 'Confirm species, chain, residue numbering and structure provenance.' },
    zh: { label: '靶标蛋白', description: '先准备靶标，再选择设计路线。', inputs: '靶标身份、序列和来源结构。', outputs: '经过审核的靶标结构与设计区域。', checks: '确认物种、链、残基编号和结构来源。' },
  },
  requirements: {
    en: { label: 'Task requirements', description: 'Define a testable objective and acceptance criteria.', inputs: 'Research question, evidence and experimental constraints.', outputs: 'An objective with measurable checks and a resource budget.', checks: 'Separate desired properties from verified results.' },
    zh: { label: '任务要求', description: '明确可验证的目标与验收标准。', inputs: '研究问题、证据与实验约束。', outputs: '包含可测检查项和资源预算的目标。', checks: '区分期望性质与已经验证的结果。' },
  },
  rfdiffusion: {
    en: { label: 'Backbone generation', description: 'Use RFdiffusion to propose binder backbones.', inputs: 'Prepared target and reviewed geometry constraints.', outputs: 'Candidate backbones with recorded generation settings.', checks: 'Inspect geometry, target contacts and clashes before sequence design.' },
    zh: { label: '主链生成', description: '使用 RFdiffusion 提出结合蛋白主链。', inputs: '准备好的靶标与审核后的几何约束。', outputs: '候选主链及其生成配置。', checks: '序列设计前检查几何、靶标接触和碰撞。' },
  },
  mpnn: {
    en: { label: 'Sequence design', description: 'Use ProteinMPNN to design sequences for candidate backbones.', inputs: 'Candidate backbone structures and fixed-residue constraints.', outputs: 'Sequences linked to their source backbones.', checks: 'Review sequence diversity and fixed positions; scores do not establish binding.' },
    zh: { label: '序列设计', description: '使用 ProteinMPNN 为候选主链设计序列。', inputs: '候选主链结构与固定残基约束。', outputs: '关联来源主链的序列。', checks: '检查序列多样性与固定位置；评分不能证明结合。' },
  },
  af2: {
    en: { label: 'Fold prediction', description: 'Predict structures and inspect confidence.', inputs: 'Candidate sequences and the target context required by the selected model.', outputs: 'Predicted structures and model confidence metrics.', checks: 'Review interface geometry and uncertainty; prediction is not experimental validation.' },
    zh: { label: '折叠预测', description: '预测结构并检查置信度。', inputs: '候选序列及所选模型需要的靶标上下文。', outputs: '预测结构与模型置信度指标。', checks: '检查界面几何与不确定性；预测不等于实验验证。' },
  },
  rosetta: {
    en: { label: 'Rosetta scoring', description: 'Relax structures and compare interface scores.', inputs: 'Predicted complexes and a declared scoring protocol.', outputs: 'Scores linked to each structure and protocol.', checks: 'Compare scores only under compatible settings; energy scores are not measured affinity.' },
    zh: { label: 'Rosetta 评分', description: '优化结构并比较界面评分。', inputs: '预测复合物与明确的评分方案。', outputs: '关联结构和方案的评分。', checks: '只比较设置相容的评分；能量评分不是实测亲和力。' },
  },
  filters: {
    en: { label: 'Candidate selection', description: 'Review evidence against the declared criteria.', inputs: 'Candidate structures, sequences, metrics and uncertainty.', outputs: 'A shortlist with explicit reasons and missing evidence.', checks: 'Keep missing measurements distinct from failed thresholds.' },
    zh: { label: '候选物筛选', description: '按既定标准审查候选物证据。', inputs: '候选结构、序列、指标与不确定性。', outputs: '附有入选理由和证据缺口的名单。', checks: '区分缺失测量与未达到阈值。' },
  },
  wetlab: {
    en: { label: 'Wet-lab validation', description: 'Test selected candidates and record experimental evidence.', inputs: 'Selected constructs, controls and an assay protocol.', outputs: 'Measurements linked to samples, conditions and raw files.', checks: 'Review controls and replicates, then decide whether to revise the next design cycle.' },
    zh: { label: '湿实验验证', description: '测试入选候选物并记录实验证据。', inputs: '入选构建体、对照与实验方案。', outputs: '关联样本、条件和原始文件的测量。', checks: '审核对照与重复实验，再决定是否调整下一轮设计。' },
  },
}

export function getDemoWorkflow(language: 'en' | 'zh') {
  const steps: DemoWorkflowStep[] = defaultWorkflowNodes.map(node => {
    const text = copy[node.id][language]
    return { ...text, node: { ...node, data: { ...node.data,
      label: text.label, description: text.description, status: 'demo',
      footer: language === 'zh' ? '步骤示例 · 未执行' : 'Example step · not executed',
    } } }
  })
  return {
    steps,
    nodes: steps.map(step => step.node),
    edges: defaultWorkflowEdges.map(edge => ({ ...edge, animated: false,
      label: edge.label ? language === 'zh' ? '审核后调整目标' : 'Revise after review' : undefined,
    })),
  }
}
