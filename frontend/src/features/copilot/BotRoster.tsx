import { Link } from 'react-router'
import { ApiState } from '../../components/ui/ApiState'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'
import { BotAvatar } from './BotAvatar'
import { byStance, useCopilotBots } from './bots/registry'
import { botHref } from './bots/workbenches'

/**
 * The research team, grouped by what each operator is for.
 *
 * Each named operator is a link to its responsibility page rather than a toggle
 * of the chat scope: choosing someone in a team roster should show what they
 * own and hold, and the conversation is one part of that page. Auto-match has no
 * page - it is the absence of an owner - so it stays an action.
 */
export function BotRoster({ projectId, activeBotId = null, autoActive = false, onAuto }: {
  projectId: string
  activeBotId?: string | null
  autoActive?: boolean
  onAuto: () => void
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const bots = useCopilotBots()
  const stanceLabel: Record<string, string> = { direct: zh ? '协调' : 'Coordinate', produce: zh ? '研究与产出' : 'Research & produce', review: zh ? '审阅' : 'Review' }

  return <aside className="bot-roster" aria-label={zh ? '研究 Bot 名录' : 'Research Bot roster'}>
    <h2>{zh ? '团队成员' : 'Team members'}</h2>
    <p className="mb-4 text-xs text-text-muted">{zh ? '打开一个职责，查看它负责什么、手上有什么。' : 'Open a responsibility to see what it owns and holds.'}</p>
    <div className="bot-roster-scroll">
      <Button variant="ghost" className="bot-roster-item" type="button" aria-pressed={autoActive} onClick={onAuto}><BotAvatar id="auto" stance="direct" /><span><strong>{zh ? '自动匹配' : 'Auto-match'}</strong><small>{zh ? '根据问题选择 Bot' : 'Match the question to a Bot'}</small></span></Button>
      <ApiState isLoading={bots.isLoading} isError={bots.isError} error={bots.error} onRetry={() => void bots.refetch()}>
        {byStance(bots.data ?? []).map((group) => <div className="bot-roster-group" key={group.stance}>
          <p className="bot-stance">{stanceLabel[group.stance]}</p>
          {group.bots.map((bot) => <Button variant="ghost" type="button" className="bot-roster-item" key={bot.id} title={bot.summary} aria-current={activeBotId === bot.id ? 'page' : undefined} render={<Link to={botHref(bot.id, projectId)} />}><BotAvatar id={bot.id} stance={bot.stance} /><span><strong>{zh ? bot.title_zh : bot.title}</strong></span></Button>)}
        </div>)}
        {bots.data?.length === 0 ? <p className="text-sm text-text-secondary">{zh ? '暂无可用 Bot。可在模型设置中检查配置。' : 'No Bots available. Check model settings.'}</p> : null}
      </ApiState>
    </div>
  </aside>
}
