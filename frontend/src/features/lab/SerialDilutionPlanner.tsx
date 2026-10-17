"use no memo"

import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table'
import { useI18n } from '../../lib/i18n'
import { parseBenchNumber } from './toolCatalog'
import { planDilutionSeries } from '../../lib/api/wetlab'
import { DataGrid, DataGridContainer } from '../../components/reui/data-grid/data-grid'
import { DataGridColumnHeader } from '../../components/reui/data-grid/data-grid-column-header'
import { DataGridScrollArea } from '../../components/reui/data-grid/data-grid-scroll-area'
import { DataGridTable } from '../../components/reui/data-grid/data-grid-table'
import { Frame, FrameHeader, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'

function NumberField({ label, value, onChange, min = 0, max, step = 'any' }: {
  label: string; value: string; onChange: (next: string) => void; min?: number; max?: number; step?: string
}) {
  return <label className="flex flex-col gap-1 text-sm"><span>{label}</span><Input type="number" required min={min} max={max} step={step} className="w-40 tabular-nums" value={value} onChange={(event) => onChange(event.target.value)} /></label>
}

function display(value: number): string {
  // Preserve small calculated transfers; display rounding is not pipette precision.
  return Number.isFinite(value) ? String(Number(value.toPrecision(8))) : '—'
}

/** Standalone server-calculated serial plan; it creates no project records. */
export function SerialDilutionPlanner({ hideTitle = false }: { hideTitle?: boolean }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [stock, setStock] = useState('100')
  const [start, setStart] = useState('50')
  const [factor, setFactor] = useState('2')
  const [steps, setSteps] = useState('6')
  const [perWell, setPerWell] = useState('200')
  const [dead, setDead] = useState('20')
  const dilution = useMutation({ mutationFn: async () => {
    const request = { stock_conc_uM: parseBenchNumber(stock), start_conc_uM: parseBenchNumber(start), dilution_factor: parseBenchNumber(factor), n_steps: parseBenchNumber(steps), vol_per_well_uL: parseBenchNumber(perWell), extra_dead_vol_uL: parseBenchNumber(dead) }
    return { result: await planDilutionSeries(request), request }
  } })
  const rows = useMemo(() => dilution.data?.result.steps.map((step, index, all) => {
    const onward = all[index + 1]?.stock_vol_uL ?? 0
    return { ...step, sourceStep: index === 0 ? null : all[index - 1].step, onward, retained: step.total_vol_uL - onward, dead: dilution.data!.request.extra_dead_vol_uL }
  }) ?? [], [dilution.data])
  const columns = useMemo<ColumnDef<(typeof rows)[number]>[]>(() => {
    const number = (id: string, title: string, read: (row: (typeof rows)[number]) => number, size = 150): ColumnDef<(typeof rows)[number]> => ({
      id, header: ({ column }) => <DataGridColumnHeader column={column} title={title} />, cell: ({ row }) => <span className="tabular-nums">{display(read(row.original))}</span>, size,
    })
    return [
      number('step', zh ? '管序号' : 'Tube', (row) => row.step, 80),
      number('concentration', zh ? '浓度 (µM)' : 'Concentration (µM)', (row) => row.conc_uM),
      { id: 'source', header: ({ column }) => <DataGridColumnHeader column={column} title={zh ? '取样来源' : 'Source'} />, cell: ({ row }) => row.original.sourceStep === null ? (zh ? '原液' : 'Stock solution') : (zh ? `第 ${row.original.sourceStep} 管` : `Tube ${row.original.sourceStep}`), size: 130 },
      number('source_volume', zh ? '从来源取用 (µL)' : 'Take from source (µL)', (row) => row.stock_vol_uL, 175),
      number('buffer', zh ? '加入缓冲液 (µL)' : 'Add buffer (µL)', (row) => row.buffer_vol_uL),
      number('total', zh ? '本管配制总量 (µL)' : 'Prepared total (µL)', (row) => row.total_vol_uL, 170),
      number('onward', zh ? '转入下一管 (µL)' : 'Transfer onward (µL)', (row) => row.onward, 175),
      number('retained', zh ? '转移后留存 (µL)' : 'Retained after transfer (µL)', (row) => row.retained, 205),
      number('dead', zh ? '留存中预留死体积 (µL)' : 'Dead reserve within retained (µL)', (row) => row.dead, 240),
    ]
  }, [zh])
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), getRowId: (row) => String(row.step) })

  return <Frame dense>
    {!hideTitle ? <FrameHeader><FrameTitle>{zh ? '串联稀释计划' : 'Serial dilution planner'}</FrameTitle></FrameHeader> : null}
    <div className="space-y-4 p-4">
      <p className="max-w-3xl text-sm text-text-secondary">{zh ? '第一管取原液，之后各管从前一管取样。混匀后再转入下一管；各管配制量可能不同，须同时满足实验用量、死体积及下一级转移量。' : 'Prepare tube 1 from stock, then each tube from the preceding tube. Mix before transferring onward. Prepared volumes can differ to cover use, dead volume and the next transfer.'}</p>
      <form onChange={() => dilution.reset()} onSubmit={(event) => { event.preventDefault(); dilution.mutate() }}>
        <fieldset disabled={dilution.isPending} className="flex flex-wrap items-end gap-3">
          <NumberField label={zh ? '原液浓度 (µM)' : 'Stock concentration (µM)'} value={stock} onChange={setStock} />
          <NumberField label={zh ? '第一管浓度 (µM)' : 'First tube concentration (µM)'} value={start} onChange={setStart} />
          <NumberField label={zh ? '稀释倍数 (>1)' : 'Dilution factor (>1)'} value={factor} onChange={setFactor} min={1} />
          <NumberField label={zh ? '管数 (1–24)' : 'Tube count (1–24)'} value={steps} onChange={setSteps} min={1} max={24} step="1" />
          <NumberField label={zh ? '每管实验用量 (µL)' : 'Use per tube (µL)'} value={perWell} onChange={setPerWell} />
          <NumberField label={zh ? '每管预留死体积 (µL)' : 'Dead reserve per tube (µL)'} value={dead} onChange={setDead} />
          <Button type="submit" disabled={dilution.isPending}>{dilution.isPending ? (zh ? '计算中…' : 'Calculating…') : (zh ? '生成稀释计划' : 'Plan dilution')}</Button>
        </fieldset>
      </form>
      {dilution.error ? <p role="alert" className="text-sm text-destructive">{dilution.error instanceof Error ? dilution.error.message : String(dilution.error)}</p> : null}
      {rows.length && dilution.data ? <section className="space-y-3" aria-label={zh ? '串联稀释步骤' : 'Serial dilution steps'}>
        <p className="text-sm">{zh ? `每管转移后至少留存 ${display(dilution.data.request.vol_per_well_uL)} µL 实验用量 + ${display(dilution.data.request.extra_dead_vol_uL)} µL 死体积。留存量包含死体积，最后一管无需继续转移。` : `After transfer, each tube must retain at least ${display(dilution.data.request.vol_per_well_uL)} µL for use + ${display(dilution.data.request.extra_dead_vol_uL)} µL dead reserve. Retained volume includes that reserve; the final tube has no onward transfer.`}</p>
        <DataGrid table={table} recordCount={rows.length} tableLayout={{ dense: true, headerBackground: true, headerBorder: true, rowBorder: true, width: 'auto' }}><DataGridContainer><DataGridScrollArea orientation="horizontal"><DataGridTable /></DataGridScrollArea></DataGridContainer></DataGrid>
        <p className="text-xs text-text-secondary">{zh ? '配制总量按服务端规划保留余量；显示精度不代表移液器精度。执行前核对最小取用量与实际量程。此计划不保存到项目。' : 'The server plan retains preparation margin. Display precision does not imply pipette precision; check the smallest transfer against the actual working range. This plan is not saved to a project.'}</p>
      </section> : null}
    </div>
  </Frame>
}
