import type { Icon } from '@phosphor-icons/react'
import {
  ChartBar,
  BookOpen,
  Cube,
  ClipboardText,
  Cpu,
  Crosshair,
  Database,
  Flask,
  Package,
  SlidersHorizontal,
  Sparkle,
} from '@phosphor-icons/react'

export interface WorkflowStationData {
  id: string
  stepNumber: number
  title: string
  stationLabel: string
  beginnerExplanation: string
  technicalDetail: string
  inputs: string[]
  outputs: string[]
  commonFailures: string[]
  userDecisions: string[]
  icon: Icon
}

export const GUIDE_WORKFLOW_STATIONS: WorkflowStationData[] = [
  {
    id: 'research',
    stepNumber: 1,
    title: 'Research & Literature Review',
    stationLabel: 'Knowledge Center',
    beginnerExplanation:
      'Before designing anything, agents help you survey published work on your target, methods, and prior design attempts. This builds a shared evidence base for every later decision.',
    technicalDetail:
      'Copilot queries Europe PMC, RCSB PDB, UniProt, and Reactome. Findings are summarized with citations and evidence grades. Accepted claims can flow into the project research review as structured findings.',
    inputs: ['Research question or target name', 'Optional seed papers or PDB IDs', 'Project type and design objective'],
    outputs: [
      'Literature summary with DOI/PMID references',
      'Mechanism and pathway context',
      'Method landscape and design precedents',
      'Risk flags and open questions',
    ],
    commonFailures: [
      'Incomplete literature review — key papers missed',
      'Missing citations for agent-generated claims',
      'Unsupported agent claims accepted without evidence',
      'Confusing computational predictions with experimental validation',
    ],
    userDecisions: [
      'Approve which findings enter the project research review',
      'Flag uncertain or contradictory evidence for follow-up',
    ],
    icon: BookOpen,
  },
  {
    id: 'target-confirmation',
    stepNumber: 2,
    title: 'Target Protein Confirmation',
    stationLabel: 'Target Selection Console',
    beginnerExplanation:
      'The system proposes up to five candidate target proteins based on your research. You must confirm the correct species, isoform, and construct boundaries before any structure work begins.',
    technicalDetail:
      'Target intelligence intake resolves UniProt accessions, gene symbols, reviewed status, and functional annotations. Evidence cards link each recommendation to literature or database sources.',
    inputs: ['Research review conclusions', 'Target name, gene, or UniProt ID', 'Species and construct preferences'],
    outputs: [
      'Ranked target options (up to five)',
      'Per-target evidence cards',
      'Confirmed target identity for downstream steps',
    ],
    commonFailures: [
      'Unclear target protein — ambiguous gene name or species',
      'Wrong target protein selected',
      'Isoform or construct boundary mismatch',
      'Ignoring reviewed vs. unreviewed UniProt status',
    ],
    userDecisions: [
      'Select one target from the proposed options',
      'Confirm species, isoform, and construct range',
    ],
    icon: Crosshair,
  },
  {
    id: 'pdb-download',
    stepNumber: 3,
    title: 'PDB / Structure Download',
    stationLabel: 'Structure Archive Gateway',
    beginnerExplanation:
      'Once the target is confirmed, agents search RCSB PDB for experimental structures. You receive recommended templates with resolution, method, and binding-state metadata.',
    technicalDetail:
      'PDB search returns entry IDs, experimental method, resolution, release date, and primary citation. Download links provide mmCIF files. Results are ranked for suitability to your design route.',
    inputs: ['Confirmed target identity', 'Optional ligand or complex constraints', 'Preferred experimental method filters'],
    outputs: [
      'Ranked PDB entry list',
      'Structure metadata and download links',
      'Template recommendation with rationale',
    ],
    commonFailures: [
      'No suitable PDB structure found for the target',
      'AlphaFold fallback used instead of experimental PDB without review',
      'Selecting a structure from the wrong species or construct',
      'Ignoring ligand or cofactor context in the template',
    ],
    userDecisions: [
      'Choose a PDB template or approve AlphaFold fallback',
      'Confirm chain selection and binding state',
    ],
    icon: Database,
  },
  {
    id: 'structure-cleaning',
    stepNumber: 4,
    title: 'Structure Cleaning & Preparation',
    stationLabel: 'Molecular Prep Lab',
    beginnerExplanation:
      'Raw structures often contain missing residues, unresolved loops, alternate conformations, or unwanted chains. This step prepares a clean, design-ready structure file.',
    technicalDetail:
      'Preparation includes chain selection, ligand/cofactor handling, missing-residue flagging, loop identification, and format normalization to mmCIF/PDB. Agents surface issues before models run.',
    inputs: ['Selected PDB or AlphaFold structure', 'Chain and ligand selection', 'Construct boundaries'],
    outputs: [
      'Cleaned structure artifact',
      'Preparation report (missing residues, loops, warnings)',
      'Design-ready mmCIF/PDB file',
    ],
    commonFailures: [
      'Missing residues not flagged before design',
      'Unresolved loops ignored in the template',
      'Wrong chain selected for the design target',
      'Ligand or cofactor removed when required for binding context',
    ],
    userDecisions: [
      'Approve chain and ligand handling',
      'Accept or reject structures with unresolved regions',
    ],
    icon: Flask,
  },
  {
    id: 'design-goal',
    stepNumber: 5,
    title: 'Design Goal Selection',
    stationLabel: 'Decision Control Room',
    beginnerExplanation:
      'Define what success looks like: binder affinity, stability, specificity, expression, or a combination. Agents translate your goal into measurable constraints for the workflow.',
    technicalDetail:
      'Design goals map to project type templates (binder design, enzyme design, sweet protein, scaffold redesign). Constraints feed route planning and model parameter selection.',
    inputs: ['Project type', 'Research review constraints', 'Cleaned structure artifact'],
    outputs: [
      'Structured design objective',
      'Scoring priorities and acceptance thresholds',
      'Route constraints for agent planning',
    ],
    commonFailures: [
      'Vague or conflicting design objectives',
      'Goals that cannot be scored by available models',
      'Constraints that contradict the chosen template structure',
    ],
    userDecisions: [
      'Confirm design objective and priority metrics',
      'Set acceptance thresholds where applicable',
    ],
    icon: SlidersHorizontal,
  },
  {
    id: 'agent-planning',
    stepNumber: 6,
    title: 'Agent Planning',
    stationLabel: 'Planning Board / Command Center',
    beginnerExplanation:
      'Agents propose a visual workflow DAG: which models run, in what order, and with what parameters. You review and adjust the plan before any compute is submitted.',
    technicalDetail:
      'Route planning uses the model plugin registry (RFdiffusion, ProteinMPNN, AlphaFold2, Rosetta, etc.). The DAG is acyclic; cross-round loops are handled by Campaign, not workflow edges.',
    inputs: ['Design goal and constraints', 'Cleaned structure', 'Available model plugins'],
    outputs: [
      'Proposed workflow DAG',
      'Per-node parameters and rationale',
      'Estimated compute requirements',
    ],
    commonFailures: [
      'Incomplete workflow state — nodes added without required inputs',
      'Parameter patch does not match model registry schema',
      'Agents ask clarifying questions that remain unanswered',
    ],
    userDecisions: [
      'Approve, edit, or reject the proposed workflow',
      'Answer agent clarifying questions',
      'Confirm model parameters before submission',
    ],
    icon: ClipboardText,
  },
  {
    id: 'model-execution',
    stepNumber: 7,
    title: 'Model Execution',
    stationLabel: 'Compute Facility',
    beginnerExplanation:
      'Approved workflows are submitted to the compute backend (local or LSF cluster). Jobs run sequentially or in parallel according to the DAG. You can monitor status in real time.',
    technicalDetail:
      'Execution goes through the compute adapter. Cluster jobs require explicit user confirmation after script review. Job stdout/stderr tails and artifact outputs are tracked per node.',
    inputs: ['Approved workflow DAG', 'Input artifacts per node', 'Compute queue and resource allocation'],
    outputs: [
      'Per-node job status (queued, running, completed, failed)',
      'Output artifacts (structures, sequences, logs)',
      'Compute metrics and runtime data',
    ],
    commonFailures: [
      'API timeout during job submission or polling',
      'Model failure — node exits with error',
      'Cluster queue unavailable or resource exhaustion',
      'Script SHA-256 mismatch on cluster confirmation',
    ],
    userDecisions: [
      'Confirm cluster job submission',
      'Retry or skip failed nodes',
      'Cancel running jobs if needed',
    ],
    icon: Cpu,
  },
  {
    id: 'candidate-generation',
    stepNumber: 8,
    title: 'Candidate Generation',
    stationLabel: 'Generation Chamber',
    beginnerExplanation:
      'Design models produce candidate protein sequences and structures. Each candidate is a potential answer to your design goal, ready for scoring and human review.',
    technicalDetail:
      'Generation outputs include designed sequences, predicted structures, and per-node metadata. Candidates are registered as artifacts linked to the workflow run and project.',
    inputs: ['Completed generation node outputs', 'Design constraints', 'Template structure context'],
    outputs: [
      'Candidate sequences and structures',
      'Generation metadata per candidate',
      'Artifact registry entries',
    ],
    commonFailures: [
      'Empty result — no candidates produced',
      'Low diversity — all candidates too similar',
      'Structures fail basic quality checks',
    ],
    userDecisions: [
      'Filter candidates before scoring',
      'Request regeneration with adjusted parameters',
    ],
    icon: Sparkle,
  },
  {
    id: 'scoring-ranking',
    stepNumber: 9,
    title: 'Scoring & Ranking',
    stationLabel: 'Evaluation Terminal',
    beginnerExplanation:
      'Scoring models evaluate candidates against your design goals. Results are ranked so you can focus on the most promising designs first. Scores are explained in plain language.',
    technicalDetail:
      'Scoring combines model-specific metrics (pLDDT, ipTM, ddG proxies, sequence heuristics). Rankings are traceable to source nodes. Scores are predictive — not experimental validation.',
    inputs: ['Generated candidates', 'Scoring node configuration', 'Design goal thresholds'],
    outputs: [
      'Ranked candidate table',
      'Per-metric scores with explanations',
      'Advance / hold / redesign recommendations',
    ],
    commonFailures: [
      'Score interpretation uncertainty — metrics conflict',
      'Frontend/backend schema mismatch in score display',
      'Over-reliance on a single proxy metric',
    ],
    userDecisions: [
      'Review top candidates and score breakdowns',
      'Decide advance, hold, or redesign',
    ],
    icon: ChartBar,
  },
  {
    id: 'visualization',
    stepNumber: 10,
    title: 'Visualization & Interpretation',
    stationLabel: 'Structure Visualization Theater',
    beginnerExplanation:
      'Inspect candidate structures in 3D, compare binding interfaces, and read agent interpretations. This is where computational results become design intuition.',
    technicalDetail:
      'Mol* renders mmCIF/PDB artifacts in-browser. Copilot explains structural features, binding contacts, and score context. Interpretation cards suggest next actions.',
    inputs: ['Ranked candidates', 'Structure artifacts', 'Score and metadata context'],
    outputs: [
      '3D structure views',
      'Interpretation summaries per candidate',
      'Suggested next actions (advance, hold, redesign)',
    ],
    commonFailures: [
      'Visualization failure — corrupt or missing structure file',
      'Misreading predicted structures as experimental evidence',
      'Ignoring unresolved regions in the 3D view',
    ],
    userDecisions: [
      'Select candidates for wet-lab follow-up',
      'Request additional interpretation from Copilot',
    ],
    icon: Cube,
  },
  {
    id: 'export',
    stepNumber: 11,
    title: 'Export & Experimental Planning',
    stationLabel: 'Experiment Handoff Station',
    beginnerExplanation:
      'Export selected candidates, sequences, and reports for lab work. Plan the next experimental round or start a Campaign loop for iterative optimization.',
    technicalDetail:
      'Exports include structure files, FASTA sequences, score reports, and workflow provenance. Campaign rounds link design → prediction → wet-lab results → evaluation → parameter adjustment with human approval.',
    inputs: ['Selected candidates', 'Workflow run provenance', 'Interpretation notes'],
    outputs: [
      'Downloadable artifact bundle',
      'Experimental planning checklist',
      'Optional Campaign round draft',
    ],
    commonFailures: [
      'Incomplete workflow state at export time',
      'Missing provenance for reproduced results',
      'Wet-lab steps attempted without human confirmation',
    ],
    userDecisions: [
      'Confirm export scope and format',
      'Approve Campaign continuation or new round',
      'Record wet-lab results when available',
    ],
    icon: Package,
  },
]

type StationCopy = Omit<WorkflowStationData, 'id' | 'stepNumber' | 'icon'>

const GUIDE_WORKFLOW_ZH: Record<string, StationCopy> = {
  research: {
    title: '研究与文献综述',
    stationLabel: '知识中心',
    beginnerExplanation: '在开始设计前，代理会帮助检索靶点、方法和既往设计工作，为后续决策建立共同的证据基础。',
    technicalDetail: 'Copilot 检索 Europe PMC、RCSB PDB、UniProt 和 Reactome，并用引用与证据等级整理发现。确认后的结论可作为结构化发现写入项目综述。',
    inputs: ['研究问题或靶点名称', '可选的种子论文或 PDB ID', '项目类型与设计目标'],
    outputs: ['含 DOI/PMID 的文献摘要', '机制与通路背景', '方法版图与设计先例', '风险提示与待解决问题'],
    commonFailures: ['文献检索不完整，遗漏关键论文', '代理结论缺少引用', '未经证据核验就接受结论', '把计算预测误当作实验验证'],
    userDecisions: ['确认哪些发现写入项目综述', '标记不确定或互相矛盾的证据'],
  },
  'target-confirmation': {
    title: '靶点蛋白确认',
    stationLabel: '靶点选择台',
    beginnerExplanation: '系统根据研究提出最多五个候选靶点。开始结构处理前，必须确认物种、亚型和构建边界。',
    technicalDetail: '靶点智能会解析 UniProt 登录号、基因符号、审阅状态与功能注释，并用证据卡片连接每项建议和文献或数据库来源。',
    inputs: ['综述结论', '靶点名称、基因或 UniProt ID', '物种和构建偏好'],
    outputs: ['排序后的候选靶点', '逐靶点证据卡片', '供下游使用的已确认靶点身份'],
    commonFailures: ['靶点名称或物种含糊', '选择了错误蛋白', '亚型或构建边界不匹配', '忽略 UniProt 审阅状态'],
    userDecisions: ['从候选中选择一个靶点', '确认物种、亚型和构建范围'],
  },
  'pdb-download': {
    title: 'PDB / 结构下载',
    stationLabel: '结构档案入口',
    beginnerExplanation: '靶点确认后，代理检索 RCSB PDB 实验结构，并按分辨率、方法和结合状态推荐模板。',
    technicalDetail: 'PDB 检索返回条目 ID、实验方法、分辨率、发布日期和主要引用，下载链接提供 mmCIF 文件并按设计适用性排序。',
    inputs: ['已确认靶点', '可选配体或复合物约束', '实验方法筛选条件'],
    outputs: ['排序后的 PDB 列表', '结构元数据与下载链接', '带理由的模板建议'],
    commonFailures: ['没有合适的实验结构', '未经审核就使用 AlphaFold 替代', '结构物种或构建错误', '忽略配体或辅因子背景'],
    userDecisions: ['选择 PDB 模板或批准 AlphaFold 替代', '确认链与结合状态'],
  },
  'structure-cleaning': {
    title: '结构清理与准备',
    stationLabel: '分子准备实验室',
    beginnerExplanation: '原始结构常含缺失残基、未解析环区、替代构象或多余链，本步骤生成可用于设计的干净结构。',
    technicalDetail: '准备过程包含链选择、配体/辅因子处理、缺失残基和环区标记，以及 mmCIF/PDB 格式规范化。',
    inputs: ['选定的 PDB 或 AlphaFold 结构', '链与配体选择', '构建边界'],
    outputs: ['清理后的结构制品', '包含缺失和警告的准备报告', '可用于设计的 mmCIF/PDB'],
    commonFailures: ['未标记缺失残基', '忽略模板未解析环区', '选择错误的链', '误删结合所需的配体或辅因子'],
    userDecisions: ['批准链和配体处理方式', '接受或拒绝包含未解析区域的结构'],
  },
  'design-goal': {
    title: '设计目标选择',
    stationLabel: '决策控制室',
    beginnerExplanation: '定义成功标准，例如亲和力、稳定性、特异性、表达或它们的组合，代理会将目标转换为可度量约束。',
    technicalDetail: '设计目标映射到结合蛋白、酶、甜味蛋白或骨架改造等项目模板，并进入路线规划和模型参数选择。',
    inputs: ['项目类型', '综述约束', '清理后的结构'],
    outputs: ['结构化设计目标', '评分优先级与验收阈值', '代理规划约束'],
    commonFailures: ['目标含糊或互相冲突', '目标无法由现有模型评分', '约束与模板结构矛盾'],
    userDecisions: ['确认目标和指标优先级', '设置适用的验收阈值'],
  },
  'agent-planning': {
    title: '代理规划',
    stationLabel: '规划指挥中心',
    beginnerExplanation: '代理提出可视化工作流 DAG，说明模型顺序和参数；任何计算提交前均由您审核和调整。',
    technicalDetail: '路线规划使用 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta 等插件。DAG 保持无环，跨轮次迭代由 Campaign 管理。',
    inputs: ['设计目标与约束', '清理后的结构', '可用模型插件'],
    outputs: ['建议工作流 DAG', '节点参数与理由', '预计计算资源'],
    commonFailures: ['节点缺少所需输入', '参数补丁与插件模式不符', '代理澄清问题未回答'],
    userDecisions: ['批准、编辑或拒绝工作流', '回答澄清问题', '提交前确认模型参数'],
  },
  'model-execution': {
    title: '模型执行',
    stationLabel: '计算设施',
    beginnerExplanation: '批准后的工作流提交到本地或 LSF 集群，任务按 DAG 串行或并行运行，并可实时监控。',
    technicalDetail: '执行由计算适配器完成。集群任务需在审核脚本后显式确认，系统按节点跟踪 stdout/stderr 和输出制品。',
    inputs: ['已批准工作流', '节点输入制品', '队列与资源配置'],
    outputs: ['节点任务状态', '结构、序列与日志制品', '运行时间与计算指标'],
    commonFailures: ['提交或轮询超时', '模型异常退出', '队列或资源不可用', '确认时脚本哈希不一致'],
    userDecisions: ['确认集群提交', '重试或跳过失败节点', '必要时取消任务'],
  },
  'candidate-generation': {
    title: '候选物生成',
    stationLabel: '生成舱',
    beginnerExplanation: '设计模型生成候选序列和结构，每个候选都将进入评分和人工审核。',
    technicalDetail: '生成输出包含序列、预测结构和节点元数据，并作为与工作流运行和项目关联的制品注册。',
    inputs: ['已完成的生成节点输出', '设计约束', '模板结构背景'],
    outputs: ['候选序列与结构', '逐候选生成元数据', '制品登记记录'],
    commonFailures: ['没有生成候选物', '候选多样性不足', '结构未通过基本质量检查'],
    userDecisions: ['评分前筛选候选物', '调整参数后重新生成'],
  },
  'scoring-ranking': {
    title: '评分与排序',
    stationLabel: '评估终端',
    beginnerExplanation: '评分模型按设计目标评估并排序候选物，同时用易懂语言解释各项指标。',
    technicalDetail: '评分组合 pLDDT、ipTM、ddG 代理和序列启发式指标，排名可追溯到来源节点；预测分数不等同于实验验证。',
    inputs: ['生成的候选物', '评分节点配置', '设计阈值'],
    outputs: ['候选物排名表', '指标分解与解释', '推进、暂缓或重设计建议'],
    commonFailures: ['多个指标互相冲突', '前后端评分模式不一致', '过度依赖单一代理指标'],
    userDecisions: ['检查头部候选和评分', '决定推进、暂缓或重设计'],
  },
  visualization: {
    title: '可视化与解读',
    stationLabel: '结构可视化室',
    beginnerExplanation: '在三维视图中检查结构和结合界面，并阅读代理解释，把计算结果转化为设计判断。',
    technicalDetail: 'Mol* 在浏览器中渲染 mmCIF/PDB，Copilot 解释结构特征、接触和评分背景，并提出下一步建议。',
    inputs: ['排序后的候选物', '结构制品', '评分与元数据'],
    outputs: ['三维结构视图', '候选物解读摘要', '推进、暂缓或重设计建议'],
    commonFailures: ['结构文件损坏或缺失', '把预测结构误当实验事实', '忽略三维视图中的未解析区域'],
    userDecisions: ['选择进入实验的候选物', '向 Copilot 请求进一步解释'],
  },
  export: {
    title: '导出与实验规划',
    stationLabel: '实验交接站',
    beginnerExplanation: '导出候选物、序列和报告供实验使用，并规划下一轮实验或 Campaign 迭代。',
    technicalDetail: '导出包包含结构、FASTA、评分报告和工作流来源。Campaign 用人工批准连接设计、预测、实验、评估和参数调整。',
    inputs: ['选定候选物', '工作流来源信息', '解读笔记'],
    outputs: ['可下载制品包', '实验规划清单', '可选 Campaign 草稿'],
    commonFailures: ['工作流不完整时导出', '结果缺少可复现来源', '未经人工确认就执行实验步骤'],
    userDecisions: ['确认导出范围和格式', '批准继续 Campaign 或新轮次', '记录可用实验结果'],
  },
}

export function getGuideWorkflowStations(language: 'en' | 'zh'): WorkflowStationData[] {
  if (language === 'en') return GUIDE_WORKFLOW_STATIONS
  return GUIDE_WORKFLOW_STATIONS.map((station) => ({
    ...station,
    ...GUIDE_WORKFLOW_ZH[station.id],
  }))
}
