import { useState } from 'react'
import { EyeIcon, EyeSlashIcon } from '@phosphor-icons/react'
import { Input } from './Input'
import { Label } from './label'
import { Button } from './Button'
import { useAccountText } from '@/lib/auth/accountText'

export function PasswordField({ id, label, value, onChange, autoComplete = 'new-password' }: {
  id: string; label: string; value: string; onChange: (value: string) => void; autoComplete?: string
}) {
  const [visible, setVisible] = useState(false)
  const t = useAccountText()
  return <div className="grid gap-2">
    <Label htmlFor={id}>{label}</Label>
    <div className="relative">
      <Input id={id} type={visible ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)} autoComplete={autoComplete} required maxLength={256} className="pr-11" />
      <Button type="button" variant="ghost" size="icon-sm" className="absolute right-1 top-1" aria-label={visible ? t.hidePassword : t.showPassword} aria-pressed={visible} onClick={() => setVisible(!visible)}>
        {visible ? <EyeSlashIcon aria-hidden="true" /> : <EyeIcon aria-hidden="true" />}
      </Button>
    </div>
  </div>
}
