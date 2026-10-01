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

// Slice 12 — search. The seeded bug (backend/scripts/seed_e2e.py) is indexed
// through the fake embedding endpoint the E2E stack runs.
test.describe('smoke — search', () => {
  test.use({ storageState: path.join(__dirname, '..', '.auth', 'qa.json') })

  const TITLE = 'Reactions disappear in group chat after refresh'

  test('the command palette finds the item, and Enter opens the search page', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible()

    await page.keyboard.press('ControlOrMeta+k')
    const input = page.getByPlaceholder(/search items, pages/i)
    await expect(input).toBeVisible()
    await input.fill('reactions group chat')
    await expect(page.getByText(TITLE)).toBeVisible()

    await input.press('Enter')
    await expect(page).toHaveURL(/\/search\?q=reactions(\+|%20)group(\+|%20)chat/)
    await expect(page.getByRole('heading', { name: 'Search' })).toBeVisible()
    await expect(page.getByRole('button', { name: new RegExp(TITLE) })).toBeVisible()
  })
})
