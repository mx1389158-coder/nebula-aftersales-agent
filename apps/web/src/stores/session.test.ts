import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSessionStore } from './session'

describe('session store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('clears the previous account conversation on sign out', () => {
    const session = useSessionStore()
    session.setThread('user-a-thread')

    session.signOut()

    expect(session.threadId).toBeUndefined()
  })
})
