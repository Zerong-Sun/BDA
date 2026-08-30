import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { relative, resolve, sep } from 'node:path'
import ts from 'typescript'
import viteConfig from '../../vite.config'
import vitestConfig from '../../vitest.config'

const root = resolve(import.meta.dirname, '../..')
const sourceRoot = resolve(root, 'src')

const requiredUiControls = [
  'button',
  'input',
  'textarea',
  'label',
  'select',
  'checkbox',
  'switch',
  'tabs',
  'tooltip',
  'accordion',
  'dialog',
  'alert-dialog',
  'sheet',
  'drawer',
  'dropdown-menu',
  'popover',
  'command',
  'scroll-area',
  'separator',
  'skeleton',
  'progress',
  'avatar',
  'breadcrumb',
  'sonner',
]

// Git tracks these generated controls with upper-case names. Keeping their
// imports and filesystem entries aligned avoids case-sensitive checkout breaks.
const trackedUiControlFilenames: Record<string, string> = {
  button: 'Button',
  input: 'Input',
  skeleton: 'Skeleton',
  tabs: 'Tabs',
}

const staleUiModules = [
  'legacy-button',
  'legacy-input',
  'legacy-skeleton',
  'legacy-tabs',
  'Card',
  'Divider',
  'Row',
] as const

const registryPrimitiveFiles = new Set([
  'Button.tsx',
  'Input.tsx',
  'Skeleton.tsx',
  'Tabs.tsx',
  'accordion.tsx',
  'alert-dialog.tsx',
  'avatar.tsx',
  'breadcrumb.tsx',
  'button-group.tsx',
  'checkbox.tsx',
  'command.tsx',
  'dialog.tsx',
  'drawer.tsx',
  'dropdown-menu.tsx',
  'input-group.tsx',
  'kbd.tsx',
  'label.tsx',
  'popover.tsx',
  'progress.tsx',
  'scroll-area.tsx',
  'select.tsx',
  'separator.tsx',
  'sheet.tsx',
  'sonner.tsx',
  'spinner.tsx',
  'switch.tsx',
  'textarea.tsx',
  'toggle-group.tsx',
  'toggle.tsx',
  'tooltip.tsx',
])

interface FileInputManifestEntry {
  intrinsicCount: number
  registryCount: number
  refInputCounts: Record<string, number>
  refTriggerCounts: Record<string, number>
  distinctReturnCount: number
  reason: string
}

const fileInputManifest = new Map<string, FileInputManifestEntry>([
  [
    'src/features/artifacts/ArtifactUploadDropzone.tsx',
    {
      intrinsicCount: 1,
      registryCount: 0,
      refInputCounts: { inputRef: 1 },
      refTriggerCounts: { inputRef: 1 },
      distinctReturnCount: 1,
      reason: 'Browser artifact upload requires one hidden native file picker.',
    },
  ],
  [
    'src/features/lab/InstrumentAnalysis.tsx',
    {
      intrinsicCount: 1,
      registryCount: 0,
      refInputCounts: { fileInput: 1 },
      refTriggerCounts: { fileInput: 1 },
      distinctReturnCount: 1,
      reason: 'Uploading an instrument export requires one hidden native file picker.',
    },
  ],
  [
    'src/features/pdb-viewer/PDBFileUpload.tsx',
    {
      intrinsicCount: 2,
      registryCount: 0,
      refInputCounts: { inputRef: 2 },
      refTriggerCounts: { inputRef: 2 },
      distinctReturnCount: 2,
      reason: 'The mutually exclusive empty and replacement PDB states each render one hidden picker.',
    },
  ],
  [
    'src/features/results/ExperimentUpload.tsx',
    {
      intrinsicCount: 1,
      registryCount: 0,
      refInputCounts: { fileInputRef: 1 },
      refTriggerCounts: { fileInputRef: 1 },
      distinctReturnCount: 1,
      reason: 'Browser experiment-result upload requires one hidden native file picker.',
    },
  ],
  [
    'src/features/workflow/ScriptAssetManager.tsx',
    {
      intrinsicCount: 0,
      registryCount: 1,
      refInputCounts: { fileInputRef: 1 },
      refTriggerCounts: { fileInputRef: 1 },
      distinctReturnCount: 1,
      reason: 'The script importer uses the registry Input as a hidden browser file picker.',
    },
  ],
])

const rawPalettePattern =
  /\b(?:bg|text|border(?:-[xysetrbl])?|ring(?:-offset)?|outline|fill|stroke|from|via|to|divide|shadow|decoration|placeholder|accent|caret)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)(?:-\d{2,3}|\/\d{1,3})?\b/g

function normalizePath(path: string) {
  return path.split(sep).join('/')
}

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return entry.isFile() && path.endsWith('.tsx') && !/\.(?:test|spec)\.tsx$/.test(path)
      ? [path]
      : []
  })
}

function applicationSourceFiles() {
  const domainFiles = ['app', 'features', 'lib'].flatMap((directory) =>
    sourceFiles(resolve(sourceRoot, directory)),
  )
  const semanticUiFiles = sourceFiles(resolve(sourceRoot, 'components/ui')).filter(
    (path) => !registryPrimitiveFiles.has(path.split(sep).at(-1) ?? ''),
  )
  return [...domainFiles, ...semanticUiFiles]
}

function jsxTagName(node: ts.JsxTagNameExpression) {
  return ts.isIdentifier(node) ? node.text : node.getText()
}

function jsxAttribute(node: ts.JsxAttributes, name: string) {
  return node.properties.find(
    (property): property is ts.JsxAttribute =>
      ts.isJsxAttribute(property) && property.name.getText() === name,
  )
}

function staticAttributeValue(attribute: ts.JsxAttribute | undefined) {
  if (!attribute?.initializer) return attribute ? '' : undefined
  if (ts.isStringLiteral(attribute.initializer)) return attribute.initializer.text
  if (
    ts.isJsxExpression(attribute.initializer) &&
    attribute.initializer.expression &&
    ts.isStringLiteral(attribute.initializer.expression)
  ) {
    return attribute.initializer.expression.text
  }
  return undefined
}

function identifierAttributeValue(attribute: ts.JsxAttribute | undefined) {
  if (
    !attribute?.initializer ||
    !ts.isJsxExpression(attribute.initializer) ||
    !attribute.initializer.expression ||
    !ts.isIdentifier(attribute.initializer.expression)
  ) {
    return undefined
  }
  return attribute.initializer.expression.text
}

function recordCount(counts: Map<string, number>, key: string) {
  counts.set(key, (counts.get(key) ?? 0) + 1)
}

function sortedCounts(counts: Map<string, number>) {
  return Object.fromEntries([...counts].sort(([left], [right]) => left.localeCompare(right)))
}

function componentReturnOwnership(node: ts.Node, sourceFile: ts.SourceFile) {
  let ancestor: ts.Node | undefined = node.parent
  let returnStatement: ts.ReturnStatement | undefined
  let containingFunction: ts.SignatureDeclaration | undefined
  while (ancestor) {
    if (!returnStatement && ts.isReturnStatement(ancestor)) {
      returnStatement = ancestor
    }
    if (ts.isFunctionLike(ancestor)) {
      containingFunction = ancestor
      break
    }
    ancestor = ancestor.parent
  }
  return returnStatement && containingFunction
    ? {
        returnPosition: returnStatement.getStart(sourceFile),
        functionPosition: containingFunction.getStart(sourceFile),
      }
    : undefined
}

function renderedAsLink(attributes: ts.JsxAttributes) {
  const render = jsxAttribute(attributes, 'render')
  if (!render?.initializer || !ts.isJsxExpression(render.initializer)) return false
  const expression = render.initializer.expression
  if (!expression || (!ts.isJsxElement(expression) && !ts.isJsxSelfClosingElement(expression))) {
    return false
  }
  const opening = ts.isJsxElement(expression) ? expression.openingElement : expression
  return ['a', 'Link', 'NavLink'].includes(jsxTagName(opening.tagName))
}

function pickerClickRefs(attribute: ts.JsxAttribute | undefined) {
  if (
    !attribute?.initializer ||
    !ts.isJsxExpression(attribute.initializer) ||
    !attribute.initializer.expression
  ) {
    return []
  }

  const refs: string[] = []
  function visit(node: ts.Node) {
    if (
      ts.isCallExpression(node) &&
      node.arguments.length === 0 &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'click'
    ) {
      const currentAccess = node.expression.expression
      if (
        ts.isPropertyAccessExpression(currentAccess) &&
        currentAccess.questionDotToken === undefined &&
        currentAccess.name.text === 'current' &&
        ts.isIdentifier(currentAccess.expression)
      ) {
        refs.push(currentAccess.expression.text)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(attribute.initializer.expression)
  return refs
}

function location(sourceFile: ts.SourceFile, node: ts.Node) {
  const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile))
  const path = normalizePath(relative(root, sourceFile.fileName))
  return `${path}:${line + 1}:${character + 1}`
}

describe('REUI migration guardrails', () => {
  it('recognizes every forbidden raw Tailwind palette utility family', () => {
    const rawPrefixes = [
      'bg',
      'text',
      'border',
      'ring',
      'outline',
      'fill',
      'stroke',
      'from',
      'via',
      'to',
      'divide',
      'shadow',
      'decoration',
      'placeholder',
      'accent',
      'caret',
    ]

    for (const prefix of rawPrefixes) {
      expect(`${prefix}-blue-500`.match(rawPalettePattern), prefix).not.toBeNull()
    }
    for (const direction of ['x', 'y', 's', 'e', 't', 'r', 'b', 'l']) {
      expect(`border-${direction}-blue-500`.match(rawPalettePattern), `border-${direction}`).not.toBeNull()
    }
    expect('ring-offset-blue-500'.match(rawPalettePattern), 'ring-offset').not.toBeNull()
    expect('border-t-rose-300/40'.match(rawPalettePattern), 'directional opacity').not.toBeNull()
    expect('ring-offset-sky-200/50'.match(rawPalettePattern), 'ring-offset opacity').not.toBeNull()
    expect('bg-primary'.match(rawPalettePattern)).toBeNull()
    expect('border-t-border'.match(rawPalettePattern)).toBeNull()
    expect('ring-offset-background'.match(rawPalettePattern)).toBeNull()
    expect('text-muted-foreground'.match(rawPalettePattern)).toBeNull()
  })

  it('recognizes picker triggers only from actual ref.current.click calls', () => {
    const fixture = ts.createSourceFile(
      'picker-fixture.tsx',
      `
        const Fixture = () => (
          <>
            <Button onClick={() => "fakeRef.current?.click()"} />
            <Button onClick={() => {
              // decoyRef.current?.click()
              actualRef.current?.click()
            }} />
          </>
        )
      `,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    )
    const buttons: Array<ts.JsxOpeningElement | ts.JsxSelfClosingElement> = []
    function visit(node: ts.Node) {
      if (
        (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        jsxTagName(node.tagName) === 'Button'
      ) {
        buttons.push(node)
      }
      ts.forEachChild(node, visit)
    }
    visit(fixture)

    expect(pickerClickRefs(jsxAttribute(buttons[0].attributes, 'onClick'))).toEqual([])
    expect(pickerClickRefs(jsxAttribute(buttons[1].attributes, 'onClick'))).toEqual([
      'actualRef',
    ])
  })

  it('has a complete REUI foundation at the conventional source layout', () => {
    const components = JSON.parse(readFileSync(resolve(root, 'components.json'), 'utf8'))
    const tsconfig = JSON.parse(readFileSync(resolve(root, 'tsconfig.app.json'), 'utf8'))
    const styles = readFileSync(resolve(root, 'src/index.css'), 'utf8')
    const aliases = Array.isArray(viteConfig.resolve?.alias) ? viteConfig.resolve.alias : []
    const rootAlias = aliases.find((alias) => alias.find === '@')
    const vitestAliases = Array.isArray(vitestConfig.resolve?.alias)
      ? vitestConfig.resolve.alias
      : []
    const vitestRootAlias = vitestAliases.find((alias) => alias.find === '@')

    expect(Object.keys(components.registries)).toEqual(['@reui'])
    expect(components.registries['@reui']).toBe('https://reui.io/r/{style}/{name}.json')
    expect(components.style).toBe('base-lyra')
    expect(components.iconLibrary).toBe('phosphor')
    expect(components.aliases).toMatchObject({
      components: '@/components',
      ui: '@/components/ui',
      lib: '@/lib',
      utils: '@/lib/utils',
    })
    expect(tsconfig.compilerOptions.types).toContain('node')
    expect(tsconfig.compilerOptions.paths).toEqual({ '@/*': ['./src/*'] })
    expect(rootAlias?.replacement).toBe(resolve(root, 'src'))
    expect(vitestRootAlias?.replacement).toBe(resolve(root, 'src'))
    expect(
      aliases.filter(
        (alias) => alias.find instanceof RegExp && alias.find.test('@/components/reui/frame'),
      ),
    ).toEqual([])

    for (const component of [
      'frame',
      'data-grid/data-grid',
      'filters',
      'stepper',
      'timeline',
      'badge',
      'alert',
      'autocomplete',
      'sortable',
      'icon-tile',
      'icon-stack',
    ]) {
      expect(existsSync(resolve(root, `src/components/reui/${component}.tsx`))).toBe(true)
    }

    for (const example of [
      'c-data-grid-3',
      'c-filters-1',
      'c-stepper-4',
      'c-timeline-4',
      'c-autocomplete-4',
      'c-sortable-1',
      'c-alert-12',
    ]) {
      expect(existsSync(resolve(root, `src/components/examples/${example}.tsx`))).toBe(true)
    }

    for (const control of requiredUiControls) {
      const filename = trackedUiControlFilenames[control] ?? control
      expect(existsSync(resolve(root, `src/components/ui/${filename}.tsx`))).toBe(true)
    }

    const exactUiEntries = new Set(readdirSync(resolve(root, 'src/components/ui')))
    for (const [lowercase, uppercase] of Object.entries(trackedUiControlFilenames)) {
      expect(exactUiEntries.has(`${uppercase}.tsx`)).toBe(true)
      expect(exactUiEntries.has(`${lowercase}.tsx`)).toBe(false)
    }

    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--primary:\s*var\(--bda-primary\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--accent:\s*var\(--bda-primary\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--success:\s*var\(--bda-success\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--success-foreground:\s*var\(--background\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--info:\s*var\(--bda-info\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--info-foreground:\s*var\(--background\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--warning:\s*var\(--bda-warning\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--warning-foreground:\s*var\(--background\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--destructive-foreground:\s*var\(--background\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--invert:\s*var\(--foreground\);/)
    expect(styles).toMatch(/\.dark\s*\{[\s\S]*--invert-foreground:\s*var\(--background\);/)
  })

  it('removes stale adapters and forbidden icon imports', () => {
    const packageJson = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'))
    expect(packageJson.dependencies).not.toHaveProperty('lucide-react')
    expect(readFileSync(resolve(root, 'package-lock.json'), 'utf8')).not.toContain('"lucide-react"')
    expect(readFileSync(resolve(root, 'bun.lock'), 'utf8')).not.toContain('"lucide-react"')

    for (const module of staleUiModules) {
      expect(existsSync(resolve(root, `src/components/ui/${module}.tsx`))).toBe(false)
    }

    const violations: string[] = []
    for (const path of sourceFiles(sourceRoot)) {
      const sourceFile = ts.createSourceFile(
        path,
        readFileSync(path, 'utf8'),
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      )
      sourceFile.forEachChild((node) => {
        if (!ts.isImportDeclaration(node) || !ts.isStringLiteral(node.moduleSpecifier)) return
        const moduleName = node.moduleSpecifier.text
        if (
          moduleName === 'lucide-react' ||
          staleUiModules.some((stale) => moduleName.endsWith(`/ui/${stale}`) || moduleName === `./${stale}`)
        ) {
          violations.push(`${location(sourceFile, node)} imports ${moduleName}`)
        }
      })
    }
    expect(violations).toEqual([])
  })

  it('enforces registry controls and the exact file-input manifest', () => {
    const violations: string[] = []
    let structureViewerDialogExceptionCount = 0
    const observedInputs = new Map<
      string,
      {
        intrinsicCount: number
        registryCount: number
        inputRefCounts: Map<string, number>
        triggerRefCounts: Map<string, number>
        inputBranchCounts: Map<string, number>
        triggerBranchCounts: Map<string, number>
        inputReturnPositions: Set<number>
        inputFunctionPositions: Set<number>
      }
    >()
    const forbiddenIntrinsic = new Set([
      'table',
      'button',
      'select',
      'textarea',
      'details',
      'summary',
    ])

    for (const path of applicationSourceFiles()) {
      const text = readFileSync(path, 'utf8')
      const sourceFile = ts.createSourceFile(
        path,
        text,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      )
      const relativePath = normalizePath(relative(root, path))
      const manifest = fileInputManifest.get(relativePath)
      const inputState = {
        intrinsicCount: 0,
        registryCount: 0,
        inputRefCounts: new Map<string, number>(),
        triggerRefCounts: new Map<string, number>(),
        inputBranchCounts: new Map<string, number>(),
        triggerBranchCounts: new Map<string, number>(),
        inputReturnPositions: new Set<number>(),
        inputFunctionPositions: new Set<number>(),
      }

      function visit(node: ts.Node) {
        if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
          const tag = jsxTagName(node.tagName)
          if (tag === 'Button') {
            const onClick = jsxAttribute(node.attributes, 'onClick')
            for (const triggerRef of pickerClickRefs(onClick)) {
              recordCount(inputState.triggerRefCounts, triggerRef)
              const ownership = componentReturnOwnership(node, sourceFile)
              if (!ownership) {
                violations.push(
                  `${location(sourceFile, node)} picker trigger must belong to a component return`,
                )
              } else {
                recordCount(
                  inputState.triggerBranchCounts,
                  `${triggerRef}@${ownership.returnPosition}`,
                )
              }
            }
            if (!renderedAsLink(node.attributes)) {
              const type = staticAttributeValue(jsxAttribute(node.attributes, 'type'))
              if (!['button', 'submit', 'reset'].includes(type ?? '')) {
                violations.push(`${location(sourceFile, node)} Button requires an explicit type`)
              }
            }
          }

          if (forbiddenIntrinsic.has(tag)) {
            violations.push(`${location(sourceFile, node)} uses raw <${tag}>`)
          }

          if (tag === 'input' || tag === 'Input') {
            const type = staticAttributeValue(jsxAttribute(node.attributes, 'type'))
            if (tag === 'input' || type === 'file') {
              if (type !== 'file') {
                violations.push(`${location(sourceFile, node)} uses raw non-file <input>`)
              } else {
                const className = staticAttributeValue(jsxAttribute(node.attributes, 'className'))
                const inputRef = identifierAttributeValue(jsxAttribute(node.attributes, 'ref'))
                if (!manifest) {
                  violations.push(`${location(sourceFile, node)} is not in the file-input manifest`)
                }
                if (!className?.split(/\s+/).includes('hidden')) {
                  violations.push(`${location(sourceFile, node)} file input is not statically hidden`)
                }
                if (tag === 'input') inputState.intrinsicCount += 1
                else inputState.registryCount += 1
                if (!inputRef) {
                  violations.push(`${location(sourceFile, node)} file input needs a static ref`)
                } else {
                  recordCount(inputState.inputRefCounts, inputRef)
                }

                const ownership = componentReturnOwnership(node, sourceFile)
                if (!ownership) {
                  violations.push(
                    `${location(sourceFile, node)} file input must belong to a component return`,
                  )
                } else {
                  inputState.inputReturnPositions.add(ownership.returnPosition)
                  inputState.inputFunctionPositions.add(ownership.functionPosition)
                  if (inputRef) {
                    recordCount(
                      inputState.inputBranchCounts,
                      `${inputRef}@${ownership.returnPosition}`,
                    )
                  }
                }
              }
            }
          }

          const role = jsxAttribute(node.attributes, 'role')
          if (role) {
            const roleText = role.getText(sourceFile)
            const isStructureViewerDialog =
              // The fullscreen surface is a hand-rolled dialog on purpose: a
              // registry Dialog would remount this subtree and dispose the Mol*
              // viewer, so the wrapper carries the dialog semantics itself.
              relativePath === 'src/features/pdb-viewer/StructureViewer.tsx' &&
              tag === 'div' &&
              (roleText === 'role="dialog"' ||
                roleText === "role={isFullscreen ? 'dialog' : undefined}")
            if (isStructureViewerDialog) structureViewerDialogExceptionCount += 1
            if (
              (roleText.includes('"button"') ||
                roleText.includes("'button'") ||
                roleText.includes('"dialog"') ||
                roleText.includes("'dialog'")) &&
              !isStructureViewerDialog
            ) {
              violations.push(`${location(sourceFile, node)} uses a manual ${roleText}`)
            }
          }

          const target = staticAttributeValue(jsxAttribute(node.attributes, 'target'))
          if (target === '_blank') {
            const rel = staticAttributeValue(jsxAttribute(node.attributes, 'rel')) ?? ''
            const relTokens = new Set(rel.split(/\s+/))
            if (!relTokens.has('noopener') || !relTokens.has('noreferrer')) {
              violations.push(`${location(sourceFile, node)} _blank link requires noopener noreferrer`)
            }
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(sourceFile)

      if (manifest || inputState.intrinsicCount || inputState.registryCount) {
        observedInputs.set(relativePath, inputState)
      }

      for (const match of text.matchAll(rawPalettePattern)) {
        const position = match.index ?? 0
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(position)
        violations.push(
          `${relativePath}:${line + 1}:${character + 1} uses raw palette token ${match[0]}`,
        )
      }
    }

    for (const [path, expected] of fileInputManifest) {
      const observed = observedInputs.get(path)
      expect(expected.reason).not.toHaveLength(0)
      expect(observed, `${path} must keep its documented hidden picker integration`).toMatchObject({
        intrinsicCount: expected.intrinsicCount,
        registryCount: expected.registryCount,
      })
      expect(sortedCounts(observed?.inputRefCounts ?? new Map()), `${path} input refs`).toEqual(
        expected.refInputCounts,
      )
      expect(sortedCounts(observed?.triggerRefCounts ?? new Map()), `${path} picker refs`).toEqual(
        expected.refTriggerCounts,
      )
      expect(
        sortedCounts(observed?.triggerBranchCounts ?? new Map()),
        `${path} each hidden input return tree needs its own connected trigger`,
      ).toEqual(sortedCounts(observed?.inputBranchCounts ?? new Map()))
      expect(observed?.inputReturnPositions.size, `${path} mutually exclusive return trees`).toBe(
        expected.distinctReturnCount,
      )
      expect(observed?.inputFunctionPositions.size, `${path} picker component ownership`).toBe(1)
    }
    expect([...observedInputs.keys()].sort()).toEqual([...fileInputManifest.keys()].sort())
    expect(structureViewerDialogExceptionCount).toBe(1)
    expect(violations).toEqual([])
  })
})
