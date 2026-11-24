import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Slice 21 (docs/phase-2/21-support-channel.md): a CTO sets a project's Support
// channel (chat ID, topic ID), cannot switch it on before a message has passed,
// and sees the reason when the test fails. The E2E stack has no reachable
// Telegram, so the passing path (test → enable → posts) is covered at the API seam
// (backend/tests/phase2/test_support_channel.py); this spec covers the screen.

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
    return { status: res.status, body: res.status === 204 ? null : await res.json().catch(() => null) }
  }, { method, url, body })
}

test('CTO saves a Support channel, cannot enable it untested, and sees the failed test', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('cto') })
  const page = await ctx.newPage()
  await page.goto('/dashboard')
  const projects = (await api(page, 'GET', '/projects')).body as { id: number; slug: string }[]
  const project = projects.find((p) => p.slug === SLUG)!
  await api(page, 'PUT', `/projects/${project.id}/support-channel`, { chat_id: -1001, enabled: false })

  await page.goto(`/settings?tab=support&project=${project.id}`)
  const panel = page.getByRole('region', { name: 'Support channel' })
  await expect(panel).toBeVisible()

  const toggle = panel.getByRole('switch', { name: 'Post to the Support channel' })
  await expect(toggle).toBeDisabled()

  await panel.getByLabel('Chat ID').fill('not a number')
  await panel.getByRole('button', { name: 'Send test message' }).click()
  await expect(panel.getByText('A chat ID is a number')).toBeVisible()

  await panel.getByLabel('Chat ID').fill('-1001234567890')
  await panel.getByLabel('Topic ID').fill('7')
  await panel.getByRole('button', { name: 'Save' }).click()
  await expect(panel.getByRole('button', { name: 'Save' })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('region', { name: 'Support channel' }).getByLabel('Chat ID')).toHaveValue('-1001234567890')
  await expect(page.getByRole('region', { name: 'Support channel' }).getByLabel('Topic ID')).toHaveValue('7')

  // No Telegram in this stack: the test fails with a reason, and the switch stays off.
  const again = page.getByRole('region', { name: 'Support channel' })
  await again.getByRole('button', { name: 'Send test message' }).click()
  // Real outbound call or no bot configured: either way a reason, within the client's own timeout.
  await expect(again.getByText(/Test failed — /)).toBeVisible({ timeout: 45_000 })
  await expect(again.getByRole('switch', { name: 'Post to the Support channel' })).toBeDisabled()

  const stale = await api(page, 'PUT', `/projects/${project.id}/support-channel`,
    { chat_id: -1001234567890, thread_id: 7, enabled: true })
  expect(stale.status).toBe(409)
  expect((stale.body as { code: string }).code).toBe('support_channel_untested')
  await ctx.close()
})

test('a Developer cannot read or change a Support channel', async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: auth('developer') })
  const page = await ctx.newPage()
  await page.goto('/dashboard')
  const projects = (await api(page, 'GET', '/projects')).body as { id: number; slug: string }[]
  const project = projects.find((p) => p.slug === SLUG)!
  expect((await api(page, 'GET', `/projects/${project.id}/support-channel`)).status).toBe(403)
  expect((await api(page, 'PUT', `/projects/${project.id}/support-channel`,
    { chat_id: -1, enabled: false })).status).toBe(403)
  await ctx.close()
})
