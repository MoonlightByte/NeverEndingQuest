import { expect, test } from '@playwright/test'

test('built player shell connects and core dialogs work', async ({ page, context }) => {
  await page.goto('/play/')

  await expect(page.getByRole('heading', { name: 'NeverEndingQuest' })).toBeVisible()
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('The wind whispers across the Forsaken Crossroads.')).toBeVisible()

  await page.getByRole('button', { name: 'Save', exact: true }).click()
  const saveDialog = page.getByRole('dialog', { name: 'Save Game' })
  await expect(saveDialog).toBeVisible()
  await expect(saveDialog.getByLabel('Description (optional):')).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(saveDialog).toBeHidden()

  await page.getByRole('button', { name: 'Settings' }).click()
  await expect(page.getByRole('menu', { name: 'Settings' })).toBeVisible()
  await expect(page.getByText('AI Provider', { exact: true })).toBeVisible()

  await context.setOffline(true)
  await expect(page.getByText('Disconnected from the game server. Reconnecting...')).toBeVisible({
    timeout: 15_000,
  })
  await context.setOffline(false)
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
})

test('legacy and React player routes coexist', async ({ request }) => {
  const legacy = await request.get('/')
  const react = await request.get('/play/')

  expect(legacy.status()).toBe(200)
  expect(react.status()).toBe(200)
  expect(await react.text()).toContain('/play/assets/')
})

test('player shell does not overflow a phone viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/play/')
  // The desktop connection label is intentionally collapsed at phone widths;
  // live game content proves the socket contract reached the responsive shell.
  await expect(page.getByText('The wind whispers across the Forsaken Crossroads.')).toBeVisible({ timeout: 15_000 })

  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    content: document.documentElement.scrollWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
})

test('first turn and combat mode render from the socket contract', async ({ page }) => {
  await page.goto('/play/')
  await expect(page.getByLabel('Player input')).toBeVisible({ timeout: 15_000 })

  await page.getByLabel('Player input').fill('Begin combat validation')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByText('Begin combat validation', { exact: true })).toBeVisible()
  await expect(page.getByText('A Storm Wraith surges forward. Roll initiative!')).toBeVisible()
  await expect(page.getByLabel('Initiative order')).toBeVisible()
  await expect(page.getByLabel('Combat, round 1')).toBeVisible()
})

test('save intent and save listing round-trip through Socket.IO', async ({ page }) => {
  await page.goto('/play/')
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Save', exact: true }).click()
  const saveDialog = page.getByRole('dialog')
  await saveDialog.getByLabel('Description (optional):').fill('Browser fixture save')
  await saveDialog.getByRole('button', { name: 'Save Game' }).click()
  await expect(page.getByText('Saved: Browser fixture save')).toBeVisible()

  await page.getByRole('button', { name: 'Load', exact: true }).click()
  await expect(page.getByRole('dialog').getByText('E2E validation')).toBeVisible()
})
