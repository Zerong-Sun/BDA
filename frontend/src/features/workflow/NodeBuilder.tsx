import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CaretDown, Check, Plus, SpinnerGap } from '@phosphor-icons/react'
import { DefaultNodeIcon, nodeIconMap, type NodeIconName } from './nodeIcons'
import { nodeTemplates, type NodeTemplate } from './workflowTypes'
import { createMethodPlugin, listMethodPlugins, listModelPlugins } from '../../lib/api/registry'
import { ParameterSchemaForm } from '../plugins'
import {
  defaultsFromFields,
  fieldsFromParameterSchema,
  parseParameterSchemaMetadata,
  type ParameterSchemaMetadata,
} from '../../lib/forms/parameterSchema'
import type { MethodPlugin, ModelPlugin } from '../../lib/schemas/registry'
import type { WorkflowNodeData } from './workflowTypes'
import { useI18n } from '../../lib/i18n'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { Checkbox } from '../../components/ui/checkbox'
import { Input } from '../../components/ui/Input'
import { ScrollArea } from '../../components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet'
import { Textarea } from '../../components/ui/textarea'

const PLUGIN_ICON: Record<string, string> = {
  RFdiffusion: 'wand-sparkles',
  ProteinMPNN: 'dna',
  AlphaFold2: 'scan-search',
  'AlphaFold 3': 'scan-search',
  Boltz: 'scan-search',
  'Chai-1': 'scan-search',
  Rosetta: 'activity',
  BindCraft: 'wand-sparkles',
}

function workflowNodeTypeForPlugin(plugin: ModelPlugin) {
  if (plugin.name === 'RFdiffusion') return 'backbone_generation'
  if (plugin.name === 'ProteinMPNN') return 'sequence_generation'
  if (plugin.name === 'AlphaFold2') return 'fold_prediction'
  if (plugin.name === 'AlphaFold 3') return 'fold_prediction'
  if (plugin.name === 'Boltz') return 'fold_prediction'
  if (plugin.name === 'Chai-1') return 'fold_prediction'
  if (plugin.name === 'BindCraft') return 'workflow_pipeline'
  if (plugin.name === 'Rosetta') return 'scoring'
  return plugin.plugin_key
}

const PLUGIN_LABELS: Record<string, string> = {
  plugin_rfdiffusion: 'RFdiffusion',
  plugin_proteinmpnn: 'ProteinMPNN',
  plugin_alphafold2: 'AlphaFold2',
  plugin_alphafold3: 'AlphaFold 3',
  plugin_boltz: 'Boltz',
  plugin_chai1: 'Chai-1',
  plugin_bindcraft: 'BindCraft',
  plugin_rosetta: 'Rosetta',
}

function parseJsonRecord(value: unknown): Record<string, unknown> {
  if (!value) return {}
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {}
    } catch {
      return {}
    }
  }
  return typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function resourceForPlugin(plugin: ModelPlugin): WorkflowNodeData['resource'] {
  const schemaMetadata = parseJsonRecord(plugin.parameter_schema.metadata)
  const resource = String(schemaMetadata.resource ?? plugin.plugin_key).toLowerCase()
  if (resource.includes('gpu') || resource.includes('pipeline')) {
    return 'gpu'
  }
  return resource.includes('manual') ? 'manual' : 'cpu'
}

function methodValue(method: MethodPlugin, key: string): unknown {
  return method.specification[key]
}

function methodString(method: MethodPlugin, key: string): string | undefined {
  const value = methodValue(method, key)
  return typeof value === 'string' ? value : undefined
}

function formatPluginList(pluginIds?: string[]): string | null {
  if (!pluginIds?.length) return null
  return pluginIds.map((id) => PLUGIN_LABELS[id] ?? id.replace(/^plugin_/, '')).join(' / ')
}

function ChainMetadata({
  metadata,
  labels,
}: {
  metadata: ParameterSchemaMetadata
  labels: { exclusiveWith: string; recommendedAfter: string; recommendedBefore: string }
}) {
  const rows = [
    [labels.exclusiveWith, formatPluginList(metadata.exclusiveWith)],
    [labels.recommendedAfter, formatPluginList(metadata.recommendedAfter)],
    [labels.recommendedBefore, formatPluginList(metadata.recommendedBefore)],
  ].filter((row): row is [string, string] => Boolean(row[1]))

  if (!metadata.workflowNote && rows.length === 0) return null

  return (
    <div className="mt-2 rounded-md border border-accent-2/40 bg-accent-2/10 p-2 text-xs leading-relaxed text-accent-2">
      {metadata.workflowNote ? <p>{metadata.workflowNote}</p> : null}
      {rows.length > 0 ? (
        <dl className="mt-1 space-y-1">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-[4.5rem_1fr] gap-2">
              <dt className="text-text-secondary">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  )
}

/** Column heading used across the three builder panes so they share one rhythm. */
function SectionLabel({ id, children, hint }: { id?: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2">
      <span id={id} className="text-xs font-medium uppercase tracking-wide text-text-secondary">
        {children}
      </span>
      {hint ? <span className="shrink-0 text-[11px] text-text-muted">{hint}</span> : null}
    </div>
  )
}

function NodeGlyph({ icon, active = false }: { icon?: string; active?: boolean }) {
  const Icon = nodeIconMap[icon as NodeIconName] ?? DefaultNodeIcon
  return (
    <span
      aria-hidden
      className={`flex size-8 shrink-0 items-center justify-center rounded-md border bg-surface-1 ${
        active ? 'border-accent-border text-accent' : 'border-border-soft text-text-secondary'
      }`}
    >
      <Icon className="size-4" />
    </span>
  )
}

interface NodeBuilderProps {
  open: boolean
  onClose: () => void
  onAdd: (
    template: NodeTemplate,
    nodeName: string,
    methods: string[],
    parameters: Record<string, unknown>,
  ) => Promise<void>
}

export function NodeBuilder({ open, onClose, onAdd }: NodeBuilderProps) {
  const { t, format } = useI18n()
  const [selected, setSelected] = useState('rf')
  const [methods, setMethods] = useState<string[]>(['Affinity score', 'Diversity cap', 'Auto report'])
  const [nodeName, setNodeName] = useState('')
  const [parameters, setParameters] = useState<Record<string, unknown>>({})
  const [adding, setAdding] = useState(false)
  const [nameError, setNameError] = useState('')
  const [newMethodName, setNewMethodName] = useState('')
  const [newMethodType, setNewMethodType] = useState('custom')
  const [newMethodDescription, setNewMethodDescription] = useState('')
  const [methodFormOpen, setMethodFormOpen] = useState(false)
  const methodDefaultsApplied = useRef<string | null>(null)
  const queryClient = useQueryClient()

  const { data: plugins = [] } = useQuery({
    queryKey: ['model-plugins'],
    queryFn: listModelPlugins,
  })

  const { data: methodPlugins = [] } = useQuery<MethodPlugin[]>({
    queryKey: ['method-plugins'],
    queryFn: listMethodPlugins,
  })

  const methodOptions =
    methodPlugins.length > 0
      ? methodPlugins.map((mp) => ({
          key: mp.id,
          label: mp.name,
          description: methodString(mp, 'description'),
          method: mp,
        }))
      : Object.keys(t.nodeBuilder.methodOptions).map((key) => ({
          key,
          label: t.nodeBuilder.methodOptions[key as keyof typeof t.nodeBuilder.methodOptions] ?? key,
          description: undefined as string | undefined,
          method: undefined as MethodPlugin | undefined,
        }))

  // Defaults are re-seeded whenever the option list itself changes, not just once:
  // the built-in fallback renders first and is replaced when method plugins load,
  // and the old selection keys do not survive that swap. Keying on the option list
  // keeps the user's own picks (same signature => no re-seed) while making sure the
  // panel never opens with an empty, un-submittable method list.
  useEffect(() => {
    if (!open) {
      methodDefaultsApplied.current = null
      return
    }
    if (methodOptions.length === 0) return
    const optionKeys = methodOptions.map((method) => method.key)
    const signature = optionKeys.join('|')
    if (methodDefaultsApplied.current === signature) return
    methodDefaultsApplied.current = signature
    const valid = new Set(optionKeys)
    setMethods((current) => {
      const validCurrent = current.filter((method) => valid.has(method))
      return validCurrent.length > 0 ? validCurrent : optionKeys.slice(0, 3)
    })
  }, [methodOptions, open])

  const activeMethodKeys = methods.filter((method) => methodOptions.some((option) => option.key === method))
  const selectedMethodOptions = methodOptions.filter((method) => activeMethodKeys.includes(method.key))

  const createMethod = useMutation({
    mutationFn: () =>
      createMethodPlugin({
        method_name: newMethodName.trim(),
        method_type: newMethodType.trim() || 'custom',
        description: newMethodDescription.trim() || null,
        compatible_model_types: template.modelName ? [template.modelName] : [],
        compatible_workflow_nodes: [template.nodeType],
        default_parameters_json: {},
        status: 'active',
      }),
    onSuccess: async (method) => {
      setNewMethodName('')
      setNewMethodType('custom')
      setNewMethodDescription('')
      setMethodFormOpen(false)
      setMethods((prev) => Array.from(new Set([...prev, method.id])))
      await queryClient.invalidateQueries({ queryKey: ['method-plugins'] })
    },
  })

  const templates = useMemo(() => {
    return plugins.filter((plugin) => plugin.enabled).map((plugin) => ({
      id: plugin.id,
      icon: PLUGIN_ICON[plugin.name] ?? 'activity',
      title: plugin.name,
      body: format(t.nodeBuilder.modelPluginFallback, { modelType: plugin.plugin_key }),
      resource: resourceForPlugin(plugin),
      nodeType: workflowNodeTypeForPlugin(plugin),
      modelName: plugin.name,
      modelVersion: plugin.plugin_version,
      pluginId: plugin.id,
      parameterSchema: plugin.parameter_schema,
    }))
  }, [plugins, t.nodeBuilder.modelPluginFallback, format])

  const template = templates.find((item) => item.id === selected) ?? templates[0] ?? nodeTemplates.rf
  const parameterFields = useMemo(
    () => fieldsFromParameterSchema(template.parameterSchema, template.modelName),
    [template.modelName, template.parameterSchema],
  )
  const parameterMetadata = useMemo(
    () => parseParameterSchemaMetadata(template.parameterSchema),
    [template.parameterSchema],
  )
  const parameterSchemaForForm = useMemo(() => ({ fields: parameterFields }), [parameterFields])

  const selectTemplate = (item: NodeTemplate) => {
    setSelected(item.id)
    setNodeName(item.title)
    setParameters(defaultsFromFields(fieldsFromParameterSchema(item.parameterSchema, item.modelName)))
    setNameError('')
  }

  const handleAdd = async () => {
    const trimmedName = nodeName.trim()
    if (!trimmedName) {
      setNameError(t.nodeBuilder.nameRequired)
      return
    }
    if (selectedMethodOptions.length === 0) return
    setNameError('')
    setAdding(true)
    try {
      const methodRefs = selectedMethodOptions.map((method) => {
        if (method.method) {
          const defaults = methodValue(method.method, 'default_parameters')
          return {
            method_plugin_id: method.method.id,
            method_name: method.method.name,
            method_type: methodString(method.method, 'method_type') ?? method.method.plugin_key,
            default_parameters:
              defaults && typeof defaults === 'object' ? defaults : {},
          }
        }
        return {
          method_plugin_id: null,
          method_name: method.label,
          method_type: 'built_in',
          default_parameters: {},
        }
      })
      await onAdd(template, trimmedName, selectedMethodOptions.map((method) => method.label), {
        ...defaultsFromFields(parameterFields),
        ...parameters,
        method_refs: methodRefs,
      })
    } finally {
      setAdding(false)
    }
  }

  const handleClose = () => {
    if (adding) return
    setNodeName('')
    setParameters({})
    setNameError('')
    setMethodFormOpen(false)
    onClose()
  }

  return (
    <Sheet open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <SheetContent
        side="right"
        className="w-[min(96vw,76rem)] sm:max-w-none"
        showCloseButton={!adding}
      >
      <SheetHeader className="border-b border-border-soft">
          <p className="text-xs uppercase tracking-wide text-accent">{t.nodeBuilder.cardEyebrow}</p>
          <SheetTitle className="text-base">{t.nodeBuilder.cardTitle}</SheetTitle>
          <SheetDescription>{t.nodeBuilder.subtitle}</SheetDescription>
      </SheetHeader>

      <ScrollArea className="min-h-0 flex-1">
      <div className="grid gap-5 p-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Model cards */}
        <section aria-labelledby="node-builder-models">
          <SectionLabel id="node-builder-models" hint={templates.length || undefined}>
            {t.nodeBuilder.modelCards}
          </SectionLabel>
          {templates.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border-soft px-3 py-6 text-center text-xs text-text-secondary">
              {t.nodeBuilder.noModels}
            </p>
          ) : (
            <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(14rem,1fr))]">
              {/* Auto-fill rather than a viewport breakpoint: the column count follows the
                  space this pane actually has, so cards never squeeze below a readable width. */}
              {templates.map((item) => {
                const metadata = parseParameterSchemaMetadata(item.parameterSchema)
                const isSelected = template.id === item.id
                return (
                  <Button type="button"
                    key={item.id}
                    variant="outline"
                    aria-pressed={isSelected}
                    className={`h-auto w-full flex-col items-stretch justify-start gap-2 rounded-lg border p-3 text-left whitespace-normal transition-colors ${
                      isSelected
                        ? 'border-accent-border bg-accent-bg hover:bg-accent-bg'
                        : 'border-border-soft hover:border-border-default'
                    }`}
                    onClick={() => {
                      selectTemplate(item)
                    }}
                    disabled={adding}
                  >
                    <span className="flex items-start gap-2">
                      <NodeGlyph icon={item.icon} active={isSelected} />
                      <span className="min-w-0 flex-1">
                        <strong className="line-clamp-2 block text-sm text-text-primary" title={item.title}>
                          {item.title}
                        </strong>
                        <span className="mt-1 flex flex-wrap items-center gap-1">
                          {item.resource ? (
                            <Badge variant="outline" size="xs" radius="full" className="uppercase">
                              {item.resource}
                            </Badge>
                          ) : null}
                          {item.modelVersion ? (
                            <span className="truncate text-[11px] text-text-muted">v{item.modelVersion}</span>
                          ) : null}
                        </span>
                      </span>
                      {/* Slot is always reserved so picking a card never reflows its title. */}
                      <span className="size-4 shrink-0">
                        {isSelected ? <Check className="size-4 text-accent" weight="bold" /> : null}
                      </span>
                    </span>
                    <small className="line-clamp-2 text-xs leading-relaxed text-text-secondary">{item.body}</small>
                    {metadata.workflowNote ? (
                      <span className="line-clamp-2 border-t border-border-soft pt-2 text-[11px] leading-relaxed text-accent-2">
                        {metadata.workflowNote}
                      </span>
                    ) : null}
                  </Button>
                )
              })}
            </div>
          )}
        </section>

        {/* Method controls + node name */}
        <section className="space-y-4">
          <div>
            <SectionLabel id="node-builder-name-label">{t.nodeBuilder.nodeNameLabel}</SectionLabel>
            <Input
              type="text"
              aria-labelledby="node-builder-name-label"
              aria-invalid={Boolean(nameError)}
              aria-describedby={nameError ? 'node-builder-name-error' : undefined}
              className={`w-full rounded-md border bg-bg-app px-2.5 py-1.5 text-sm text-text-primary placeholder:text-text-secondary ${
                nameError ? 'border-danger' : 'border-border-soft'
              }`}
              placeholder={t.nodeBuilder.nodeNamePlaceholder}
              value={nodeName}
              onChange={(e) => {
                setNodeName(e.target.value)
                if (nameError) setNameError('')
              }}
              disabled={adding}
            />
            {nameError ? (
              <p id="node-builder-name-error" className="mt-1 text-xs text-danger">
                {nameError}
              </p>
            ) : null}
          </div>

          <div>
            <SectionLabel
              id="node-builder-methods"
              hint={format(t.nodeBuilder.selectedMethods, { count: selectedMethodOptions.length })}
            >
              {t.nodeBuilder.methodControls}
            </SectionLabel>
            <div
              role="group"
              aria-labelledby="node-builder-methods"
              className="max-h-64 space-y-0.5 overflow-y-auto rounded-md border border-border-soft p-1.5"
            >
              {methodOptions.map((method) => (
                <label
                  key={method.key}
                  className="flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 text-sm text-text-primary transition-colors hover:bg-bg-app"
                >
                  <Checkbox
                    className="mt-0.5 shrink-0"
                    checked={activeMethodKeys.includes(method.key)}
                    onCheckedChange={(checked) => {
                      setMethods(
                        checked === true
                          ? Array.from(new Set([...activeMethodKeys, method.key]))
                          : activeMethodKeys.filter((m) => m !== method.key),
                      )
                    }}
                    disabled={adding}
                  />
                  <div className="min-w-0">
                    <span className="block leading-snug">{method.label}</span>
                    {method.description ? (
                      <span className="block text-xs text-text-secondary">{method.description}</span>
                    ) : null}
                  </div>
                </label>
              ))}
            </div>
            {selectedMethodOptions.length === 0 ? (
              <p className="mt-1.5 text-xs text-danger">{t.nodeBuilder.noMethodsSelected}</p>
            ) : null}
          </div>

          <div className="rounded-md border border-dashed border-border-soft p-2">
            <Button type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-between px-1"
              aria-expanded={methodFormOpen}
              onClick={() => setMethodFormOpen((current) => !current)}
              disabled={adding}
            >
              <span className="text-xs font-medium uppercase tracking-wide text-text-secondary">
                {t.nodeBuilder.newMethodSection}
              </span>
              <CaretDown className={`size-3.5 transition-transform ${methodFormOpen ? 'rotate-180' : ''}`} />
            </Button>
            {methodFormOpen ? (
              <div className="mt-2">
                <div className="grid gap-2 sm:grid-cols-[1fr_0.75fr]">
                  <Input
                    type="text"
                    aria-label={t.nodeBuilder.newMethodName}
                    className="min-w-0 rounded-md border border-border-soft bg-bg-app px-2 py-1.5 text-sm text-text-primary placeholder:text-text-secondary"
                    placeholder={t.nodeBuilder.newMethodName}
                    value={newMethodName}
                    onChange={(e) => setNewMethodName(e.target.value)}
                    disabled={adding || createMethod.isPending}
                  />
                  <Input
                    type="text"
                    aria-label={t.nodeBuilder.methodType}
                    className="min-w-0 rounded-md border border-border-soft bg-bg-app px-2 py-1.5 text-sm text-text-primary placeholder:text-text-secondary"
                    placeholder={t.nodeBuilder.methodType}
                    value={newMethodType}
                    onChange={(e) => setNewMethodType(e.target.value)}
                    disabled={adding || createMethod.isPending}
                  />
                </div>
                <Textarea
                  aria-label={t.nodeBuilder.methodNote}
                  className="mt-2 min-h-14 w-full resize-y rounded-md border border-border-soft bg-bg-app px-2 py-1.5 text-sm text-text-primary placeholder:text-text-secondary"
                  placeholder={t.nodeBuilder.methodNote}
                  value={newMethodDescription}
                  onChange={(e) => setNewMethodDescription(e.target.value)}
                  disabled={adding || createMethod.isPending}
                />
                <Button type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => createMethod.mutate()}
                  disabled={adding || createMethod.isPending || !newMethodName.trim()}
                >
                  {createMethod.isPending ? <SpinnerGap className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                  {t.nodeBuilder.createMethod}
                </Button>
                {createMethod.isError ? (
                  <Alert className="mt-2" variant="destructive">
                    <AlertDescription>{t.nodeBuilder.createMethodFailed}</AlertDescription>
                  </Alert>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>

        {/* Preview card + parameters */}
        <section className="md:col-span-2 xl:col-span-1">
        <Frame variant="inverse" spacing="sm" className="xl:sticky xl:top-4">
          <FramePanel className="space-y-4">
          <div>
            <SectionLabel id="node-builder-preview">{t.nodeBuilder.previewCard}</SectionLabel>
            <article
              aria-labelledby="node-builder-preview"
              className="rounded-lg border border-border-soft bg-surface-1 p-3 text-sm"
            >
              <div className="flex items-start gap-2">
                <NodeGlyph icon={template.icon} active />
                <div className="min-w-0 flex-1">
                  <strong className="block truncate" title={nodeName || template.title}>
                    {nodeName || template.title}
                  </strong>
                  <p className="mt-0.5 text-xs text-text-secondary">{template.body}</p>
                </div>
                {template.resource ? (
                  <Badge variant="outline" size="xs" radius="full" className="uppercase">
                    {template.resource}
                  </Badge>
                ) : null}
              </div>
              <ChainMetadata
                metadata={parameterMetadata}
                labels={{
                  exclusiveWith: t.nodeBuilder.exclusiveWith,
                  recommendedAfter: t.nodeBuilder.recommendedAfter,
                  recommendedBefore: t.nodeBuilder.recommendedBefore,
                }}
              />
              {selectedMethodOptions.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1 border-t border-border-soft pt-2">
                  {selectedMethodOptions.map((method) => (
                    <Badge key={method.key} variant="outline" size="xs" radius="full">
                      {method.label}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </article>
          </div>
          <div>
            <SectionLabel>{t.nodeBuilder.pluginParameters}</SectionLabel>
            <ParameterSchemaForm
              schema={parameterSchemaForForm}
              values={{ ...defaultsFromFields(parameterFields), ...parameters }}
              onChange={setParameters}
              disabled={adding}
            />
          </div>
          </FramePanel>
        </Frame>
        </section>
      </div>
      </ScrollArea>
      <SheetFooter className="flex-row justify-end border-t border-border-soft">
        <Button type="button" variant="outline" className="flex-1 sm:flex-none sm:min-w-28" onClick={handleClose} disabled={adding}>
          {t.nodeBuilder.cancel}
        </Button>
        <Button type="button"
          className="flex-1 sm:flex-none sm:min-w-44"
          onClick={() => void handleAdd()}
          disabled={adding || templates.length === 0 || selectedMethodOptions.length === 0}
        >
          {adding ? (
            <>
              <SpinnerGap className="h-3.5 w-3.5 animate-spin" />
              {t.nodeBuilder.adding}
            </>
          ) : (
            t.nodeBuilder.addCardButton
          )}
        </Button>
      </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
