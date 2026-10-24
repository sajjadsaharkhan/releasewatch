import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// The item sidebar's Assignee row is the searchable UserPicker (inline trigger,
// same menu as New issue); picking someone still asks before reassigning.
// Seed: backend/scripts/seed_e2e.py (E2E Product, E2E Developer is assignable).

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
    return res.json()
  }, { method, url, body })
}

test('the assignee is picked by searching people, after a confirm', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('cto') })
  const page = await ctx.newPage()
  await page.goto('/inbox')
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === 'e2e-product')
  const title = `Sidebar assignee ${Date.now()}`
  const task = await api(page, 'POST', '/issues', { type: 'task', title, project_id: project.id, release_id: project.stream_id })

  await page.goto(`/issue/task-${task.issue_number}`)
  const trigger = page.getByRole('button', { name: /Unassigned/ })
  await trigger.click()
  const search = page.getByLabel('Search people')
  await expect(search).toBeFocused()

  // Search narrows the list; Escape closes it without touching anything.
  await search.fill('developer')
  await expect(page.getByRole('option')).toHaveCount(1)
  await expect(page.getByRole('option')).toContainText('E2E Developer')
  await search.press('Escape')
  await expect(search).toBeHidden()

  // Enter picks — and the sidebar asks first. Cancel leaves it unassigned.
  await trigger.click()
  await search.fill('developer')
  await search.press('Enter')
  await expect(page.getByRole('heading', { name: 'Reassign task?' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.getByRole('button', { name: /Unassigned/ })).toBeVisible()

  // Confirm assigns.
  await trigger.click()
  await search.fill('developer')
  await search.press('Enter')
  await page.getByRole('button', { name: 'Reassign' }).click()
  await expect(page.getByRole('button', { name: /E2E Developer/ })).toBeVisible()
  await expect.poll(async () => (await api(page, 'GET', `/issues/${task.id}`)).assignee_user?.username).toBe('e2e-developer')

  await ctx.close()
})
