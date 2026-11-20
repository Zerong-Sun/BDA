import type { PluginContext } from 'molstar/lib/mol-plugin/context'
import type { ViewPreset } from './ColorPresets'

const VIEW_DIRECTIONS: Record<
  Exclude<ViewPreset, 'focus'>,
  { dir: [number, number, number]; up: [number, number, number] }
> = {
  front: { dir: [0, 0, 1], up: [0, 1, 0] },
  back: { dir: [0, 0, -1], up: [0, 1, 0] },
  top: { dir: [0, -1, 0], up: [0, 0, 1] },
  bottom: { dir: [0, 1, 0], up: [0, 0, -1] },
  side: { dir: [1, 0, 0], up: [0, 1, 0] },
}

export async function applyViewPreset(plugin: PluginContext, view: ViewPreset): Promise<void> {
  if (view === 'focus') {
    plugin.managers.camera.focusObject({ durationMs: 250 })
    return
  }

  const canvas3d = plugin.canvas3d
  if (!canvas3d) return

  plugin.managers.camera.orientAxes(undefined, 0)

  const { Vec3 } = await import('molstar/lib/mol-math/linear-algebra/3d/vec3')
  const sphere = canvas3d.boundingSphere
  const center = sphere.center
  const radius = Math.max(sphere.radius, 10)

  const { dir, up } = VIEW_DIRECTIONS[view]
  const dirVec = Vec3.create(dir[0], dir[1], dir[2])
  const upVec = Vec3.create(up[0], up[1], up[2])
  const snapshot = canvas3d.camera.getInvariantFocus(center, radius, upVec, dirVec)
  plugin.managers.camera.setSnapshot(snapshot, 250)
}
