import { describe, expect, it } from 'vitest'
import { jsonArray, jsonRecord, text } from './jsonHelpers'

describe('research jsonHelpers', () => {
  it('parses JSON strings into records', () => {
    expect(jsonRecord('{"a":1}')).toEqual({ a: 1 })
  })

  it('returns empty array for invalid JSON arrays', () => {
    expect(jsonArray('not-json')).toEqual([])
  })

  it('coerces unknown values to empty text', () => {
    expect(text(42)).toBe('')
  })
})
