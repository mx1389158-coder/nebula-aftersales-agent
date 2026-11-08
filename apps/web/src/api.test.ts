import { describe, expect, it } from 'vitest'
import { IdempotencyAttempt } from './api'

describe('IdempotencyAttempt', () => {
  it('reuses a key while retrying the same logical operation', () => {
    const attempt = new IdempotencyAttempt('web-ticket')
    const payload = { summary: 'X2 无法取得 WAN 地址', contact: '13800000000' }
    expect(attempt.keyFor(payload)).toBe(attempt.keyFor(payload))
  })

  it('generates a new key after success even for the same payload', () => {
    const attempt = new IdempotencyAttempt('web-ticket')
    const payload = { summary: 'X2 无法取得 WAN 地址', contact: '13800000000' }
    const first = attempt.keyFor(payload)
    attempt.complete()
    expect(attempt.keyFor(payload)).not.toBe(first)
  })

  it('starts a new operation when the request payload changes', () => {
    const attempt = new IdempotencyAttempt('web-ticket')
    const first = attempt.keyFor({ summary: '故障 A', contact: '13800000000' })
    expect(attempt.keyFor({ summary: '故障 A', contact: '13900000000' })).not.toBe(first)
  })
})
