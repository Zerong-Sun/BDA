import type { FAQAccordionSectionData } from '../../components/ui/FAQAccordion'

export const GUIDE_FAQ_SECTIONS: FAQAccordionSectionData[] = [
  {
    id: 'workflow-fundamentals',
    label: 'Workflow fundamentals',
    title: 'Why the workflow is ordered this way',
    items: [
      {
        id: 'why-research-first',
        question: 'Why does research come first?',
        answer:
          'Every downstream decision — target selection, structure choice, design constraints — depends on evidence. Skipping research leads to wrong targets, inappropriate templates, and design goals that contradict published biology. The research review is the single source of truth for project conclusions.',
      },
      {
        id: 'why-target-mandatory',
        question: 'Why is target protein confirmation mandatory?',
        answer:
          'Ambiguous target identity causes cascading errors: wrong PDB templates, incorrect chain selection, and design goals applied to the wrong protein. Confirmation locks species, isoform, and construct boundaries before any structure or model work begins.',
      },
      {
        id: 'why-five-options',
        question: 'Why does the system give five target protein options?',
        answer:
          'Literature and database searches often surface multiple plausible targets (isoforms, orthologs, fusion constructs). Presenting up to five ranked options with evidence lets you make an informed choice rather than accepting a single agent guess.',
      },
      {
        id: 'why-clarifying-questions',
        question: 'Why do agents ask clarifying questions?',
        answer:
          'Protein design has many valid paths. Agents ask when constraints are ambiguous, when multiple PDB templates are equally suitable, or when design goals conflict. Answering these questions prevents expensive compute on the wrong configuration.',
      },
    ],
  },
  {
    id: 'structures',
    label: 'Structures',
    title: 'PDB download and structure preparation',
    items: [
      {
        id: 'how-pdb-download',
        question: 'How does PDB download work?',
        answer:
          'After target confirmation, Copilot searches RCSB PDB by protein name, gene, ligand, or complex. Results include PDB ID, experimental method, resolution, release date, and citation. You select a template and the system downloads mmCIF for preparation.',
      },
      {
        id: 'no-good-pdb',
        question: 'What happens if no good PDB exists?',
        answer:
          'The system flags the gap and may suggest AlphaFold-predicted structures as a fallback. AlphaFold models lack experimental binding data and may have lower confidence in loops. You must explicitly approve fallback use and understand the limitations.',
      },
      {
        id: 'alphafold-fallback',
        question: 'How does AlphaFold fallback work?',
        answer:
          'When no experimental structure is suitable, an AlphaFold prediction can serve as a design template. The preparation step flags low-confidence regions (pLDDT). Agents will note that predicted structures are not experimental evidence for binding or function.',
      },
    ],
  },
  {
    id: 'execution',
    label: 'Execution & results',
    title: 'Running models and interpreting output',
    items: [
      {
        id: 'interpret-scores',
        question: 'How should I interpret scores?',
        answer:
          'Scores are model-specific proxies — pLDDT, ipTM, ddG estimates, sequence heuristics — not experimental measurements. Use them to rank and prioritize candidates, not as proof of binding or function. Copilot explains each metric in context.',
      },
      {
        id: 'incomplete-results',
        question: 'What should I do when results are incomplete?',
        answer:
          'Check workflow node status for failed or skipped steps. Review job logs for API timeouts or model errors. Retry failed nodes or adjust parameters. If the workflow state is incomplete, do not export — resolve missing steps first.',
      },
      {
        id: 'workflow-state-saved',
        question: 'How is workflow state saved?',
        answer:
          'Project data, workflow graphs, artifacts, and job status persist in the BDA backend database. This guide is educational and separate from live project state. Your actual progress is visible on the Projects, Workflow, and Candidates pages.',
      },
    ],
  },
  {
    id: 'troubleshooting',
    label: 'Troubleshooting',
    title: 'When things go wrong',
    items: [
      {
        id: 'buttons-fail',
        question:
          'What should I do when buttons like Getting Started, Start, or Delete Project fail?',
        answer:
          'First verify the backend is running (port 8100). Check the settings drawer connection status. Refresh the page and retry. If the error persists, open the browser console for details and confirm your session has not expired (re-login if needed).',
      },
      {
        id: 'api-errors',
        question: 'How do I troubleshoot API errors?',
        answer:
          'API errors often indicate backend unavailability, authentication expiry, or request validation failures. Check the backend health banner, re-login if you see 401 errors, and verify Copilot API configuration in settings. For 4xx errors, the request payload may be invalid — review the workflow state.',
      },
      {
        id: 'schema-mismatch',
        question: 'What causes frontend/backend schema mismatch?',
        answer:
          'This usually happens when the frontend and backend versions are out of sync, or when workflow data was created with an older schema. Refresh both services to the same version. If scores or node metadata display incorrectly, report the specific page and field.',
      },
    ],
  },
]

const GUIDE_FAQ_SECTIONS_ZH: FAQAccordionSectionData[] = [
  {
    id: 'workflow-fundamentals',
    label: '工作流基础',
    title: '为什么工作流采用这个顺序',
    items: [
      { id: 'why-research-first', question: '为什么研究必须放在第一步？', answer: '靶点选择、结构模板和设计约束都依赖证据。跳过研究容易选择错误靶点或与已知生物学冲突的目标。项目综述是后续结论的统一依据。' },
      { id: 'why-target-mandatory', question: '为什么必须确认靶点蛋白？', answer: '含糊的靶点身份会造成错误的 PDB、链选择和设计目标。确认步骤会在结构和模型工作前锁定物种、亚型与构建边界。' },
      { id: 'why-five-options', question: '为什么系统会给出五个靶点选项？', answer: '文献与数据库常会返回多个合理的亚型、同源蛋白或融合构建。最多五个带证据的排序选项能让您做出判断，而不是接受单一代理猜测。' },
      { id: 'why-clarifying-questions', question: '为什么代理会提出澄清问题？', answer: '蛋白设计往往有多条有效路径。当约束含糊、模板同样适用或目标冲突时，代理会要求澄清，以免在错误配置上消耗计算资源。' },
    ],
  },
  {
    id: 'structures',
    label: '结构',
    title: 'PDB 下载与结构准备',
    items: [
      { id: 'how-pdb-download', question: 'PDB 下载如何工作？', answer: '靶点确认后，Copilot 按蛋白名称、基因、配体或复合物检索 RCSB PDB，并展示 PDB ID、实验方法、分辨率、发布日期和引用。您选择模板后，系统下载 mmCIF 供准备。' },
      { id: 'no-good-pdb', question: '没有合适的 PDB 怎么办？', answer: '系统会标记缺口，并可能建议 AlphaFold 预测结构。预测模型缺少实验结合证据，环区可信度也可能较低，因此必须明确批准并理解限制。' },
      { id: 'alphafold-fallback', question: 'AlphaFold 替代方案如何工作？', answer: '没有合适实验结构时，可使用 AlphaFold 预测作为设计模板。准备步骤会标记低可信区域，代理也会说明预测结构不能作为结合或功能的实验证据。' },
    ],
  },
  {
    id: 'execution',
    label: '执行与结果',
    title: '运行模型并解读输出',
    items: [
      { id: 'interpret-scores', question: '应该如何解读评分？', answer: 'pLDDT、ipTM、ddG 估计和序列启发式指标都是模型代理值，不是实验测量。它们适合排序和筛选，不能证明结合或功能。' },
      { id: 'incomplete-results', question: '结果不完整时应该怎么办？', answer: '检查工作流节点是否失败或被跳过，并查看日志中的超时和模型错误。重试失败节点或调整参数；工作流不完整时不要导出。' },
      { id: 'workflow-state-saved', question: '工作流状态如何保存？', answer: '项目、工作流图、制品与任务状态保存在 BDA 后端。Guide 仅用于教学，真实进度显示在项目、工作流和候选物页面。' },
    ],
  },
  {
    id: 'troubleshooting',
    label: '故障排查',
    title: '出现问题时如何处理',
    items: [
      { id: 'buttons-fail', question: '开始、删除等按钮无效时怎么办？', answer: '先确认 8100 端口的后端正在运行，并检查设置中的连接状态。刷新后重试；仍失败时检查浏览器控制台，并确认登录会话没有过期。' },
      { id: 'api-errors', question: '如何排查 API 错误？', answer: 'API 错误常来自后端不可用、认证过期或请求校验失败。检查健康提示，401 时重新登录，并在设置中核对 Copilot 配置。' },
      { id: 'schema-mismatch', question: '前后端模式不一致是什么原因？', answer: '通常是前后端版本不同，或工作流数据由旧模式创建。让两个服务使用相同版本；若评分或节点字段显示异常，请记录具体页面和字段。' },
    ],
  },
]

export function getGuideFaqSections(language: 'en' | 'zh'): FAQAccordionSectionData[] {
  return language === 'zh' ? GUIDE_FAQ_SECTIONS_ZH : GUIDE_FAQ_SECTIONS
}
