import { useId } from 'react'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getColorOptions, type ColorPreset } from './ColorPresets'
import { useI18n } from '../../lib/i18n'

interface ColorSchemeSelectorProps {
  value: ColorPreset
  onChange: (value: ColorPreset) => void
}

export function ColorSchemeSelector({ value, onChange }: ColorSchemeSelectorProps) {
  const { t } = useI18n()
  const options = getColorOptions(t.viewer)
  const id = useId()

  return (
    <div className="grid min-w-40 gap-1">
      <Label htmlFor={id}>{t.viewer.color}</Label>
      <Select
        value={value}
        onValueChange={(nextValue) => {
          if (nextValue) onChange(nextValue as ColorPreset)
        }}
      >
        <SelectTrigger id={id} className="w-full" aria-label={t.viewer.color}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.id} value={option.id} title={option.description}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
