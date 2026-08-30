import { describe, expect, it } from 'vitest'
import { copilotSkills, matchSkill } from './registry'

describe('copilot skill registry', () => {
  it('registers all planned skills', () => {
    expect(copilotSkills.map((skill) => skill.name)).toEqual([
      'literature-search',
      'research-gap-repair',
      'target-intelligence',
      'compute-drafting',
      'workflow-planning',
      'result-interpretation',
      'knowledge-authoring',
      'research-read',
      'project-read',
    ])
  })

  it('matches candidate ranking prompts', () => {
    expect(matchSkill('Which candidate should we rank first?')?.name).toBe('project-read')
  })

  it('matches programmable biomaterials prompts', () => {
    expect(matchSkill('How should RFdiffusion connect to a protein workflow?')?.name).toBe('workflow-planning')
  })

  it('matches workflow prompts in Chinese', () => {
    expect(matchSkill('调整工作流阈值')?.name).toBe('workflow-planning')
  })

  it('treats broad read triggers as background to a focused capability', () => {
    expect(matchSkill('请补齐 Research target 的 gaps')?.name).toBe('research-gap-repair')
  })

  it('returns undefined for unrelated prompts', () => {
    expect(matchSkill('hello world')).toBeUndefined()
  })

  it('does not collapse a multi-capability request to one hidden skill', () => {
    expect(matchSkill('Interpret the BLI result and search the literature')).toBeUndefined()
  })
})
