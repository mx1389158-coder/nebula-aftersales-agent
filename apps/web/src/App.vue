<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { api, businessApi, IdempotencyAttempt, resumeChat, streamChat, type ChatResult } from './api'
import { useSessionStore, type CurrentUser } from './stores/session'

type Tab = 'chat' | 'devices' | 'knowledge' | 'memory' | 'tickets' | 'skills' | 'evals' | 'admin'
type MemoryItem = { id: string; kind: string; fact: string; confidence: number; status: string; created_at: string }
type DocumentItem = { id: string; title: string; model?: string; firmware_version?: string; doc_version: string; status: string }
type TicketEvent = { event_type: string; from_status?: string; to_status?: string; payload: Record<string, unknown>; created_at: string }
type TicketItem = { id: string; ticket_no: string; status: string; summary: string; contact: string; version: number; created_at: string; events?: TicketEvent[] }
type DeviceItem = { id: string; serial_no: string; nickname?: string; product_name: string; model_code: string; firmware_version: string; version: number }
type EvalRun = { id: string; dataset_version: string; status: string; metrics: Record<string, unknown>; created_at: string }
type Job = { id: string; status: string; progress: number; error?: string; result: Record<string, unknown> }
type Skill = { id: string; name: string; status: string; active_version?: number; rollout_percent: number; success_count: number; failure_count: number }
type ConversationItem = { thread_id: string; title: string; status: string; updated_at: string }
type ProductModel = { id: string; model_code: string; name: string }
type ProductItem = { id: string; product_code: string; name: string; category: string; models: ProductModel[] }
type FirmwareItem = { id: string; model_id: string; version: string; released_at: string }
type AuditItem = { id: string; actor_id: string; action: string; resource_type: string; request_id?: string; trace_id?: string; created_at: string }

const sessionStore = useSessionStore()
const { user: currentUser, threadId } = storeToRefs(sessionStore)

const tab = ref<Tab>('chat')
const busy = ref(false)
const error = ref('')
const conversations = ref<ConversationItem[]>([])
const streamController = ref<AbortController>()
const question = ref('X2 红灯常亮，无法联网应该怎么排查？')
const productId = ref('router')
const model = ref('X2')
const firmware = ref('2.1.0')
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string; result?: ChatResult }>>([])
const memories = ref<MemoryItem[]>([])
const memoryFact = ref('我使用的是 X2 路由器，固件版本 2.1.0')
const documents = ref<DocumentItem[]>([])
const tickets = ref<TicketItem[]>([])
const devices = ref<DeviceItem[]>([])
const selectedDeviceId = ref('')
const evals = ref<EvalRun[]>([])
const ticketSummary = ref('X2 固件 2.1.0 无法取得 WAN 地址，重启后仍未恢复')
const ticketContact = ref('13800000000')
const uploadFile = ref<File>()
const uploadJob = ref<Job>()
const autoMemory = ref(false)
const skills = ref<Skill[]>([])
const chatContact = ref('13800000000')
const needsLogin = ref(false)
const authMode = ref<'login' | 'register'>('login')
const loginEmail = ref('demo@example.com')
const loginPassword = ref('')
const registerName = ref('')
const registerPasswordConfirm = ref('')
const products = ref<ProductItem[]>([])
const firmwares = ref<FirmwareItem[]>([])
const bindModelId = ref('')
const bindFirmwareId = ref('')
const bindSerial = ref('')
const bindNickname = ref('')
const selectedTicket = ref<TicketItem>()
const adminUsers = ref<CurrentUser[]>([])
const auditLogs = ref<AuditItem[]>([])
const adminProductCode = ref('')
const adminProductName = ref('')
const adminProductCategory = ref('')
const adminProductId = ref('')
const adminModelId = ref('')
const adminModelCode = ref('')
const adminModelName = ref('')
const adminFirmwareVersion = ref('')
const adminFirmwareDate = ref(new Date().toISOString().slice(0, 10))
const ticketAttempt = new IdempotencyAttempt('web-ticket')

const nav = computed<Array<{ key: Tab; label: string; index: string; icon: string }>>(() => {
  const items: Array<{ key: Tab; label: string; icon: string }> = [
    { key: 'chat', label: '智能会话', icon: '✦' },
    { key: 'devices', label: '设备中心', icon: '▣' },
    ...(sessionStore.isAdmin ? [{ key: 'knowledge' as const, label: '知识版本', icon: '◇' }] : []),
    { key: 'memory', label: '记忆中心', icon: '◌' },
    { key: 'tickets', label: '工单闭环', icon: '✓' },
    ...(sessionStore.isAdmin ? [
      { key: 'skills' as const, label: '技能治理', icon: '⌘' },
      { key: 'evals' as const, label: '评测观测', icon: '↗' },
      { key: 'admin' as const, label: '平台管理', icon: '⚙' },
    ] : []),
  ]
  return items.map((item, index) => ({ ...item, index: String(index + 1).padStart(2, '0') }))
})

const pageDescriptions: Record<Tab, string> = {
  chat: '基于产品版本与可信证据，为用户提供可追溯的售后建议',
  devices: '管理设备归属、型号及固件信息',
  knowledge: '维护可发布、可回滚的产品知识版本',
  memory: '查看和管理经过用户同意的长期记忆',
  tickets: '创建售后请求，并追踪处理进度与状态流转',
  skills: '审核、发布和回滚 Agent 候选技能',
  evals: '运行固定回归集并查看质量指标',
  admin: '管理用户权限、产品目录与审计记录',
}
const roleLabel = computed(() => ({ USER: '普通用户', SUPPORT: '售后人员', ADMIN: '管理员' })[currentUser.value?.role || 'USER'])
const userInitial = computed(() => currentUser.value?.display_name?.slice(0, 1).toUpperCase() || 'N')

const lastResult = computed(() => [...messages.value].reverse().find((item) => item.result)?.result)

async function run<T>(action: () => Promise<T>) {
  busy.value = true
  error.value = ''
  try { return await action() } catch (reason) {
    error.value = reason instanceof Error ? reason.message : String(reason)
  } finally { busy.value = false }
}

async function sendMessage() {
  const content = question.value.trim()
  if (!content) return
  messages.value.push({ role: 'user', content })
  question.value = ''
  await run(async () => {
    streamController.value = new AbortController()
    const item = reactive({ role: 'assistant' as const, content: '', result: undefined as ChatResult | undefined })
    messages.value.push(item)
    await streamChat({ message: content, thread_id: threadId.value, product_id: productId.value || null, model: model.value || null, firmware_version: firmware.value || null, contact: chatContact.value || null }, ({ event, data }) => {
      if (event === 'meta') {
        const meta = data as Partial<ChatResult>
        sessionStore.setThread(meta.thread_id)
        item.result = { ...meta, answer: '', citations: [], trace: [] } as ChatResult
      } else if (event === 'token') {
        item.content += (data as { text: string }).text
      } else if (event === 'citations' && item.result) {
        item.result.citations = data as ChatResult['citations']
        item.result.answer = item.content
      }
    }, streamController.value.signal)
    await loadConversations()
  })
}

async function cancelStream() {
  streamController.value?.abort()
  if (threadId.value) await api(`/chat/${threadId.value}/cancel`, { method: 'POST' })
  busy.value = false
  await recoverConversation()
}

async function loadConversations() { conversations.value = await api<ConversationItem[]>('/conversations') }
async function recoverConversation(target = threadId.value) {
  if (!target) return
  const detail = await api<{ thread_id: string; messages: Array<{ role: 'user' | 'assistant'; content: string; citations: ChatResult['citations'] }> }>(`/conversations/${target}`)
  sessionStore.setThread(detail.thread_id)
  messages.value = detail.messages.map((item) => ({ role: item.role, content: item.content }))
}
function newConversation() {
  sessionStore.setThread(undefined)
  messages.value = []
}

async function confirmPending() {
  const pending = lastResult.value?.pending_action
  if (!pending) return
  question.value = String(pending.summary || '确认创建工单')
  const content = question.value
  messages.value.push({ role: 'user', content: '确认执行上述操作' })
  question.value = ''
  await run(async () => {
    if (!threadId.value) throw new Error('会话状态不存在，请重新发起请求')
    const result = await resumeChat(threadId.value, { confirmed: true, message: content, contact: pending.contact })
    messages.value.push({ role: 'assistant', content: result.answer, result })
  })
}

async function loadMemories() { memories.value = await api<MemoryItem[]>('/memories') }
async function loadMemorySettings() { autoMemory.value = (await api<{ auto_memory_enabled: boolean }>('/memories/settings')).auto_memory_enabled }
async function setAutoMemory() { await run(async () => { await api('/memories/settings', { method: 'PATCH', body: JSON.stringify({ auto_memory_enabled: autoMemory.value }) }) }) }
async function addMemory() {
  if (!memoryFact.value.trim()) return
  await run(async () => {
    await api('/memories', { method: 'POST', body: JSON.stringify({ kind: 'fact', fact: memoryFact.value, confidence: 1, consent: true }) })
    memoryFact.value = ''
    await loadMemories()
  })
}
async function deleteMemory(id: string) {
  await run(async () => { await api(`/memories/${id}`, { method: 'DELETE' }); await loadMemories() })
}
async function editMemory(item: MemoryItem) {
  const fact = window.prompt('修改记忆', item.fact)
  if (!fact || fact === item.fact) return
  await run(async () => { await api(`/memories/${item.id}`, { method: 'PATCH', body: JSON.stringify({ fact }) }); await loadMemories() })
}

async function loadDocuments() { documents.value = await api<DocumentItem[]>('/documents') }
async function uploadDocument() {
  if (!uploadFile.value) return
  const form = new FormData()
  form.set('file', uploadFile.value)
  form.set('product_id', productId.value)
  form.set('model', model.value)
  form.set('firmware_version', firmware.value)
  form.set('doc_version', `manual-${Date.now()}`)
  await run(async () => {
    uploadJob.value = await api<Job>('/documents', { method: 'POST', body: form })
    while (uploadJob.value && ['queued', 'running'].includes(uploadJob.value.status)) {
      await new Promise((resolve) => window.setTimeout(resolve, 800))
      uploadJob.value = await api<Job>(`/jobs/${uploadJob.value.id}`)
    }
    if (uploadJob.value?.status !== 'completed') throw new Error(uploadJob.value?.error || '文档处理失败')
    await loadDocuments()
  })
}
async function publishDocument(id: string) {
  await run(async () => { await api(`/documents/${id}/publish`, { method: 'POST', body: JSON.stringify({ active: true }) }); await loadDocuments() })
}

async function loadDevices() {
  devices.value = await businessApi<DeviceItem[]>('/devices')
  if (!selectedDeviceId.value && devices.value[0]) selectedDeviceId.value = devices.value[0].id
}
async function loadProducts() {
  products.value = await businessApi<ProductItem[]>('/products')
  if (!bindModelId.value) bindModelId.value = products.value[0]?.models?.[0]?.id || ''
  await loadFirmwares()
}
async function loadFirmwares() {
  if (!bindModelId.value) { firmwares.value = []; return }
  firmwares.value = await businessApi<FirmwareItem[]>(`/products/models/${bindModelId.value}/firmwares`)
  bindFirmwareId.value = firmwares.value[0]?.id || ''
}
async function bindDevice() {
  await run(async () => {
    await businessApi('/devices/bind', { method: 'POST', body: JSON.stringify({ model_id: bindModelId.value, firmware_id: bindFirmwareId.value, serial_no: bindSerial.value, nickname: bindNickname.value || null }) })
    bindSerial.value = ''; bindNickname.value = ''
    await loadDevices()
    ElMessage.success('设备绑定成功')
  })
}
async function loadTickets() { tickets.value = await businessApi<TicketItem[]>('/tickets') }
async function openTicket(id: string) { selectedTicket.value = await businessApi<TicketItem>(`/tickets/${id}`) }
async function updateTicketStatus(ticket: TicketItem, status: string) {
  await run(async () => {
    selectedTicket.value = await businessApi<TicketItem>(`/tickets/${ticket.id}/status`, { method: 'PATCH', body: JSON.stringify({ status, version: ticket.version, note: '由售后工作台更新' }) })
    await loadTickets()
    ElMessage.success('工单状态已更新')
  })
}
async function createTicket() {
  await run(async () => {
    const payload = {
      summary: ticketSummary.value,
      contact: ticketContact.value,
      device_id: selectedDeviceId.value || null,
    }
    await businessApi('/tickets', {
      method: 'POST',
      headers: { 'Idempotency-Key': ticketAttempt.keyFor(payload) },
      body: JSON.stringify(payload),
    })
    ticketAttempt.complete()
    await loadTickets()
    ElMessage.success('工单创建成功')
  })
}

async function loadEvals() { evals.value = await api<EvalRun[]>('/evals') }
async function runEval() {
  await run(async () => { await api('/evals/run', { method: 'POST', body: JSON.stringify({ dataset_version: 'aftersales-eval-v2', retrieval_variant: 'hybrid' }) }); await loadEvals() })
}
async function loadSkills() { skills.value = await api<Skill[]>('/skills') }
async function approveSkill(id: string) { await run(async () => { await api(`/skills/${id}/approve`, { method: 'POST' }); await loadSkills() }) }
async function deactivateSkill(id: string) { await run(async () => { await api(`/skills/${id}/deactivate`, { method: 'POST' }); await loadSkills() }) }

async function switchTab(next: Tab) {
  tab.value = next
  if (next === 'memory') await run(loadMemories)
  if (next === 'devices') await run(async () => { await Promise.all([loadDevices(), loadProducts()]) })
  if (next === 'knowledge') await run(loadDocuments)
  if (next === 'tickets') await run(loadTickets)
  if (next === 'evals') await run(loadEvals)
  if (next === 'skills') await run(loadSkills)
  if (next === 'admin') await run(loadAdmin)
}

async function loadAdmin() {
  [adminUsers.value, auditLogs.value] = await Promise.all([
    businessApi<CurrentUser[]>('/admin/users'),
    businessApi<AuditItem[]>('/admin/audit-logs?limit=100'),
  ])
}
async function updateUser(item: CurrentUser, field: 'status' | 'role', value: string) {
  await run(async () => {
    await businessApi(`/admin/users/${item.id}`, { method: 'PATCH', body: JSON.stringify({ [field]: value }) })
    await loadAdmin()
  })
}
async function createProduct() {
  await run(async () => {
    await businessApi('/products', { method: 'POST', body: JSON.stringify({ product_code: adminProductCode.value, name: adminProductName.value, category: adminProductCategory.value }) })
    adminProductCode.value = ''; adminProductName.value = ''; adminProductCategory.value = ''
    await loadProducts()
  })
}
async function createModel() {
  await run(async () => {
    const modelItem = await businessApi<ProductModel>(`/products/${adminProductId.value}/models`, { method: 'POST', body: JSON.stringify({ model_code: adminModelCode.value, name: adminModelName.value }) })
    adminModelId.value = modelItem.id
    adminModelCode.value = ''; adminModelName.value = ''
    await loadProducts()
  })
}
async function createFirmware() {
  await run(async () => {
    await businessApi(`/products/models/${adminModelId.value}/firmwares`, { method: 'POST', body: JSON.stringify({ version: adminFirmwareVersion.value, released_at: adminFirmwareDate.value }) })
    adminFirmwareVersion.value = ''
    await loadProducts()
  })
}

async function initialize() {
  try {
    await sessionStore.bootstrap()
    await Promise.all([loadMemories(), loadMemorySettings(), loadDevices(), loadProducts(), loadTickets(), loadConversations()])
    if (sessionStore.isAdmin) await Promise.all([loadDocuments(), loadSkills(), loadEvals()])
    if (threadId.value) await recoverConversation()
    needsLogin.value = false
  } catch (reason) {
    needsLogin.value = true
    error.value = reason instanceof Error ? reason.message : String(reason)
  }
}

async function submitLogin() {
  await run(async () => {
    await sessionStore.signIn(loginEmail.value, loginPassword.value)
    await initialize()
  })
}

async function submitRegister() {
  if (loginPassword.value !== registerPasswordConfirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  await run(async () => {
    await sessionStore.signUp(registerName.value, loginEmail.value, loginPassword.value)
    await initialize()
  })
}

function switchAuthMode(mode: 'login' | 'register') {
  authMode.value = mode
  error.value = ''
  loginPassword.value = ''
  registerPasswordConfirm.value = ''
  if (mode === 'register' && loginEmail.value === 'demo@example.com') loginEmail.value = ''
}

function signOut() {
  ticketAttempt.complete()
  sessionStore.signOut()
  tab.value = 'chat'
  messages.value = []
  selectedTicket.value = undefined
  devices.value = []
  tickets.value = []
  adminUsers.value = []
  auditLogs.value = []
  error.value = ''
  authMode.value = 'login'
  loginPassword.value = ''
  registerPasswordConfirm.value = ''
  needsLogin.value = true
}

onMounted(initialize)
</script>

<template>
  <div v-if="needsLogin" class="login-shell">
    <form class="login-card" @submit.prevent="authMode === 'login' ? submitLogin() : submitRegister()">
      <p class="eyebrow">NEBULA CARE / SECURE ACCESS</p>
      <div class="auth-heading">
        <h1>{{ authMode === 'login' ? '登录售后智能台' : '创建新账户' }}</h1>
        <p>{{ authMode === 'login' ? '登录后继续管理设备、会话和售后工单。' : '注册账户后即可使用智能售后服务。' }}</p>
      </div>
      <label v-if="authMode === 'register'">姓名<input v-model.trim="registerName" type="text" autocomplete="name" maxlength="120" required /></label>
      <label>邮箱<input v-model="loginEmail" type="email" autocomplete="username" required /></label>
      <label>密码<input v-model="loginPassword" type="password" :autocomplete="authMode === 'login' ? 'current-password' : 'new-password'" minlength="8" :maxlength="authMode === 'register' ? 72 : 256" required /></label>
      <label v-if="authMode === 'register'">确认密码<input v-model="registerPasswordConfirm" type="password" autocomplete="new-password" minlength="8" maxlength="72" required /></label>
      <button class="primary" :disabled="busy" type="submit">{{ busy ? '请稍候…' : authMode === 'login' ? '登录' : '注册并登录' }}</button>
      <p class="auth-switch">{{ authMode === 'login' ? '还没有账户？' : '已经有账户？' }}<button type="button" @click="switchAuthMode(authMode === 'login' ? 'register' : 'login')">{{ authMode === 'login' ? '立即注册' : '返回登录' }}</button></p>
      <p v-if="error" class="error-banner">{{ error }}</p>
    </form>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">N</div>
        <div><strong>星云智家</strong><span>NEBULA CARE</span></div>
      </div>
      <nav>
        <button v-for="item in nav" :key="item.key" :aria-label="item.label" :class="{ active: tab === item.key }" @click="switchTab(item.key)">
          <span class="nav-icon">{{ item.icon }}</span><span class="nav-label">{{ item.label }}</span><span class="nav-index">{{ item.index }}</span>
        </button>
      </nav>
      <div class="system-card">
        <div class="pulse"></div>
        <div><strong>服务运行正常</strong></div>
      </div>
    </aside>

    <main class="main-content">
      <header class="page-header">
        <div class="page-heading"><p class="eyebrow">NEBULA SERVICE WORKSPACE</p><h1>{{ nav.find((item) => item.key === tab)?.label }}</h1><p class="page-description">{{ pageDescriptions[tab] }}</p></div>
        <div class="user-menu"><div class="user-avatar">{{ userInitial }}</div><div class="user-copy"><strong>{{ currentUser?.display_name }}</strong><span>{{ roleLabel }}</span></div><button class="logout-button" @click="signOut">退出</button></div>
      </header>
      <div v-if="error" class="error-banner">{{ error }}<button @click="error = ''">×</button></div>

      <section v-if="tab === 'chat'" class="chat-layout">
        <div class="conversation panel">
          <div class="context-strip">
            <label>产品<input v-model="productId" /></label>
            <label>型号<input v-model="model" /></label>
            <label>固件<input v-model="firmware" /></label>
            <label>联系方式<input v-model="chatContact" /></label>
          </div>
          <div class="conversation-toolbar">
            <button class="text-button" @click="newConversation">＋ 新会话</button>
            <select :value="threadId || ''" @change="recoverConversation(($event.target as HTMLSelectElement).value)">
              <option value="">选择历史会话</option>
              <option v-for="item in conversations" :key="item.thread_id" :value="item.thread_id">{{ item.title }} · {{ item.status }}</option>
            </select>
          </div>
          <div class="message-list">
            <div v-if="!messages.length" class="empty-state"><span>◎</span><h2>从可追溯证据开始</h2><p>系统会先核对产品与固件版本，再检索发布中的知识。</p></div>
            <article v-for="(messageItem, index) in messages" :key="index" :class="['message', messageItem.role]">
              <small>{{ messageItem.role === 'user' ? 'YOU' : 'NEBULA AGENT' }}</small>
              <p>{{ messageItem.content }}</p>
              <div v-if="messageItem.result?.citations.length" class="citation-row">
                <button v-for="citation in messageItem.result.citations" :key="citation.chunk_id" :title="citation.excerpt">
                  {{ citation.title }} · {{ citation.version }}
                </button>
              </div>
              <button v-if="messageItem.result?.pending_action" class="confirm-action" @click="confirmPending">确认执行写操作</button>
            </article>
          </div>
          <form class="composer" @submit.prevent="sendMessage">
            <textarea v-model="question" rows="3" placeholder="描述故障现象…"></textarea>
            <button v-if="!busy" class="primary">发送请求 →</button>
            <button v-else class="danger-button" type="button" @click="cancelStream">停止并恢复</button>
          </form>
        </div>
        <aside class="trace panel">
          <div class="panel-title"><span>TRACE</span><strong>决策轨迹</strong></div>
          <div v-if="lastResult" class="decision">{{ lastResult.decision }}</div>
          <ol v-if="lastResult">
            <li v-for="item in lastResult.trace" :key="item.node"><span></span><div><strong>{{ item.node }}</strong><code>{{ JSON.stringify(item.detail) }}</code></div></li>
          </ol>
          <div v-else class="trace-placeholder">发送请求后，这里将展示上下文加载、检索与决策节点。</div>
        </aside>
      </section>

      <section v-else-if="tab === 'devices'" class="workspace-grid">
        <div class="panel form-panel"><div class="panel-title"><span>BIND</span><strong>绑定我的设备</strong></div>
          <label>产品型号<select v-model="bindModelId" @change="loadFirmwares"><option v-for="product in products" :key="product.id" disabled>{{ product.name }}</option><option v-for="product in products" :key="`${product.id}-models`" disabled>────────</option><template v-for="product in products" :key="`${product.id}-options`"><option v-for="item in product.models" :key="item.id" :value="item.id">{{ product.name }} · {{ item.model_code }}</option></template></select></label>
          <label>固件<select v-model="bindFirmwareId"><option v-for="item in firmwares" :key="item.id" :value="item.id">{{ item.version }} · {{ item.released_at }}</option></select></label>
          <label>设备序列号<input v-model="bindSerial" placeholder="例如 NB-X2-2026-001" /></label>
          <label>昵称<input v-model="bindNickname" placeholder="例如 客厅路由器" /></label>
          <button class="primary" :disabled="busy || !bindModelId || !bindFirmwareId || !bindSerial" @click="bindDevice">校验并绑定</button>
        </div>
        <div class="panel table-panel"><div class="panel-title"><span>OWNERSHIP</span><strong>我的设备</strong></div>
          <article v-for="device in devices" :key="device.id" class="ticket"><span class="ticket-id">{{ device.model_code }}</span><div><strong>{{ device.nickname || device.product_name }}</strong><small>{{ device.serial_no }} · 固件 {{ device.firmware_version }}</small></div><span class="badge active">已绑定</span></article>
          <div v-if="!devices.length" class="table-empty">暂无绑定设备</div>
        </div>
      </section>

      <section v-else-if="tab === 'knowledge'" class="workspace-grid">
        <div class="panel form-panel"><div class="panel-title"><span>INGEST</span><strong>导入版本化知识</strong></div>
          <div class="dropzone"><input type="file" accept=".pdf,.md,.txt,.html" @change="uploadFile = ($event.target as HTMLInputElement).files?.[0]" /><strong>{{ uploadFile?.name || '选择售后文档' }}</strong><span>PDF / Markdown / TXT / HTML，最大 20MB</span></div>
          <div class="three-fields"><label>产品<input v-model="productId" /></label><label>型号<input v-model="model" /></label><label>固件<input v-model="firmware" /></label></div>
          <button class="primary" :disabled="busy || !uploadFile" @click="uploadDocument">创建草稿索引</button>
          <div v-if="uploadJob" class="job-progress"><span :style="{ width: `${uploadJob.progress * 100}%` }"></span><small>{{ uploadJob.status }} · {{ Math.round(uploadJob.progress * 100) }}%</small></div>
        </div>
        <div class="panel table-panel"><div class="panel-title"><span>VERSIONS</span><strong>知识发布</strong></div>
          <table><thead><tr><th>文档</th><th>适用范围</th><th>版本</th><th>状态</th><th></th></tr></thead><tbody>
            <tr v-for="doc in documents" :key="doc.id"><td>{{ doc.title }}</td><td>{{ doc.model || '通用' }} / {{ doc.firmware_version || '全部' }}</td><td>{{ doc.doc_version }}</td><td><span :class="['badge', doc.status]">{{ doc.status }}</span></td><td><button v-if="doc.status !== 'active'" class="text-button" @click="publishDocument(doc.id)">发布</button></td></tr>
          </tbody></table>
        </div>
      </section>

      <section v-else-if="tab === 'memory'" class="workspace-grid">
        <div class="panel form-panel"><div class="panel-title"><span>CONSENT</span><strong>新增可治理记忆</strong></div>
          <label class="confirm"><input v-model="autoMemory" type="checkbox" @change="setAutoMemory" />允许系统在获得明确证据时自动提议记忆</label>
          <textarea v-model="memoryFact" rows="5" placeholder="仅记录用户明确提供的事实或偏好"></textarea>
          <p class="hint">密码、验证码和完整身份证号会被拦截。记忆始终按 tenant_id + user_id 隔离。</p>
          <button class="primary" :disabled="busy" @click="addMemory">确认并保存</button>
        </div>
        <div class="panel cards-panel"><div class="panel-title"><span>MEMORY</span><strong>我的记忆</strong></div>
          <article v-for="item in memories" :key="item.id" class="memory-card"><div><span class="badge active">{{ item.kind }}</span><small>置信度 {{ item.confidence }}</small></div><p>{{ item.fact }}</p><div class="row-actions"><button class="text-button" @click="editMemory(item)">编辑</button><button class="danger" @click="deleteMemory(item.id)">删除并停止检索</button></div></article>
          <div v-if="!memories.length" class="table-empty">暂无记忆</div>
        </div>
      </section>

      <section v-else-if="tab === 'tickets'" class="workspace-grid">
        <div class="panel form-panel"><div class="panel-title"><span>NEW REQUEST</span><strong>创建售后工单</strong></div>
          <label>关联设备<select v-model="selectedDeviceId"><option value="">不关联设备</option><option v-for="device in devices" :key="device.id" :value="device.id">{{ device.model_code }} · {{ device.nickname || device.serial_no }}</option></select></label>
          <label>故障摘要<textarea v-model="ticketSummary" rows="5" /></label><label>联系方式<input v-model="ticketContact" /></label>
          <button class="primary" :disabled="busy" @click="createTicket">创建工单</button>
        </div>
        <div class="panel table-panel"><div class="panel-title"><span>REQUESTS</span><strong>全部工单</strong></div>
          <article v-for="ticket in tickets" :key="ticket.id" class="ticket ticket-row clickable" @click="openTicket(ticket.id)"><div class="ticket-number"><small>工单编号</small><span class="ticket-id">{{ ticket.ticket_no || `#${ticket.id.slice(0, 8)}` }}</span></div><div class="ticket-content"><strong>{{ ticket.summary }}</strong><small>{{ ticket.contact }}<span>·</span>{{ new Date(ticket.created_at).toLocaleString('zh-CN') }}<span>·</span>版本 {{ ticket.version }}</small></div><span :class="['badge', ticket.status.toLowerCase(), 'ticket-status']">{{ ticket.status }}</span></article>
          <div v-if="!tickets.length" class="table-empty">暂无工单</div>
          <div v-if="selectedTicket" class="ticket-detail"><h3>{{ selectedTicket.ticket_no }} · {{ selectedTicket.status }}</h3>
            <div v-if="sessionStore.isStaff" class="row-actions"><button v-for="status in ['ASSIGNED', 'PROCESSING', 'RESOLVED', 'CLOSED']" :key="status" class="text-button" @click="updateTicketStatus(selectedTicket, status)">{{ status }}</button></div>
            <ol><li v-for="eventItem in selectedTicket.events" :key="eventItem.created_at">{{ eventItem.event_type }} · {{ eventItem.from_status || '-' }} → {{ eventItem.to_status || '-' }} · {{ new Date(eventItem.created_at).toLocaleString('zh-CN') }}</li></ol>
          </div>
        </div>
      </section>

      <section v-else-if="tab === 'skills'" class="workspace-grid">
        <div class="panel score-panel"><div class="panel-title"><span>GOVERNANCE</span><strong>技能发布门禁</strong></div><div class="score-number">P4<span>SKILLS</span></div><p>正向反馈可生成候选技能；静态安全检查和回归用例通过后，管理员才能发布并设置灰度比例。</p></div>
        <div class="panel table-panel"><div class="panel-title"><span>VERSIONS</span><strong>候选与在线技能</strong></div>
          <article v-for="skill in skills" :key="skill.id" class="ticket"><span class="ticket-id">v{{ skill.active_version || '-' }}</span><div><strong>{{ skill.name }}</strong><small>灰度 {{ skill.rollout_percent }}% · 成功 {{ skill.success_count }} / 失败 {{ skill.failure_count }}</small></div><div class="row-actions"><button v-if="skill.status === 'candidate'" class="text-button" @click="approveSkill(skill.id)">审批发布</button><button v-else class="danger" @click="deactivateSkill(skill.id)">停用</button></div></article>
          <div v-if="!skills.length" class="table-empty">暂无候选技能；可从带引用的满意会话中生成。</div>
        </div>
      </section>

      <section v-else-if="tab === 'evals'" class="workspace-grid eval-layout">
        <div class="panel score-panel"><div class="panel-title"><span>REGRESSION</span><strong>固定回归集</strong></div><div class="score-number">300<span>QA</span></div><p>当前仓库包含最小冒烟集；扩展脚本会按方案生成 300 问答 + 100 任务。</p><button class="primary" :disabled="busy" @click="runEval">运行混合检索评测</button></div>
        <div class="panel table-panel"><div class="panel-title"><span>RUNS</span><strong>实验记录</strong></div>
          <article v-for="runItem in evals" :key="runItem.id" class="eval-run"><div><strong>{{ runItem.dataset_version }}</strong><small>{{ runItem.id.slice(0, 8) }} · {{ new Date(runItem.created_at).toLocaleString('zh-CN') }}</small></div><span :class="['badge', runItem.status]">{{ runItem.status }}</span><pre>{{ JSON.stringify(runItem.metrics, null, 2) }}</pre></article>
          <div v-if="!evals.length" class="table-empty">还没有评测记录</div>
        </div>
      </section>

      <section v-else-if="tab === 'admin'" class="workspace-grid">
        <div class="panel form-panel"><div class="panel-title"><span>CATALOG</span><strong>新增产品</strong></div>
          <label>产品编码<input v-model="adminProductCode" placeholder="ROUTER-X" /></label><label>名称<input v-model="adminProductName" /></label><label>分类<input v-model="adminProductCategory" /></label>
          <button class="primary" :disabled="busy || !adminProductCode || !adminProductName || !adminProductCategory" @click="createProduct">新增产品</button>
          <div class="panel-title nested-title"><span>MODEL</span><strong>新增型号</strong></div>
          <label>所属产品<select v-model="adminProductId"><option v-for="item in products" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>型号编码<input v-model="adminModelCode" /></label><label>型号名称<input v-model="adminModelName" /></label>
          <button class="primary" :disabled="busy || !adminProductId || !adminModelCode || !adminModelName" @click="createModel">新增型号</button>
          <div class="panel-title nested-title"><span>FIRMWARE</span><strong>发布固件</strong></div>
          <label>产品型号<select v-model="adminModelId"><template v-for="product in products" :key="product.id"><option v-for="item in product.models" :key="item.id" :value="item.id">{{ product.name }} · {{ item.model_code }}</option></template></select></label><label>固件版本<input v-model="adminFirmwareVersion" /></label><label>发布日期<input v-model="adminFirmwareDate" type="date" /></label>
          <button class="primary" :disabled="busy || !adminModelId || !adminFirmwareVersion" @click="createFirmware">发布固件</button>
        </div>
        <div class="panel table-panel"><div class="panel-title"><span>RBAC</span><strong>用户与角色</strong></div>
          <table><thead><tr><th>用户</th><th>角色</th><th>状态</th></tr></thead><tbody><tr v-for="item in adminUsers" :key="item.id"><td>{{ item.display_name }}<small>{{ item.email }}</small></td><td><select :value="item.role" @change="updateUser(item, 'role', ($event.target as HTMLSelectElement).value)"><option>USER</option><option>SUPPORT</option><option>ADMIN</option></select></td><td><select :value="item.status" @change="updateUser(item, 'status', ($event.target as HTMLSelectElement).value)"><option>ACTIVE</option><option>DISABLED</option></select></td></tr></tbody></table>
          <div class="panel-title audit-title"><span>AUDIT</span><strong>最近审计记录</strong></div>
          <article v-for="item in auditLogs" :key="item.id" class="audit-row"><strong>{{ item.action }}</strong><small>{{ item.resource_type }} · request {{ item.request_id || '-' }} · trace {{ item.trace_id || '-' }}</small></article>
        </div>
      </section>
    </main>
  </div>
</template>

