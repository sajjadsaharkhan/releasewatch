import { test, expect, type Browser, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Settings — guided sections (grouped side nav + section header, chosen from
// the ?variant= prototype round, 2026-10-01) and the General tab's timezone
// Select. The timezone control was a Dropdown with width="w-full", which made
// the placement math NaN and dropped the portaled menu into the viewport's
// top-left corner; the geometry assertions pin it back under its trigger.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function api(page: Page, method: string, url: string, body?: unknown) {
  return page.evaluate(async ({ method, url, body }) => {
    const res = await fetch(`/api/v1${url}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('rw:token')}`,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`${method} ${url} → ${res.status} ${await res.text()}`)
    return res.status === 204 ? null : res.json()
  }, { method, url, body })
}

async function asRole(browser: Browser, role: string) {
  const ctx = await browser.newContext({ storageState: auth(role) })
  const page = await ctx.newPage()
  await page.goto('/inbox')
  return { ctx, page }
}

// The Select's portaled panel — createPortal(document.body) is the only thing
// that puts a direct z-[100] child on <body> (toasts live inside the app root).
const portaledPanel = (page: Page) => page.locator('body > div[class*="z-[100]"]')
// The timezone trigger — the only .h-9 control in General carrying an offset.
const tzTrigger = (page: Page) =>
  page.locator('main div.h-9').filter({ hasText: /[+-]\d{2}:\d{2}/ })

test('admin switches sections through the grouped side nav', async ({ browser }) => {
  const { ctx, page } = await asRole(browser, 'admin')
  await page.goto('/settings')

  // Three groups in the side nav, General active by default.
  const nav = page.getByRole('navigation', { name: 'Settings sections' })
  await expect(nav).toContainText('Workspace')
  await expect(nav).toContainText('Workflow')
  await expect(nav).toContainText('System')
  await expect(nav.getByRole('button', { name: 'General' })).toHaveAttribute('aria-current', 'page')

  // The section header names the tab and its content; General has no action.
  await expect(page.getByRole('heading', { name: 'General' })).toBeVisible()
  await expect(page.getByText('Workspace name and timezone.')).toBeVisible()
  await expect(page.getByText('Workspace name', { exact: true })).toBeVisible()

  // Team carries the tab's primary action in the header, not in the content.
  await nav.getByRole('button', { name: 'Team' }).click()
  await expect(page).toHaveURL(/tab=team/)
  await expect(page.getByRole('heading', { name: 'Team' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add member' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add member' })).toBeEnabled()
  await expect(nav.getByRole('button', { name: 'Team' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('table')).toContainText('E2E CTO')

  // A deep link lands straight on a section — here the notification matrix.
  await page.goto('/settings?tab=notifications')
  await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
  await expect(nav.getByRole('button', { name: 'Notifications' })).toHaveAttribute('aria-current', 'page')
  for (const role of ['Reporter', 'Assignee', 'Triage Lead', 'CTO', 'Subscriber']) {
    await expect(page.getByRole('columnheader', { name: role })).toBeVisible()
  }

  await ctx.close()
})

test('below lg the side nav collapses to the horizontal tab row', async ({ browser }) => {
  const { ctx, page } = await asRole(browser, 'admin')
  await page.setViewportSize({ width: 900, height: 800 })
  await page.goto('/settings')

  const nav = page.getByRole('navigation', { name: 'Settings sections' })
  await expect(nav).toBeHidden()
  const tabs = page.getByRole('tablist')
  await expect(tabs.getByRole('tab', { name: 'Notifications' })).toBeVisible()

  await tabs.getByRole('tab', { name: 'Team' }).click()
  await expect(page).toHaveURL(/tab=team/)
  await expect(page.getByRole('heading', { name: 'Team' })).toBeVisible()

  await ctx.close()
})

test('the timezone select opens anchored to its trigger and saves', async ({ browser }) => {
  const { ctx, page } = await asRole(browser, 'admin')
  await page.goto('/settings?tab=general')

  // The fresh E2E database defaults to UTC.
  await expect(tzTrigger(page)).toContainText('UTC')
  await tzTrigger(page).click()

  // Geometry regression for the width="w-full" NaN placement: the panel sits
  // flush under the trigger, left-aligned, exactly as wide as the trigger.
  const panel = portaledPanel(page)
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('Berlin')
  const p = await panel.boundingBox()
  const t = await tzTrigger(page).boundingBox()
  expect(p!.x).toBeCloseTo(t!.x, 1)
  expect(p!.width).toBeCloseTo(t!.width, 1)
  expect(p!.y).toBeGreaterThan(t!.y + t!.height)

  await page.getByRole('button', { name: /Berlin/ }).click()
  await expect(tzTrigger(page)).toContainText('Berlin')

  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Settings saved')).toBeVisible()

  // Persisted server-side, and still Berlin after a reload.
  const saved = await api(page, 'GET', '/settings/general')
  expect(saved.general.timezone).toBe('Europe/Berlin')
  await page.reload()
  await expect(tzTrigger(page)).toContainText('Berlin')

  // General settings are workspace-global — put the default back.
  await api(page, 'PUT', '/settings/general', { workspaceName: 'Releasewatch', timezone: 'UTC' })

  await ctx.close()
})

test('non-admins are redirected away from Settings', async ({ browser }) => {
  const { ctx, page } = await asRole(browser, 'developer')
  await page.goto('/settings')
  await page.waitForURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

  await ctx.close()
})
