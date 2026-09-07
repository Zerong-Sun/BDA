import { useRef } from 'react'
import { Input } from '../../components/ui/Input'
import { Checkbox } from '../../components/ui/checkbox'
import { Textarea } from '../../components/ui/textarea'
import { WorkflowSection, WorkflowSelect, WorkflowOption } from './WorkflowControls'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import type { GatePolicy, GateRules } from './gates'

const field =
  'w-full rounded border border-border-soft bg-surface-1 p-1.5 text-xs text-text-primary'
export function GatePolicyEditor({
  value,
  onChange,
  disabled = false,
  output = false,
}: {
  value: GatePolicy
  onChange: (v: GatePolicy) => void
  disabled?: boolean
  output?: boolean
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { language } = useI18n()
  const zh = language === 'zh'
  const rules = value.rules
  const setRules = (patch: Partial<GateRules>) =>
    onChange({ ...value, configured: true, rules: { ...rules, ...patch } })
  if (!output && (value.mode === 'integrity' || value.mode === 'dependency')) {
    return (
      <p className="text-xs text-text-secondary">
        {value.mode === 'integrity'
          ? zh
            ? '完整性检查：核对文件大小和 SHA256 后放行。'
            : 'Integrity check: release after verifying file size and SHA256.'
          : zh
            ? '等待上一步完成后继续。'
            : 'Continue after the previous step completes.'}
      </p>
    )
  }
  return (
    <fieldset disabled={disabled} className="grid gap-2 text-xs">
      {!output && (
        <label>
          {zh ? '放行方式' : 'Release mode'}
          <WorkflowSelect
            className={field}
            value={value.mode}
            onChange={(e) =>
              onChange({ ...value, mode: e.target.value as GatePolicy['mode'], configured: true })
            }
          >
            <WorkflowOption value="automatic">
              {zh ? '规则自动放行' : 'Automatic screening'}
            </WorkflowOption>
            <WorkflowOption value="manual">{zh ? '人工选择' : 'Manual selection'}</WorkflowOption>
            <WorkflowOption value="review">
              {zh ? '筛选后人工确认' : 'Screen then review'}
            </WorkflowOption>
            {value.mode === 'integrity' && (
              <WorkflowOption value="integrity">
                {zh ? '完整性检查' : 'Integrity check'}
              </WorkflowOption>
            )}
            {value.mode === 'dependency' && (
              <WorkflowOption value="dependency">
                {zh ? '仅等待完成' : 'Completion dependency'}
              </WorkflowOption>
            )}
          </WorkflowSelect>
        </label>
      )}
      <label>
        {zh ? '条件组合' : 'Combine conditions'}
        <WorkflowSelect
          className={field}
          value={rules.operator}
          onChange={(e) => setRules({ operator: e.target.value as 'and' | 'or' })}
        >
          <WorkflowOption value="and">AND</WorkflowOption>
          <WorkflowOption value="or">OR</WorkflowOption>
        </WorkflowSelect>
      </label>
      {rules.conditions.map((rule, index) => (
        <div key={index} className="grid grid-cols-[1fr_55px_65px_24px] gap-1">
          <Input
            className={field}
            aria-label="Metric"
            placeholder="pLDDT"
            value={rule.metric}
            onChange={(e) =>
              setRules({
                conditions: rules.conditions.map((r, i) =>
                  i === index ? { ...r, metric: e.target.value } : r,
                ),
              })
            }
          />
          <WorkflowSelect
            className={field}
            aria-label="Comparison"
            value={rule.op}
            onChange={(e) =>
              setRules({
                conditions: rules.conditions.map((r, i) =>
                  i === index ? { ...r, op: e.target.value as typeof rule.op } : r,
                ),
              })
            }
          >
            {['gt', 'gte', 'lt', 'lte', 'eq', 'ne'].map((op, i) => (
              <WorkflowOption key={op} value={op}>
                {['>', '≥', '<', '≤', '=', '≠'][i]}
              </WorkflowOption>
            ))}
          </WorkflowSelect>
          <Input
            className={field}
            aria-label="Threshold"
            type="number"
            value={rule.value}
            onChange={(e) =>
              setRules({
                conditions: rules.conditions.map((r, i) =>
                  i === index ? { ...r, value: Number(e.target.value) } : r,
                ),
              })
            }
          />
          <Button
            type="button"
            variant="ghost"
            aria-label="Remove condition"
            onClick={() => setRules({ conditions: rules.conditions.filter((_, i) => i !== index) })}
          >
            ×
          </Button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() =>
          setRules({ conditions: [...rules.conditions, { metric: '', op: 'gte', value: 0 }] })
        }
      >
        {zh ? '添加指标条件' : 'Add metric condition'}
      </Button>
      <label>
        {zh ? '排序指标' : 'Ranking metric'}
        <Input
          className={field}
          value={rules.sort_metric ?? ''}
          onChange={(e) => setRules({ sort_metric: e.target.value || null })}
        />
      </label>
      <label>
        <Checkbox
          checked={rules.descending}
          onCheckedChange={(checked) => setRules({ descending: !!checked })}
        />{' '}
        {zh ? '从高到低' : 'Descending'}
      </label>
      <label>
        Top N
        <Input
          className={field}
          type="number"
          min="1"
          value={rules.top_n ?? ''}
          onChange={(e) => setRules({ top_n: e.target.value ? Number(e.target.value) : null })}
        />
      </label>
      <label>
        <Checkbox
          checked={!!value.structure}
          onCheckedChange={(checked) =>
            onChange({
              ...value,
              configured: true,
              structure: checked ? { chains: [], min_helices: 2, min_helix_length: 4 } : null,
            })
          }
        />{' '}
        {zh ? '结构质量标准（DSSP）' : 'Structure quality standard (DSSP)'}
      </label>
      {value.structure && (
        <div className="grid gap-2 rounded border border-border-soft p-2">
          <label>
            {zh ? '结构预设' : 'Structure preset'}
            <WorkflowSelect
              value={value.structure.preset ?? 'multi_helix'}
              onChange={(e) =>
                onChange({
                  ...value,
                  structure: {
                    ...value.structure!,
                    preset: e.target.value as 'multi_helix' | 'structured' | 'beta_sheet',
                  },
                })
              }
            >
              <WorkflowOption value="multi_helix">
                {zh ? '多螺旋骨架' : 'Multi-helix backbone'}
              </WorkflowOption>
              <WorkflowOption value="structured">
                {zh ? '必须存在二级结构' : 'Secondary structure required'}
              </WorkflowOption>
              <WorkflowOption value="beta_sheet">
                {zh ? 'β结构（至少两个E片段）' : 'Beta structure (at least two E segments)'}
              </WorkflowOption>
            </WorkflowSelect>
          </label>
          <label>
            {zh ? '设计链（必填，逗号分隔）' : 'Design chains (required, comma separated)'}
            <Input
              className={field}
              value={value.structure.chains.join(',')}
              onChange={(e) =>
                onChange({
                  ...value,
                  structure: {
                    ...value.structure!,
                    chains: e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean),
                  },
                })
              }
            />
          </label>
          {(['min_helices', 'min_helix_length', 'min_strands', 'start', 'end'] as const).map(
            (key, i) => (
              <label key={key}>
                {
                  (zh
                    ? [
                        '至少几个螺旋',
                        '每个螺旋至少几个残基',
                        '至少几个 β 片段',
                        '起始残基（可选）',
                        '结束残基（可选）',
                      ]
                    : [
                        'Minimum helices',
                        'Minimum helix length',
                        'Minimum beta segments',
                        'First residue (optional)',
                        'Last residue (optional)',
                      ])[i]
                }
                <Input
                  className={field}
                  type="number"
                  value={value.structure![key] ?? ''}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      structure: {
                        ...value.structure!,
                        [key]: e.target.value ? Number(e.target.value) : null,
                      } as NonNullable<GatePolicy['structure']>,
                    })
                  }
                />
              </label>
            ),
          )}
        </div>
      )}
      <WorkflowSection title={<> {zh ? 'Python 筛选脚本' : 'Python screening script'} </>}>
        <p className="my-2 text-text-secondary">screen(records) → [{'{id, passed, reason}'}]</p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
        >
          Upload Python script
        </Button>
        <input
          className="hidden"
          ref={fileInputRef}
          aria-label="Upload gate script"
          type="file"
          accept=".py"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (file) onChange({ ...value, configured: true, script: await file.text() })
          }}
        />
        <Textarea
          className={`${field} mt-2 min-h-40 font-mono`}
          aria-label="Gate Python script"
          value={value.script ?? ''}
          onChange={(e) => onChange({ ...value, configured: true, script: e.target.value || null })}
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() =>
            onChange({
              ...value,
              configured: true,
              script:
                'def screen(records):\n    return [{"id": r["id"], "passed": r.get("metrics", {}).get("helix_count", 0) >= 2, "reason": "Requires at least two helices"} for r in records]\n',
            })
          }
        >
          {zh ? '生成双螺旋筛选模板' : 'Generate two-helix template'}
        </Button>
      </WorkflowSection>
    </fieldset>
  )
}
