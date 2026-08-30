"use no memo"

import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'
import { useI18n } from '../../lib/i18n'
import { computeConcentration, convertUnits, planDilutionSeries } from '../../lib/api/wetlab'
import type { DilutionStepRead } from '../../lib/api/generated/types.gen'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { Frame, FrameHeader, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'

const UNITS = ['M', 'uM', 'nM', 'mg/mL', 'ug/mL', 'ng/uL'] as const

function NumberField({
  label,
  value,
  onChange,
  step = 'any',
}: {
  label: string
  value: string
  onChange: (next: string) => void
  step?: string
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span>{label}</span>
      <Input
        type="number"
        step={step}
        className="w-36 tabular-nums"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function UnitSelect({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (next: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span>{label}</span>
      <Select value={value} onValueChange={(next) => onChange(next ?? value)}>
        <SelectTrigger aria-label={label} className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {UNITS.map((unit) => (
            <SelectItem key={unit} value={unit}>
              {unit}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  )
}

/**
 * The three calculations a run starts from.
 *
 * Each calls a pure server function rather than repeating the arithmetic here.
 * protein-lab kept a line-by-line mirror of its unit kernel in the frontend and
 * had to keep both in step by hand; one implementation means one source of
 * rounding, and the numbers in a saved experiment match what the screen showed.
 */
export function BenchCalculators({ projectId }: { projectId: string }) {
  const { t } = useI18n()
  const copy = t.lab.bench

  const [a280, setA280] = useState('1.0')
  const [epsilon, setEpsilon] = useState('10000')
  const [mass, setMass] = useState('12000')
  const [pathLength, setPathLength] = useState('1')

  const concentration = useMutation({
    mutationFn: () =>
      computeConcentration(projectId, {
        a280: Number(a280),
        ext_coeff: Number(epsilon),
        molecular_weight: Number(mass),
        path_length_cm: Number(pathLength),
      }),
  })

  const [value, setValue] = useState('1')
  const [fromUnit, setFromUnit] = useState<string>('mg/mL')
  const [toUnit, setToUnit] = useState<string>('uM')
  const [conversionMass, setConversionMass] = useState('12000')

  const conversion = useMutation({
    mutationFn: () =>
      convertUnits({
        value: Number(value),
        from_unit: fromUnit,
        to_unit: toUnit,
        molecular_weight: Number(conversionMass) || undefined,
      }),
  })

  const [stock, setStock] = useState('100')
  const [start, setStart] = useState('50')
  const [factor, setFactor] = useState('2')
  const [steps, setSteps] = useState('6')
  const [perWell, setPerWell] = useState('200')
  const [dead, setDead] = useState('20')

  const dilution = useMutation({
    mutationFn: () =>
      planDilutionSeries({
        stock_conc_uM: Number(stock),
        start_conc_uM: Number(start),
        dilution_factor: Number(factor),
        n_steps: Number(steps),
        vol_per_well_uL: Number(perWell),
        extra_dead_vol_uL: Number(dead),
      }),
  })

  const dilutionRows = useMemo(() => dilution.data?.steps ?? [], [dilution.data])

  const dilutionColumns = useMemo<ColumnDef<DilutionStepRead>[]>(
    () => [
      {
        id: 'step',
        accessorKey: 'step',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.step} />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.step}</span>,
        size: 80,
      },
      {
        id: 'conc',
        accessorKey: 'conc_uM',
        header: ({ column }) => <DataGridColumnHeader column={column} title="µM" />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.conc_uM}</span>,
        size: 110,
      },
      {
        id: 'stock',
        accessorKey: 'stock_vol_uL',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.stock} />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.stock_vol_uL}</span>,
        size: 130,
      },
      {
        id: 'buffer',
        accessorKey: 'buffer_vol_uL',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.bufferVolume} />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.buffer_vol_uL}</span>,
        size: 130,
      },
      {
        id: 'total',
        accessorKey: 'total_vol_uL',
        header: ({ column }) => <DataGridColumnHeader column={column} title={copy.totalVolume} />,
        cell: ({ row }) => <span className="tabular-nums">{row.original.total_vol_uL}</span>,
        size: 130,
      },
    ],
    [copy],
  )

  const dilutionTable = useReactTable({
    data: dilutionRows,
    columns: dilutionColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => String(row.step),
  })

  return (
    <Frame dense>
      <FrameHeader>
        <FrameTitle>{copy.title}</FrameTitle>
      </FrameHeader>

      <div className="space-y-6 p-4">
        <section aria-label={copy.concentration} className="space-y-3">
          <h3 className="text-sm font-medium">{copy.concentration}</h3>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              concentration.mutate()
            }}
          >
            <NumberField label={copy.a280} value={a280} onChange={setA280} />
            <NumberField label="ε" value={epsilon} onChange={setEpsilon} />
            <NumberField label={copy.molecularWeight} value={mass} onChange={setMass} />
            <NumberField label={copy.pathLength} value={pathLength} onChange={setPathLength} />
            <Button type="submit" disabled={concentration.isPending}>
              {copy.compute}
            </Button>
          </form>
          {concentration.data ? (
            <p className="text-sm tabular-nums">
              {concentration.data.molar_conc_uM} µM · {concentration.data.mass_conc_mg_mL} mg/mL
            </p>
          ) : null}
          {concentration.error ? (
            <p role="alert" className="text-sm text-destructive">
              {(concentration.error as Error).message}
            </p>
          ) : null}
        </section>

        <section aria-label={copy.units} className="space-y-3">
          <h3 className="text-sm font-medium">{copy.units}</h3>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              conversion.mutate()
            }}
          >
            <NumberField label={copy.value} value={value} onChange={setValue} />
            <UnitSelect label={copy.from} value={fromUnit} onChange={setFromUnit} />
            <UnitSelect label={copy.to} value={toUnit} onChange={setToUnit} />
            {/* Only molar <-> mass needs a mass. The server decides which pairs
                those are and says so, rather than this form second-guessing it. */}
            <NumberField
              label={copy.molecularWeight}
              value={conversionMass}
              onChange={setConversionMass}
            />
            <Button type="submit" disabled={conversion.isPending}>
              {copy.convert}
            </Button>
          </form>
          {conversion.data ? (
            <p className="text-sm tabular-nums">
              {conversion.data.value} {conversion.data.unit}
            </p>
          ) : null}
          {conversion.error ? (
            <p role="alert" className="text-sm text-destructive">
              {(conversion.error as Error).message}
            </p>
          ) : null}
        </section>

        <section aria-label={copy.dilution} className="space-y-3">
          <h3 className="text-sm font-medium">{copy.dilution}</h3>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              dilution.mutate()
            }}
          >
            <NumberField label={copy.stock} value={stock} onChange={setStock} />
            <NumberField label={copy.start} value={start} onChange={setStart} />
            <NumberField label={copy.factor} value={factor} onChange={setFactor} />
            <NumberField label={copy.steps} value={steps} onChange={setSteps} step="1" />
            <NumberField label={copy.perWell} value={perWell} onChange={setPerWell} />
            <NumberField label={copy.deadVolume} value={dead} onChange={setDead} />
            <Button type="submit" disabled={dilution.isPending}>
              {copy.plan}
            </Button>
          </form>
          {dilution.error ? (
            <p role="alert" className="text-sm text-destructive">
              {(dilution.error as Error).message}
            </p>
          ) : null}
          {dilutionRows.length > 0 ? (
            <DataGrid
              table={dilutionTable}
              recordCount={dilutionRows.length}
              tableLayout={{
                dense: true,
                headerBackground: true,
                headerBorder: true,
                rowBorder: true,
                width: 'auto',
              }}
            >
              <DataGridContainer>
                <DataGridScrollArea orientation="horizontal">
                  <DataGridTable />
                </DataGridScrollArea>
              </DataGridContainer>
            </DataGrid>
          ) : null}
        </section>
      </div>
    </Frame>
  )
}
