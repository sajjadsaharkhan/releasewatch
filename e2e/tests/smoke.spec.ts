import { test, expect } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ROLES } from '../roles.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

for (const role of ROLES) {
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
