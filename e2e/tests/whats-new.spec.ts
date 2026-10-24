import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PASSWORD } from '../roles.js'

// TASK-575: the newest What's new note opens once per person, per team, and
// its tours walk the real UI. The role users (global-setup) join at seed time,
// after every shipped note, so it never opens for them; `e2e-veteran` (tech)
// and `e2e-veteran-support` joined long before (backend/scripts/seed_e2e.py).
// Expectations come from the API, so a new note doesn't break the spec. Each
// veteran sees the note once per seed — `make e2e` reseeds every run.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function signIn(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL(/\/(dashboard|inbox)$/)
}

type Note = { id: string; title: string; highlights: { kind: string; title: string; tour: unknown[] }[] }

/** A highlight's title as the screen shows it: its inline markdown rendered away. */
const shown = (title: string) => title.replace(/[`*_]/g, '')

/** Whether the person's notes hold a highlight with this title and a tour. */
async function hasJourney(page: Page, title: string) {
  const { notes } = await whatsNew(page)
  return notes.some((n) => n.highlights.some((h) => h.title === title && h.tour.length > 0))
}

async function whatsNew(page: Page): Promise<{ notes: Note[]; show: string | null }> {
  return page.evaluate(async () => {
    const res = await fetch('/api/v1/whats-new', { headers: { Authorization: `Bearer ${localStorage.getItem('rw:token')}` } })
    return res.json()
  })
}

test('the newest note opens once for a tech user, with their highlights', async ({ page }) => {
  await signIn(page, 'e2e-veteran')
  const { notes, show } = await whatsNew(page)
  const note = notes.find((n) => n.id === show)!
  expect(note, 'a shipped note with news for tech').toBeTruthy()

  const modal = page.getByRole('dialog', { name: note.title })
  await expect(modal).toBeVisible()
  for (const h of note.highlights) await expect(modal.getByText(shown(h.title), { exact: true }).last()).toBeVisible()

  await modal.getByRole('button', { name: 'Got it' }).click()
  await expect(modal).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  await expect(page.getByRole('dialog', { name: note.title })).toHaveCount(0)
  expect((await whatsNew(page)).show).toBeNull()

  // The sidebar's What's new reopens it as the changelog.
  await page.getByRole('complementary', { name: 'Sidebar' }).getByRole('button', { name: /What’s new/ }).click()
  const sheet = page.getByRole('dialog', { name: 'What’s new' })
  await expect(sheet.getByRole('heading', { name: note.title })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
})

test('Support sees only the Support highlights', async ({ page }) => {
  await signIn(page, 'e2e-veteran-support')
  const { notes, show } = await whatsNew(page)
  const note = notes.find((n) => n.id === show)
  test.skip(!note, 'the newest note has nothing new for Support')

  const modal = page.getByRole('dialog', { name: note!.title })
  await expect(modal).toBeVisible()
  // The API sends Support only its highlights (backend tests prove the split);
  // the modal shows exactly those, and the Support headline.
  for (const h of note!.highlights) await expect(modal.getByText(shown(h.title), { exact: true }).last()).toBeVisible()
  await expect(modal.getByRole('button', { name: 'Show me' })).toHaveCount(
    note!.highlights.filter((h) => h.tour.length > 0).length,
  )
  await modal.getByRole('button', { name: 'Close' }).click()
  await expect(modal).toHaveCount(0)
})

test('a person who joined after every note never gets the modal', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const page = await ctx.newPage()
  await page.goto('/my-work')
  await expect(page.getByRole('heading', { name: 'My Work' })).toBeVisible()
  expect((await whatsNew(page)).show).toBeNull()
  // The modal waits for the page to go idle (≤ 1.2s) before it would open.
  await page.waitForTimeout(1500)
  await expect(page.getByRole('dialog', { name: /What’s new/ })).toHaveCount(0)
  await ctx.close()
})

test('a tour walks the real UI: the sidebar journey', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const page = await ctx.newPage()
  await page.goto('/my-work')
  const sidebar = page.getByRole('complementary', { name: 'Sidebar' })
  test.skip(!(await hasJourney(page, 'Collapse the sidebar')), 'no sidebar journey in the shipped notes')
  await sidebar.getByRole('button', { name: /What’s new/ }).click()
  const sheet = page.getByRole('dialog', { name: 'What’s new' })
  await sheet.getByText('Collapse the sidebar', { exact: true }).first().locator('xpath=ancestor::div[2]').getByRole('button', { name: 'Show me' }).click()

  const tour = page.getByTestId('feature-tour')
  await expect(tour).toContainText('1 of 3')
  await expect(tour).toContainText('Click it to go on')
  // A click step moves on when the person does it for real.
  await sidebar.getByRole('button', { name: 'Collapse sidebar' }).click()
  await expect(tour).toContainText('2 of 3')
  await expect(sidebar.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()
  await tour.getByRole('button', { name: 'Next' }).click()
  await expect(tour).toContainText('3 of 3')
  await sidebar.getByRole('button', { name: 'Expand sidebar' }).click()
  await expect(tour).toHaveCount(0)
  await expect(sidebar.getByRole('button', { name: 'Collapse sidebar' })).toBeVisible()
  await ctx.close()
})

test("a tour can start on another page: Support's project search", async ({ browser }) => {
  // Starts on the Inbox; the tour's first step opens Support reports itself.
  const ctx = await browser.newContext({ storageState: auth('support') })
  const page = await ctx.newPage()
  await page.goto('/inbox')
  test.skip(!(await hasJourney(page, 'Search for a project')), 'no Support project-search journey in the shipped notes')
  await page.getByRole('complementary', { name: 'Sidebar' }).getByRole('button', { name: /What’s new/ }).click()
  const sheet = page.getByRole('dialog', { name: 'What’s new' })
  await sheet.getByText('Search for a project', { exact: true }).first().locator('xpath=ancestor::div[2]').getByRole('button', { name: 'Show me' }).click()

  const tour = page.getByTestId('feature-tour')
  await expect(page).toHaveURL(/\/support\/reports$/)
  await expect(tour).toContainText('1 of 3')
  await page.getByRole('button', { name: 'New report' }).click()
  await expect(tour).toContainText('2 of 3')
  await page.locator('[data-tour="project-picker"]').click()
  await expect(tour).toContainText('3 of 3')
  await expect(page.getByLabel('Search projects')).toBeVisible()
  await tour.getByRole('button', { name: 'Done' }).click()
  await expect(tour).toHaveCount(0)
  await ctx.close()
})
