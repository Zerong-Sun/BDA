import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

const nativeFileInputCounts = new Map([
  ['src/features/artifacts/ArtifactUploadDropzone.tsx', 1],
  ['src/features/lab/InstrumentAnalysis.tsx', 1],
  ['src/features/pdb-viewer/PDBFileUpload.tsx', 2],
  ['src/features/results/ExperimentUpload.tsx', 1],
])

const registryPrimitiveLintIgnores = [
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
].map((filename) => `src/components/ui/${filename}`)

function normalizeFilename(filename) {
  return filename.replaceAll('\\', '/').replace(`${process.cwd().replaceAll('\\', '/')}/`, '')
}

function jsxAttribute(node, name) {
  return node.attributes.find(
    (attribute) => attribute.type === 'JSXAttribute' && attribute.name.name === name,
  )
}

function staticAttributeValue(attribute) {
  if (!attribute?.value) return attribute ? '' : undefined
  if (attribute.value.type === 'Literal') return String(attribute.value.value)
  if (
    attribute.value.type === 'JSXExpressionContainer' &&
    attribute.value.expression.type === 'Literal'
  ) {
    return String(attribute.value.expression.value)
  }
  return undefined
}

const rawUiRule = {
  meta: {
    type: 'problem',
    schema: [],
    messages: {
      rawControl: 'Use the installed shadcn/ReUI control instead of raw <{{name}}>.',
      manualRole: 'Use the registry primitive instead of a manual {{role}} role.',
      invalidFileInput:
        'Native file inputs are limited to the exact hidden browser-picker manifest.',
      fileInputCount:
        'Expected {{expected}} manifested native file input(s) in this file, but found {{actual}}.',
    },
  },
  create(context) {
    const filename = normalizeFilename(context.filename)
    const sourceCode = context.sourceCode
    const forbidden = new Set(['table', 'button', 'select', 'textarea', 'details', 'summary'])
    let validNativeFileInputCount = 0

    return {
      'Program:exit'(node) {
        const expected = nativeFileInputCounts.get(filename)
        if (expected !== undefined && validNativeFileInputCount !== expected) {
          context.report({
            node,
            messageId: 'fileInputCount',
            data: { expected, actual: validNativeFileInputCount },
          })
        }
      },
      JSXOpeningElement(node) {
        if (node.name.type !== 'JSXIdentifier') return
        const name = node.name.name
        if (forbidden.has(name)) {
          context.report({ node, messageId: 'rawControl', data: { name } })
        }

        if (name === 'input') {
          const type = staticAttributeValue(jsxAttribute(node, 'type'))
          const className = staticAttributeValue(jsxAttribute(node, 'className')) ?? ''
          const isManifestFileInput =
            type === 'file' &&
            className.split(/\s+/).includes('hidden') &&
            nativeFileInputCounts.has(filename)
          if (!isManifestFileInput) {
            context.report({ node, messageId: 'invalidFileInput' })
          } else {
            validNativeFileInputCount += 1
          }
        }

        const roleAttribute = jsxAttribute(node, 'role')
        if (!roleAttribute) return
        const roleText = sourceCode.getText(roleAttribute)
        const role = roleText.includes('button')
          ? 'button'
          : roleText.includes('dialog')
            ? 'dialog'
            : null
        if (!role) return
        // The Mol* fullscreen surface owns its dialog semantics: a registry
        // Dialog would remount the subtree and dispose the WebGL viewer.
        const isStructureViewerFullscreenDialog =
          filename === 'src/features/pdb-viewer/StructureViewer.tsx' &&
          name === 'div' &&
          (roleText === 'role="dialog"' ||
            roleText === "role={isFullscreen ? 'dialog' : undefined}")
        if (!isStructureViewerFullscreenDialog) {
          context.report({ node: roleAttribute, messageId: 'manualRole', data: { role } })
        }
      },
    }
  },
}

export default defineConfig([
  globalIgnores([
    'dist',
    'src/lib/api/generated',
    'src/components/reui/**',
    'src/components/examples/**',
  ]),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'lucide-react',
              message: 'Use verified @phosphor-icons/react exports.',
            },
          ],
          patterns: [
            {
              regex:
                '(^|/)(legacy-button|legacy-input|legacy-skeleton|legacy-tabs|Card|Divider|Row)$',
              message: 'Use active registry primitives or semantic ReUI compositions.',
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      'src/app/**/*.tsx',
      'src/features/**/*.tsx',
      'src/lib/**/*.tsx',
      'src/components/ui/**/*.tsx',
    ],
    ignores: [
      '**/*.test.tsx',
      '**/*.spec.tsx',
      ...registryPrimitiveLintIgnores,
    ],
    plugins: {
      'bda-migration': {
        rules: {
          'no-raw-ui': rawUiRule,
        },
      },
    },
    rules: {
      'bda-migration/no-raw-ui': 'error',
    },
  },
  {
    files: ['src/components/ui/**/*.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
