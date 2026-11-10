import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// The issue table (Issues list, profile Assigned/Reported tabs, release work
// list): a row opens its item in a new tab from the link (ID, title) and from
// anywhere else on the row; a plain click stays in the tab.

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

const row = (page: Page, title: string) => page.getByTestId('issue-row').filter({ hasText: title })

test('issue table rows open in a new tab from the Issues list and a profile', async ({ browser }) => {
  const title = `Table new tab ${Date.now()}`
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const dev = await ctx.newPage()
  await dev.goto('/inbox')
  const me = await api(dev, 'GET', '/auth/me')
  const projects = await api(dev, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const item = await api(dev, 'POST', '/issues', {
    title, type: 'task', priority: 'medium', project_id: project.id, release_id: project.stream_id, assignee_id: me.id,
  })
  const href = `/issue/task-${item.issue_number}`

  // ── Issues list: Ctrl/Cmd-click the title link ─────────────────────────
  await dev.goto('/issues')
  const link = row(dev, title).getByRole('link', { name: title })
  await expect(link).toHaveAttribute('href', href)
  const [fromLink] = await Promise.all([ctx.waitForEvent('page'), link.click({ modifiers: ['ControlOrMeta'] })])
  await fromLink.waitForLoadState()
  await expect(fromLink).toHaveURL(new RegExp(`${href}$`))
  await fromLink.close()
  await expect(dev).toHaveURL(/\/issues$/)

  // ── Profile: middle-click elsewhere on the row ─────────────────────────
  await dev.goto(`/u/${me.username}?tab=reported`)
  const age = row(dev, title).getByRole('cell').last()
  const [fromRow] = await Promise.all([ctx.waitForEvent('page'), age.click({ button: 'middle' })])
  await fromRow.waitForLoadState()
  await expect(fromRow).toHaveURL(new RegExp(`${href}$`))
  await fromRow.close()
  await expect(dev).toHaveURL(/\/u\//)

  // ── A plain click on the row opens it here ─────────────────────────────
  await age.click()
  await expect(dev).toHaveURL(new RegExp(`${href}$`))
  await ctx.close()
})
