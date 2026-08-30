import { useMemo } from 'react'
import { parseParameterSchema, type ParameterFieldDefinition } from '../../lib/forms/parameterSchema'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Checkbox } from '../../components/ui/checkbox'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
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
import { Textarea } from '../../components/ui/textarea'

interface ParameterSchemaFormProps {
  schema: unknown
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
  disabled?: boolean
}

function optionValue(option: string | { label: string; value: string }) {
  return typeof option === 'string' ? option : option.value
}

function optionLabel(option: string | { label: string; value: string }) {
  return typeof option === 'string' ? option : option.label
}

export function ParameterSchemaForm({ schema, values, onChange, disabled = false }: ParameterSchemaFormProps) {
  const { t } = useI18n()
  const fields = useMemo(() => parseParameterSchema(schema), [schema])

  if (fields.length === 0) {
    return (
      <Alert>
        <AlertDescription>{t.plugins.parameterSchema.noSchema}</AlertDescription>
      </Alert>
    )
  }

  const basicFields = fields.filter((field) => !field.advanced)
  const advancedFields = fields.filter((field) => field.advanced)

  const renderField = (field: ParameterFieldDefinition) => (
    <ParameterField
      key={field.key}
      field={field}
      value={values[field.key] ?? field.default ?? ''}
      changed={values[field.key] !== undefined && values[field.key] !== field.default}
      onChange={(value) => onChange({ ...values, [field.key]: value })}
      disabled={disabled}
    />
  )

  return (
    <div className="space-y-3">
      {basicFields.map(renderField)}
      {advancedFields.length > 0 ? (
        <Accordion className="rounded-md border border-border-soft bg-bg-app">
          <AccordionItem value="advanced-parameters" className="border-0">
            <AccordionTrigger className="px-3">
              {t.plugins.parameterSchema.advancedParameters}
            </AccordionTrigger>
            <AccordionContent className="space-y-3 px-3 pb-3">
              {advancedFields.map(renderField)}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      ) : null}
    </div>
  )
}

function ParameterField({
  field,
  value,
  changed,
  onChange,
  disabled,
}: {
  field: ParameterFieldDefinition
  value: unknown
  changed: boolean
  onChange: (value: unknown) => void
  disabled: boolean
}) {
  const { t } = useI18n()
  const label = field.label ?? field.key
  const id = `param-${field.key}`

  return (
    <div className="block">
      <Label htmlFor={id} className="flex items-center justify-between gap-2">
        <span>
          {label}
          {field.required ? (
            <span className="ml-1 text-danger" title={t.plugins.parameterSchema.required}>
              *
            </span>
          ) : null}
        </span>
        {changed ? <span className="text-[10px] uppercase text-accent">{t.plugins.parameterSchema.changed}</span> : null}
      </Label>
      <FieldControl id={id} field={field} value={value} onChange={onChange} disabled={disabled} />
      {field.help ? <span className="mt-1 block text-xs leading-relaxed text-text-secondary">{field.help}</span> : null}
    </div>
  )
}

function FieldControl({
  id,
  field,
  value,
  onChange,
  disabled,
}: {
  id: string
  field: ParameterFieldDefinition
  value: unknown
  onChange: (value: unknown) => void
  disabled: boolean
}) {
  if (field.type === 'boolean') {
    return (
      <Checkbox
        id={id}
        className="mt-2"
        checked={Boolean(value)}
        disabled={disabled}
        onCheckedChange={(checked) => onChange(checked === true)}
      />
    )
  }

  if (field.type === 'enum') {
    return (
      <Select value={String(value ?? '')} onValueChange={(nextValue) => onChange(nextValue ?? '')} disabled={disabled}>
        <SelectTrigger id={id} className="mt-1 w-full" disabled={disabled}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((option) => (
            <SelectItem key={optionValue(option)} value={optionValue(option)}>
              {optionLabel(option)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  if (field.type === 'json') {
    return (
      <Textarea
        id={id}
        className="mt-1 min-h-24 font-mono text-xs"
        value={typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2)}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  // Sequences, SMILES and residue lists run to hundreds of characters; a single-line
  // input hides all but the tail of what the scientist is checking.
  if (field.type === 'textarea') {
    return (
      <Textarea
        id={id}
        className="mt-1 min-h-16 font-mono text-xs"
        value={String(value ?? '')}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    )
  }

  if (field.type === 'integer' || field.type === 'number') {
    return (
      <Input
        id={id}
        type="number"
        className="mt-1"
        min={field.min}
        max={field.max}
        step={field.type === 'integer' ? 1 : 'any'}
        value={Number(value)}
        disabled={disabled}
        onChange={(event) => onChange(field.type === 'integer' ? Number.parseInt(event.target.value, 10) : Number(event.target.value))}
      />
    )
  }

  return (
    <Input
      id={id}
      type="text"
      className="mt-1"
      value={String(value ?? '')}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
