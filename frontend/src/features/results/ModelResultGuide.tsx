import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../../components/ui/accordion'
import { useI18n } from '../../lib/i18n'
import { findModelResultGuide, modelResultGuides } from './modelResultGuides'

/** Informational only. A completed job and a scientific pass are different states. */
export function ModelResultGuide({ pluginKey }: { pluginKey: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const guide = findModelResultGuide(pluginKey)
  const copy = guide?.[zh ? 'zh' : 'en']
  return (
    <Accordion className="rounded-md border border-border-soft bg-bg-app p-3 text-sm">
      <AccordionItem value="guide">
      <AccordionTrigger className="text-sm text-text-primary">
        {guide?.pluginKey ?? pluginKey} · {zh ? '结果判读指南' : 'Result interpretation guide'}
      </AccordionTrigger>
      <AccordionContent className="mt-3 space-y-3 break-words text-text-secondary">
        <p className="text-xs">
          {zh
            ? '参考指南 · 2026-09-07 · 不自动筛选。实际放行以本次运行的已校准规则为准；计算通过不等于实验成功。缺失、非有限值或量纲不明的指标应记为未评估。'
            : 'Reference guide · 2026-09-07 · No automatic filtering. Use the run’s calibrated criteria for acceptance; computational acceptance is not experimental success. Missing, non-finite or unknown-scale metrics remain unassessed.'}
        </p>
        {copy ? (
          <dl className="space-y-3">
            {([
              [zh ? '指标与量纲' : 'Metrics and units', copy.metrics],
              [zh ? '参考标准与适用范围' : 'Reference criteria and scope', copy.reference],
              [zh ? '下一步' : 'Next step', copy.next],
            ] as const).map(([label, value]) => (
              <div key={label}>
                <dt className="font-medium text-text-primary">{label}</dt>
                <dd className="mt-1 leading-relaxed">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p>{zh
            ? '该模型尚无专用指南。先确认模型版本、输出字段、单位、完整性及对照结果，再制定阈值；不能根据名称相似或单个高分套用其他模型标准。'
            : 'No model-specific guide is registered. Verify version, output fields, units, completeness and controls before setting thresholds; do not borrow another model’s criteria from a similar name or a high score.'}</p>
        )}
        {guide?.source ? (
          <a className="text-accent underline" href={guide.source} target="_blank" rel="noopener noreferrer">
            {zh ? '指标说明来源' : 'Metric documentation'}
          </a>
        ) : null}
        {guide?.pluginKey === 'superfold' || guide?.pluginKey === 'Rosetta' ? (
          <p className="text-xs">{zh
            ? '数值来源：BDA route_catalog，de-novo-binder-pooled 路线的 Tier A/B 建议；仅适用于匹配的预测与评分协议，需先用对照校准。'
            : 'Numeric source: BDA route_catalog, de-novo-binder-pooled Tier A/B suggestions. Apply only to matching prediction/scoring protocols after control calibration.'}</p>
        ) : null}
      </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

export function ModelResultGuideLibrary() {
  const { language } = useI18n()
  const zh = language === 'zh'
  return (
    <Accordion className="mb-5 rounded-md border border-border-soft p-4">
      <AccordionItem value="library">
      <AccordionTrigger className="text-sm">
        {zh ? '各模型输出 · 结果判读标准指南' : 'Model outputs · Interpretation reference library'}
      </AccordionTrigger>
      <AccordionContent>
      <p className="my-3 text-sm text-text-secondary">
        {zh
          ? '按模型查阅指标、参考范围和后续验证要求。此目录包含尚不可运行的插件；运行状态以插件注册表为准。'
          : 'Look up metrics, reference ranges and follow-up checks by model. This library includes unavailable plugins; consult the registry for runtime status.'}
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        {modelResultGuides.map((guide) => <ModelResultGuide key={guide.pluginKey} pluginKey={guide.pluginKey} />)}
      </div>
      </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
