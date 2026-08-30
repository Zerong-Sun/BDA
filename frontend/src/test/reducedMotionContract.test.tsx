import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Button } from '@/components/ui/Button'
import { Progress } from '@/components/ui/progress'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'

const root = resolve(import.meta.dirname, '../..')

function extractReducedMotionRule(styles: string) {
  const marker = '@media (prefers-reduced-motion: reduce)'
  const start = styles.indexOf(marker)
  if (start < 0) return ''

  const firstBrace = styles.indexOf('{', start)
  let depth = 0

  for (let index = firstBrace; index < styles.length; index += 1) {
    if (styles[index] === '{') depth += 1
    if (styles[index] === '}') depth -= 1
    if (depth === 0) return styles.slice(start, index + 1)
  }

  return ''
}

function declarationsCovering(
  element: Element,
  rules: CSSRuleList | readonly CSSRule[],
) {
  return Array.from(rules).flatMap((rule) => {
    if (rule.type !== CSSRule.STYLE_RULE) return []
    const styleRule = rule as CSSStyleRule
    const matches = styleRule.selectorText
      .split(',')
      .map((selector) => selector.trim())
      .filter((selector) => !selector.includes('::'))
      .some((selector) => element.matches(selector))

    return matches ? [styleRule.style] : []
  })
}

function effectiveDeclaration(
  declarations: CSSStyleDeclaration[],
  property: string,
) {
  return declarations.reduce(
    (value, declaration) => declaration.getPropertyValue(property).trim() || value,
    '',
  )
}

function effectivePriority(
  declarations: CSSStyleDeclaration[],
  property: string,
) {
  return declarations.reduce(
    (priority, declaration) =>
      declaration.getPropertyValue(property).trim()
        ? declaration.getPropertyPriority(property)
        : priority,
    '',
  )
}

function MotionContractSurface() {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button type="button" />}>Open run settings</SheetTrigger>
      <SheetContent>
        <SheetTitle>Run settings</SheetTitle>
        <SheetDescription>Configure this run.</SheetDescription>
        <Tabs defaultValue="summary">
          <TabsList>
            <TabsTrigger value="summary">Summary</TabsTrigger>
          </TabsList>
          <TabsContent value="summary">Summary content</TabsContent>
        </Tabs>
        <Progress value={40} aria-label="Run progress" />
        <Button type="button">Run model</Button>
      </SheetContent>
    </Sheet>
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  document.querySelector('style[data-reduced-motion-contract]')?.remove()
})

describe('global reduced-motion contract', () => {
  it('neutralizes non-essential motion before mount without breaking Sheet close and focus return', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }))

    const reducedMotionRule = extractReducedMotionRule(
      readFileSync(resolve(root, 'src/index.css'), 'utf8'),
    )
    const stylesheet = document.createElement('style')
    stylesheet.dataset.reducedMotionContract = ''
    stylesheet.textContent = reducedMotionRule
    document.head.append(stylesheet)

    const mediaRule = Array.from(stylesheet.sheet?.cssRules ?? []).find(
      (rule) => rule.type === CSSRule.MEDIA_RULE,
    ) as CSSMediaRule | undefined

    expect(mediaRule).toBeDefined()
    expect(window.matchMedia(mediaRule?.conditionText ?? '').matches).toBe(true)

    const universalRule = Array.from(mediaRule?.cssRules ?? []).find(
      (rule) =>
        rule.type === CSSRule.STYLE_RULE &&
        (rule as CSSStyleRule).selectorText.split(',').includes('*'),
    ) as CSSStyleRule | undefined
    expect(
      universalRule?.selectorText
        .split(',')
        .map((selector) => selector.trim())
        .sort(),
    ).toEqual(['*', '*::after', '*::before'])

    render(<MotionContractSurface />)
    const focusOrigin = screen.getByRole('button', { name: 'Open run settings' })
    focusOrigin.focus()
    expect(focusOrigin).toHaveFocus()

    fireEvent.click(focusOrigin)

    const dialog = screen.getByRole('dialog', { name: 'Run settings' })
    const movingSurfaces = [
      dialog,
      within(dialog).getByRole('tab', { name: 'Summary' }),
      within(dialog).getByRole('progressbar', { name: 'Run progress' }).querySelector(
        '[data-slot="progress-indicator"]',
      ),
      within(dialog).getByRole('button', { name: 'Run model' }),
    ]

    for (const surface of movingSurfaces) {
      expect(surface).not.toBeNull()
      expect(surface?.className).toMatch(/(?:animate|duration|transition)/)
    }

    for (const surface of movingSurfaces) {
      const declarations = declarationsCovering(surface as Element, mediaRule?.cssRules ?? [])

      expect(effectiveDeclaration(declarations, 'animation-delay')).toBe('0ms')
      expect(effectiveDeclaration(declarations, 'animation-duration')).toBe('0.01ms')
      expect(effectiveDeclaration(declarations, 'animation-iteration-count')).toBe('1')
      expect(effectiveDeclaration(declarations, 'transition-duration')).toBe('0.01ms')
      expect(effectiveDeclaration(declarations, 'transition-delay')).toBe('0ms')
      expect(effectiveDeclaration(declarations, 'scroll-behavior')).toBe('auto')
      expect(effectiveDeclaration(declarations, 'scroll-snap-type')).toBe('none')

      for (const property of [
        'animation-delay',
        'animation-duration',
        'animation-iteration-count',
        'transition-duration',
        'transition-delay',
        'scroll-behavior',
        'scroll-snap-type',
      ]) {
        expect(effectivePriority(declarations, property), property).toBe('important')
      }
    }

    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Run settings' })).not.toBeInTheDocument()
      expect(focusOrigin).toHaveFocus()
    })
    expect(focusOrigin.isConnected).toBe(true)
  })
})
