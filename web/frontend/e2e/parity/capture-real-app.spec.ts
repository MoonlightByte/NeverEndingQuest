import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs/promises'
import { assertNamedPair, captureStable, installDeterminism, parityOutputRoot, settleApplication } from './strict-oracle'

const outputRoot = parityOutputRoot

async function settle(page: Page, legacy: boolean) {
  await settleApplication(page, legacy)
}

async function capture(page: Page, name: string, legacy: boolean) {
  const side = legacy ? 'legacy' : 'react'
  await captureStable(page, name, side)
  if (!legacy) await assertNamedPair(name)
}

test.beforeAll(async () => fs.mkdir(outputRoot, { recursive: true }))

test('capture real application legacy and React parity surfaces', async ({ browser }) => {
  test.setTimeout(240_000)
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the real NeverEndingQuest server')

  const legacyContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  // The parity fixture deliberately exposes process-global transition states
  // (combat, compression, reconnect, and module progress).  Always restore
  // the canonical game before opening either UI so a prior scenario run can
  // never contaminate the supposedly static 01-19 capture set.
  const baseline = await legacyContext.request.post('/__parity__/scenario/baseline')
  expect(baseline.ok(), 'Parity fixture baseline reset must succeed').toBeTruthy()
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  await legacy.goto('/')
  await react.goto('/play/')
  await settle(legacy, true)
  await settle(react, false)
  await expect(legacy.getByText('3 rounds', { exact: true })).toBeVisible()
  await expect(react.getByText('Blessed — 3 rounds', { exact: true })).toBeVisible()

  await capture(legacy, '01-character', true)
  await capture(react, '01-character', false)

  const tabs = [
    { name: '02-inventory', legacy: 'Inventory', react: 'Inventory' },
    { name: '03-spells', legacy: 'Spells & Magic', react: 'Spells & Magic' },
    { name: '04-npcs', legacy: 'NPCs', react: 'NPCs' },
    { name: '05-debug', legacy: 'Debug', react: 'Debug' },
  ]
  for (const tab of tabs) {
    await legacy.getByRole('button', { name: tab.legacy, exact: true }).click()
    await react.getByRole('tab', { name: tab.react, exact: true }).click()
    await legacy.waitForTimeout(300)
    await react.waitForTimeout(300)
    await capture(legacy, tab.name, true)
    await capture(react, tab.name, false)
  }

  await legacy.locator('#journal-btn').click()
  await react.getByRole('button', { name: 'Journal', exact: true }).click()
  await capture(legacy, '06-journal', true)
  await capture(react, '06-journal', false)
  await legacy.reload()
  await react.reload()
  await settle(legacy, true)
  await settle(react, false)

  const dialogs = [
    { name: '07-save', legacy: '#save-button', react: 'Save' },
    { name: '08-load', legacy: '#load-button', react: 'Load' },
    { name: '09-reset', legacy: '#reset-button', react: 'Reset' },
  ]
  for (const dialog of dialogs) {
    // Exercise both applications through the same real user interaction.
    // Calling only the legacy global function leaves focus in the command
    // field while clicking React moves it to the header button, creating a
    // large but artificial native-focus screenshot difference.
    await legacy.locator(dialog.legacy).click()
    await react.getByRole('button', { name: dialog.react, exact: true }).click()
    await legacy.waitForTimeout(300)
    await react.waitForTimeout(300)
    await capture(legacy, dialog.name, true)
    await capture(react, dialog.name, false)
    await legacy.reload()
    await react.reload()
    await settle(legacy, true)
    await settle(react, false)
  }

  await legacy.locator('.settings-button').click()
  await react.getByRole('button', { name: 'Settings', exact: true }).click()
  await capture(legacy, '10-settings', true)
  await capture(react, '10-settings', false)

  const reloadPair = async () => {
    await Promise.all([legacy.reload(), react.reload()])
    await Promise.all([settle(legacy, true), settle(react, false)])
  }

  // Inventory auxiliary surfaces.
  await reloadPair()
  await legacy.getByRole('button', { name: 'Inventory', exact: true }).click()
  await react.getByRole('tab', { name: 'Inventory', exact: true }).click()
  await legacy.getByRole('button', { name: 'View Player Storage', exact: true }).click()
  await react.getByRole('button', { name: 'View Player Storage', exact: true }).click()
  await legacy.waitForTimeout(300); await react.waitForTimeout(300)
  await capture(legacy, '11-storage', true); await capture(react, '11-storage', false)

  await reloadPair()
  await legacy.getByRole('button', { name: 'Inventory', exact: true }).click()
  await react.getByRole('tab', { name: 'Inventory', exact: true }).click()
  await legacy.getByRole('button', { name: 'Search', exact: true }).click()
  await react.getByRole('button', { name: 'Search', exact: true }).click()
  await capture(legacy, '12-inventory-search', true); await capture(react, '12-inventory-search', false)

  // Every independent NPC detail surface.
  for (const [index, action] of ['Saving Throw', 'Skills', 'Inventory', 'Key Abilities', 'Racial Traits', 'Background', 'Spells'].entries()) {
    await reloadPair()
    await legacy.getByRole('button', { name: 'NPCs', exact: true }).click()
    await react.getByRole('tab', { name: 'NPCs', exact: true }).click()
    await legacy.waitForTimeout(300); await react.waitForTimeout(300)
    const legacyAction = action === 'Inventory'
      ? legacy.locator('.npc-detail-button').filter({ hasText: /^Inventory$/ }).first()
      : legacy.getByRole('button', { name: action, exact: true }).first()
    await legacyAction.click()
    await react.getByRole('button', { name: action, exact: true }).first().click()
    if (action === 'Inventory') {
      await expect(legacy.locator('#npc-inventory-modal')).toBeVisible()
      await expect(react.getByRole('dialog', { name: /Inventory/ })).toBeVisible()
    }
    const slug = action.toLowerCase().replace(/\s+/g, '-')
    await capture(legacy, `${String(13 + index).padStart(2, '0')}-npc-${slug}`, true)
    await capture(react, `${String(13 + index).padStart(2, '0')}-npc-${slug}`, false)
  }

  await legacyContext.close()
  await reactContext.close()
})
