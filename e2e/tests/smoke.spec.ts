import { test, expect } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { TECH_ROLES } from '../roles.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

for (const role of TECH_ROLES) {
  test.describe(`smoke — ${role}`, () => {
    test.use({ storageState: path.join(__dirname, '..', '.auth', `${role}.json`) })

    test(`dashboard renders with no console errors`, async ({ page }) => {
      const consoleErrors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text())
      })
      page.on('pageerror', (err) => consoleErrors.push(err.message))

      await page.goto('/dashboard')
      await expect(page).toHaveURL(/\/dashboard$/)
      await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible()

      expect(consoleErrors, `console errors: ${consoleErrors.join('\n')}`).toEqual([])
    })
  })
}

test.describe('smoke — support', () => {
  test.use({ storageState: path.join(__dirname, '..', '.auth', 'support.json') })

  test('tech screens redirect to the inbox, with a minimal nav and no console errors', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })
    page.on('pageerror', (err) => consoleErrors.push(err.message))

    for (const screen of ['/dashboard', '/issues', '/releases', '/search']) {
      await page.goto(screen)
      await expect(page).toHaveURL(/\/inbox$/)
    }
    const nav = page.getByRole('complementary')
    await expect(nav.getByRole('link', { name: 'Inbox' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Dashboard' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /new issue/i })).toHaveCount(0)

    expect(consoleErrors, `console errors: ${consoleErrors.join('\n')}`).toEqual([])
  })
})
