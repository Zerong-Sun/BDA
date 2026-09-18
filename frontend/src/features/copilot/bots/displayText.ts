import type { CopilotBot } from './registry'

const planner = {
  summary: '解读结构，比较研究路线，形成可复核的计算与实验方案。',
  charter: [
    '结构解读：查看蛋白链、残基编号、界面接触、位点邻域、二硫键与非标准原子，注明坐标来源和编号体系。对于预测结构，先说明置信度，再解释几何测量；结构接近并不等于功能已经验证。',
    '路线比较：结合项目已有证据和工作流状态，说明推荐方案的依据、备选路线的取舍，以及输入资料和验证证据的缺口。',
    '计算草案：明确输入、参数、计算资源与预期产物，说明资源需求的依据。方案经复核与人工确认后交由执行成员处理；草案阶段不自动确认或提交任务。',
  ].join('\n\n'),
}
/** Localized presentation only; server capabilities and execution charter remain authoritative. */
export function botDisplayText(bot: CopilotBot, language: string) {
  return language === 'zh' && bot.id === 'planner' ? planner : { summary: bot.summary, charter: bot.charter }
}
