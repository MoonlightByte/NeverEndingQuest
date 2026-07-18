import { expect, test } from '@playwright/test'

test('reconnect deduplicates input and recovers a missed operation terminal event', async ({ page, context, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  await page.goto('/play/')
  await expect(page.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })

  await page.getByLabel('Player input').fill('A uniquely correlated reconnect command')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByText('A uniquely correlated reconnect command', { exact: true })).toHaveCount(1)

  await request.post('/__parity__/scenario/compression')
  await expect(page.getByText('Chronicle Compression')).toBeVisible()
  await context.setOffline(true)
  await expect(page.getByText('Disconnected from the game server. Reconnecting...')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Game Running' })).toBeDisabled()
  await expect(page.getByText('Welcome to NeverEndingQuest! Before you start', { exact: false })).toBeHidden()
  await request.post('/__parity__/scenario/compression-complete')
  await context.setOffline(false)
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('A uniquely correlated reconnect command', { exact: true })).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Chronicle Compression', exact: true })).toBeHidden({ timeout: 8_000 })
})

test('a new server instance accepts fresh low revisions without reloading the browser', async ({ page, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  await page.goto('/play/')
  await expect(page.getByText(/Mosswatch Gate/).first()).toBeVisible({ timeout: 15_000 })
  await request.post('/__parity__/scenario/server-instance-reset')
  await expect(page.getByText(/Restarted Watchtower/).first()).toBeVisible({ timeout: 10_000 })
})
