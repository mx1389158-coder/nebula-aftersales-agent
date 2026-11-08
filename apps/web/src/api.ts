const AI_API_ROOT = import.meta.env.VITE_AI_API_ROOT ?? '/api/ai/v1'
const BUSINESS_API_ROOT = import.meta.env.VITE_BUSINESS_API_ROOT ?? '/api/business/v1'

const storage = typeof window === 'undefined' ? undefined : window.localStorage
let token = storage?.getItem('aftersales-token') ?? ''

function saveToken(value: string) {
  token = value
  storage?.setItem('aftersales-token', value)
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${BUSINESS_API_ROOT}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error(await authError(response, '邮箱或密码错误'))
  saveToken((await response.json()).access_token)
}

export async function registerAccount(displayName: string, email: string, password: string): Promise<void> {
  const response = await fetch(`${BUSINESS_API_ROOT}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName, email, password }),
  })
  if (!response.ok) throw new Error(await authError(response, '注册失败，请稍后重试'))
  saveToken((await response.json()).access_token)
}

async function authError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => undefined) as { message?: string; detail?: string } | undefined
  return body?.message || body?.detail || fallback
}

export function logout() {
  token = ''
  storage?.removeItem('aftersales-token')
}

async function ensureToken() {
  if (token) return token
  throw new Error('请先登录')
}

async function request<T>(root: string, path: string, init: RequestInit = {}): Promise<T> {
  const accessToken = await ensureToken()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  headers.set('X-Request-ID', crypto.randomUUID())
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${root}${path}`, { ...init, headers })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  return request<T>(AI_API_ROOT, path, init)
}

export function businessApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  return request<T>(BUSINESS_API_ROOT, path, init)
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
  signal?: AbortSignal,
): Promise<void> {
  const accessToken = await ensureToken()
  const response = await fetch(`${AI_API_ROOT}/chat/stream`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
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

export function resumeChat(
  threadId: string,
  payload: Record<string, unknown>,
): Promise<ChatResult> {
  return api<ChatResult>(`/chat/${threadId}/resume`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export class IdempotencyAttempt {
  private key?: string
  private fingerprint?: string

  constructor(private readonly prefix: string) {}

  keyFor(payload: Record<string, unknown>): string {
    const fingerprint = JSON.stringify(payload)
    if (!this.key || this.fingerprint !== fingerprint) {
      this.key = `${this.prefix}-${crypto.randomUUID()}`
      this.fingerprint = fingerprint
    }
    return this.key
  }

  complete(): void {
    this.key = undefined
    this.fingerprint = undefined
  }
}

