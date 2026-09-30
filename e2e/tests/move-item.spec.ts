import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Move… on the item page (the ⋯ menu): Stream → backlog with a chosen
// category → a release, and the sidebar's placement rows follow — a Release
// picker in a release, read-only placement elsewhere, Category only in the
// backlog. Seed: backend/scripts/seed_e2e.py.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)
const SLUG = 'e2e-product'

test.use({ storageState: auth('admin') })

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

test('Move an item from the Stream to the backlog, then to a release', async ({ page }) => {
  await page.goto('/inbox')
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const stamp = Date.now()
  const version = `9.${stamp % 1000}.0`
  const categoryName = `Later ${stamp % 10000}`
  await api(page, 'POST', '/releases', { project_id: project.id, version })
  await api(page, 'POST', `/projects/${project.id}/backlog-categories`, {
    name: categoryName, icon: 'rocket', color: 'violet',
  })
  const task = await api(page, 'POST', '/issues', {
    title: `Move check ${stamp}`, type: 'task', project_id: project.id, release_id: project.stream_id,
  })

  await page.goto(`/issue/task-${task.issue_number}`)
  const sidebar = page.getByTestId('issue-sidebar')
  await expect(sidebar).toContainText('Stream')
  await expect(sidebar.getByText('Category', { exact: true })).toHaveCount(0)

  const openMove = async () => {
    await page.getByRole('button', { name: 'More actions' }).click()
    await page.getByText('Move…').click()
  }

  // ── Stream → backlog, with a category ────────────────────────────────────
  await openMove()
  const destinations = page.getByRole('radiogroup', { name: 'Destination' })
  await expect(destinations.getByRole('radio', { name: /Stream/ })).toHaveCount(0) // it's there already
  await expect(destinations.getByRole('group', { name: 'Releases' })).toContainText(version)
  await destinations.getByRole('radio', { name: /Backlog/ }).click()
  await page.getByText('Default', { exact: true }).last().click() // the category Select
  await page.getByText(categoryName).last().click()
  await page.getByRole('button', { name: 'Move', exact: true }).click()
  await expect.poll(async () => (await api(page, 'GET', `/issues/${task.id}`)).release_id).toBeNull()
  expect((await api(page, 'GET', `/issues/${task.id}`)).backlog_category.name).toBe(categoryName)
  await expect(sidebar.getByText('Category', { exact: true })).toBeVisible()
  await expect(sidebar).toContainText('Backlog')

  // ── backlog → the release ────────────────────────────────────────────────
  await openMove()
  await page.getByRole('radio', { name: new RegExp(version.replace(/\./g, '\\.')) }).click()
  await page.getByRole('button', { name: 'Move', exact: true }).click()
  await expect.poll(async () => (await api(page, 'GET', `/issues/${task.id}`)).release_version).toBe(version)
  // In a release the sidebar offers a Release picker, and no Category.
  await expect(sidebar.getByText('Release', { exact: true })).toBeVisible()
  await expect(sidebar.getByText('Category', { exact: true })).toHaveCount(0)
})
