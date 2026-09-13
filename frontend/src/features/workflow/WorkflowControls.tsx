import { Children, isValidElement, type ReactNode } from 'react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'

/** Small adapters keep policy forms on the application's accessible registry controls. */
export function WorkflowSection({
  title,
  children,
  className,
}: {
  title: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Accordion className={className} multiple>
      <AccordionItem value="section">
        <AccordionTrigger>{title}</AccordionTrigger>
        <AccordionContent>{children}</AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
export function WorkflowOption(_props: {
  value?: string
  disabled?: boolean
  children: ReactNode
}) {
  void _props
  return null
}
export function WorkflowSelect({
  value,
  onChange,
  children,
  className,
  disabled,
  'aria-label': label,
}: {
  value: string
  onChange: (e: { target: { value: string } }) => void
  children: ReactNode
  className?: string
  disabled?: boolean
  'aria-label'?: string
}) {
  const options = Children.toArray(children)
    .filter(isValidElement<{ value?: string; disabled?: boolean; children: ReactNode }>)
    .map((element) => ({
      value: element.props.value ?? String(element.props.children),
      disabled: element.props.disabled,
      label: element.props.children,
    }))
  const placeholder = options.find((o) => o.value === '')?.label
  return (
    <Select
      value={value}
      disabled={disabled}
      onValueChange={(next) => onChange({ target: { value: next ?? '' } })}
    >
      <SelectTrigger aria-label={label} className={className}>
        <SelectValue placeholder={placeholder}>{options.find((o) => o.value === value)?.label}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
            <SelectItem key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  )
}
