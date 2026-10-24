import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// TASK-748: the sidebar collapses to a 56px icon rail (chosen from a prototype,
// 2026-10-24) — from the toggle in the logo row or `[`, remembered per browser.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

const width = async (page: Page) => (await page.getByRole('complementary', { name: 'Sidebar' }).boundingBox())!.width

test('the sidebar collapses to an icon rail and remembers it', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const page = await ctx.newPage()
  await page.goto('/my-work')
  const sidebar = page.getByRole('complementary', { name: 'Sidebar' })

  // Expanded by default: labels and section headers show.
  await expect(sidebar.getByRole('button', { name: 'Collapse sidebar' })).toBeVisible()
  await expect(sidebar.getByText('All Issues')).toBeVisible()
  await expect.poll(() => width(page)).toBe(224)

  // Collapse: icons only, each still named, with its label on hover.
  await sidebar.getByRole('button', { name: 'Collapse sidebar' }).click()
  await expect.poll(() => width(page)).toBe(56)
  await expect(sidebar.getByText('All Issues')).toHaveCount(0)
  await expect(sidebar.getByText('Issues', { exact: true })).toHaveCount(0)
  const allIssues = sidebar.getByRole('link', { name: 'All Issues' })
  await allIssues.hover()
  await expect(page.getByRole('tooltip')).toHaveText('All Issues')

  // Rail links still navigate, and the choice survives a reload.
  await allIssues.click()
  await expect(page).toHaveURL(/\/issues$/)
  await page.reload()
  await expect.poll(() => width(page)).toBe(56)
  await expect(sidebar.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()

  // `[` toggles it — but not while typing. (`c` opens New issue without also
  // typing a "c" into the title it focuses.)
  await page.keyboard.press('c')
  const title = page.getByRole('dialog', { name: 'New bug' }).getByLabel('Title', { exact: true })
  await title.pressSequentially('[draft')
  await expect(title).toHaveValue('[draft')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'New bug' })).toHaveCount(0)
  await expect.poll(() => width(page)).toBe(56)
  await page.keyboard.press('[')
  await expect.poll(() => width(page)).toBe(224)
  await expect(sidebar.getByText('All Issues')).toBeVisible()

  await ctx.close()
})
