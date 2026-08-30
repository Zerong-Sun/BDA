import {
  Database,
  Dna,
  FileJs,
  Flask,
  Funnel,
  MagicWand,
  Pulse,
  Scan,
} from '@phosphor-icons/react'

/**
 * Icon names stored on workflow nodes and node templates. Shared so the builder
 * preview and the canvas card resolve the same glyph for a given plugin.
 */
export const nodeIconMap = {
  database: Database,
  'file-json': FileJs,
  'wand-sparkles': MagicWand,
  dna: Dna,
  'scan-search': Scan,
  activity: Pulse,
  filter: Funnel,
  'flask-conical': Flask,
}

export type NodeIconName = keyof typeof nodeIconMap

/**
 * Resolve with `nodeIconMap[name as NodeIconName] ?? DefaultNodeIcon` at the use
 * site. A helper that returns the component instead trips the React Compiler's
 * static-components rule.
 */
export const DefaultNodeIcon = Database
