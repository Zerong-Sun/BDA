import type { FAQAccordionSectionData } from '../../components/ui/FAQAccordion'

export const GUIDE_FAQ_SECTIONS: FAQAccordionSectionData[] = [
  {
    id: "workflow-fundamentals",
    label: "Workflow fundamentals",
    title: "Planning the work",
    items: [
      {
        id: "why-research-first",
        question: "Why gather evidence first?",
        answer: "Sources help you choose a target, inputs and evaluation criteria. Save supporting references and keep unresolved claims visible.",
      },
      {
        id: "why-target-mandatory",
        question: "Why confirm the target?",
        answer: "Check species, isoform, chains and residue ranges so the selected sequence or structure matches the question. Confirmation does not guarantee that the structure is suitable.",
      },
      {
        id: "why-five-options",
        question: "How do I choose between target options?",
        answer: "Compare database identifiers, species, constructs and source evidence. The number of options depends on the available records; resolve ambiguity before using an input.",
      },
      {
        id: "why-clarifying-questions",
        question: "Why does a bot ask for more information?",
        answer: "A plan needs a clear goal, inputs, constraints and success criteria. Answer the missing details or record them as open questions before committing compute.",
      },
    ],
  },
  {
    id: "structures",
    label: "Structures",
    title: "Choosing and preparing structures",
    items: [
      {
        id: "how-pdb-download",
        question: "How do I import a structure?",
        answer: "Search available PDB records, inspect the metadata and choose an entry to import. You can also upload an existing PDB/mmCIF file. Check the resulting artifact and retain its source.",
      },
      {
        id: "no-good-pdb",
        question: "What if no suitable PDB structure exists?",
        answer: "Check other structures or import a prediction with its source and confidence information. Decide whether its coverage and uncertainty are acceptable for the planned calculation.",
      },
      {
        id: "alphafold-fallback",
        question: "What should I check in a predicted structure?",
        answer: "Keep it labelled as predicted. Inspect chains, numbering, missing regions and available confidence metrics. Preparation does not automatically rebuild missing loops or validate binding.",
      },
    ],
  },
  {
    id: "execution",
    label: "Execution & results",
    title: "Running and reviewing work",
    items: [
      {
        id: "interpret-scores",
        question: "How should I interpret scores?",
        answer: "Check the metric, units, method and conditions. Structural confidence and energy scores are computational evidence, not experimental proof. Missing values are not zero.",
      },
      {
        id: "incomplete-results",
        question: "What should I do with incomplete results?",
        answer: "Check task status, errors and collected files. Correct the cause and use an available retry action or create a new workflow for a changed plan. You can export available files while clearly recording missing or failed steps.",
      },
      {
        id: "workflow-state-saved",
        question: "When is a workflow saved?",
        answer: "Workflow edits remain local until you save the draft. Check the saved status before leaving. Submitted runs keep their snapshots; this guide does not display live project progress.",
      },
    ],
  },
  {
    id: "troubleshooting",
    label: "Troubleshooting",
    title: "Resolving common problems",
    items: [
      {
        id: "buttons-fail",
        question: "What if a button is unavailable or an action fails?",
        answer: "Check the displayed reason, selected project and permissions. After a timeout, inspect the task list before submitting again. Sign in again if the session expired.",
      },
      {
        id: "api-errors",
        question: "How do I report an API error?",
        answer: "Record the page, action, error message and task ID. A 401 usually needs a new login; input errors need correction. Ask an administrator to check service availability when requests keep failing.",
      },
      {
        id: "schema-mismatch",
        question: "What if data display incorrectly?",
        answer: "Refresh once and check the selected project. If the problem remains, report the page and affected fields so an administrator can compare frontend and API versions. Preserve the original data.",
      },
    ],
  },
]

const GUIDE_FAQ_SECTIONS_ZH: FAQAccordionSectionData[] = [
  {
    id: "workflow-fundamentals",
    label: "工作流基础",
    title: "规划研究工作",
    items: [
      {
        id: "why-research-first",
        question: "为什么先收集证据？",
        answer: "来源有助于选择靶点、输入和评价标准。保存支持文献，并保留尚未确定的结论。",
      },
      {
        id: "why-target-mandatory",
        question: "为什么要确认靶点？",
        answer: "核对物种、亚型、链和残基范围，确保序列或结构对应研究问题。确认身份后仍需检查结构是否适用。",
      },
      {
        id: "why-five-options",
        question: "如何选择候选靶点？",
        answer: "比较数据库标识、物种、构建范围和来源证据。选项数量取决于可用记录；使用输入前先解决身份歧义。",
      },
      {
        id: "why-clarifying-questions",
        question: "Bot 为什么需要补充信息？",
        answer: "方案需要明确目标、输入、约束和成功标准。投入计算前，补充缺失信息或明确记录待解决问题。",
      },
    ],
  },
  {
    id: "structures",
    label: "结构",
    title: "选择和准备结构",
    items: [
      {
        id: "how-pdb-download",
        question: "如何导入结构？",
        answer: "检索可用 PDB 记录，查看元数据后选择条目导入。也可上传已有 PDB/mmCIF 文件。导入后核对制品并保留来源。",
      },
      {
        id: "no-good-pdb",
        question: "没有合适的 PDB 结构怎么办？",
        answer: "检查其他结构，或导入带来源和置信信息的预测结构。判断覆盖范围和不确定性是否适合计划中的计算。",
      },
      {
        id: "alphafold-fallback",
        question: "使用预测结构时要检查什么？",
        answer: "保留预测标识，检查链、编号、缺失区域和可用置信指标。结构准备不会自动补建缺失环区，也不会验证结合能力。",
      },
    ],
  },
  {
    id: "execution",
    label: "执行与结果",
    title: "运行和审阅任务",
    items: [
      {
        id: "interpret-scores",
        question: "应该如何解读评分？",
        answer: "核对指标、单位、方法和条件。结构置信度与能量评分属于计算证据，不能代替实验验证；缺失值不等于零。",
      },
      {
        id: "incomplete-results",
        question: "结果不完整时应该怎么办？",
        answer: "查看任务状态、错误和已收集文件。修正原因后使用可用的重试入口；方案改变时新建工作流。可以导出已有文件，但需注明缺失或失败步骤。",
      },
      {
        id: "workflow-state-saved",
        question: "工作流什么时候保存？",
        answer: "工作流编辑需要保存草稿后才写入后端。离开前检查保存状态。已提交运行保留快照；本指南不显示项目实时进度。",
      },
    ],
  },
  {
    id: "troubleshooting",
    label: "故障排查",
    title: "处理常见问题",
    items: [
      {
        id: "buttons-fail",
        question: "按钮不可用或操作失败怎么办？",
        answer: "查看页面提示、所选项目和权限。超时后先检查任务列表，避免重复提交；会话过期时重新登录。",
      },
      {
        id: "api-errors",
        question: "如何反馈 API 错误？",
        answer: "记录页面、操作、错误信息和任务标识。401 通常需要重新登录；输入错误需要修正。请求持续失败时，请管理员检查服务状态。",
      },
      {
        id: "schema-mismatch",
        question: "数据显示异常怎么办？",
        answer: "刷新一次并确认所选项目。仍有问题时，记录页面和异常字段，由管理员核对前后端版本；保留原始数据。",
      },
    ],
  },
]

export function getGuideFaqSections(language: 'en' | 'zh'): FAQAccordionSectionData[] {
  return language === 'zh' ? GUIDE_FAQ_SECTIONS_ZH : GUIDE_FAQ_SECTIONS
}
