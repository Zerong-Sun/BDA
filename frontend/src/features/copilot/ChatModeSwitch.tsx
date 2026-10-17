import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'

export function ChatModeSwitch({ mode, onChange, disabled }: {
  mode: 'general' | 'bench'
  onChange: (mode: 'general' | 'bench') => void
  disabled: boolean
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  return <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-4 py-2">
    <Button type="button" size="sm" variant={mode === 'general' ? 'secondary' : 'ghost'}
      aria-pressed={mode === 'general'} disabled={disabled} onClick={() => onChange('general')}>
      {zh ? '研究问答' : 'Research chat'}
    </Button>
    <Button type="button" size="sm" variant={mode === 'bench' ? 'secondary' : 'ghost'}
      aria-pressed={mode === 'bench'} disabled={disabled} onClick={() => onChange('bench')}>
      {zh ? '实验计算' : 'Lab calculations'}
    </Button>
    {mode === 'bench' ? <span className="text-xs text-muted-foreground">
      {zh ? '查询蛋白库、计算与单位换算；不写入实验记录。' : 'Protein lookup, calculations and unit conversion; no experiment records are written.'}
    </span> : null}
  </div>
}
