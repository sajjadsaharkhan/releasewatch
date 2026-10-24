import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// New issue: the searchable project switcher (BUG-574) and the confirmation the
// modal turns into once an item is filed — its link, Copy link, Create another
// and Open (chosen from a prototype, 2026-10-24). Seed: backend/scripts/seed_e2e.py
// (E2E Product, the default project, and E2E Internal Tools).

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function api(page: Page, method: string, url: string) {
  return page.evaluate(async ({ method, url }) => {
    const res = await fetch(`/api/v1${url}`, {
      method,
      headers: { Authorization: `Bearer ${localStorage.getItem('rw:token')}` },
    })
    if (!res.ok) throw new Error(`${method} ${url} → ${res.status} ${await res.text()}`)
    return res.json()
  }, { method, url })
}

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

test('filing an item shows its link, copies it, and opens it', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('cto'), permissions: ['clipboard-read', 'clipboard-write'] })
  const page = await ctx.newPage()
  const first = `Checkout total overlaps on small screens ${Date.now()}`
  const second = `${first} (second)`

  let modal = await openNewIssue(page)
  await modal.getByLabel('Title', { exact: true }).fill(first)
  await modal.getByRole('button', { name: 'Create bug' }).click()

  // The modal turns into the confirmation instead of closing.
  const done = page.getByRole('dialog', { name: 'Bug created' })
  await expect(done.getByRole('heading', { name: 'Bug created' })).toBeVisible()
  await expect(done).toContainText(first)
  const key = (await done.getByText(/^BUG-\d+$/).textContent())!
  const number = Number(key.split('-')[1])
  const url = `${new URL(page.url()).origin}/issue/bug-${number}`
  await expect(done.getByText(url, { exact: true })).toBeVisible()
  expect((await api(page, 'GET', `/issues/by-number/${number}`)).title).toBe(first)

  // Copy link puts the item's URL on the clipboard.
  await done.getByRole('button', { name: 'Copy link' }).click()
  await expect(done.getByRole('button', { name: 'Copied' })).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url)

  // Create another: a fresh form in the same project.
  await done.getByRole('button', { name: 'Create another' }).click()
  modal = page.getByRole('dialog', { name: 'New bug' })
  await expect(modal.getByLabel('Title', { exact: true })).toHaveValue('')
  await expect(modal.getByLabel('Title', { exact: true })).toBeFocused()
  await expect(modal.getByRole('button', { name: /E2E Product/ })).toBeVisible()

  // ⌘/Ctrl+Enter files it; Open is focused, so Enter goes to the new item.
  await modal.getByLabel('Title', { exact: true }).fill(second)
  await page.keyboard.press('ControlOrMeta+Enter')
  await expect(done.getByRole('button', { name: 'Open bug' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/issue\/bug-\d+$/)
  await expect(page.getByRole('dialog', { name: 'Bug created' })).toHaveCount(0)
  await expect(page.getByText(second).first()).toBeVisible()

  await ctx.close()
})
