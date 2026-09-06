import { expect, test } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Explicit populated interactive preview only')
test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Smashing Jack')
})

test('preview exposes NPC details, alias scrolls, journal and storage', async ({ page }) => {
  await page.getByRole('tab', { name: 'NPCs', exact: true }).click()
  const npc = page.locator('.neq-npc-character-sheet').first()
  for (const name of ['Saving Throw', 'Skills', 'Inventory', 'Key Abilities', 'Racial Traits', 'Background', 'Spells']) {
    await npc.getByRole('button', { name, exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
  }
  await page.getByRole('tab', { name: 'Spells & Magic', exact: true }).click()
  await page.getByRole('button', { name: /Scroll of Melf/ }).click()
  await expect(page.getByRole('dialog')).toContainText('powdered rhubarb leaf')
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Journal', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('The Thornwood Road')
  await page.keyboard.press('Escape')
  await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
  await page.getByRole('button', { name: 'View Player Storage' }).click()
  await expect(page.getByRole('dialog')).toContainText('Outpost Locker')
})

test('inventory query and sort survive tab switches, polling and viewport changes', async ({ page }) => {
  const inventory = page.getByRole('tab', { name: 'Inventory', exact: true })
  await inventory.click()
  await page.getByLabel('Sort inventory').selectOption('name-desc')
  const search = page.getByRole('button', { name: 'Search', exact: true })
  await search.click()
  await page.getByRole('textbox', { name: 'Search items', exact: true }).fill('Scroll')
  await page.keyboard.press('Escape')
  await expect(search).toBeFocused()
  await expect(page.locator('.neq-inventory-item')).toHaveCount(2)
  await page.getByRole('tab', { name: 'Character', exact: true }).click()
  await inventory.click()
  for (const width of [1023, 1024, 390, 1586]) {
    await page.setViewportSize({ width, height: 992 })
    await expect(page.locator('.neq-inventory-item')).toHaveCount(2)
    await expect(page.getByLabel('Sort inventory')).toHaveValue('name-desc')
    await expect(page.getByRole('dialog', { name: 'Search Inventory' })).toHaveCount(0)
  }
  await expect.poll(() => page.locator('.neq-inventory-item').count()).toBe(2)
  await search.click()
  await expect(page.getByRole('textbox', { name: 'Search items', exact: true })).toHaveValue('Scroll')
})

test('long feature content can be pinned and scrolled without covering its trigger', async ({ page }) => {
  // Mutate only rendered synthetic content to exercise overflow, never game data.
  const feature = page.getByRole('button', { name: 'Unarmored Defense', exact: true })
  await page.setViewportSize({ width: 1586, height: 500 })
  await feature.click()
  const panel = page.getByRole('dialog', { name: 'Unarmored Defense details' })
  const body = panel.locator('.ember-inspection-body')
  await body.evaluate(node => { node.textContent = 'Long supplied feature description. '.repeat(300) })
  await expect(panel.getByRole('button', { name: 'Close Unarmored Defense details' })).toBeFocused()
  await body.focus()
  await body.press('End')
  await expect.poll(() => body.evaluate(node => node.scrollTop)).toBeGreaterThan(0)
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
  await expect(feature).toBeFocused()
})

test('unchanged visibility retains media; changed pack revision refreshes portraits', async ({ page }) => {
  await page.locator('.ember-people').getByRole('button', { name: 'Ranger Elen', exact: true }).click()
  const viewer = page.getByRole('dialog', { name: 'Character media', exact: true })
  await expect(viewer).toBeVisible()
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(viewer).toBeVisible()
  const portrait = page.locator('.neq-character-portrait img')
  const before = await portrait.getAttribute('src')
  await page.evaluate(() => window.dispatchEvent(new StorageEvent('storage', { key: 'neq_media_revision', newValue: 'preview-pack-replacement' })))
  await expect(viewer).toHaveCount(0)
  await expect(portrait).not.toHaveAttribute('src', before!)
})
