import { useId } from 'react'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getRepresentationOptions, type RepresentationPreset } from './ColorPresets'
import { useI18n } from '../../lib/i18n'

interface RepresentationSelectorProps {
  value: RepresentationPreset
  onChange: (value: RepresentationPreset) => void
}

export function RepresentationSelector({ value, onChange }: RepresentationSelectorProps) {
  const { t } = useI18n()
  const options = getRepresentationOptions(t.viewer)
  const id = useId()

  return (
    <div className="grid min-w-36 gap-1">
      <Label htmlFor={id}>{t.viewer.style}</Label>
      <Select
        value={value}
        onValueChange={(nextValue) => {
          if (nextValue) onChange(nextValue as RepresentationPreset)
        }}
      >
        <SelectTrigger id={id} className="w-full" aria-label={t.viewer.style}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
