import { useId } from 'react'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useI18n } from '../../lib/i18n'

interface ChainSelectorProps {
  chains: string[]
  value: string | null
  onChange: (chainId: string | null) => void
}

export function ChainSelector({ chains, value, onChange }: ChainSelectorProps) {
  const { t } = useI18n()
  const id = useId()

  if (chains.length <= 1) return null

  return (
    <div className="grid min-w-32 gap-1">
      <Label htmlFor={id}>{t.viewer.chain}</Label>
      <Select
        value={value ?? ALL_CHAINS_VALUE}
        onValueChange={(nextValue) =>
          onChange(nextValue === ALL_CHAINS_VALUE ? null : nextValue ?? null)
        }
      >
        <SelectTrigger id={id} className="w-full" aria-label={t.viewer.chain}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_CHAINS_VALUE} data-value={ALL_CHAINS_VALUE}>
            {t.viewer.allChains}
          </SelectItem>
        {chains.map((chain) => (
          <SelectItem key={chain} value={chain}>
            {chain}
          </SelectItem>
        ))}
        </SelectContent>
      </Select>
    </div>
  )
}

const ALL_CHAINS_VALUE = '__all_chains__'
