import { expect, test } from '@playwright/test'


test('ticket identifiers and summaries stay in separate layout columns', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByLabel('邮箱').fill('demo@example.com')
  await page.getByLabel('密码').fill('demo-change-me')
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByRole('button', { name: /工单闭环/ }).click()

  const firstRow = page.locator('.ticket-row').first()
  await expect(firstRow).toBeVisible()
  const numberBox = await firstRow.locator('.ticket-number').boundingBox()
  const contentBox = await firstRow.locator('.ticket-content').boundingBox()
  expect(numberBox).not.toBeNull()
  expect(contentBox).not.toBeNull()
  expect(numberBox!.x + numberBox!.width).toBeLessThanOrEqual(contentBox!.x)

  await page.screenshot({ path: '../../docs/demo/ui-tickets-v2.png', fullPage: true })

  await page.getByRole('button', { name: /智能会话/ }).click()
  await expect(page.locator('.conversation')).toBeVisible()
  await expect(page.locator('.trace')).toBeVisible()
  await page.screenshot({ path: '../../docs/demo/ui-chat-v2.png', fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: /工单闭环/ }).click()
  await expect(page.locator('.ticket-row').first()).toBeVisible()
  const mobileNumber = await page.locator('.ticket-row').first().locator('.ticket-number').boundingBox()
  const mobileContent = await page.locator('.ticket-row').first().locator('.ticket-content').boundingBox()
  expect(mobileNumber).not.toBeNull()
  expect(mobileContent).not.toBeNull()
  expect(mobileContent!.y).toBeGreaterThanOrEqual(mobileNumber!.y + mobileNumber!.height)
  await page.screenshot({ path: '../../docs/demo/ui-tickets-mobile-v2.png', fullPage: true })
})
