import { expect, test, type Page } from '@playwright/test'

async function login(page: Page, email: string, password: string) {
  await page.goto('/')
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '智能会话' })).toBeVisible()
}

test('user, support and admin complete the authoritative aftersales loop', async ({ page }) => {
  await login(page, 'demo@example.com', 'demo-change-me')

  await page.getByRole('button', { name: /发送请求/ }).click()
  await expect(page.locator('.message.assistant')).toContainText('排查')
  await expect(page.locator('.citation-row button').first()).toBeVisible()
  await expect(page.locator('.decision')).toHaveText('ANSWER')

  await page.getByRole('button', { name: /新会话/ }).click()
  await expect(page.locator('.message')).toHaveCount(0)
  await page.locator('.conversation-toolbar select').selectOption({ index: 1 })
  await expect(page.locator('.message.assistant')).toBeVisible()

  await page.getByRole('button', { name: /设备中心/ }).click()
  const serial = `E2E-X2-${Date.now()}`
  await page.getByLabel('设备序列号').fill(serial)
  await page.getByLabel('昵称').fill('E2E 路由器')
  await page.getByRole('button', { name: '校验并绑定' }).click()
  await expect(page.locator('.ticket', { hasText: serial })).toBeVisible()

  await page.getByRole('button', { name: /记忆中心/ }).click()
  const memoryText = `E2E 偏好 ${Date.now()}`
  await page.locator('.form-panel textarea').fill(memoryText)
  await page.getByRole('button', { name: '确认并保存' }).click()
  await expect(page.locator('.memory-card', { hasText: memoryText })).toBeVisible()

  await page.getByRole('button', { name: /工单闭环/ }).click()
  const summary = `E2E 无法联网 ${Date.now()}`
  await page.getByLabel('故障摘要').fill(summary)
  await page.getByRole('button', { name: '创建工单' }).click()
  await expect(page.locator('.ticket', { hasText: summary })).toBeVisible()

  await page.getByRole('button', { name: '退出' }).click()
  await login(page, 'support@example.com', 'support-change-me')
  await page.getByRole('button', { name: /工单闭环/ }).click()
  await page.locator('.ticket', { hasText: summary }).click()
  await page.getByRole('button', { name: 'ASSIGNED' }).click()
  await expect(page.locator('.ticket-detail')).toContainText('ASSIGNED')

  await page.getByRole('button', { name: '退出' }).click()
  await login(page, 'admin@example.com', 'admin-change-me')
  await page.getByRole('button', { name: /平台管理/ }).click()
  await expect(page.getByText('用户与角色')).toBeVisible()
  await expect(page.getByText('最近审计记录')).toBeVisible()
  expect(await page.locator('tbody tr').count()).toBeGreaterThanOrEqual(3)
})
