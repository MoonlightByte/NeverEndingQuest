import { expect, test } from '@playwright/test'
import {
  assertNamedPair,
  canonicalViewport,
  captureStable,
  freezePage,
  installDeterminism,
  settleApplication,
} from './strict-oracle'

async function capturePair(
  legacy: import('@playwright/test').Page,
  react: import('@playwright/test').Page,
  name: string,
  clip?: { x: number; y: number; width: number; height: number },
) {
  await captureStable(legacy, name, 'legacy', clip ? { clip } : {})
  await captureStable(react, name, 'react', clip ? { clip } : {})
  return assertNamedPair(name)
}

test('animation and randomness normalization for base, reset, and compression', async ({ browser, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  test.setTimeout(120_000)
  await request.post('/__parity__/scenario/reset')
  const legacyContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  await Promise.all([legacy.goto('/'), react.goto('/play/')])
  await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])

  await capturePair(legacy, react, 'normalization-01-base')
  await capturePair(legacy, react, 'normalization-01-title', { x: 20, y: 0, width: 370, height: 60 })
  const logBox = await legacy.locator('#game-output').boundingBox()
  if (!logBox) throw new Error('Missing legacy game log box')
  await capturePair(legacy, react, 'normalization-01-log', logBox)

  await legacy.evaluate(() => {
    const open = (window as unknown as { openResetDialog?: () => void }).openResetDialog
    if (!open) throw new Error('Missing legacy reset dialog function')
    open()
  })
  await react.getByRole('button', { name: 'Reset', exact: true }).click()
  await expect(legacy.locator('#reset-confirmation-code')).toHaveText('21250')
  await expect(react.getByTestId('reset-code')).toHaveText('21250')
  await capturePair(legacy, react, 'normalization-09-reset')

  await Promise.all([legacy.reload(), react.reload()])
  await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])
  await request.post('/__parity__/scenario/compression')
  const flavor = 'The Dungeon Master carefully inscribes your deeds into the eternal chronicle...'
  await expect(legacy.getByText(flavor, { exact: true })).toBeVisible()
  await expect(react.getByText(flavor, { exact: true })).toBeVisible()
  await capturePair(legacy, react, 'normalization-25-compression')

  await legacyContext.close()
  await reactContext.close()
})

test('finite entrance animations settle at their visible end state', async ({ browser, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')
  await request.post('/__parity__/scenario/reset')
  const context = await browser.newContext({ viewport: canonicalViewport, deviceScaleFactor: 1 })
  await installDeterminism(context)
  const page = await context.newPage()
  await page.goto('/')
  await settleApplication(page, true)
  await page.evaluate(() => {
    const open = (window as unknown as { openSaveDialog?: () => void }).openSaveDialog
    if (!open) throw new Error('Missing legacy save dialog function')
    open()
  })

  await freezePage(page)
  await expect(page.locator('.save-mode-details:visible')).toHaveCSS('opacity', '1')
  await captureStable(page, 'normalization-07-save-finite-animation', 'legacy')
  await context.close()
})

test('baseline scenario clears sticky processing before an initial capture', async ({ browser, request }) => {
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires the deterministic real server')

  // Reproduce the cross-run contaminant, then apply the same reset used by
  // capture-real-states before either application navigates.
  await request.post('/__parity__/scenario/processing')
  await request.post('/__parity__/scenario/baseline')

  const legacy = await browser.newPage({ viewport: canonicalViewport })
  const react = await browser.newPage({ viewport: canonicalViewport })
  await Promise.all([legacy.goto('/'), react.goto('/play/')])
  await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])

  await expect(legacy.locator('#user-input')).toBeEnabled()
  await expect(react.getByLabel('Player input')).toBeEnabled()
  await expect(legacy.locator('#user-input')).toHaveAttribute('placeholder', 'Enter your command...')
  await expect(react.getByLabel('Player input')).toHaveAttribute('placeholder', 'Enter your command...')

  await Promise.all([legacy.close(), react.close()])
})
