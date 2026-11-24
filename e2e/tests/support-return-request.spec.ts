import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Slice 20 (docs/phase-2/20-support-verify-and-return-requests.md): Support
// verifies a hotfix from To review, presses Problem is back on a Done bug, and a
// triager confirms the request in the Triage page's Return requests tab — the bug
// ends up Rejected in the Stream. Seed: backend/scripts/seed_e2e.py (support
// template on E2E Product).

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

/** A support-sourced bug accepted into the Stream, as the admin. Returns its key and id. */
async function supportBugInStream(adminPage: Page, supportPage: Page, title: string) {
  await supportPage.goto('/support/reports')
  const projects = await api(supportPage, 'GET', '/support/projects')
  const project = projects.find((p: { name: string }) => /E2E Product/.test(p.name))
  const template = (await api(supportPage, 'GET', `/support/projects/${project.id}/templates`))[0]
  const values: Record<string, string> = {}
  for (const f of template.fields) {
    if (f.is_required) values[String(f.id)] = new Date().toISOString().slice(0, 19)
  }
  const report = await api(supportPage, 'POST', '/support/reports', {
    template_id: template.id, title, values,
  })
  await adminPage.goto('/inbox')
  const all = await api(adminPage, 'GET', '/projects')
  const proj = all.find((p: { slug: string }) => p.slug === SLUG)
  await api(adminPage, 'POST', `/issues/${report.id}/triage`, {
    outcome: 'accept', priority: 'high', release_id: proj.stream_id,
  })
  return { id: report.id as number, key: report.key as string, issue_number: report.issue_number as number }
}

test('Support verifies from To review, then Problem is back is confirmed in Triage', async ({ browser }) => {
  const adminCtx = await browser.newContext({ storageState: auth('admin') })
  const supportCtx = await browser.newContext({ storageState: auth('support') })
  const admin = await adminCtx.newPage()
  const support = await supportCtx.newPage()
  const title = `Class audio drops ${Date.now()}`
  const bug = await supportBugInStream(admin, support, title)

  // ── Support verifies a hotfix that is in To review ──────────────────────────
  for (const to of ['in_progress', 'to_review']) {
    await api(admin, 'POST', `/issues/${bug.id}/transition`, { to })
  }
  await support.goto(`/issue/bug-${bug.issue_number}`)
  // In the Stream, Verify opens a menu: Verified, or Done — tested on production.
  await support.getByRole('button', { name: /Verify/ }).click()
  await expect(support.getByText('tested on production')).toBeVisible()
  await support.getByText('Verified', { exact: true }).first().click()
  await expect(support.getByTestId('issue-sidebar').getByText('Verified').first()).toBeVisible()
  // Support has no other status control: the status is a plain badge, not a menu.
  await expect(support.getByRole('button', { name: /Start work|Send to review|Unblock/ })).toHaveCount(0)

  // ── The fix reaches production; Problem is back ─────────────────────────────
  await api(admin, 'POST', `/issues/${bug.id}/transition`, { to: 'done' })
  await support.reload()
  await expect(support.getByRole('button', { name: 'Reject' })).toHaveCount(0)
  await support.getByRole('button', { name: 'Problem is back' }).click()
  const send = support.getByRole('button', { name: 'Send request' })
  await expect(send).toBeDisabled()
  await support.getByPlaceholder('Customer, account or order, when it happened, what they see…')
    .fill('Still drops after ten minutes on the iOS app.')
  await send.click()
  await expect(support.getByText('Return requested').first()).toBeVisible()
  await expect(support.getByTestId('return-request-banner')).toContainText('waiting for triage')
  await expect(support.getByRole('button', { name: 'Add to pending request' })).toBeVisible()

  // The Support reports list shows the request, and its filter chip finds it.
  await support.goto('/support/reports')
  const row = support.locator('tr', { hasText: title })
  await expect(row.getByText('Return requested')).toBeVisible()
  await support.getByRole('button', { name: 'Return requested', exact: true }).click()
  await expect(support.locator('tr', { hasText: title })).toBeVisible()

  // ── A triager confirms it in the Return requests tab ────────────────────────
  await admin.goto('/triage')
  await admin.getByRole('tab', { name: /Return requests/ }).click()
  const queueRow = admin.getByTestId('return-requests-queue').getByRole('button', { name: new RegExp(title) })
  await expect(queueRow).toBeVisible()
  await queueRow.click()
  const detail = admin.getByTestId('return-request-detail')
  await expect(detail).toContainText('Still drops after ten minutes on the iOS app.')
  await detail.getByRole('button', { name: 'Confirm' }).click()
  // Other specs may hold their own pending requests in this project: only this row must go.
  await expect(admin.getByRole('button', { name: new RegExp(title) })).toHaveCount(0)

  // The bug is Rejected, in the Stream, as a production return.
  const item = await api(admin, 'GET', `/issues/${bug.id}`)
  expect(item.status).toBe('rejected')
  expect(item.container_kind).toBe('stream')
  expect(item.reject_reason).toBe('production')
  expect(item.pending_return_request).toBeNull()

  await adminCtx.close()
  await supportCtx.close()
})

test('Dismissing a return request needs a comment and leaves the bug Done', async ({ browser }) => {
  const adminCtx = await browser.newContext({ storageState: auth('admin') })
  const supportCtx = await browser.newContext({ storageState: auth('support') })
  const admin = await adminCtx.newPage()
  const support = await supportCtx.newPage()
  const title = `Replay stutters ${Date.now()}`
  const bug = await supportBugInStream(admin, support, title)
  for (const to of ['in_progress', 'in_review', 'verified', 'done']) {
    await api(admin, 'POST', `/issues/${bug.id}/transition`, { to })
  }
  await api(support, 'POST', `/issues/${bug.id}/return-requests`, { comment: 'It stutters again.' })

  await admin.goto(`/issue/bug-${bug.issue_number}`)
  const banner = admin.getByTestId('return-request-banner')
  await expect(banner).toContainText('1 report')
  await banner.getByRole('button', { name: 'Dismiss' }).click()
  const dialog = admin.locator('.dialog-enter')
  await expect(dialog.getByRole('button', { name: 'Dismiss request' })).toBeDisabled()
  await dialog.getByPlaceholder("What you checked, why this isn't the same problem…")
    .fill('That is the old build — it is fixed in 2.4.1.')
  await dialog.getByRole('button', { name: 'Dismiss request' }).click()
  await expect(banner).toHaveCount(0)

  const item = await api(admin, 'GET', `/issues/${bug.id}`)
  expect(item.status).toBe('done')
  expect(item.pending_return_request).toBeNull()

  await adminCtx.close()
  await supportCtx.close()
})
