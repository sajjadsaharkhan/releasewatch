import { test, expect, type Browser } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Comment composer: a single newline renders as a line break (BUG-812) and
// Ctrl/⌘+Z undoes toolbar and shortcut edits, which used to wipe the undo
// history. Seed: backend/scripts/seed_e2e.py.

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const auth = (role: string) => path.join(__dirname, '..', '.auth', `${role}.json`)

async function openComposer(browser: Browser) {
  const ctx = await browser.newContext({ storageState: auth('cto') })
  const page = await ctx.newPage()
  await page.goto('/issues')
  // list rows are not links: click the first row's key
  await page.getByText(/^(BUG|TASK)-\d+$/).first().click()
  const box = page.getByPlaceholder('Leave a comment…')
  await expect(box).toBeVisible()
  return { page, box }
}

test('a single newline shows as a line break in the preview', async ({ browser }) => {
  const { page, box } = await openComposer(browser)
  await box.fill('first line\nsecond line\nسطر سوم')
  await page.getByRole('tab', { name: 'Preview' }).click()
  const p = page.locator('p', { hasText: 'first line' })
  await expect(p.locator('br')).toHaveCount(2)
  await expect(p).toContainText('second line')
  await expect(p).toContainText('سطر سوم')
})

test('a blank line still starts a new paragraph', async ({ browser }) => {
  const { page, box } = await openComposer(browser)
  await box.fill('para one\n\npara two')
  await page.getByRole('tab', { name: 'Preview' }).click()
  await expect(page.locator('p', { hasText: 'para one' })).toBeVisible()
  await expect(page.locator('p', { hasText: 'para two' })).toBeVisible()
})

test('Ctrl+Z undoes a toolbar edit, and redo brings it back', async ({ browser }) => {
  const { page, box } = await openComposer(browser)
  await box.click()
  await box.pressSequentially('hello')
  await box.press('ControlOrMeta+a')
  await page.getByRole('button', { name: /Bold/ }).click()
  await expect(box).toHaveValue('**hello**')
  await box.press('ControlOrMeta+z')
  await expect(box).toHaveValue('hello')
  await box.press('ControlOrMeta+Shift+z')
  await expect(box).toHaveValue('**hello**')
})

test('Ctrl+Z undoes a keyboard-shortcut edit', async ({ browser }) => {
  const { box } = await openComposer(browser)
  await box.click()
  await box.pressSequentially('world')
  await box.press('ControlOrMeta+a')
  await box.press('ControlOrMeta+i')
  await expect(box).toHaveValue('_world_')
  await box.press('ControlOrMeta+z')
  await expect(box).toHaveValue('world')
})

test('underscores inside an identifier stay literal; _word_ is still italic (BUG-904)', async ({ browser }) => {
  const { page, box } = await openComposer(browser)
  await box.fill('app_Teacher_Select_Educational_Calendar_1 and _emphasis_')
  await page.getByRole('tab', { name: 'Preview' }).click()
  const p = page.locator('p', { hasText: 'app_Teacher' })
  await expect(p).toContainText('app_Teacher_Select_Educational_Calendar_1')
  await expect(p.locator('em')).toHaveCount(1)
  await expect(p.locator('em')).toHaveText('emphasis')
})
