import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  FlaskIcon,
  SparkleIcon,
  SpinnerGapIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import {
  createResearchGapResolution,
  waitForResearchGapResolution,
} from '../../lib/api/researchGaps'
import { useI18n } from '../../lib/i18n'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import { Button } from '../../components/ui/Button'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function array(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(record) : []
}

function statusLabel(status: string, language: 'en' | 'zh'): string {
  const labels: Record<string, [string, string]> = {
    pending: ['Pending', '等待处理'],
    resolved: ['Resolved', '已补齐'],
    resolved_with_predicted_model: ['Resolved with predicted model', '已导入预测模型'],
    failed: ['Failed', '补齐失败'],
    requires_review: ['Requires molecular identity review', '需要人工确认分子身份'],
    requires_experiment: ['Requires new evidence / experiment', '需要新证据或实验'],
  }
  const pair = labels[status]
  return pair ? pair[language === 'zh' ? 1 : 0] : status.replaceAll('_', ' ')
}

function itemLabel(item: Record<string, unknown>, language: 'en' | 'zh'): string {
  const id = String(item.id || '')
  if (id === 'predicted_structure') {
    return language === 'zh' ? '结构模型' : 'Structure model'
  }
  if (id === 'scientific_validation') {
    return language === 'zh' ? '科学验证类缺口' : 'Scientific validation gaps'
  }
  if (id.startsWith('reference:')) {
    return language === 'zh' ? `文献内容 ${id.slice(10)}` : `Reference content ${id.slice(10)}`
  }
  return id || String(item.kind || 'Gap')
}

export function ResearchGapResolutionButton({
  projectId,
  researchTargetId,
  properties,
}: {
  projectId: string
  researchTargetId: string
  properties: Record<string, unknown>
}) {
  const { language } = useI18n()
  const client = useQueryClient()
  const resolution = record(properties.gap_resolution)
  const items = array(resolution.items)
  const savedPending = resolution.status === 'pending'
  const mutation = useMutation({
    mutationFn: async () => {
      const accepted = await createResearchGapResolution(projectId, researchTargetId)
      return waitForResearchGapResolution(accepted.operation_id)
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['research-workspace', projectId] })
    },
  })
  const pending = savedPending || mutation.isPending

  return (
    <div className="mt-2">
      <Button
        type="button"
        variant="outline"
        size="xs"
        disabled={pending}
        title={language === 'zh'
          ? '自动导入可获取的全文与预测结构；实验类缺口会保留为未解决。'
          : 'Imports retrievable full text and predicted structures; experimental gaps remain open.'}
        onClick={() => mutation.mutate()}
      >
        {pending
          ? <SpinnerGapIcon className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
          : <SparkleIcon aria-hidden="true" />}
        {language === 'zh' ? '补齐可自动修复的 Gaps' : 'Resolve data gaps'}
      </Button>

      {items.length ? (
        <Accordion defaultValue={['gaps']} className="mt-2 border border-border-soft bg-bg-app px-2">
          <AccordionItem value="gaps" className="border-0">
            <AccordionTrigger className="py-2 text-[10px] font-semibold text-text-secondary">
              {language === 'zh' ? '全部 Gaps：补齐状态' : 'All Gaps: Resolution Status'}
            </AccordionTrigger>
            <AccordionContent>
              <ul className="grid gap-1 pb-2">
            {items.map((item) => {
              const status = String(item.status || '')
              const resolved = status.startsWith('resolved')
              const requiresHuman = ['requires_experiment', 'requires_review'].includes(status)
              return (
                <li key={String(item.id || item.kind)} className="flex items-start gap-1 text-[10px] text-text-secondary">
                  {resolved
                    ? <CheckCircleIcon className="mt-0.5 size-3 shrink-0 text-success" aria-hidden="true" />
                    : requiresHuman
                      ? <FlaskIcon className="mt-0.5 size-3 shrink-0 text-accent-2" aria-hidden="true" />
                      : <WarningCircleIcon className="mt-0.5 size-3 shrink-0 text-danger" aria-hidden="true" />}
                  <span>{itemLabel(item, language)} · {statusLabel(status, language)}</span>
                </li>
              )
            })}
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      ) : null}
      {mutation.isError ? (
        <p className="mt-1 text-[10px] text-danger">
          {mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}
        </p>
      ) : null}
    </div>
  )
}
