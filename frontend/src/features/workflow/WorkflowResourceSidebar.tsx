import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus } from '@phosphor-icons/react'
import { ArtifactBrowser, ArtifactUploadDropzone } from '../artifacts'
import { listModelPlugins } from '../../lib/api/registry'
import type { Artifact } from '../../lib/schemas/artifact'
import type { ModelPlugin } from '../../lib/schemas/registry'
import { StatusPill } from '../../components/ui/StatusPill'
import { statusTone } from '../../components/ui/statusTone'
import { Button } from '../../components/ui/Button'
import { ScrollArea } from '../../components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs'
import { Frame, FramePanel } from '../../components/reui/frame'
import { ScriptAssetManager } from './ScriptAssetManager'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import { useI18n } from '../../lib/i18n'

interface WorkflowResourceSidebarProps {
  projectId?: string
  artifacts: Artifact[]
  selectedNode?: WorkflowNode | null
  selectedArtifactId?: string
  onArtifactUploaded: (artifact: Artifact, file: File) => void
  onArtifactSelected: (artifact: Artifact) => void
  onPluginAdd?: (plugin: ModelPlugin) => void
  readOnly?: boolean
}

export function WorkflowResourceSidebar({
  projectId,
  artifacts,
  selectedNode,
  selectedArtifactId,
  onArtifactUploaded,
  onArtifactSelected,
  onPluginAdd,
  readOnly = false,
}: WorkflowResourceSidebarProps) {
  const { t, format } = useI18n()
  const [tab, setTab] = useState('artifacts')
  const { data: plugins = [] } = useQuery({
    queryKey: ['model-plugins'],
    queryFn: listModelPlugins,
  })
  const nodeArtifacts = selectedNode
    ? artifacts.filter((artifact) => artifact.lineage.workflow_node_id === selectedNode.id)
    : artifacts
  const visibleArtifacts = selectedNode ? nodeArtifacts : artifacts

  return (
    <Frame variant="inverse" spacing="xs" className="h-full min-h-[32rem] w-[300px] shrink-0 2xl:min-h-0">
      <FramePanel className="min-h-0 overflow-hidden p-0">
      <Tabs value={tab} onValueChange={(value) => setTab(String(value))} className="h-full min-h-0">
        <TabsList variant="line" className="mx-3 mt-2">
          <TabsTrigger value="artifacts">{t.workflowExt.resourceSidebar.artifacts}</TabsTrigger>
          <TabsTrigger value="plugins">{t.workflowExt.resourceSidebar.plugins}</TabsTrigger>
        </TabsList>
      <ScrollArea className="min-h-0 flex-1 p-3">
        <TabsContent value="artifacts">
          <>
            {selectedNode ? (
              <p className="mb-2 text-xs text-text-secondary">
                {format(
                  visibleArtifacts.length === 1
                    ? t.workflowExt.resourceSidebar.nodeArtifacts
                    : t.workflowExt.resourceSidebar.nodeArtifactsPlural,
                  { nodeName: selectedNode.node_key, count: visibleArtifacts.length },
                )}
              </p>
            ) : null}
            <ArtifactUploadDropzone
              projectId={projectId}
              readOnly={readOnly}
              onUploaded={onArtifactUploaded}
            />
            <div className="mt-3">
              <ArtifactBrowser
                artifacts={visibleArtifacts}
                selectedArtifactId={selectedArtifactId}
                onSelect={onArtifactSelected}
              />
            </div>
          </>
        </TabsContent>
        <TabsContent value="plugins">
          <div className="space-y-2">
            {plugins.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border-soft px-3 py-4 text-center text-xs text-text-secondary">
                {t.workflowExt.resourceSidebar.noPlugins}
              </p>
            ) : (
              plugins.map((plugin) => (
                <article
                  key={plugin.id}
                  className="flex items-center justify-between gap-2 rounded-xl border border-border-soft bg-bg-app px-2.5 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <strong className="truncate text-sm">{plugin.name}</strong>
                      <StatusPill
                        label={
                          plugin.enabled ? plugin.validation_status : t.shared.status.disconnected
                        }
                        tone={statusTone(plugin.enabled ? plugin.validation_status : 'disconnected')}
                      />
                    </div>
                    <p className="truncate text-xs text-text-secondary">
                      v{plugin.plugin_version} · {plugin.plugin_key}
                    </p>
                    <p className="truncate text-[11px] text-text-muted">
                      {format(t.workflowExt.resourceSidebar.runtimeProof, {
                        status: plugin.runtime_validation_status,
                      })}
                    </p>
                  </div>
                  {onPluginAdd ? (
                    <Button type="button"
                      variant="outline"
                      size="icon"
                      aria-label={format(t.workflowExt.resourceSidebar.addPluginAria, {
                        modelName: plugin.name,
                      })}
                      disabled={readOnly || !plugin.enabled}
                      onClick={() => onPluginAdd(plugin)}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </TabsContent>
        <div className="mt-4">
          <ScriptAssetManager />
        </div>
      </ScrollArea>
      </Tabs>
      </FramePanel>
    </Frame>
  )
}
