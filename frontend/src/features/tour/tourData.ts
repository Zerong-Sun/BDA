export type TourSectionId = 'projects' | 'research' | 'team' | 'workflow' | 'candidates' | 'lab' | 'results' | 'copilot-settings' | 'faq'
export type TourAdvanceMode = 'button' | 'target-click'
export type TourPreparation = 'copilot' | 'settings'

export interface TourCopy {
  title: string
  body: string
  interactionHint?: string
}

export interface TourAnchor {
  id: string
  selector: string
}

export interface TourStep {
  id: string
  sectionId: TourSectionId
  route: string
  anchor?: TourAnchor
  advance: TourAdvanceMode
  prepare?: TourPreparation
  copy: { en: TourCopy; zh: TourCopy }
}

export interface TourSection {
  id: TourSectionId
  route: string
  title: { en: string; zh: string }
  description: { en: string; zh: string }
  steps: TourStep[]
}

const step = (
  sectionId: TourSectionId,
  id: string,
  route: string,
  anchor: string | undefined,
  advance: TourAdvanceMode,
  en: TourCopy,
  zh: TourCopy,
  prepare?: TourPreparation,
): TourStep => ({
  id,
  sectionId,
  route,
  anchor: anchor ? { id: anchor, selector: `[data-tour-id="${anchor}"]` } : undefined,
  advance,
  prepare,
  copy: { en, zh },
})

export const TOUR_SECTIONS: TourSection[] = [
  {
    id: 'projects', route: '/projects',
    title: { en: 'Projects & navigation', zh: '项目与全局导航' },
    description: { en: 'Choose a project and learn the shared workspace controls.', zh: '选择项目并认识工作区的通用控件。' },
    steps: [
      step('projects', 'projects-welcome', '/projects', undefined, 'button',
        { title: 'Welcome to the interface tour', body: 'Learn the controls with the read-only demo. Follow the highlighted area, or choose Next. Pause whenever you like; your progress is saved.' },
        { title: '欢迎使用界面导览', body: '在只读演示项目中认识常用操作。跟随高亮区域，或点击“下一步”。可以随时暂停，进度会保留。' }),
      step('projects', 'project-selector', '/projects', 'project-selector', 'target-click',
        { title: 'Active project', body: 'The selected project follows you across pages.', interactionHint: 'Open the project list, then close it to continue.' },
        { title: '当前项目', body: '切换页面时，仍会保留当前项目。', interactionHint: '打开项目列表，关闭后继续导览。' }),
      step('projects', 'project-library', '/projects', 'project-library', 'button',
        { title: 'Project library', body: 'Find a project and open its brief. Start real work by creating a project in application mode.' },
        { title: '项目库', body: '找到项目，打开任务书。正式开始研究时，在应用模式中新建项目。' }),
      step('projects', 'main-navigation', '/projects', 'main-navigation', 'button',
        { title: 'Main navigation', body: 'Start with Research or Research team. Workbenches opens Workflow, Candidates, Lab and Results.' },
        { title: '主导航', body: '从“研究”或“研究团队”开始。“工作台”中可打开工作流、候选物、实验台和结果。' }),
    ],
  },
  {
    id: 'research', route: '/research?tab=evidence',
    title: { en: 'Research workspace', zh: '研究工作区' },
    description: { en: 'Review evidence, references, structures, data, and methods.', zh: '查看证据、文献、结构、数据与方法。' },
    steps: [
      step('research', 'research-tabs', '/research?tab=evidence', 'research-tabs', 'target-click',
        { title: 'Research views', body: 'Move between goals, evidence, plans and decisions.', interactionHint: 'Select a research tab to continue.' },
        { title: '研究视图', body: '在目标、文献证据、实验方案和决策记录之间切换。', interactionHint: '选择一个研究标签继续。' }),
      step('research', 'research-workspace', '/research?tab=evidence', 'research-workspace', 'button',
        { title: 'Stored research content', body: 'Read the evidence and open its sources. A missing translation stays in the original language.' },
        { title: '已存研究内容', body: '阅读证据并打开来源。资料没有译文时保留原文。' }),
      step('research', 'research-operations', '/research?tab=evidence', 'research-operations', 'target-click',
        { title: 'Research operations', body: 'Open the tools when you need to search or add evidence.', interactionHint: 'Expand this section. The tour will not run a search or save data.' },
        { title: '研究操作区', body: '需要检索或补充证据时，再展开相关工具。', interactionHint: '展开此区域；导览不会检索或保存数据。' }),
    ],
  },
  {
    id: 'team', route: '/bots',
    title: { en: 'Research team & decisions', zh: '研究团队与待办' },
    description: { en: 'Ask a Bot, inspect its work, and make decisions.', zh: '向 Bot 提问、查看交付物并作出决定。' },
    steps: [
      step('team', 'team-room', '/bots?view=chat', 'research-room', 'button',
        { title: 'Research room', body: 'Address a Bot with @. Messages, tasks and handoffs stay together here. The demo does not send messages.' },
        { title: '研究室', body: '用 @ 指定 Bot。消息、任务和交接记录集中在这里。演示模式不会发送消息。' }),
      step('team', 'team-tasks', '/bots?view=tasks', 'bot-workspace', 'button',
        { title: 'Tasks and deliverables', body: 'Choose an owner and review the task scope. Check the delivered evidence, missing inputs and next step.' },
        { title: '任务与交付物', body: '选择负责人并检查任务范围。完成后查看证据、缺失信息和下一步。' }),
      step('team', 'team-decisions', '/inbox', 'decision-inbox', 'button',
        { title: 'Needs your decision', body: 'Find tasks waiting for your input. Open each item to review and decide; Bots cannot confirm for you.' },
        { title: '待我决定', body: '这里汇总等待你处理的事项。打开原记录检查并决定，Bot 不会代你确认。' }),
    ],
  },
  {
    id: 'workflow', route: '/workflow',
    title: { en: 'Workflow', zh: '工作流' },
    description: { en: 'Inspect the route, graph, resources, jobs, and node details.', zh: '查看路线、画布、资源、任务与节点详情。' },
    steps: [
      step('workflow', 'workflow-page', '/workflow', 'workflow-page', 'button',
        { title: 'Workflow workspace', body: 'Build a plan from connected steps. Before a real run, prepare the target and review the inputs.' },
        { title: '工作流工作区', body: '把步骤连成计算方案。正式运行前，先准备靶点并检查输入。' }),
      step('workflow', 'workflow-canvas', '/workflow', 'workflow-canvas', 'target-click',
        { title: 'Connected steps', body: 'Each node is a step; lines show which step supplies the next input.', interactionHint: 'Select a node to inspect it.' },
        { title: '步骤与连线', body: '每个节点是一个步骤，连线表示下一步的输入来源。', interactionHint: '选择一个节点，查看详情。' }),
      step('workflow', 'workflow-inspector', '/workflow', 'workflow-inspector', 'button',
        { title: 'Step details', body: 'Check parameters, status and outputs here. For a real run, finish preflight, review the script, then confirm submission.' },
        { title: '步骤详情', body: '在这里查看参数、状态和输出。正式运行时，先通过预检、查看脚本，再确认提交。' }),
    ],
  },
  {
    id: 'candidates', route: '/candidates',
    title: { en: 'Candidates', zh: '候选物' },
    description: { en: 'Filter, compare, select, and inspect generated designs.', zh: '筛选、比较、选择并检查生成设计。' },
    steps: [
      step('candidates', 'candidate-funnel', '/candidates', 'candidate-funnel', 'button',
        { title: 'Candidate funnel', body: 'These counts show how many designs reached generation, design, folding, scoring, and ordering.' },
        { title: '候选物漏斗', body: '这些数量展示设计进入生成、设计、折叠、评分和订购阶段的情况。' }),
      step('candidates', 'candidate-filters', '/candidates', 'candidate-filters', 'target-click',
        { title: 'Filter candidates', body: 'Search by candidate and narrow by status or priority.', interactionHint: 'Click a filter control to continue.' },
        { title: '筛选候选物', body: '可按候选物搜索，并按状态或优先级缩小范围。', interactionHint: '点击任一筛选控件继续。' }),
      step('candidates', 'candidate-table', '/candidates', 'candidate-table', 'button',
        { title: 'Table and structure detail', body: 'Select rows to compare metrics and inspect structures. Export and download controls are explained but not activated.' },
        { title: '表格与结构详情', body: '选择数据行以比较指标和查看结构。导出和下载只作说明，不会自动触发。' }),
    ],
  },
  {
    id: 'lab', route: '/lab',
    title: { en: 'Lab', zh: '实验台' },
    description: { en: 'Connect constructs and measurements to the project.', zh: '把构建体和实验测量关联到项目。' },
    steps: [
      step('lab', 'lab-workspace', '/lab', 'lab-page', 'button',
        { title: 'Lab records', body: 'Inspect constructs, concentrations and instrument results. In application mode, preview an uploaded file before saving its analysis.' },
        { title: '实验记录', body: '查看构建体、浓度和仪器结果。正式分析文件时，先预览，再保存到项目。' }),
    ],
  },
  {
    id: 'results', route: '/results',
    title: { en: 'Results & delivery', zh: '结果与交付' },
    description: { en: 'Read validation evidence and understand delivery artifacts.', zh: '阅读验证证据并了解交付制品。' },
    steps: [
      step('results', 'results-metrics', '/results', 'results-metrics', 'button',
        { title: 'Outcome metrics', body: 'Summary metrics connect experimental results back to the candidate and workflow.' },
        { title: '结果指标', body: '汇总指标把实验结果与候选物和工作流连接起来。' }),
      step('results', 'results-validation', '/results', 'results-validation', 'button',
        { title: 'Validation evidence', body: 'Review pass/fail readouts and candidate-specific evidence here. Upload and AI interpretation are write/external actions and are not run.' },
        { title: '验证证据', body: '在这里审核通过/失败读数和候选物证据。上传与 AI 解读属于写入或外部操作，导览不会执行。' }),
      step('results', 'results-delivery', '/results', 'results-delivery', 'button',
        { title: 'Delivery package', body: 'The delivery panel collects traceable artifacts for handoff. Downloads remain user-initiated.' },
        { title: '交付包', body: '交付面板收集可追溯制品供交接使用，下载始终由用户主动发起。' }),
    ],
  },
  {
    id: 'copilot-settings', route: '/projects',
    title: { en: 'Copilot & settings', zh: 'Copilot 与设置' },
    description: { en: 'Learn assistant context, modes, appearance, and connections.', zh: '了解助手上下文、模式、外观与连接。' },
    steps: [
      step('copilot-settings', 'copilot-drawer', '/projects', 'copilot-drawer', 'button',
        { title: 'Project-aware Copilot', body: 'Copilot receives the current page and project context. You remain in control of any submission or external action.' },
        { title: '感知项目的 Copilot', body: 'Copilot 会获得当前页面和项目上下文，任何提交或外部操作仍由您控制。' }, 'copilot'),
      step('copilot-settings', 'settings-drawer', '/projects', 'settings-drawer', 'button',
        { title: 'Application settings', body: 'Switch operating mode, inspect connections, change appearance, configure Copilot, open Guide, or restart this tour.' },
        { title: '应用设置', body: '可切换运行模式、检查连接、调整外观、配置 Copilot、打开 Guide 或重新开始本导览。' }, 'settings'),
    ],
  },
  {
    id: 'faq', route: '/faq',
    title: { en: 'FAQ & next steps', zh: 'FAQ 与下一步' },
    description: { en: 'Find operational answers and continue to the scientific Guide.', zh: '查找操作答案并进入科研流程 Guide。' },
    steps: [
      step('faq', 'faq-content', '/faq', 'faq-content', 'target-click',
        { title: 'Operational FAQ', body: 'Open a section for setup, workflow, data, and troubleshooting answers.', interactionHint: 'Open an FAQ section to finish.' },
        { title: '操作 FAQ', body: '展开章节可查看设置、工作流、数据与故障排查答案。', interactionHint: '展开一个 FAQ 章节以完成导览。' }),
    ],
  },
]

export function getTourSection(sectionId: string): TourSection | undefined {
  return TOUR_SECTIONS.find((section) => section.id === sectionId)
}

export function getTourStep(sectionId: string, stepId: string): TourStep | undefined {
  return getTourSection(sectionId)?.steps.find((item) => item.id === stepId)
}

export function firstTourStep(sectionId: TourSectionId): TourStep {
  return getTourSection(sectionId)!.steps[0]
}

export function adjacentTourStep(sectionId: TourSectionId, stepId: string, direction: 1 | -1): TourStep | undefined {
  const steps = getTourSection(sectionId)?.steps ?? []
  const index = steps.findIndex((item) => item.id === stepId)
  return steps[index + direction]
}
