import type { CopilotBot } from './registry'

type DisplayText = { summary: string; charter: string }
const zh: Record<string, DisplayText> = {
  conductor: { summary: '选择下一位负责的 Bot，跟进交接并明确停止条件。', charter: '先检查项目与交接记录，再安排一个已授权步骤。只问建议时不会启动任务；实际委派会保留子任务记录。需要补充资料或人工决定时会停下，不替用户授权写入或提交计算。' },
  researcher: { summary: '明确可验证的研究问题，整理文献与靶点证据。', charter: '读取已保存的摘要或全文，注明来源、证据范围与缺口。区分已知事实、推断和待检验假设；缺少数据时不补造结论。保存笔记或开展外部检索需获得对应授权。' },
  planner: { summary: '解读结构，比较路线，准备待审核的计算草稿。', charter: '说明结构来源、残基编号、距离单位及置信度依据；几何接触不等于功能验证。比较路线与输入缺口，写清参数、资源和预期产物。只起草方案，由用户确认并提交计算。' },
  runner: { summary: '跟踪已提交的作业，等待结果并解释记录中的失败。', charter: '分别报告已完成、进行中与受阻状态，依据日志和资源记录区分确定原因与可能原因。恢复建议交给方案设计；不会自行提交、重试或改写失败记录。测试夹具的状态不代表真实计算。' },
  analyst: { summary: '解读已有结果，区分达标、未达标与缺失数据。', charter: '注明指标的单位、方法和分析版本，区分预测分数与实验测量。缺失值不判为失败，合成数据不作为研究结论。提出下一轮验证建议；保存研究决策仍需明确授权。' },
  auditor: { summary: '对照真实工具记录与来源，复核结论和资源声明。', charter: '逐条判断主张是否有支持、缺少依据或与记录矛盾。没有关联运行或完整证据时说明无法复核。只报告发现与改进建议，不直接修复记录，也不代替人工批准。' },
}
const en: Record<string, DisplayText> = {
  conductor: { summary: 'Choose the next Bot, track its handoff and state when to stop.', charter: 'Read project state and handoffs, then delegate one authorized step. A recommendation does not start a run. Actual delegation has a child-run record. Stop for missing inputs or a human decision; never authorize writes or submit compute for the user.' },
  researcher: { summary: 'Frame a testable question and review source evidence.', charter: 'Read saved abstracts or full text and identify sources, scope and gaps. Separate facts, inferences and hypotheses; never fill missing measurements with invented values. Saving notes or searching external sources requires the corresponding authorization.' },
  planner: { summary: 'Inspect structures, compare routes and prepare drafts for review.', charter: 'State coordinate sources, residue numbering, distance units and confidence provenance. Contacts alone do not establish function. Compare routes, inputs, parameters and resource needs. The user confirms and submits compute.' },
  runner: { summary: 'Track submitted jobs, wait for results and diagnose recorded failures.', charter: 'Separate completed, pending and blocked work. Use logs and resource records to distinguish confirmed from possible causes. Hand recovery proposals to planner; never submit, retry or rewrite failure records. Synthetic job states are not real execution evidence.' },
  analyst: { summary: 'Interpret recorded results and distinguish pass, fail and missing.', charter: 'Report units, methods and analysis versions. Keep predictions separate from experiments; missing values are not failures and synthetic data are not research findings. Propose the next validation step. Recording a research decision requires explicit authorization.' },
  auditor: { summary: 'Check claims and resource declarations against actual evidence.', charter: 'Identify supported, unsupported and contradicted claims. State when a missing run or incomplete evidence prevents review. Report findings and proposed corrections; do not repair records or grant human approval.' },
}
/** Presentation only: server capabilities and execution rules remain authoritative. */
export function botDisplayText(bot: CopilotBot, language: string): DisplayText {
  return (language === 'zh' ? zh : en)[bot.id] ?? { summary: bot.summary, charter: bot.charter }
}
