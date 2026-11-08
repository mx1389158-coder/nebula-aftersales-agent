import { expect, test } from '@playwright/test'

test('a visitor can register, sign out and sign back in', async ({ page }) => {
  const email = `new-user-${Date.now()}@example.com`
  const password = 'new-user-password'

  await page.goto('/')
  await page.getByRole('button', { name: '立即注册' }).click()
  await expect(page.getByRole('heading', { name: '创建新账户' })).toBeVisible()
  await page.screenshot({ path: '../../docs/demo/ui-register-v2.png', fullPage: true })
  await page.getByLabel('姓名').fill('注册测试用户')
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByLabel('确认密码').fill(password)
  await page.getByRole('button', { name: '注册并登录' }).click()

  await expect(page.getByRole('heading', { name: '智能会话' })).toBeVisible()
  await expect(page.getByText('注册测试用户')).toBeVisible()
  await page.getByRole('button', { name: '退出' }).click()
  await expect(page.getByRole('heading', { name: '登录售后智能台' })).toBeVisible()

  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '智能会话' })).toBeVisible()
})
