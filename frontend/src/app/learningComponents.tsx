import { Children, isValidElement, useState, type ReactNode } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { DataGrid } from '../components/reui/data-grid/data-grid'
import { DataGridTable } from '../components/reui/data-grid/data-grid-table'
import { Disclosure } from '../components/ui/Disclosure'

export function Choice({ children, name, value, onChange, required, disabled }: {
  children: ReactNode; name?: string; value?: string; required?: boolean; disabled?: boolean;
  onChange?: (event: { target: { value: string } }) => void;
}) {
  const options = Children.toArray(children).filter(isValidElement<{ value?: string; children: ReactNode }>).map((child) => ({
    value: child.props.value ?? String(child.props.children), label: child.props.children,
  }))
  const [chosen, setChosen] = useState('')
  const selected = value ?? (options.some((o) => o.value === chosen) ? chosen : options[0]?.value ?? '')
  return <Select name={name} required={required} disabled={disabled} value={selected} onValueChange={(next) => {
    if (next === null) return
    setChosen(next); onChange?.({ target: { value: next } })
  }} items={options}>
    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
    <SelectContent>{options.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
  </Select>
}

export function LearningTable({ headings, cells }: { headings: string[]; cells: ReactNode[][] }) {
  const table = useReactTable<ReactNode[]>({ data: cells, columns: headings.map((header, index) => ({
    id: String(index), header, cell: ({ row }) => row.original[index],
  })), getCoreRowModel: getCoreRowModel() })
  return <DataGrid table={table} recordCount={cells.length}><DataGridTable /></DataGrid>
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="learning-field"><span>{label}</span>{children}</label>
}
export function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="learning-section"><h2 id={`learning-step-${title.slice(0, 2)}`} tabIndex={-1}>{title}</h2>{children}</section>
}
export function JsonDetails({ label, data }: { label: string; data: unknown }) {
  return <Disclosure className="learning-details" title={label}><pre>{JSON.stringify(data, null, 2)}</pre></Disclosure>
}
