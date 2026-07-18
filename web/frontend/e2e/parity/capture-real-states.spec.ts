import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs/promises'
import { assertNamedPair, captureStable, installDeterminism, parityOutputRoot, settleApplication } from './strict-oracle'

const outputRoot = parityOutputRoot
async function settle(page: Page, legacy: boolean) {
  await settleApplication(page, legacy)
}
async function shot(page: Page, name: string, legacy: boolean) {
  await captureStable(page, name, legacy ? 'legacy' : 'react')
  if (!legacy) await assertNamedPair(name)
}

test.beforeAll(async () => fs.mkdir(outputRoot, { recursive: true }))
test('capture real hover, combat, operation, and reconnect states', async ({ browser }) => {
  test.setTimeout(150_000)
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires deterministic real server')
  const legacyContext = await browser.newContext({ viewport: { width: 2048, height: 1228 } })
  const reactContext = await browser.newContext({ viewport: { width: 2048, height: 1228 } })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  // The parity server is intentionally long-lived so local audit commands can
  // reuse it. Reset its process-global status/cache before the first capture;
  // otherwise a previous run that ended in processing/combat can contaminate
  // the initial hover and tooltip states even though both pages are fresh.
  await legacy.request.post('/__parity__/scenario/baseline')
  await Promise.all([legacy.goto('/'), react.goto('/play/')]); await Promise.all([settle(legacy, true), settle(react, false)])

  await test.step('portrait hover', async () => {
    await expect(legacy.locator('.character-portrait')).toBeVisible({ timeout: 10_000 })
    await expect(react.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 10_000 })
    await legacy.locator('.character-portrait').hover(); await react.getByAltText('Portrait of Arden Vale').locator('..').hover()
    await shot(legacy, '20-portrait-hover', true); await shot(react, '20-portrait-hover', false)
  })

  await test.step('spell tooltip', async () => {
    await legacy.getByRole('button', { name: 'Spells & Magic', exact: true }).click(); await react.getByRole('tab', { name: 'Spells & Magic', exact: true }).click()
    await expect(legacy.locator('.spell-name').first()).toBeVisible({ timeout: 10_000 }); await legacy.locator('.spell-name').first().hover()
    await expect(react.getByText('Goodberry', { exact: true }).first()).toBeVisible({ timeout: 10_000 }); await react.getByText('Goodberry', { exact: true }).first().hover()
    await legacy.waitForTimeout(150); await shot(legacy, '21-spell-tooltip', true); await shot(react, '21-spell-tooltip', false)
  })

  await test.step('combat turns and exit', async () => {
    await Promise.all([legacy.reload(), react.reload()]); await Promise.all([settle(legacy, true), settle(react, false)])
    await legacy.request.post('/__parity__/scenario/combat-player-turn'); await legacy.waitForTimeout(5500)
    await expect(legacy.locator('#initiative-tracker-container')).toBeVisible(); await expect(react.getByLabel('Initiative order')).toBeVisible()
    await shot(legacy, '22-combat-player-turn', true); await shot(react, '22-combat-player-turn', false)
    await legacy.request.post('/__parity__/scenario/combat-enemy-turn'); await legacy.waitForTimeout(500)
    await shot(legacy, '23-combat-enemy-turn', true); await shot(react, '23-combat-enemy-turn', false)
    await legacy.request.post('/__parity__/scenario/processing'); await legacy.waitForTimeout(5500)
    await expect(react.getByLabel('Initiative order')).toBeHidden()
    await shot(legacy, '24-processing-lock', true); await shot(react, '24-processing-lock', false)
  })

  await test.step('operation overlays', async () => {
    await legacy.request.post('/__parity__/scenario/compression'); await legacy.waitForTimeout(150)
    await shot(legacy, '25-compression-progress', true); await shot(react, '25-compression-progress', false)
    await legacy.request.post('/__parity__/scenario/compression-complete'); await legacy.waitForTimeout(2200)
    await legacy.request.post('/__parity__/scenario/module-progress'); await legacy.waitForTimeout(150)
    await shot(legacy, '26-module-progress', true); await shot(react, '26-module-progress', false)
    await legacy.request.post('/__parity__/scenario/module-complete')
    await legacy.waitForTimeout(3200)
  })

  await test.step('update dialog', async () => {
    await Promise.all([legacy.reload(), react.reload()]); await Promise.all([settle(legacy, true), settle(react, false)])
    await legacy.request.post('/__parity__/scenario/update'); await legacy.waitForTimeout(150)
    await legacy.locator('#update-button').click(); await react.getByRole('button', { name: /Update Available/ }).click()
    await shot(legacy, '27-update', true); await shot(react, '27-update', false)
  })

  await test.step('disconnect and recover', async () => {
    await Promise.all([legacy.reload(), react.reload()]); await Promise.all([settle(legacy, true), settle(react, false)])
    await Promise.all([legacy.context().setOffline(true), react.context().setOffline(true)]); await legacy.waitForTimeout(500)
    await shot(legacy, '28-disconnected', true); await shot(react, '28-disconnected', false)
    await Promise.all([legacy.context().setOffline(false), react.context().setOffline(false)]); await Promise.all([settle(legacy, true), settle(react, false)])
  })
  await legacyContext.close(); await reactContext.close()
})
