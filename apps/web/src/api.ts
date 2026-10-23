const API_ROOT = import.meta.env.VITE_API_ROOT ?? '/api/v1'

const storage = typeof window === 'undefined' ? undefined : window.localStorage
let token = storage?.getItem('aftersales-token') ?? ''

function saveToken(value: string) {
  token = value
  storage?.setItem('aftersales-token', value)
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch(`${API_ROOT}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) throw new Error('邮箱或密码错误')
  saveToken((await response.json()).access_token)
}

export function logout() {
  token = ''
  storage?.removeItem('aftersales-token')
}

async function ensureToken() {
  if (token) return token
  const response = await fetch(`${API_ROOT}/auth/demo-token`, { method: 'POST' })
  if (!response.ok) throw new Error('无法获取演示访问令牌')
  saveToken((await response.json()).access_token)
  return token
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await ensureToken()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export type Citation = {
  chunk_id: string
  title: string
  section: string
  version: string
  page?: number
  score: number
  excerpt: string
}

export type ChatResult = {
  request_id: string
  message_id: string
  thread_id: string
  decision: 'ANSWER' | 'ASK' | 'TOOL' | 'ESCALATE' | 'REFUSE'
  answer: string
  citations: Citation[]
  trace: Array<{ node: string; detail: Record<string, unknown> }>
  pending_action?: Record<string, unknown>
  tool_result?: Record<string, unknown>
  handoff_id?: string
}

export type StreamEvent = { event: string; data: unknown }

export async function streamChat(
  payload: Record<string, unknown>,
  onEvent: (item: StreamEvent) => void,
): Promise<void> {
  const accessToken = await ensureToken()
  const response = await fetch(`${API_ROOT}/chat/stream`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) throw new Error('流式会话连接失败')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      let event = 'message'
      let raw = '{}'
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) raw = line.slice(5).trim()
      }
      onEvent({ event, data: JSON.parse(raw) })
    }
    if (done) break
  }
}

export function stableIdempotencyKey(summary: string): string {
  let hash = 0x811c9dc5
  for (const byte of new TextEncoder().encode(summary.trim())) {
    hash ^= byte
    hash = Math.imul(hash, 0x01000193)
  }
  return `web-${(hash >>> 0).toString(16).padStart(8, '0')}`
}

