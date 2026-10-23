<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, login, logout, stableIdempotencyKey, streamChat, type ChatResult } from './api'

type Tab = 'chat' | 'knowledge' | 'memory' | 'tickets' | 'skills' | 'evals'
type MemoryItem = { id: string; kind: string; fact: string; confidence: number; status: string; created_at: string }
type DocumentItem = { id: string; title: string; model?: string; firmware_version?: string; doc_version: string; status: string }
type TicketItem = { id: string; status: string; summary: string; contact: string; created_at: string }
type EvalRun = { id: string; dataset_version: string; status: string; metrics: Record<string, unknown>; created_at: string }
type Job = { id: string; status: string; progress: number; error?: string; result: Record<string, unknown> }
type Skill = { id: string; name: string; status: string; active_version?: number; rollout_percent: number; success_count: number; failure_count: number }

const tab = ref<Tab>('chat')
const busy = ref(false)
const error = ref('')
const threadId = ref<string>()
const question = ref('X2 红灯常亮，无法联网应该怎么排查？')
const productId = ref('router')
const model = ref('X2')
const firmware = ref('2.1.0')
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string; result?: ChatResult }>>([])
const memories = ref<MemoryItem[]>([])
const memoryFact = ref('我使用的是 X2 路由器，固件版本 2.1.0')
const documents = ref<DocumentItem[]>([])
const tickets = ref<TicketItem[]>([])
const evals = ref<EvalRun[]>([])
const ticketSummary = ref('X2 固件 2.1.0 无法取得 WAN 地址，重启后仍未恢复')
const ticketContact = ref('13800000000')
const ticketConfirmed = ref(false)
const uploadFile = ref<File>()
const uploadJob = ref<Job>()
const autoMemory = ref(false)
const skills = ref<Skill[]>([])
const chatContact = ref('13800000000')
const needsLogin = ref(false)
const loginEmail = ref('')
const loginPassword = ref('')

const nav = [
  { key: 'chat', label: '智能会话', index: '01' },
  { key: 'knowledge', label: '知识版本', index: '02' },
  { key: 'memory', label: '记忆中心', index: '03' },
  { key: 'tickets', label: '工单闭环', index: '04' },
  { key: 'skills', label: '技能治理', index: '05' },
  { key: 'evals', label: '评测观测', index: '06' },
] as const

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
    const item = reactive({ role: 'assistant' as const, content: '', result: undefined as ChatResult | undefined })
    messages.value.push(item)
    await streamChat({ message: content, thread_id: threadId.value, product_id: productId.value || null, model: model.value || null, firmware_version: firmware.value || null, contact: chatContact.value || null }, ({ event, data }) => {
      if (event === 'meta') {
        const meta = data as Partial<ChatResult>
        threadId.value = meta.thread_id
        item.result = { ...meta, answer: '', citations: [], trace: [] } as ChatResult
      } else if (event === 'token') {
        item.content += (data as { text: string }).text
      } else if (event === 'citations' && item.result) {
        item.result.citations = data as ChatResult['citations']
        item.result.answer = item.content
      }
    })
  })
}

async function confirmPending() {
  const pending = lastResult.value?.pending_action
  if (!pending) return
  question.value = String(pending.summary || '确认创建工单')
  const content = question.value
  messages.value.push({ role: 'user', content: '确认执行上述操作' })
  question.value = ''
  await run(async () => {
    const result = await api<ChatResult>('/chat', { method: 'POST', body: JSON.stringify({ message: content, thread_id: threadId.value, confirmed: true, contact: pending.contact }) })
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

async function loadTickets() { tickets.value = await api<TicketItem[]>('/tickets') }
async function createTicket() {
  await run(async () => {
    await api('/tickets', { method: 'POST', body: JSON.stringify({ summary: ticketSummary.value, contact: ticketContact.value, idempotency_key: stableIdempotencyKey(ticketSummary.value), confirmed: ticketConfirmed.value }) })
    await loadTickets()
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
  if (next === 'knowledge') await run(loadDocuments)
  if (next === 'tickets') await run(loadTickets)
  if (next === 'evals') await run(loadEvals)
  if (next === 'skills') await run(loadSkills)
}

async function initialize() {
  try {
    await Promise.all([loadMemories(), loadMemorySettings(), loadDocuments(), loadTickets(), loadSkills(), loadEvals()])
    needsLogin.value = false
  } catch (reason) {
    needsLogin.value = true
    error.value = reason instanceof Error ? reason.message : String(reason)
  }
}

async function submitLogin() {
  await run(async () => {
    await login(loginEmail.value, loginPassword.value)
    await initialize()
  })
}

function signOut() {
  logout()
  needsLogin.value = true
}

onMounted(initialize)
</script>

<template>
  <div v-if="needsLogin" class="login-shell">
    <form class="login-card" @submit.prevent="submitLogin">
      <p class="eyebrow">NEBULA CARE / SECURE ACCESS</p>
      <h1>登录售后智能台</h1>
      <label>邮箱<input v-model="loginEmail" type="email" autocomplete="username" required /></label>
      <label>密码<input v-model="loginPassword" type="password" autocomplete="current-password" required /></label>
      <button class="primary" :disabled="busy" type="submit">登录</button>
      <p v-if="error" class="error-banner">{{ error }}</p>
    </form>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">N</div>
        <div><strong>NEBULA CARE</strong><span>星云智家 · 售后智能台</span></div>
      </div>
      <nav>
        <button v-for="item in nav" :key="item.key" :class="{ active: tab === item.key }" @click="switchTab(item.key)">
          <span>{{ item.index }}</span>{{ item.label }}
        </button>
      </nav>
      <div class="system-card">
        <div class="pulse"></div>
        <div><strong>LOCAL SYSTEM</strong><span>API · RAG · Memory</span></div>
      </div>
    </aside>

    <main>
      <header>
        <div><p class="eyebrow">AFTERSALES INTELLIGENCE / 2026</p><h1>{{ nav.find((item) => item.key === tab)?.label }}</h1></div>
        <div class="status"><span></span>服务在线 <button class="text-button" @click="signOut">退出</button></div>
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
            <button class="primary" :disabled="busy">{{ busy ? '处理中…' : '发送请求 →' }}</button>
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
        <div class="panel form-panel"><div class="panel-title"><span>WRITE TOOL</span><strong>创建售后工单</strong></div>
          <label>故障摘要<textarea v-model="ticketSummary" rows="5" /></label><label>联系方式<input v-model="ticketContact" /></label>
          <label class="confirm"><input v-model="ticketConfirmed" type="checkbox" />我已核对摘要和联系方式，确认创建工单</label>
          <button class="primary" :disabled="busy" @click="createTicket">提交幂等写操作</button>
        </div>
        <div class="panel table-panel"><div class="panel-title"><span>TIMELINE</span><strong>工单状态</strong></div>
          <article v-for="ticket in tickets" :key="ticket.id" class="ticket"><span class="ticket-id">#{{ ticket.id.slice(0, 8) }}</span><div><strong>{{ ticket.summary }}</strong><small>{{ ticket.contact }} · {{ new Date(ticket.created_at).toLocaleString() }}</small></div><span class="badge active">{{ ticket.status }}</span></article>
          <div v-if="!tickets.length" class="table-empty">暂无工单</div>
        </div>
      </section>

      <section v-else-if="tab === 'skills'" class="workspace-grid">
        <div class="panel score-panel"><div class="panel-title"><span>GOVERNANCE</span><strong>技能发布门禁</strong></div><div class="score-number">P4<span>SKILLS</span></div><p>正向反馈可生成候选技能；静态安全检查和回归用例通过后，管理员才能发布并设置灰度比例。</p></div>
        <div class="panel table-panel"><div class="panel-title"><span>VERSIONS</span><strong>候选与在线技能</strong></div>
          <article v-for="skill in skills" :key="skill.id" class="ticket"><span class="ticket-id">v{{ skill.active_version || '-' }}</span><div><strong>{{ skill.name }}</strong><small>灰度 {{ skill.rollout_percent }}% · 成功 {{ skill.success_count }} / 失败 {{ skill.failure_count }}</small></div><div class="row-actions"><button v-if="skill.status === 'candidate'" class="text-button" @click="approveSkill(skill.id)">审批发布</button><button v-else class="danger" @click="deactivateSkill(skill.id)">停用</button></div></article>
          <div v-if="!skills.length" class="table-empty">暂无候选技能；可从带引用的满意会话中生成。</div>
        </div>
      </section>

      <section v-else class="workspace-grid eval-layout">
        <div class="panel score-panel"><div class="panel-title"><span>REGRESSION</span><strong>固定回归集</strong></div><div class="score-number">300<span>QA</span></div><p>当前仓库包含最小冒烟集；扩展脚本会按方案生成 300 问答 + 100 任务。</p><button class="primary" :disabled="busy" @click="runEval">运行混合检索评测</button></div>
        <div class="panel table-panel"><div class="panel-title"><span>RUNS</span><strong>实验记录</strong></div>
          <article v-for="runItem in evals" :key="runItem.id" class="eval-run"><div><strong>{{ runItem.dataset_version }}</strong><small>{{ runItem.id.slice(0, 8) }} · {{ new Date(runItem.created_at).toLocaleString() }}</small></div><span :class="['badge', runItem.status]">{{ runItem.status }}</span><pre>{{ JSON.stringify(runItem.metrics, null, 2) }}</pre></article>
          <div v-if="!evals.length" class="table-empty">还没有评测记录</div>
        </div>
      </section>
    </main>
  </div>
</template>

