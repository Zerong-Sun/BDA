export type TourSectionId = 'projects' | 'research' | 'workflow' | 'candidates' | 'results' | 'copilot-settings' | 'faq'
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
        { title: 'Welcome to the interface tour', body: 'Explore demo is a read-only walkthrough of the product. Guide explains the scientific workflow; this tour teaches you where controls live and how to use them.' },
        { title: '欢迎使用界面导览', body: 'Explore Demo 是只读的产品操作教学。Guide 解释科研工作流，本导览帮助您认识控件位置和使用方式。' }),
      step('projects', 'project-selector', '/projects', 'project-selector', 'target-click',
        { title: 'Active project', body: 'Every page shares this project context. Open the selector to see the available projects.', interactionHint: 'Click the project selector to continue.' },
        { title: '当前项目', body: '所有页面共享这里的项目上下文。打开选择器可以查看可用项目。', interactionHint: '点击项目选择器继续。' }),
      step('projects', 'project-library', '/projects', 'project-library', 'button',
        { title: 'Project library', body: 'Search, filter, sort, open, and manage research projects here. Destructive actions are explained but never run by this tour.' },
        { title: '项目库', body: '在这里搜索、筛选、排序、打开和管理研究项目。导览只说明破坏性操作，不会实际执行。' }),
      step('projects', 'main-navigation', '/projects', 'main-navigation', 'button',
        { title: 'Main navigation', body: 'Research, Workflow, Candidates, Results, and FAQ form the complete product loop. Each has its own tour chapter.' },
        { title: '主导航', body: '研究、工作流、候选物、结果与 FAQ 组成完整产品闭环，每一部分都有独立导览章节。' }),
    ],
  },
  {
    id: 'research', route: '/research?tab=evidence',
    title: { en: 'Research workspace', zh: '研究工作区' },
    description: { en: 'Review evidence, references, structures, data, and methods.', zh: '查看证据、文献、结构、数据与方法。' },
    steps: [
      step('research', 'research-tabs', '/research?tab=evidence', 'research-tabs', 'target-click',
        { title: 'Five research views', body: 'The same project evidence is organized into five focused views.', interactionHint: 'Click any research tab to continue.' },
        { title: '五个研究视图', body: '同一项目的研究资料被整理为五个聚焦视图。', interactionHint: '点击任一研究标签继续。' }),
      step('research', 'research-workspace', '/research?tab=evidence', 'research-workspace', 'button',
        { title: 'Stored research content', body: 'Review claims and citations here. Switching language only uses text already stored in the library; missing translations remain in the original language.' },
        { title: '已存研究内容', body: '在这里审核声明和引用。切换语言只读取资料库已有文本，缺少译文时保留原文。' }),
      step('research', 'research-operations', '/research?tab=evidence', 'research-operations', 'target-click',
        { title: 'Research operations', body: 'Operational tools are grouped in collapsible areas so the evidence remains readable.', interactionHint: 'Expand this area to continue. Write actions will not be run.' },
        { title: '研究操作区', body: '操作工具集中在折叠区域，避免干扰证据阅读。', interactionHint: '展开此区域继续；导览不会执行写入操作。' }),
    ],
  },
  {
    id: 'workflow', route: '/workflow',
    title: { en: 'Workflow', zh: '工作流' },
    description: { en: 'Inspect the route, graph, resources, jobs, and node details.', zh: '查看路线、画布、资源、任务与节点详情。' },
    steps: [
      step('workflow', 'workflow-page', '/workflow', 'workflow-page', 'button',
        { title: 'Workflow workspace', body: 'Demo mode shows a read-only reference DAG. In application mode, target readiness gates editing and submission.' },
        { title: '工作流工作区', body: '演示模式展示只读参考 DAG；应用模式中，必须先满足靶点准备条件才能编辑和提交。' }),
      step('workflow', 'workflow-canvas', '/workflow', 'workflow-canvas', 'target-click',
        { title: 'Interactive DAG', body: 'Pan, zoom, and select nodes to understand dependencies and status.', interactionHint: 'Click the workflow canvas to continue.' },
        { title: '交互式 DAG', body: '可平移、缩放并选择节点，以理解依赖关系和状态。', interactionHint: '点击工作流画布继续。' }),
      step('workflow', 'workflow-inspector', '/workflow', 'workflow-inspector', 'button',
        { title: 'Resources and inspector', body: 'Artifacts and plugins appear beside the graph; selecting a node exposes parameters, status, and outputs. Submission is never triggered by the tour.' },
        { title: '资源与检查器', body: '制品和插件位于画布旁，选择节点后可查看参数、状态和输出。导览不会提交任务。' }),
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
