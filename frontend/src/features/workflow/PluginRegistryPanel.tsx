import { useQuery } from '@tanstack/react-query'
import { listModelPlugins } from '../../lib/api/registry'
import { useI18n } from '../../lib/i18n'
import { Badge } from '../../components/reui/badge'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'

export function PluginRegistryPanel() {
  const { t, format } = useI18n()
  const { data: plugins = [], isLoading } = useQuery({
    queryKey: ['model-plugins'],
    queryFn: listModelPlugins,
  })

  return (
    <Frame variant="inverse" spacing="sm" className="mb-4">
      <FrameHeader>
      <p className="text-xs uppercase tracking-wide text-accent">{t.workflowExt.pluginRegistry.eyebrow}</p>
      <FrameTitle>{t.workflowExt.pluginRegistry.title}</FrameTitle>
      </FrameHeader>
      <FramePanel>
      {isLoading ? (
        <p className="mt-2 text-sm text-text-secondary">{t.workflowExt.pluginRegistry.loading}</p>
      ) : (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {plugins.map((plugin) => (
            <article key={plugin.id} className="rounded-md border border-border-soft bg-bg-app p-3">
              <div className="flex items-center justify-between gap-2">
                <strong className="text-sm">{plugin.name}</strong>
                <Badge variant={plugin.enabled ? 'success-light' : 'outline'}>
                  {plugin.enabled ? plugin.validation_status : t.shared.status.disconnected}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-text-secondary">
                {plugin.container_image} · v{plugin.plugin_version} · {plugin.plugin_key}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {format(t.workflowExt.pluginRegistry.runtimeProof, {
                  status: plugin.runtime_validation_status,
                })}
              </p>
            </article>
          ))}
        </div>
      )}
      </FramePanel>
    </Frame>
  )
}
