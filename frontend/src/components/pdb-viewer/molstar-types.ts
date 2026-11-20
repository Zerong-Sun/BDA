/**
 * Minimal structural typing for the subset of the Mol* plugin API used by the
 * viewer. Mol*'s own types are heavy and partly internal, so instead of leaking
 * `any` across the viewer we describe exactly the surface we depend on. This
 * gives real autocomplete and compile-time safety without pulling in unstable
 * internal type paths.
 */

/** Opaque handle to a loaded structure in the Mol* hierarchy. */
export type MolStructure = unknown

export interface MolBoundingSphere {
  center: [number, number, number] | Float32Array
  radius: number
}

export interface MolCamera {
  getInvariantFocus(
    center: MolBoundingSphere['center'],
    radius: number,
    up: unknown,
    dir: unknown,
  ): unknown
}

export interface MolCanvas3D {
  boundingSphere: MolBoundingSphere
  camera: MolCamera
}

export interface MolPlugin {
  readonly managers: {
    structure: {
      hierarchy: { current: { structures: readonly MolStructure[] } }
      component: { clear(structures: readonly MolStructure[]): Promise<void> }
    }
    camera: {
      focusObject(options: { durationMs?: number }): void
      orientAxes(adjustedRegion: unknown, durationMs?: number): void
      setSnapshot(snapshot: unknown, durationMs?: number): void
    }
  }
  readonly builders: {
    structure: {
      representation: {
        addRepresentation(
          structure: MolStructure,
          params: { type: string; colorTheme?: { name: string } },
        ): Promise<unknown>
      }
    }
  }
  readonly canvas3d: MolCanvas3D | undefined
}
