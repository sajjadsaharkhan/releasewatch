import { test, expect, type Browser, type Page, type Locator } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen 3 — My Work (docs/phase-2/10-personal-queue.md, redesigned
// 2026-10-01 from prototype variant D). Each test seeds its own items with a
// unique stamp; other specs also assign work to E2E Developer, so every order
// check is relative to this test's items.

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

/** Seeds tasks assigned to the developer; returns `{ me, project, make }`. */
async function seed(dev: Page) {
  const me = await api(dev, 'GET', '/auth/me')
  const projects = await api(dev, 'GET', '/projects')
  const project = projects.find((p: { slug: string }) => p.slug === SLUG)
  const make = (title: string, priority: string, extra: Record<string, unknown> = {}) => api(dev, 'POST', '/issues', {
    title, type: 'task', priority, project_id: project.id, release_id: project.stream_id, assignee_id: me.id, ...extra,
  })
  return { me, project, make }
}

/** Titles from `mine`, in the order their cards appear inside `scope`. */
async function orderOf(scope: Locator, mine: string[]) {
  const texts = await scope.getByTestId('queue-row').allInnerTexts()
  return texts.map((t) => mine.find((m) => t.includes(m))).filter((m): m is string => Boolean(m))
}

async function boardOrder(scope: Locator, mine: string[]) {
  const texts = await scope.getByTestId('work-item').allInnerTexts()
  return texts.map((t) => mine.find((m) => t.includes(m))).filter((m): m is string => Boolean(m))
}

const row = (page: Page, title: string) => page.getByTestId('queue-row').filter({ hasText: title })

async function drag(page: Page, from: Locator, to: Locator) {
  const a = (await from.boundingBox())!
  const b = (await to.boundingBox())!
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2, a.y - 10, { steps: 5 })
  await page.mouse.move(b.x + 30, b.y + 6, { steps: 15 })
}

test('list: default order, drag to reorder, pin, and change priority', async ({ browser }) => {
  const run = Date.now()
  const [first, second, third] = [`Crit ${run}`, `High ${run}`, `Med ${run}`]
  const mine = [first, second, third]
  const { ctx, page: dev } = await asRole(browser, 'developer')
  const { make } = await seed(dev)
  await make(first, 'critical')
  await make(third, 'medium')
  await make(second, 'high')

  // ── Default order: priority first ──────────────────────────────────────
  await dev.goto('/my-work')
  await expect(row(dev, third)).toBeVisible()
  expect(await orderOf(dev.locator('main'), mine)).toEqual([first, second, third])

  // ── Move the third above the first with the keyboard; it survives a reload ─
  // (Space lifts, arrows move one slot, Space drops — dnd-kit's keyboard sensor.)
  const titles = await dev.getByTestId('section-queue').getByTestId('queue-row').allInnerTexts()
  const steps = titles.findIndex((t) => t.includes(third)) - titles.findIndex((t) => t.includes(first))
  const grip = row(dev, third).getByRole('button', { name: `Reorder ${third}` })
  await grip.focus()
  await dev.keyboard.press('Space')
  await dev.waitForTimeout(150) // let the sensor pick the lift up before moving
  for (let i = 0; i < steps; i++) {
    await dev.keyboard.press('ArrowUp')
    await dev.waitForTimeout(120)
  }
  const saved = dev.waitForResponse((r) => r.url().includes('/queue/move') && r.ok())
  await dev.keyboard.press('Space')
  await saved
  await dev.reload()
  await expect(row(dev, third)).toBeVisible()
  expect(await orderOf(dev.locator('main'), mine)).toEqual([third, first, second])

  // ── Pin the second: it moves to Pinned, and the slot count says so ─────
  await row(dev, second).getByRole('button', { name: `Pin ${second}` }).click()
  const pinned = dev.getByTestId('section-pinned')
  await expect(pinned.getByTestId('queue-row').filter({ hasText: second })).toBeVisible()
  await expect(pinned).toContainText(/Pinned · \d of 4/)
  expect(await orderOf(dev.locator('main'), mine)).toEqual([second, third, first])

  // ── Change the third's priority to Low: the default rule re-places it ──
  await row(dev, third).getByRole('button', { name: /^Priority: Medium/ }).click()
  await dev.getByRole('button', { name: 'Low', exact: true }).click()
  await expect(dev.getByText(/is Low now/)).toBeVisible()
  await expect(row(dev, third).getByRole('button', { name: /^Priority: Low/ })).toBeVisible()
  expect(await orderOf(dev.locator('main'), mine)).toEqual([second, first, third])

  // ── Unpin: it goes back by the default rule ────────────────────────────
  await row(dev, second).getByRole('button', { name: `Unpin ${second}` }).click()
  await expect(pinned.getByTestId('queue-row').filter({ hasText: second })).toHaveCount(0)
  expect(await orderOf(dev.locator('main'), mine)).toEqual([first, second, third])
  await ctx.close()
})

test("locked CTO pin, and the queue history page with its filters", async ({ browser }) => {
  const run = Date.now()
  const [alpha, beta] = [`Alpha ${run}`, `Beta ${run}`]
  const { ctx: devCtx, page: dev } = await asRole(browser, 'developer')
  const { me, make } = await seed(dev)
  const alphaItem = await make(alpha, 'high')
  await make(beta, 'medium')

  // ── The CTO opens the developer's work and pins Alpha ──────────────────
  const { ctx: ctoCtx, page: cto } = await asRole(browser, 'cto')
  await cto.goto(`/u/${me.username}/work`)
  await expect(cto.getByRole('heading', { name: `${me.name}’s work` })).toBeVisible()
  await expect(cto.getByText(/will be notified of changes/)).toBeVisible()
  await row(cto, alpha).getByRole('button', { name: `Pin ${alpha}` }).click()
  await expect(cto.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: alpha })).toBeVisible()

  // ── The developer sees it locked; unpin is disabled with the reason ────
  await dev.goto('/my-work')
  const locked = dev.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: alpha })
  await expect(locked).toBeVisible()
  await expect(locked.getByRole('button', { name: `${alpha} — locked pin` })).toBeDisabled()
  await locked.getByTestId('pin-toggle').hover()
  await expect(dev.getByText('only a CTO or Admin can unpin it', { exact: false }).first()).toBeVisible()

  // ── The developer moves Beta, so the history has two actors ────────────
  await row(dev, beta).getByRole('button', { name: `Pin ${beta}` }).click()
  await expect(dev.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: beta })).toBeVisible()

  // ── History page: both changes, then "Not the owner" leaves the CTO's ──
  await dev.getByRole('button', { name: 'Queue history' }).click()
  await expect(dev).toHaveURL(/\/my-work\/history/)
  const history = dev.getByTestId('queue-history')
  const ctoPin = history.getByTestId('history-item').filter({ hasText: 'E2E CTO' }).filter({ hasText: alphaItem.key })
  await expect(ctoPin).toBeVisible()
  await expect(ctoPin).toContainText('changed your queue')
  await expect(history.getByTestId('history-item').filter({ hasText: beta })).toBeVisible()

  await dev.getByRole('button', { name: /Not the owner/ }).click()
  await expect(history.getByTestId('history-item').filter({ hasText: beta })).toHaveCount(0)
  await expect(ctoPin).toBeVisible()

  // Search by key narrows to that item.
  await dev.getByRole('button', { name: /^Anyone/ }).click()
  await dev.getByLabel('Search queue history').fill(alphaItem.key)
  await expect(history.getByTestId('history-item').filter({ hasText: beta })).toHaveCount(0)
  await expect(history.getByTestId('history-item').filter({ hasText: alphaItem.key }).first()).toBeVisible()

  await dev.getByRole('link', { name: 'My Work' }).first().click()
  await expect(dev).toHaveURL(/\/my-work$/)
  await devCtx.close()
  await ctoCtx.close()
})

test('tabs: in progress, blockers, and done with its date range', async ({ browser }) => {
  const run = Date.now()
  const [working, finished, blocker] = [`Working ${run}`, `Finished ${run}`, `Blocking ${run}`]
  const { ctx: devCtx, page: dev } = await asRole(browser, 'developer')
  const { me, project, make } = await seed(dev)
  const w = await make(working, 'medium')
  const f = await make(finished, 'medium')
  await api(dev, 'POST', `/issues/${w.id}/transition`, { to: 'in_progress' })
  await api(dev, 'POST', `/issues/${f.id}/transition`, { to: 'done' })

  // A release blocker: a bug in a release, accepted onto the developer.
  const { ctx: adminCtx, page: admin } = await asRole(browser, 'admin')
  const release = await api(admin, 'POST', '/releases', { project_id: project.id, version: `7.${run % 1000}.0` })
  const bug = await api(admin, 'POST', '/issues', {
    title: blocker, project_id: project.id, release_id: release.id, is_release_blocker: true,
  })
  await api(admin, 'POST', `/issues/${bug.id}/triage`, { outcome: 'accept', priority: 'low', assignee_id: me.id })

  await dev.goto('/my-work')
  await expect(row(dev, working)).toBeVisible()
  await expect(row(dev, blocker).getByText('Blocker')).toBeVisible()

  await dev.getByRole('tab', { name: /^In progress/ }).click()
  await expect(dev).toHaveURL(/tab=in_progress/)
  await expect(row(dev, working)).toBeVisible()
  await expect(row(dev, blocker)).toHaveCount(0)

  await dev.getByRole('tab', { name: /^Blockers/ }).click()
  await expect(row(dev, blocker)).toBeVisible()
  await expect(row(dev, working)).toHaveCount(0)

  await dev.getByRole('tab', { name: /^Done/ }).click()
  const doneList = dev.getByTestId('done-list')
  await expect(doneList.getByRole('button', { name: /Done: Last 7 days/ })).toBeVisible()
  const doneRow = doneList.getByTestId('queue-row').filter({ hasText: finished })
  await expect(doneRow).toBeVisible()
  await expect(doneRow).toContainText('Finished')
  await expect(doneRow.getByRole('button', { name: /^Pin / })).toHaveCount(0)
  await devCtx.close()
  await adminCtx.close()
})

test('board: same order as the list, drag changes status, hover shows key and due date', async ({ browser }) => {
  const run = Date.now()
  const [one, two] = [`Board one ${run}`, `Board two ${run}`]
  const due = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10)
  const { ctx, page: dev } = await asRole(browser, 'developer')
  const { make } = await seed(dev)
  const oneItem = await make(one, 'critical', { due_date: due })
  await make(two, 'high')

  await dev.goto('/my-work')
  await expect(row(dev, two)).toBeVisible()
  const listOrder = await orderOf(dev.locator('main'), [one, two])

  await dev.getByRole('button', { name: 'Board', exact: true }).click()
  await expect(dev).toHaveURL(/view=board/)
  const todo = dev.getByTestId('board-column-todo')
  await expect(todo.getByText(two)).toBeVisible()
  expect(await boardOrder(todo, [one, two])).toEqual(listOrder)

  // Hover a card: its key and due date.
  await todo.getByTestId('work-item').filter({ hasText: one }).hover()
  const details = dev.getByTestId('work-item-details')
  await expect(details).toBeVisible()
  await expect(details).toContainText(oneItem.key)
  await expect(details).toContainText('Due ')
  await dev.mouse.move(5, 5)

  // Drag the second card into In progress.
  const card = todo.getByTestId('work-item').filter({ hasText: two })
  await drag(dev, card, dev.getByTestId('board-column-in_progress'))
  const moved = dev.waitForResponse((r) => r.url().includes('/transition') && r.ok())
  await dev.mouse.up()
  await moved
  await expect(dev.getByTestId('board-column-in_progress').getByText(two)).toBeVisible()
  await ctx.close()
})
