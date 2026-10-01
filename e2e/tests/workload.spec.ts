import { test, expect, type Browser, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen — Team → Workload (docs/phase-2/11-team-overview.md; person cards
// from prototype variant C, 2026-10-01). Other specs also give E2E Developer
// work, and Up next shows only three items, so the seeded item is put In
// progress — the Now list shows all of them.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)
const SLUG = 'e2e-product'

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

test('CTO sees everyone’s work and opens a person’s board', async ({ browser }) => {
  const title = `Workload ${Date.now()}`
  const { ctx: devCtx, page: dev } = await asRole(browser, 'developer')
  const me = await api(dev, 'GET', '/auth/me')
  const project = (await api(dev, 'GET', '/projects')).find((p: { slug: string }) => p.slug === SLUG)
  const item = await api(dev, 'POST', '/issues', {
    title, type: 'task', priority: 'high', project_id: project.id,
    release_id: project.stream_id, assignee_id: me.id,
  })
  await api(dev, 'POST', `/issues/${item.id}/transition`, { to: 'in_progress' })
  await devCtx.close()

  const { ctx, page } = await asRole(browser, 'cto')
  await page.goto('/team')
  await page.getByRole('tab', { name: 'Workload' }).click()
  await expect(page).toHaveURL(/tab=workload/)

  const card = page.getByTestId('workload-row').filter({ hasText: 'E2E Developer' })
  await expect(card.getByTestId('workload-in-progress')).toContainText(title)
  await expect(card.getByTestId('workload-counts')).toContainText(/\d+ open/)

  // Only <main> scrolls — the document never does (the sr-only escape, a49f51a).
  // A short window makes <main> overflow, which is when the escape shows.
  await page.setViewportSize({ width: 1280, height: 420 })
  await page.evaluate(() => { document.querySelector('main')!.scrollTop = 1e6 })
  const overflow = await page.evaluate(() => document.scrollingElement!.scrollHeight - window.innerHeight)
  expect(overflow).toBeLessThanOrEqual(0)
  await page.setViewportSize({ width: 1280, height: 720 })

  // The role filter narrows to developers; the card stays.
  await page.getByRole('button', { name: /Role:/ }).click()
  await page.getByRole('button', { name: 'Developer', exact: true }).click()
  await expect(page).toHaveURL(/role=developer/)
  await expect(card).toBeVisible()
  await expect(page.getByTestId('workload-row').filter({ hasText: 'E2E QA' })).toHaveCount(0)

  // Clicking the card (not a link inside it) opens their board.
  await card.getByText('Open board').click()
  await expect(page).toHaveURL(/\/u\/e2e-developer\/work/)
  await expect(page.getByTestId('queue-row').filter({ hasText: title })).toBeVisible()
  await ctx.close()
})

test('developer sees only the member directory', async ({ browser }) => {
  const { ctx, page } = await asRole(browser, 'developer')
  await page.goto('/team?tab=workload')
  await expect(page.getByRole('heading', { name: 'Team' })).toBeVisible()
  await expect(page.getByText('E2E CTO')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Workload' })).toHaveCount(0)
  await expect(page.getByTestId('workload-row')).toHaveCount(0)
  await ctx.close()
})
