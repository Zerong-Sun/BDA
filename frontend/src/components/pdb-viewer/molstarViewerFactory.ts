import type { PluginContext } from 'molstar/lib/mol-plugin/context'

export interface MolstarViewer {
  plugin: PluginContext
  dispose(): void
  loadStructureFromData(
    data: string,
    format: 'pdb' | 'mmcif',
    options?: { dataLabel?: string },
  ): Promise<void>
}

const VIEWER_OPTIONS = {
  layoutIsExpanded: false,
  layoutShowControls: false,
  layoutShowSequence: false,
  layoutShowLog: false,
  layoutShowLeftPanel: false,
  collapseRightPanel: true,
  viewportShowExpand: false,
  // Mol*'s own fullscreen icon calls document.body.requestFullscreen(), which is
  // blocked in embedded browsers and swallows its own failure, so the button
  // reads as broken. The viewer's "Expand viewer" control replaces it.
  viewportShowToggleFullscreen: false,
  viewportShowControls: false,
  viewportShowSelectionMode: false,
  viewportShowAnimation: false,
  viewportShowScreenshotControls: false,
  viewportShowSettings: false,
  viewportShowReset: false,
  viewportShowTrajectoryControls: false,
} as const

export async function createMolstarViewer(
  container: HTMLDivElement,
): Promise<MolstarViewer> {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light'
  const [{ Viewer }, { PluginConfig }, { registerBdaColorThemes }] = await Promise.all([
    import('molstar/lib/apps/viewer/app'),
    import('molstar/lib/mol-plugin/config'),
    import('./molstarColorThemes'),
    isLight
      ? import('molstar/lib/mol-plugin-ui/skin/light.scss')
      : import('molstar/lib/mol-plugin-ui/skin/dark.scss'),
  ])
  const viewer = await Viewer.create(container, {
    ...VIEWER_OPTIONS,
    // Not exposed as Viewer options: both render a floating icon over the
    // canvas that this embedded viewer has no use for.
    config: [
      [PluginConfig.Viewport.ShowIllumination, false],
      [PluginConfig.Viewport.ShowXR, 'never'],
    ],
  })
  try {
    await viewer.plugin.initialized
    registerBdaColorThemes(viewer.plugin)
    return viewer
  } catch (caught) {
    viewer.dispose()
    throw caught
  }
}
