import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Verified and "Done = on production" (docs/phase-2/19-verified-and-production.md):
// QA verifies, a deployer selects Verified Stream items and presses On production,
// a release only reaches Done at ship, and the Phase 1 reports carry the PD-1
// notice. Seed: backend/scripts/seed_e2e.py.

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

/** A task in `releaseId` (the Stream by default) walked to In review. */
async function inReview(page: Page, title: string, releaseId?: number) {
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const task = await api(page, 'POST', '/issues', {
    title, type: 'task', project_id: project.id, release_id: releaseId ?? project.stream_id,
  })
  for (const to of ['in_progress', 'to_review', 'in_review']) {
    await api(page, 'POST', `/issues/${task.id}/transition`, { to })
  }
  return { task, project }
}

test('verify one, select Verified Stream items, On production makes them Done', async ({ page }) => {
  await page.goto('/inbox')
  const stamp = Date.now()
  const titles = [`Prod A ${stamp}`, `Prod B ${stamp}`, `Prod C ${stamp}`]
  const items: Array<{ id: number; key: string; issue_number: number }> = []
  for (const t of titles) items.push((await inReview(page, t)).task)

  // ── QA verifies the first from its page: Verified, not Done ──────────────
  await page.goto(`/issue/task-${items[0].issue_number}`)
  await page.getByRole('button', { name: 'Mark as verified' }).click()
  await expect(page.getByTestId('issue-sidebar').getByText('Verified', { exact: true }).first()).toBeVisible()
  expect((await api(page, 'GET', `/issues/${items[0].id}`)).status).toBe('verified')
  for (const it of items.slice(1)) await api(page, 'POST', `/issues/${it.id}/transition`, { to: 'verified' })

  // ── Stream board: a Verified column, cards selectable ────────────────────
  await page.goto(`/projects/${SLUG}/stream`)
  const verified = page.getByTestId('board-column-verified')
  await expect(verified).toBeVisible()
  const card = (i: number) => verified.getByTestId('work-item').filter({ hasText: titles[i] })
  for (let i = 0; i < 3; i++) await expect(card(i)).toBeVisible()
  const box = (i: number) => card(i).getByRole('checkbox', { name: `Select ${items[i].key}` })
  await expect(page.getByTestId('production-bar')).toHaveCount(0)

  // Shift-click selects the range between two clicks.
  const all = verified.getByRole('checkbox')
  const keys = await all.evaluateAll((els) => els.map((el) => el.getAttribute('aria-label')))
  const ia = keys.indexOf(`Select ${items[0].key}`)
  const ic = keys.indexOf(`Select ${items[2].key}`)
  await card(0).hover()
  await box(0).click()
  await card(2).hover()
  await box(2).click({ modifiers: ['Shift'] })
  await expect(verified.locator('[role=checkbox][aria-checked=true]')).toHaveCount(Math.abs(ia - ic) + 1)

  // Back to exactly the first two.
  await page.getByRole('button', { name: 'Clear selection' }).click()
  await expect(page.getByTestId('production-bar')).toHaveCount(0)
  await card(0).hover(); await box(0).click()
  await card(1).hover(); await box(1).click()
  const bar = page.getByTestId('production-bar')
  await expect(bar).toContainText('2 selected')

  // ── The confirm dialog lists the keys; confirm → both are Done ───────────
  await bar.getByRole('button', { name: 'On production' }).click()
  const dialog = page.locator('.dialog-enter')
  await expect(dialog).toContainText(items[0].key)
  await expect(dialog).toContainText(items[1].key)
  await expect(dialog).not.toContainText(items[2].key)
  await dialog.getByRole('button', { name: 'On production' }).click()

  const done = page.getByTestId('board-column-done')
  await expect(done.getByTestId('work-item').filter({ hasText: titles[0] })).toBeVisible()
  await expect(done.getByTestId('work-item').filter({ hasText: titles[1] })).toBeVisible()
  await expect(card(0)).toHaveCount(0)
  await expect(card(2)).toBeVisible()
  await expect(page.getByTestId('production-bar')).toHaveCount(0)
  expect((await api(page, 'GET', `/issues/${items[0].id}`)).status).toBe('done')
  expect((await api(page, 'GET', `/issues/${items[2].id}`)).status).toBe('verified')
})

test('a refused On production names the item and changes nothing', async ({ page }) => {
  await page.goto('/inbox')
  const title = `Prod refused ${Date.now()}`
  const { task } = await inReview(page, title)
  await api(page, 'POST', `/issues/${task.id}/transition`, { to: 'verified' })
  await page.goto(`/projects/${SLUG}/stream`)
  const verified = page.getByTestId('board-column-verified')
  const card = verified.getByTestId('work-item').filter({ hasText: title })
  await card.hover()
  await card.getByRole('checkbox').click()
  // Another session moves it out of Verified before the confirm.
  await api(page, 'POST', `/issues/${task.id}/transition`, { to: 'in_progress' })
  await page.getByTestId('production-bar').getByRole('button', { name: 'On production' }).click()
  await page.locator('.dialog-enter').getByRole('button', { name: 'On production' }).click()
  await expect(page.getByRole('alert')).toContainText(task.key)
  await expect(page.getByRole('alert')).toContainText('Nothing was changed')
  expect((await api(page, 'GET', `/issues/${task.id}`)).status).toBe('in_progress')
})

test('Stream: a Verified item waiting 3+ days carries the age marker; a fresh one does not', async ({ page }) => {
  await page.goto('/inbox')
  const stamp = Date.now()
  const [oldTitle, freshTitle] = [`Aged ${stamp}`, `Fresh ${stamp}`]
  const old = (await inReview(page, oldTitle)).task
  const fresh = (await inReview(page, freshTitle)).task
  for (const t of [old, fresh]) await api(page, 'POST', `/issues/${t.id}/transition`, { to: 'verified' })

  // The board payload says the first was verified 4 days ago.
  await page.route(/\/api\/v1\/releases\/[^/]+\/board/, async (route) => {
    const res = await route.fetch()
    const json = await res.json()
    const ago = new Date(Date.now() - 4 * 86_400_000).toISOString()
    for (const col of json.columns) {
      for (const it of col.items) if (it.id === old.id) it.verified_at = ago
    }
    await route.fulfill({ response: res, json })
  })
  await page.goto(`/projects/${SLUG}/stream`)
  const aged = page.getByTestId('work-item').filter({ hasText: oldTitle })
  await expect(aged.getByTestId('verified-age-marker')).toBeAttached()
  await expect(aged.getByTestId('verified-age-marker')).toContainText('Verified 4 days ago — not on production yet')
  await expect(page.getByTestId('work-item').filter({ hasText: freshTitle }).getByTestId('verified-age-marker')).toHaveCount(0)
})

test('release: Done is empty until ship, the status control says why, ship makes Verified Done', async ({ page }) => {
  await page.goto('/inbox')
  const stamp = Date.now()
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const release = await api(page, 'POST', '/releases', { project_id: project.id, version: `19.${stamp % 1000}.0` })
  const [verifiedTitle, leftTitle] = [`Ships ${stamp}`, `Stays ${stamp}`]
  const { task } = await inReview(page, verifiedTitle, release.id)
  const left = await api(page, 'POST', '/issues', {
    title: leftTitle, type: 'task', project_id: project.id, release_id: release.id,
  })

  // ── The status control: Verified yes, Done disabled with the reason ──────
  await page.goto(`/issue/task-${task.issue_number}`)
  await page.getByTestId('issue-sidebar').getByRole('button', { name: 'In Review' }).click()
  const doneOption = page.getByTestId('done-at-ship-option')
  await expect(doneOption.getByRole('button')).toBeDisabled()
  await doneOption.hover()
  await expect(page.getByText(/^Done when the release ships\.?$/)).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Mark as verified' }).click()
  await expect(page.getByTestId('issue-sidebar').getByRole('button', { name: 'Verified' })).toBeVisible()

  // ── Release board: Verified column holds it, Done waits for ship ─────────
  await api(page, 'POST', `/releases/${release.id}/status`, { to: 'development' })
  await api(page, 'POST', `/releases/${release.id}/status`, { to: 'qa' })
  await page.goto(`/releases/${release.id}`)
  await expect(page.getByTestId('board-column-verified').getByTestId('work-item').filter({ hasText: verifiedTitle })).toBeVisible()
  await expect(page.getByTestId('board-column-done')).toContainText('Done after ship')
  // The server refuses a move to Done in a release.
  const refused = await page.evaluate(async ({ id, token }) => {
    const res = await fetch(`/api/v1/issues/${id}/transition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ to: 'done' }),
    })
    return { status: res.status, body: await res.json() }
  }, { id: task.id, token: await page.evaluate(() => localStorage.getItem('rw:token')) })
  expect(refused.status).toBe(409)
  expect(JSON.stringify(refused.body)).toContain('done_at_ship')

  // ── Ship: two lines, then the Verified item is Done ──────────────────────
  await page.getByRole('button', { name: 'Ship', exact: true }).click()
  const dialog = page.locator('.dialog-enter')
  await expect(dialog.getByTestId('ship-to-production')).toContainText('1 item goes to production')
  await expect(dialog.getByTestId('ship-to-backlog')).toContainText('1 item goes to the backlog (1 To do)')
  await dialog.getByRole('button', { name: /^Ship and move 1 item/ }).click()
  await expect(page.getByText(/1 item on production/)).toBeVisible()
  expect((await api(page, 'GET', `/issues/${task.id}`)).status).toBe('done')
  expect((await api(page, 'GET', `/issues/${left.id}`)).release_id).toBeNull()
  await expect(page.getByTestId('board-column-done').getByTestId('work-item').filter({ hasText: verifiedTitle })).toBeVisible()
})

test('Reject a Verified item: caught before production', async ({ page }) => {
  await page.goto('/inbox')
  const { task } = await inReview(page, `Caught ${Date.now()}`)
  await api(page, 'POST', `/issues/${task.id}/transition`, { to: 'verified' })
  await page.goto(`/issue/task-${task.issue_number}`)
  await page.getByRole('button', { name: 'Reject', exact: true }).click()
  await page.getByPlaceholder('What release QA found, what you expected…').fill('Fails on the staging data.')
  await page.getByRole('button', { name: 'Reject', exact: true }).last().click()
  await expect(page.getByText(`${task.key} is rejected`)).toBeVisible()
  await expect(page.getByText('Caught before production').first()).toBeVisible()
  expect((await api(page, 'GET', `/issues/${task.id}`)).reject_reason).toBe('release_qa')
})

for (const [route, heading] of [
  ['/dashboard', 'Dashboard'],
  ['/regressions', 'Regression Analytics Dashboard'],
  ['/contributions', 'Contributions'],
] as const) {
  test(`${route}: the Phase 1 report notice (PD-1) is shown and cannot be dismissed`, async ({ page }) => {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    const notice = page.getByTestId('pd1-notice')
    await expect(notice).toContainText('These numbers are not reliable since Phase 2 and will be rebuilt (PD-1).')
    await expect(notice.getByRole('button')).toHaveCount(0)
  })
}

test('release board: Done is locked while dragging and refuses the drop', async ({ page }) => {
  await page.goto('/inbox')
  const stamp = Date.now()
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const release = await api(page, 'POST', '/releases', { project_id: project.id, version: `20.${stamp % 1000}.0` })
  const title = `Locked drop ${stamp}`
  const item = await api(page, 'POST', '/issues', {
    title, type: 'task', project_id: project.id, release_id: release.id,
  })
  await page.goto(`/releases/${release.id}`)
  const done = page.getByTestId('board-column-done')
  await expect(done).toContainText('Done after ship')
  await expect(page.getByTestId('column-locked-note')).toHaveCount(0)

  const card = page.getByTestId('board-column-todo').getByTestId('work-item').filter({ hasText: title })
  const from = (await card.boundingBox())!
  const to = (await done.boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2, from.y - 10, { steps: 5 })
  await page.mouse.move(to.x + 30, to.y + 60, { steps: 15 })
  // While dragging, Done says why it takes no drop.
  await expect(done.getByTestId('column-locked-note')).toContainText('Done when the release ships')

  let sent = false
  page.on('request', (r) => { if (r.url().includes('/transition')) sent = true })
  await page.mouse.up()
  await expect(page.getByTestId('column-locked-note')).toHaveCount(0)
  await page.waitForTimeout(500)
  expect(sent).toBe(false)
  expect((await api(page, 'GET', `/issues/${item.id}`)).status).toBe('todo')
})
