import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './Tabs'

afterEach(cleanup)

describe('TabsContent', () => {
  it('provides a visible focus treatment when the panel receives keyboard focus', () => {
    render(
      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
        </TabsList>
        <TabsContent value="summary">Summary content</TabsContent>
      </Tabs>,
    )

    expect(screen.getByRole('tabpanel')).toHaveClass(
      'focus-visible:ring-[3px]',
      'focus-visible:ring-ring/50',
    )
  })
})
