import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// The To review tab in My Work (docs/phase-2/22-review-tab.md, FR-72/73):
// QA lands on it, sees items from every project whoever they are assigned to,
// picks one up on its page (To review → In review), verifies it and watches it
// leave the list. A Developer lands on My queue. Seed: backend/scripts/seed_e2e.py.

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

test('QA lands on To review, picks an item up, verifies it, and it leaves the list', async ({ browser }) => {
  const adminCtx = await browser.newContext({ storageState: auth('admin') })
  const admin = await adminCtx.newPage()
  await admin.goto('/inbox')
  const project = (await api(admin, 'GET', '/projects')).find((p: { slug: string }) => p.slug === SLUG)
  const title = `Review tab ${Date.now()}`
  const task = await api(admin, 'POST', '/issues', {
    title, type: 'task', project_id: project.id, release_id: project.stream_id,
  })
  for (const to of ['in_progress', 'to_review']) {
    await api(admin, 'POST', `/issues/${task.id}/transition`, { to })
  }

  const qaCtx = await browser.newContext({ storageState: auth('qa') })
  const qa = await qaCtx.newPage()
  await qa.goto('/my-work')
  const toReview = qa.getByTestId('work-mode').getByRole('button', { name: /^To review/ })
  await expect(toReview).toHaveAttribute('aria-pressed', 'true')
  await expect(qa.getByTestId('review-queue')).toBeVisible()
  const row = qa.getByTestId('review-row').filter({ hasText: title })
  await expect(row).toBeVisible()
  await expect(qa.getByTestId('review-group-to_review').filter({ hasText: title })).toBeVisible()

  // The queue tab is one click away and keeps today's page.
  await qa.getByTestId('work-mode').getByRole('button', { name: /^My queue/ }).click()
  await expect(qa).toHaveURL(/mode=queue/)
  await expect(qa.getByTestId('review-queue')).toHaveCount(0)
  await qa.getByTestId('work-mode').getByRole('button', { name: /^To review/ }).click()

  // Open it, pick it up (the move to In review is the claim), verify.
  await row.getByRole('link', { name: title }).click()
  await expect(qa).toHaveURL(new RegExp(`/issue/task-${task.issue_number}`))
  await qa.getByRole('button', { name: 'Start review' }).click()
  await expect.poll(async () => (await api(qa, 'GET', `/issues/${task.id}`)).status).toBe('in_review')
  await qa.getByRole('button', { name: 'Mark as verified' }).click()
  await expect.poll(async () => (await api(qa, 'GET', `/issues/${task.id}`)).status).toBe('verified')

  // Back on My Work the item is gone.
  await qa.goto('/my-work')
  await expect(qa.getByTestId('review-queue')).toBeVisible()
  await expect(qa.getByTestId('review-row').filter({ hasText: title })).toHaveCount(0)

  await qaCtx.close()
  await adminCtx.close()
})

test('a Developer lands on My queue and can still open To review', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const dev = await ctx.newPage()
  await dev.goto('/my-work')
  await expect(dev.getByTestId('work-mode').getByRole('button', { name: /^My queue/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(dev.getByTestId('review-queue')).toHaveCount(0)
  await dev.getByTestId('work-mode').getByRole('button', { name: /^To review/ }).click()
  await expect(dev.getByTestId('review-queue')).toBeVisible()
  // The mode is for this visit only: a fresh visit opens on My queue again.
  await dev.goto('/my-work')
  await expect(dev.getByTestId('work-mode').getByRole('button', { name: /^My queue/ })).toHaveAttribute('aria-pressed', 'true')
  await ctx.close()
})
