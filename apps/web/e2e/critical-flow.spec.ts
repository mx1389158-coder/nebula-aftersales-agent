import { expect, test } from '@playwright/test'

test('chat evidence, governed memory and confirmed ticket work end to end', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '智能会话' })).toBeVisible()

  await page.getByRole('button', { name: /发送请求/ }).click()
  await expect(page.locator('.message.assistant')).toContainText('排查')
  await expect(page.locator('.citation-row button').first()).toBeVisible()
  await expect(page.locator('.decision')).toHaveText('ANSWER')

  await page.getByRole('button', { name: /记忆中心/ }).click()
  const memoryText = `E2E 偏好 ${Date.now()}`
  await page.locator('.form-panel textarea').fill(memoryText)
  await page.getByRole('button', { name: '确认并保存' }).click()
  await expect(page.locator('.memory-card', { hasText: memoryText })).toBeVisible()

  await page.getByRole('button', { name: /工单闭环/ }).click()
  const summary = `E2E 无法联网 ${Date.now()}`
  await page.getByLabel('故障摘要').fill(summary)
  await page.getByLabel(/我已核对摘要/).check()
  await page.getByRole('button', { name: '提交幂等写操作' }).click()
  await expect(page.locator('.ticket', { hasText: summary })).toBeVisible()
})
