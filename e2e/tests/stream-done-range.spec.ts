import { test, expect, type Page, type Request } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// The Stream board's Done-column time picker (docs/phase-2/09-releases-and-stream.md,
// FR-47, AC-63; components/ui/DateTimeRangePicker + RangeCalendar + TimeField).
// Every step checks three things: the URL (the range is shareable), the
// `done_from` / `done_to` the board request actually sends, and what the Done
// column shows. Seed: backend/scripts/seed_e2e.py (E2E Product).

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)
const SLUG = 'e2e-product'
const DAY = 86_400_000

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

const isBoard = (r: Request) => /\/api\/v1\/releases\/\d+\/board/.test(r.url())

/** Run `action`, then return the query of the board request it triggered. */
async function boardQuery(page: Page, action: () => Promise<unknown>) {
  const req = page.waitForRequest(isBoard)
  await action()
  const url = new URL((await req).url())
  return { from: url.searchParams.get('done_from'), to: url.searchParams.get('done_to') }
}

/** A local `YYYY-MM-DDTHH:mm` → ISO, computed in the browser's own time zone. */
const localToIso = (page: Page, local: string) =>
  page.evaluate((v) => new Date(v).toISOString(), local)

/** The calendar's accessible name for a day, in the browser's locale. */
const dayLabel = (page: Page, y: number, m: number, d: number) =>
  page.evaluate(({ y, m, d }) => new Date(y, m, d).toLocaleDateString(undefined, {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  }), { y, m, d })

const pad = (n: number) => String(n).padStart(2, '0')
const ymd = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`

function expectAbout(iso: string | null, expectedMs: number) {
  expect(iso).not.toBeNull()
  // The page computes "now − N days" a moment after the test does.
  expect(Math.abs(new Date(iso!).getTime() - expectedMs)).toBeLessThan(2 * 60_000)
}

test('Stream Done column: presets, last N days, custom range, persistence', async ({ page }) => {
  // ── Data: one task Done just now, one still in progress, both in the Stream ─
  await page.goto('/inbox')
  const projects = await api(page, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const stamp = Date.now()
  const doneTitle = `Done range check — shipped ${stamp}`
  const openTitle = `Done range check — still open ${stamp}`
  const done = await api(page, 'POST', '/issues', {
    title: doneTitle, type: 'task', project_id: project.id, release_id: project.stream_id,
  })
  await api(page, 'POST', `/issues/${done.id}/transition`, { to: 'done' })
  const open = await api(page, 'POST', '/issues', {
    title: openTitle, type: 'task', project_id: project.id, release_id: project.stream_id,
  })
  await api(page, 'POST', `/issues/${open.id}/transition`, { to: 'in_progress' })

  const trigger = page.getByRole('button', { name: /^Done:/ })
  const doneColumn = page.getByTestId('board-column-done')
  const progressColumn = page.getByTestId('board-column-in_progress')

  // ── 1. Default: last 7 days — no range in the URL ────────────────────────
  const initial = await boardQuery(page, () => page.goto(`/projects/${SLUG}/stream`))
  await expect(trigger).toContainText('Last 7 days')
  expectAbout(initial.from, Date.now() - 7 * DAY)
  expect(initial.to).toBeNull()
  expect(new URL(page.url()).search).toBe('')
  await expect(doneColumn.getByText(doneTitle)).toBeVisible()
  await expect(progressColumn.getByText(openTitle)).toBeVisible()

  // ── 2. Quick select: Last 30 days ────────────────────────────────────────
  await trigger.click()
  await expect(page.getByText('Quick select')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Last 7 days', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const d30 = await boardQuery(page, () => page.getByRole('button', { name: 'Last 30 days', exact: true }).click())
  expectAbout(d30.from, Date.now() - 30 * DAY)
  expect(d30.to).toBeNull()
  await expect(page).toHaveURL(/[?&]done=30d(&|$)/)
  await expect(trigger).toContainText('Last 30 days')
  await expect(page.getByText('Quick select')).toBeHidden()

  // ── 3. Last N days: invalid N can't be applied; 45 can ───────────────────
  await trigger.click()
  const nDays = page.getByLabel('Number of days')
  const applyN = page.getByRole('dialog', { name: 'Quick select' }).getByRole('button', { name: 'Apply' })
  await nDays.fill('0')
  await expect(applyN).toBeDisabled()
  await nDays.fill('45')
  await expect(applyN).toBeEnabled()
  const d45 = await boardQuery(page, () => applyN.click())
  expectAbout(d45.from, Date.now() - 45 * DAY)
  await expect(page).toHaveURL(/[?&]done=45d(&|$)/)
  await expect(trigger).toContainText('Last 45 days')

  // ── 4. Escape closes the picker without changing anything ────────────────
  await trigger.click()
  await expect(page.getByText('Quick select')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('Quick select')).toBeHidden()
  await expect(page).toHaveURL(/[?&]done=45d(&|$)/)

  // Dates relative to today, so the scenario never goes stale.
  const now = new Date()
  const [y, m, today] = [now.getFullYear(), now.getMonth(), now.getDate()]
  const prev = new Date(y, m - 1, 1)
  const [py, pm] = [prev.getFullYear(), prev.getMonth()]

  // ── 5. Custom range: the 10th of last month 09:30 → today 23:59 ──────────
  await trigger.click()
  await page.getByRole('button', { name: /Custom time range/ }).click()
  const custom = page.getByRole('dialog', { name: 'Custom time range' })
  await expect(custom).toBeVisible()
  // Apply is always reachable, even in a 720px-tall window (six-row months).
  await expect(custom.getByRole('button', { name: 'Apply' })).toBeInViewport()
  // Opened from "Last 45 days": both ends are pre-filled, so the range is set
  // and the next click starts a new one.
  await expect(custom.getByText('Pick a day')).toHaveCount(0)

  await custom.getByRole('button', { name: 'Previous month' }).click()
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 10), exact: true }).click()
  // Only the start is set: the End box asks for a day, the hint says "until now".
  await expect(custom.getByText('Pick a day')).toBeVisible()
  await expect(custom.getByText('No end day — the range runs until now.')).toBeVisible()
  await custom.getByRole('button', { name: 'Next month' }).click()
  await custom.getByRole('button', { name: await dayLabel(page, y, m, today), exact: true }).click()
  await expect(custom.getByText('Pick a day')).toHaveCount(0)

  // Times: typed freely and normalized on blur.
  const startTime = custom.getByLabel('Start time')
  const endTime = custom.getByLabel('End time')
  await startTime.fill('930')
  await startTime.blur()
  await expect(startTime).toHaveValue('09:30')
  await endTime.fill('23:59')
  await endTime.blur()

  const from5 = `${ymd(py, pm, 10)}T09:30`
  const to5 = `${ymd(y, m, today)}T23:59`
  const q5 = await boardQuery(page, () => custom.getByRole('button', { name: 'Apply' }).click())
  expect(q5.from).toBe(await localToIso(page, from5))
  expect(q5.to).toBe(await localToIso(page, to5))
  const url5 = new URL(page.url())
  expect(url5.searchParams.get('done_from')).toBe(from5)
  expect(url5.searchParams.get('done_to')).toBe(to5)
  expect(url5.searchParams.get('done')).toBeNull()
  await expect(trigger).toContainText(`${ymd(py, pm, 10)} 09:30 → ${ymd(y, m, today)} 23:59`)
  // The task completed just now is inside the range.
  await expect(doneColumn.getByText(doneTitle)).toBeVisible()

  // ── 6. The range survives a reload and re-opens as chosen ────────────────
  const reloaded = await boardQuery(page, () => page.reload())
  expect(reloaded).toEqual(q5)
  await expect(trigger).toContainText(`${ymd(py, pm, 10)} 09:30 → ${ymd(y, m, today)} 23:59`)
  await trigger.click()
  await page.getByRole('button', { name: /Custom time range/ }).click()
  await expect(startTime).toHaveValue('09:30')
  await expect(endTime).toHaveValue('23:59')
  await expect(custom.getByRole('button', { name: await dayLabel(page, y, m, today), exact: true }))
    .toHaveAttribute('aria-pressed', 'true')

  // ── 7. A range that ends before today hides the task; open columns don't care ─
  await custom.getByRole('button', { name: 'Previous month' }).click()
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 10), exact: true }).click()
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 20), exact: true }).click()
  await startTime.fill('00:00')
  await endTime.fill('18:00')
  await endTime.blur()
  const from7 = `${ymd(py, pm, 10)}T00:00`
  const to7 = `${ymd(py, pm, 20)}T18:00`
  const q7 = await boardQuery(page, () => custom.getByRole('button', { name: 'Apply' }).click())
  expect(q7.from).toBe(await localToIso(page, from7))
  expect(q7.to).toBe(await localToIso(page, to7))
  await expect(doneColumn.getByText(doneTitle)).toHaveCount(0)
  await expect(doneColumn).toContainText('Nothing done')
  await expect(progressColumn.getByText(openTitle)).toBeVisible()

  // ── 8. Start after end on the same day is refused ────────────────────────
  await trigger.click()
  await page.getByRole('button', { name: /Custom time range/ }).click()
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 20), exact: true }).click() // new range
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 20), exact: true }).click() // same end day
  await startTime.fill('10:00')
  await startTime.blur()
  await endTime.fill('09:00')
  await endTime.blur()
  await expect(custom.getByRole('alert')).toHaveText('The start must be before the end.')
  await expect(custom.getByRole('button', { name: 'Apply' })).toBeDisabled()

  // ── 9. Arrow keys step the time 15 minutes, wrapping past midnight ───────
  await endTime.fill('23:50')
  await endTime.press('ArrowUp')
  await expect(endTime).toHaveValue('00:05')
  await endTime.press('ArrowDown')
  await expect(endTime).toHaveValue('23:50')
  await expect(custom.getByRole('alert')).toHaveCount(0)

  // ── 10. A start with no end: done_from only, "until now" ─────────────────
  await custom.getByRole('button', { name: await dayLabel(page, py, pm, 10), exact: true }).click() // restart
  await startTime.fill('08:15')
  await startTime.blur()
  const from10 = `${ymd(py, pm, 10)}T08:15`
  const q10 = await boardQuery(page, () => custom.getByRole('button', { name: 'Apply' }).click())
  expect(q10.from).toBe(await localToIso(page, from10))
  expect(q10.to).toBeNull()
  expect(new URL(page.url()).searchParams.get('done_to')).toBeNull()
  await expect(trigger).toContainText(`${ymd(py, pm, 10)} 08:15 → now`)
  await expect(doneColumn.getByText(doneTitle)).toBeVisible()

  // ── 11. Cancel keeps the applied range; Reset-to-preset goes back to 7 days ─
  await trigger.click()
  await page.getByRole('button', { name: /Custom time range/ }).click()
  await custom.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.getByText('Quick select')).toBeVisible()
  await expect(page).toHaveURL(/done_from=/)
  const back = await boardQuery(page, () => page.getByRole('button', { name: 'Last 7 days', exact: true }).click())
  expectAbout(back.from, Date.now() - 7 * DAY)
  expect(back.to).toBeNull()
  expect(new URL(page.url()).search).toBe('')
  await expect(trigger).toContainText('Last 7 days')
})
