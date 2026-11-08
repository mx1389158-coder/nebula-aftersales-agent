import { defineStore } from 'pinia'
import { businessApi, login, logout, registerAccount } from '../api'

export type CurrentUser = {
  id: string
  tenant_id: string
  username: string
  email: string
  display_name: string
  role: 'USER' | 'SUPPORT' | 'ADMIN'
  status: 'ACTIVE' | 'DISABLED'
}

const storage = typeof window === 'undefined' ? undefined : window.localStorage

export const useSessionStore = defineStore('session', {
  state: () => ({
    user: undefined as CurrentUser | undefined,
    threadId: storage?.getItem('aftersales-thread') || undefined as string | undefined,
  }),
  getters: {
    isStaff: (state) => ['SUPPORT', 'ADMIN'].includes(state.user?.role || ''),
    isAdmin: (state) => state.user?.role === 'ADMIN',
  },
  actions: {
    async bootstrap() {
      this.user = await businessApi<CurrentUser>('/users/me')
    },
    async signIn(username: string, password: string) {
      await login(username, password)
      await this.bootstrap()
    },
    async signUp(displayName: string, email: string, password: string) {
      await registerAccount(displayName, email, password)
      await this.bootstrap()
    },
    signOut() {
      logout()
      this.user = undefined
      this.setThread(undefined)
    },
    setThread(threadId?: string) {
      this.threadId = threadId
      if (threadId) storage?.setItem('aftersales-thread', threadId)
      else storage?.removeItem('aftersales-thread')
    },
  },
})
