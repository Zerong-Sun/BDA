import { useId, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import { Checkbox } from '../../components/ui/checkbox'
import { useI18n } from '../../lib/i18n'
import type { HighlightedResidue } from './types'
import { parseResidueSelection } from './residueSelectionParser'

export function ResidueSelection({ disabled, onApply }: {
  disabled: boolean
  onApply: (residues: HighlightedResidue[], sideChainsOnly: boolean) => Promise<{ residues: HighlightedResidue[]; atomCount: number } | undefined>
}) {
  const { language } = useI18n(), id = useId(), zh = language === 'zh'
  const [input, setInput] = useState('')
  const [sideChains, setSideChains] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function apply(clear = false) {
    if (disabled || busy) return
    setError(''); setBusy(true)
    try {
      const residues = clear ? [] : parseResidueSelection(input)
      const result = await onApply(residues, sideChains)
      if (clear) { setMessage(''); return }
      if (!result?.atomCount) throw new Error(zh ? '未找到对应原子，请检查链名和作者残基编号。' : 'No atoms found. Check the chain and author residue numbering.')
      const missing = residues.filter(r => !result.residues.some(found => found.chainId === r.chainId && found.seq === r.seq))
      setMessage(`${sideChains ? (zh ? '侧链' : 'Side chains') : (zh ? '氨基酸' : 'Residues')}: ${result.residues.map(r => r.label).join(' · ')} · ${result.atomCount} ${zh ? '个原子' : 'atoms'}`)
      if (missing.length) setError(`${zh ? '未找到' : 'Not found'}: ${missing.map(r => `${r.chainId}:${r.seq}`).join(', ')}`)
    } catch (caught) { setMessage(''); setError(zh && caught instanceof Error && caught.message.startsWith('Use chain:') ? '请输入链名:残基编号，例如 A:56 或 A:56, A:57。' : caught instanceof Error ? caught.message : 'Selection failed') }
    finally { setBusy(false) }
  }
  return <div className="mb-2 rounded-lg border border-border-soft bg-surface-1 px-4 py-3">
    <div className="flex flex-wrap items-end gap-3">
      <div className="grid min-w-56 max-w-lg flex-1 gap-1"><Label htmlFor={id}>{zh ? '残基选择（作者编号）' : 'Residue selection (author numbering)'}</Label><Input id={id} value={input} placeholder="A:56, A:57, A:115" onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void apply() }} /></div>
      <div className="flex h-9 items-center gap-2 text-xs text-text-secondary"><Checkbox id={`${id}-sidechains`} aria-label={zh ? '仅侧链' : 'Side chains only'} checked={sideChains} onCheckedChange={setSideChains} /><Label htmlFor={`${id}-sidechains`}>{zh ? '仅侧链' : 'Side chains only'}</Label></div>
      <Button type="button" size="sm" disabled={disabled || busy || !input.trim()} onClick={() => void apply()}>{zh ? '高亮并聚焦' : 'Highlight & focus'}</Button>
      <Button type="button" size="sm" variant="outline" disabled={disabled || busy} onClick={() => void apply(true)}>{zh ? '清除选择' : 'Clear selection'}</Button>
    </div>
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary"><p aria-live="polite">{message || (zh ? '保留蛋白骨架作为背景，选择的原子以球棍模型显示。' : 'Selected atoms appear as ball-and-stick within the protein context.')}</p><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#e83e9b]" />{zh ? '洋红色：已选原子' : 'Magenta: selected atoms'}</span></div>
    {error ? <p role="alert" className="mt-2 text-xs text-danger">{error}</p> : null}
  </div>
}
