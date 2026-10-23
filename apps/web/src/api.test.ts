import { describe, expect, it } from 'vitest'
import { stableIdempotencyKey } from './api'

describe('stableIdempotencyKey', () => {
  it('is stable for the same Chinese summary', () => {
    const summary = 'X2 无法取得 WAN 地址'
    expect(stableIdempotencyKey(summary)).toBe(stableIdempotencyKey(` ${summary} `))
  })

  it('changes when the summary changes', () => {
    expect(stableIdempotencyKey('故障 A')).not.toBe(stableIdempotencyKey('故障 B'))
  })
})
