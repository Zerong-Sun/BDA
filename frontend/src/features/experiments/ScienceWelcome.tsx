import { Link } from 'react-router'
import { ArrowUpRightIcon } from '@phosphor-icons/react'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { Button } from '../../components/ui/Button'
import { projectText } from '../../lib/i18n/projectText'
import { BotAvatar } from '../copilot/BotAvatar'

export function ScienceWelcome() {
  const { language } = useI18n()
  const { activeProject, projectId } = useProjectContext()
  const zh = language === 'zh'
  return <section className="science-welcome">
    <div>
      <p className="science-eyebrow">BIGO / AI FOR SCIENCE</p>
      <h1>{zh ? <>从一个问题，<br />开始研究。</> : <>Your next discovery<br />starts with a question.</>}</h1>
      <p className="science-intro">{zh ? '提出目标，与研究 Bot 协作。在证据、结构和结果之间，找到下一步。' : 'Set a goal. Work with your research Bots. Find the next step in evidence, structures and results.'}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button type="button" className="science-primary" render={<Link to={`/bots${projectId ? `?project=${encodeURIComponent(projectId)}` : ''}`} />}>
          {zh ? '进入研究团队' : 'Open research team'}<ArrowUpRightIcon />
        </Button>
      </div>
    </div>
    <div className="science-team-preview">
      <div className="flex items-center justify-between gap-3"><span className="science-eyebrow">{zh ? '你的研究伙伴' : 'YOUR RESEARCH TEAM'}</span><span className="text-xs">{zh ? '从目标到交付' : 'Goal → deliverable'}</span></div>
      <div className="science-team-roles">
        {[
          ['researcher', 'produce', zh ? '研究员 · 问题与证据' : 'Researcher · question & evidence'],
          ['planner', 'produce', zh ? '方案设计 · 路线与计算' : 'Planner · route & compute'],
          ['runner', 'produce', zh ? '执行与排障 · 运行' : 'Runner · run & diagnose'],
          ['analyst', 'produce', zh ? '解读与归档 · 结果' : 'Analyst · results & record'],
          ['auditor', 'review', zh ? '复核 · 核对依据' : 'Auditor · checks the evidence'],
        ].map(([id, stance, label], index) => <div key={id}><BotAvatar id={id} stance={stance} /><span className="font-mono text-xs">0{index + 1}</span><span>{label}</span></div>)}
      </div>
      <div className="science-preview-footer"><span>{zh ? '当前项目' : 'PROJECT CONTEXT'}</span><span>{activeProject ? projectText(activeProject, 'name', language) : (zh ? '选择一个项目开始' : 'Choose a project to begin')}</span></div>
    </div>
  </section>
}
