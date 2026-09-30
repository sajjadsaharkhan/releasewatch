import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// One Reject action (docs/phase-2/09a-review-queue-and-rejected.md): reject an
// In review item from its page, find it in the Rejected area of the Stream's
// To do column, pick it up, and see the cycle badge. Seed: backend/scripts/seed_e2e.py.

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

test('Reject an In review item, find it Rejected in To do, pick it up', async ({ page }) => {
  await page.goto('/inbox')
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const title = `Reject check ${Date.now()}`
  const task = await api(page, 'POST', '/issues', {
    title, type: 'task', project_id: project.id, release_id: project.stream_id,
  })
  for (const to of ['in_progress', 'to_review', 'in_review']) {
    await api(page, 'POST', `/issues/${task.id}/transition`, { to })
  }

  // ── Reject from the item page ────────────────────────────────────────────
  await page.goto(`/issue/task-${task.issue_number}`)
  await page.getByRole('button', { name: 'Reject', exact: true }).click()
  const confirm = page.getByRole('button', { name: 'Reject', exact: true }).last()
  await expect(confirm).toBeDisabled()
  await page.getByPlaceholder('What you tested, what happened, what you expected…')
    .fill('The empty state still shows the spinner.')
  await confirm.click()
  await expect(page.getByText(`${task.key} is rejected`)).toBeVisible()
  // The Reject reads as a status change like any other: In Review → Rejected.
  const move = page.locator('li[id^="event-"]').filter({ hasText: 'changed status' }).last()
  await expect(move).toContainText('In Review')
  await expect(move).toContainText('Rejected')
  await expect(page.getByText('The empty state still shows the spinner.').first()).toBeVisible()

  // ── On the Stream board: in the To do column's Rejected area, above To do ─
  await page.goto(`/projects/${SLUG}/stream`)
  const todo = page.getByTestId('board-column-todo')
  const rejectedArea = todo.getByTestId('todo-area-rejected')
  const card = rejectedArea.getByRole('button', { name: new RegExp(title) })
  await expect(card).toBeVisible()
  await expect(todo).toContainText(/\d+ rejected/)
  // The Rejected area comes before the plain To do area.
  const areas = await todo.locator('[data-testid^="todo-area-"]').evaluateAll(
    (els) => els.map((el) => el.getAttribute('data-testid')),
  )
  expect(areas.indexOf('todo-area-rejected')).toBeLessThan(
    areas.includes('todo-area-todo') ? areas.indexOf('todo-area-todo') : Infinity,
  )

  // The area collapses and expands.
  const toggle = rejectedArea.getByRole('button', { name: /^Rejected/ })
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(card).toBeHidden()
  await toggle.click()
  await expect(card).toBeVisible()

  // ── Pick it up: In progress, the cycle badge stays ──────
  await page.goto(`/issue/task-${task.issue_number}`)
  await page.getByRole('button', { name: 'Start work' }).click()
  await expect.poll(async () => (await api(page, 'GET', `/issues/${task.id}`)).status)
    .toBe('in_progress')
  await page.goto(`/projects/${SLUG}/stream`)
  const inProgress = page.getByTestId('board-column-in_progress')
  const picked = inProgress.getByRole('button', { name: new RegExp(title) })
  await expect(picked).toBeVisible()
  await expect(picked.getByText('Cycle 2')).toBeAttached()
})
