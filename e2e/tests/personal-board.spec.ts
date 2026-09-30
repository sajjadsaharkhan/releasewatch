import { test, expect, type Page, type Locator } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Key screen 3 (docs/phase-2/10-personal-queue.md): the developer's queue is
// in default order, a drag reorders it for good, a pin lifts an item, a CTO's
// pin is locked, the History drawer lists it, the Kanban agrees with the list,
// and hovering a card spells out its key and due date. Other specs also assign
// work to E2E Developer, so every order check is relative to this spec's items.

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

/** Titles of `mine` in the order they appear in `scope`. */
async function orderOf(scope: Locator, mine: string[]) {
  const texts = await scope.getByTestId('work-item').allInnerTexts()
  return texts
    .map((t) => mine.find((m) => t.includes(m)))
    .filter((m): m is string => Boolean(m))
}

const row = (page: Page, title: string) => page.getByTestId('queue-row').filter({ hasText: title })

test('personal queue: order, drag, pins, locked CTO pin, history, kanban, hover', async ({ browser }) => {
  const run = Date.now()
  const first = `Queue first ${run}`
  const second = `Queue second ${run}`
  const third = `Queue third ${run}`
  const mine = [first, second, third]
  const due = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10)

  // ── Seed three tasks assigned to the developer, one per priority ───────
  const devCtx = await browser.newContext({ storageState: auth('developer') })
  const dev = await devCtx.newPage()
  await dev.goto('/inbox')
  const me = await api(dev, 'GET', '/auth/me')
  const [project] = await api(dev, 'GET', '/projects')
  const { stream_id: streamId } = await api(dev, 'GET', `/projects/id/${project.id}`)
  const make = (title: string, priority: string, extra = {}) => api(dev, 'POST', '/issues', {
    title, type: 'task', priority, project_id: project.id, release_id: streamId, assignee_id: me.id, ...extra,
  })
  const firstItem = await make(first, 'critical', { due_date: due })
  await make(third, 'medium')
  await make(second, 'high')

  // ── 1. Default order ────────────────────────────────────────────────────
  await dev.goto('/my-work')
  const queue = dev.getByTestId('section-queue')
  await expect(row(dev, third)).toBeVisible()
  expect(await orderOf(queue, mine)).toEqual([first, second, third])

  // ── 2. Drag the third above the first; it survives a reload ────────────
  const grip = row(dev, third).getByRole('button', { name: `Reorder ${third}` })
  const target = row(dev, first)
  const from = await grip.boundingBox()
  const to = await target.boundingBox()
  await dev.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2)
  await dev.mouse.down()
  await dev.mouse.move(from!.x + from!.width / 2, from!.y - 10, { steps: 5 })
  await dev.mouse.move(to!.x + 20, to!.y + 4, { steps: 15 })
  const saved = dev.waitForResponse((r) => r.url().includes('/queue/move') && r.ok())
  await dev.mouse.up()
  await saved
  await expect.poll(() => orderOf(queue, mine)).toEqual([third, first, second])
  await dev.reload()
  await expect(row(dev, third)).toBeVisible()
  expect(await orderOf(dev.getByTestId('section-queue'), mine)).toEqual([third, first, second])

  // ── 3. The developer pins the second item ──────────────────────────────
  await row(dev, second).getByRole('button', { name: `Pin ${second}` }).click()
  await expect(dev.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: second })).toBeVisible()

  // ── 4. The CTO opens the developer's board and pins the first item ─────
  const ctoCtx = await browser.newContext({ storageState: auth('cto') })
  const cto = await ctoCtx.newPage()
  await cto.goto(`/u/${me.username}/work`)
  await expect(cto.getByRole('heading', { name: `${me.name}’s work` })).toBeVisible()
  await row(cto, first).getByRole('button', { name: `Pin ${first}` }).click()
  await expect(cto.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: first })).toBeVisible()

  // ── 5. The developer sees it locked; unpin is disabled with a reason ───
  await dev.reload()
  const locked = dev.getByTestId('section-pinned').getByTestId('queue-row').filter({ hasText: first })
  await expect(locked).toBeVisible()
  const unpin = locked.getByTestId('unpin')
  await expect(unpin).toBeDisabled()
  await locked.getByTestId('pin-toggle-wrapper').hover()
  await expect(dev.getByText('only a CTO or Admin can unpin it')).toBeVisible()

  // ── 6. The History drawer lists the CTO's pin ──────────────────────────
  await dev.getByRole('button', { name: 'History' }).click()
  const history = dev.getByTestId('queue-history')
  await expect(history.getByTestId('history-item').filter({ hasText: 'E2E CTO' }).filter({ hasText: 'pinned' })).toBeVisible()
  await dev.keyboard.press('Escape')

  // Full list order of this spec's items: pins (second, first), then third.
  const listOrder = await orderOf(dev.locator('main'), mine)
  expect(listOrder).toEqual([second, first, third])

  // ── 7. The Kanban shows the same relative order in To do ───────────────
  await dev.getByRole('button', { name: 'Kanban' }).click()
  const todo = dev.getByTestId('board-column-todo')
  await expect(todo.getByText(third)).toBeVisible()
  expect(await orderOf(todo, mine)).toEqual(listOrder)

  // ── 8. Hovering a card shows its key and due date ──────────────────────
  await todo.getByTestId('work-item').filter({ hasText: first }).hover()
  const details = dev.getByTestId('work-item-details')
  await expect(details).toBeVisible()
  await expect(details).toContainText(firstItem.key)
  await expect(details).toContainText('Due ')

  await devCtx.close()
  await ctoCtx.close()
})
