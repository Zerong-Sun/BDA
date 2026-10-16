import { generatedClient } from './generatedTransport'

export interface BotRecordItem {
  kind: 'message' | 'agent_run'
  id: string
  bot: string
  status: string
  created_at: string
  updated_at: string
  source_version: number
  content: string
  error?: string | null
  conversation_id?: string
  parent_run_id?: string | null
  references: Array<[string, string]>
  citations?: unknown[]
  turn_ids?: string[]
  outcome?: Record<string, unknown>
}
export interface BotRecords {
  project_id: string
  bot_id: string
  record_id: string | null
  sha256: string | null
  updated_at: string | null
  total: number
  matched: number
  offset: number
  items: BotRecordItem[]
}
const path = (projectId: string, botId: string) => `/api/v2/copilot/projects/${encodeURIComponent(projectId)}/bots/${encodeURIComponent(botId)}/records`
export async function getBotRecords(projectId: string, botId: string, query = '', offset = 0) {
  const response = await generatedClient.get<{ 200: BotRecords }, unknown, true>({ url: path(projectId, botId), query: { query, offset, limit: 50 }, throwOnError: true })
  return response.data!
}
export async function downloadBotRecords(projectId: string, botId: string) {
  const response = await generatedClient.get<{ 200: string }, unknown, true>({ url: `${path(projectId, botId)}.md`, parseAs: 'text', throwOnError: true })
  const blob = new Blob([response.data!], { type: 'text/markdown;charset=utf-8' })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = `${botId}-${projectId}.md`
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
