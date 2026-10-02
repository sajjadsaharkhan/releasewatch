import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen 2 (docs/phase-2/06-triage-outcomes.md): the triage lead asks for
// more information, Support answers on the report, the bug returns to New, and
// the lead accepts it onto the board. Seed: backend/scripts/seed_e2e.py
// (E2E QA leads E2E Product; E2E Developer is assignable).

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

test('needs info round-trip, then accept onto the board', async ({ browser }) => {
  const title = `Whiteboard freezes ${Date.now()}`
  const question = 'Which browser is the student using?'

  // ── Support files a report through the API ──────────────────────────────
  const supportCtx = await browser.newContext({ storageState: auth('support') })
  const support = await supportCtx.newPage()
  await support.goto('/inbox')
  const [project] = await api(support, 'GET', '/support/projects')
  const [template] = await api(support, 'GET', `/support/projects/${project.id}/templates`)
  const timeField = template.fields.find((f: { field_type: string }) => f.field_type === 'datetime')
  const report = await api(support, 'POST', '/support/reports', {
    template_id: template.id,
    title,
    values: { [timeField.id]: '2026-09-15T18:30' },
  })
  const slug = `bug-${report.issue_number}`

  // ── 1. The lead sees it in the queue ────────────────────────────────────
  const leadCtx = await browser.newContext({ storageState: auth('qa') })
  const lead = await leadCtx.newPage()
  await lead.goto('/triage')
  const queue = lead.getByTestId('triage-queue')
  const row = queue.getByRole('button', { name: new RegExp(title) })
  await expect(row).toBeVisible()
  await row.click()
  const detail = lead.getByTestId('triage-detail')
  await expect(detail.getByRole('heading', { name: title })).toBeVisible()

  // ── 2. Needs info requires a comment; the item moves to the Needs info tab ─
  await detail.getByRole('button', { name: 'Needs info' }).click()
  const ask = detail.getByRole('button', { name: 'Ask reporter' })
  await expect(ask).toBeDisabled()
  await detail.getByLabel(/What's missing/).fill(question)
  await ask.click()
  await expect(queue.getByRole('button', { name: new RegExp(title) })).toHaveCount(0)
  await lead.getByRole('tab', { name: /^Needs info/ }).click()
  await expect(lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })).toBeVisible()

  // ── 3. Support sees the question on the report and replies ─────────────
  await support.goto(`/issue/${slug}`)
  const pinned = support.getByRole('note', { name: 'Information requested' })
  await expect(pinned).toBeVisible()
  await expect(pinned.getByText(question)).toBeVisible()
  await support.getByPlaceholder('Leave a comment…').fill('Chrome 128 on a school Chromebook.')
  await support.getByRole('button', { name: 'Comment', exact: true }).click()
  await expect(pinned).toBeHidden()

  // ── 4. The item returns to New in the lead's queue ─────────────────────
  await lead.reload()
  await expect(lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })).toBeVisible()
  await lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) }).click()

  // ── 5. The lead accepts it with a priority and an assignee ─────────────
  const detail2 = lead.getByTestId('triage-detail')
  await detail2.getByRole('button', { name: 'Accept', exact: true }).click()
  await detail2.getByRole('button', { name: 'High', exact: true }).click()
  // The assignee picker searches by full name or username.
  await detail2.getByRole('button', { name: 'Unassigned' }).click()
  await lead.getByLabel('Search people').fill('e2e-dev')
  await expect(lead.getByRole('option')).toHaveCount(1)
  await lead.getByRole('option', { name: /E2E Developer/ }).click()
  await expect(detail2.getByRole('button', { name: /E2E Developer/ })).toBeVisible()
  await detail2.getByRole('button', { name: 'Accept', exact: true }).last().click()

  // ── 6. It leaves the queue and appears on the board in To do ───────────
  await expect(lead.getByRole('button', { name: new RegExp(title) })).toHaveCount(0)
  await lead.goto('/issues?view=board')
  await expect(lead.getByTestId('board-column-todo').getByText(title)).toBeVisible()

  await supportCtx.close()
  await leadCtx.close()
})

// Key screen (docs/phase-2/14-similar-item-suggestions.md): a New bug gets a
// stored possible-duplicate hint, the lead merges from the hint into a Done
// Stream bug, and the merge returns it as a production cycle (PRD BR-49/AC-50).
// The fake Jev answers "same" for everything, so the seeded items are the
// candidates; the compute job runs on the worker after its 10 s debounce.
test('possible duplicate hint merges into the Done Stream bug', async ({ browser }) => {
  const title = `Reactions in group chat lost again ${Date.now()}`

  const leadCtx = await browser.newContext({ storageState: auth('qa') })
  const lead = await leadCtx.newPage()
  await lead.goto('/inbox')

  // ── 1. The seeded Done Stream bug, and a new bug filed through the API ────
  const streamBug = (await api(lead, 'GET', '/issues?search='
    + encodeURIComponent('Reaction state on group messages'))).items[0]
  expect(streamBug, 'the seeded Done Stream bug exists').toBeTruthy()
  const dup = await api(lead, 'POST', '/issues', {
    project_id: streamBug.project_id,
    title,
    description: 'After a refresh the reaction state on group messages is gone.',
  })

  // ── 2. The worker computes the hint after its debounce ────────────────────
  const hintsCount = () => lead.evaluate(async (id) => {
    const res = await fetch(`/api/v1/issues/${id}/duplicate-hints`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('rw:token')}` },
    })
    return res.ok ? (await res.json()).hints.length : -1
  }, dup.id)
  await expect.poll(hintsCount, { timeout: 45_000 }).toBeGreaterThan(0)

  // ── 3. The queue row is marked, the detail pane shows the hint ────────────
  await lead.goto('/triage')
  const row = lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })
  await expect(row.getByText(/×\d/)).toBeVisible() // the possible-duplicates marker
  await row.click()
  const detail = lead.getByTestId('triage-detail')
  // The Duplicates tab leads with the best match's similarity.
  await detail.getByRole('tab', { name: /^Duplicates · \d+%/ }).click()
  const hints = detail.getByTestId('duplicate-hints')
  await expect(hints).toBeVisible()
  const hintRow = hints.locator('li').filter({ hasText: streamBug.key })
  await expect(hintRow).toBeVisible()
  await expect(hintRow.getByRole('img', { name: /\d+% similar/ })).toBeVisible()
  await expect(hintRow.getByText('Done → back to To do (production)')).toBeVisible()

  // ── 4. "Merge" preselects the Duplicate outcome ──────────────────────────
  await hintRow.getByRole('button', { name: 'Merge', exact: true }).click()
  await expect(detail.getByRole('button', { name: `Merge into ${streamBug.key}` })).toBeVisible()
  await detail.getByRole('button', { name: `Merge into ${streamBug.key}` }).click()

  // ── 5. The Done Stream bug returns: Rejected, production cycle (AC-50) ────
  await expect(lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })).toHaveCount(0)
  const after = await api(lead, 'GET', `/issues/${streamBug.id}`)
  expect(after.status).toBe('rejected')
  expect(after.reject_reason).toBe('production')
  const cycles = await api(lead, 'GET', `/issues/${streamBug.id}/cycles`)
  expect(cycles.at(-1).start_reason).toBe('production')

  await leadCtx.close()
})

// Reject needs only the triager's comment: no structured reason is asked for
// or stored, and the comment is what the reporter reads.
test('reject takes a comment and no reason', async ({ browser }) => {
  const title = `Rejected without a reason ${Date.now()}`

  const leadCtx = await browser.newContext({ storageState: auth('qa') })
  const lead = await leadCtx.newPage()
  await lead.goto('/inbox')
  const [project] = await api(lead, 'GET', '/projects')
  const bug = await api(lead, 'POST', '/issues', { project_id: project.id, title, description: 'Not a real problem.' })

  await lead.goto('/triage')
  await lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) }).click()
  const detail = lead.getByTestId('triage-detail')
  await detail.getByRole('button', { name: 'Reject', exact: true }).click()

  await expect(detail.getByText('Choose a reason')).toHaveCount(0)
  const submit = detail.getByRole('button', { name: 'Reject', exact: true }).last()
  await expect(submit).toBeDisabled() // the comment is required
  await detail.getByRole('textbox', { name: /Why it is rejected/ }).fill('Works as designed.')
  await submit.click()

  await expect(lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })).toHaveCount(0)
  const after = await api(lead, 'GET', `/issues/${bug.id}`)
  expect(after.status).toBe('cancelled')
  expect(after.cancel_reason).toBeNull()

  await leadCtx.close()
})

// The Duplicate outcome's original-bug box works like the Search page's: an
// item number, `#n` or `BUG-n` jumps to that item; a prefix pins the type; the
// item being triaged is never offered.
test('duplicate picker finds the original by number or key', async ({ browser }) => {
  const stamp = Date.now()
  const leadCtx = await browser.newContext({ storageState: auth('qa') })
  const lead = await leadCtx.newPage()
  await lead.goto('/inbox')
  const [project] = await api(lead, 'GET', '/projects')
  const original = await api(lead, 'POST', '/issues', { project_id: project.id, title: `Original login bug ${stamp}`, description: 'x' })
  const title = `Second login report ${stamp}`
  const dup = await api(lead, 'POST', '/issues', { project_id: project.id, title, description: 'y' })

  await lead.goto('/triage')
  await lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) }).click()
  const detail = lead.getByTestId('triage-detail')
  await detail.getByRole('button', { name: 'Duplicate', exact: true }).click()
  const box = detail.getByRole('textbox', { name: 'Search for the original item' })
  const options = detail.getByRole('listbox', { name: 'Original item' })

  for (const text of [original.key, `#${original.issue_number}`, String(original.issue_number)]) {
    await box.fill(text)
    await expect(options.getByRole('option', { name: new RegExp(`${original.key}.*Original login bug`) })).toBeVisible()
  }
  // The wrong type prefix and the item itself are not offered as a jump.
  await box.fill(`TASK-${original.issue_number}`)
  await expect(detail.getByText(/No bug or task TASK-\d+ in this project/)).toBeVisible()
  await box.fill(dup.key)
  await expect(detail.getByText(new RegExp(`No bug or task ${dup.key} in this project`))).toBeVisible()
  await expect(options.getByRole('option', { name: new RegExp(`${dup.key}\\b`) })).toHaveCount(0)

  await box.fill(original.key)
  await options.getByRole('option', { name: new RegExp(original.key) }).click()
  await detail.getByRole('button', { name: `Merge into ${original.key}` }).click()
  await expect(lead.getByTestId('triage-queue').getByRole('button', { name: new RegExp(title) })).toHaveCount(0)

  await leadCtx.close()
})
