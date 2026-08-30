export interface CopilotTool {
  name: string
  description: string
  parameters?: Record<string, unknown>
}

export interface CopilotSkill {
  name: string
  description: string
  trigger: string[]
  systemPrompt: string
  tools?: CopilotTool[]
}
