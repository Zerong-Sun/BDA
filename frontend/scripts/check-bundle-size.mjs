import { readFile, stat } from 'node:fs/promises'
import { join } from 'node:path'

const manifest = JSON.parse(await readFile(join('dist', '.vite', 'manifest.json'), 'utf8'))
const entries = Object.values(manifest).filter((item) => item.isEntry)
if (entries.length !== 1) throw new Error(`Expected one frontend entry chunk, found ${entries.length}`)

const entryBytes = (await stat(join('dist', entries[0].file))).size
const maxEntryBytes = 750 * 1024
if (entryBytes > maxEntryBytes) {
  throw new Error(`Frontend entry chunk is ${(entryBytes / 1024).toFixed(1)} KiB; limit is 750 KiB`)
}

const oversized = []
for (const item of Object.values(manifest)) {
  if (
    !item.file?.endsWith('.js')
    || item.file.includes('molstar-')
    || item.file.includes('h264-mp4-encoder.web-')
  ) continue
  const bytes = (await stat(join('dist', item.file))).size
  if (bytes > 900 * 1024) oversized.push(`${item.file}: ${(bytes / 1024).toFixed(1)} KiB`)
}
if (oversized.length) throw new Error(`Ordinary chunks exceed 900 KiB:\n${oversized.join('\n')}`)

console.log(`Bundle gate passed: entry ${(entryBytes / 1024).toFixed(1)} KiB`)
