import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// New issue: the searchable project switcher (BUG-574). Seed:
// backend/scripts/seed_e2e.py (E2E Product, the default project, and E2E Internal Tools).

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function openNewIssue(page: Page) {
  await page.goto('/inbox')
  await page.getByRole('button', { name: 'New issue' }).first().click()
  const modal = page.getByRole('dialog', { name: 'New bug' })
  await expect(modal.getByLabel('Title', { exact: true })).toBeVisible()
  return modal
}

test('the project switcher searches, picks with the keyboard, and Escape keeps the modal', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('cto') })
  const page = await ctx.newPage()
  const modal = await openNewIssue(page)

  const trigger = modal.getByRole('button', { name: /E2E Product/ })
  await trigger.click()
  const search = page.getByLabel('Search projects')
  const list = page.getByRole('listbox', { name: 'Projects' })
  await expect(search).toBeFocused()
  await expect(list.getByRole('option')).toHaveCount(2)

  // By name, and by slug.
  await search.fill('internal')
  await expect(list.getByRole('option')).toHaveCount(1)
  await expect(list.getByRole('option')).toContainText('E2E Internal Tools')
  await search.fill('e2e-product')
  await expect(list.getByRole('option')).toHaveCount(1)
  await expect(list.getByRole('option')).toContainText('E2E Product')

  await search.fill('nothing-like-this')
  await expect(list.getByRole('option')).toHaveCount(0)
  await expect(page.getByText('No project matches “nothing-like-this”.')).toBeVisible()

  // Enter picks the highlighted match and closes the menu.
  await search.fill('tools')
  await search.press('Enter')
  await expect(list).toBeHidden()
  await expect(modal.getByRole('button', { name: /E2E Internal Tools/ })).toBeVisible()

  // Escape closes the menu only — the half-written item stays open.
  await modal.getByRole('button', { name: /E2E Internal Tools/ }).click()
  await expect(list).toBeVisible()
  await search.press('Escape')
  await expect(list).toBeHidden()
  await expect(modal).toBeVisible()

  await ctx.close()
})
