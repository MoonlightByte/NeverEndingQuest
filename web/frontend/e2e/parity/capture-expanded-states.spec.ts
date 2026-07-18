import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'
import fs from 'node:fs/promises'
import {
  assertNamedPair,
  captureStable,
  installDeterminism,
  parityOutputRoot,
  settleApplication,
} from './strict-oracle'

type Pair = {
  legacy: Page
  react: Page
  legacyContext: BrowserContext
  reactContext: BrowserContext
}

async function capturePair(legacy: Page, react: Page, name: string) {
  // Transient completion overlays auto-hide after two seconds. Capture both
  // exact/stable transactions concurrently so one side's three screenshots
  // cannot consume the other side's entire visibility window.
  await Promise.all([
    captureStable(legacy, name, 'legacy'),
    captureStable(react, name, 'react'),
  ])
  await assertNamedPair(name)
}

async function settlePair(legacy: Page, react: Page) {
  await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])
}

async function resetScenario(context: BrowserContext, name = 'baseline') {
  const response = await context.request.post(`/__parity__/scenario/${name}`)
  expect(response.ok(), `Parity scenario ${name} must reset successfully`).toBeTruthy()
}

/**
 * Every expanded state gets a clean browser pair. Production session/dialog
 * stores are process-global per tab; carrying one destructive/modal state into
 * another would test ordering contamination instead of the named UI surface.
 */
async function withPair(
  browser: Browser,
  run: (pair: Pair) => Promise<void>,
  options: { scenario?: string; dismissBanner?: boolean } = {},
) {
  const legacyContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  await Promise.all([
    installDeterminism(legacyContext, { dismissBanner: options.dismissBanner ?? true }),
    installDeterminism(reactContext, { dismissBanner: options.dismissBanner ?? true }),
  ])
  await resetScenario(legacyContext, options.scenario ?? 'baseline')
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  try {
    await Promise.all([legacy.goto('/'), react.goto('/play/')])
    await settlePair(legacy, react)
    await run({ legacy, react, legacyContext, reactContext })
  } finally {
    await legacyContext.close()
    await reactContext.close()
  }
}

test.beforeAll(async () => fs.mkdir(parityOutputRoot, { recursive: true }))

test('capture expanded high-value legacy and React states', async ({ browser }) => {
  test.setTimeout(600_000)
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires deterministic real server')
  const startAt = Number(process.env.NEQ_EXPANDED_START_AT ?? '29')

  if (startAt <= 29) await test.step('first-run banner and pre-start controls', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await expect(legacy.locator('#first-run-banner')).toBeVisible()
      await expect(react.getByText('Welcome to NeverEndingQuest!', { exact: false })).toBeVisible()
      await expect(legacy.locator('#start-button')).toHaveText('New Game')
      await expect(react.getByRole('button', { name: 'New Game', exact: true })).toBeEnabled()
      await capturePair(legacy, react, '29-first-run-pre-start')
    }, { scenario: 'pre-start', dismissBanner: false })
  })

  if (startAt <= 30) await test.step('full archive save mode', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await legacy.locator('#save-button').click()
      await react.getByRole('button', { name: 'Save', exact: true }).click()
      await legacy.locator('#save-mode').selectOption('full')
      await react.locator('#save-mode').selectOption('full')
      await expect(legacy.getByText('Archive Edition Save', { exact: true })).toBeVisible()
      await expect(react.getByText('Archive Edition Save', { exact: true })).toBeVisible()
      await capturePair(legacy, react, '30-save-full-mode')
    })
  })

  if (startAt <= 31) await test.step('selected saved game', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await legacy.locator('#load-button').click()
      await react.getByRole('button', { name: 'Load', exact: true }).click()
      await expect(legacy.locator('#save-list .save-item').first()).toBeVisible({ timeout: 5_000 })
      await expect(react.locator('.neq-save-item-parity').first()).toBeVisible({ timeout: 5_000 })
      // The legacy card fills its overlay and Chromium reports that ancestor
      // as intercepting pointer input. Invoke the legacy selection contract
      // directly; the dedicated proof test verified its normal resulting DOM.
      await legacy.evaluate(() => {
        const item = document.querySelector('#save-list .save-item') as HTMLElement | null
        const select = (window as typeof window & { selectSaveGame?: (folder: string, element: HTMLElement) => void }).selectSaveGame
        if (!item || !select) throw new Error('Legacy save selection contract unavailable')
        select('save_20260717_120000', item)
      })
      await react.locator('.neq-save-item-parity').first().click()
      await expect(legacy.locator('#save-list .save-item.selected')).toBeVisible({ timeout: 2_000 })
      await expect(legacy.locator('#load-save-button')).toBeEnabled({ timeout: 2_000 })
      await expect(react.locator('.neq-save-item-parity[aria-pressed="true"]')).toBeVisible({ timeout: 2_000 })
      await expect(react.getByRole('button', { name: 'Load Game', exact: true })).toBeEnabled({ timeout: 2_000 })
      await capturePair(legacy, react, '31-load-selected')
    })
  })

  if (startAt <= 32) await test.step('valid campaign reset confirmation', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await legacy.locator('#reset-button').click()
      await react.getByRole('button', { name: 'Reset', exact: true }).click()
      const legacyCode = (await legacy.locator('#reset-confirmation-code').textContent())?.trim() ?? ''
      const reactCode = (await react.getByTestId('reset-code').textContent())?.trim() ?? ''
      expect(legacyCode).toBe('21250')
      expect(reactCode).toBe(legacyCode)
      await legacy.locator('#reset-code-input').fill(legacyCode)
      await react.getByLabel('Reset confirmation code').fill(reactCode)
      await expect(legacy.locator('#confirm-reset-button')).toBeEnabled()
      await expect(react.getByRole('button', { name: 'Confirm Reset', exact: true })).toBeEnabled()
      await capturePair(legacy, react, '32-reset-valid-code')
    })
  })

  if (startAt <= 33) await test.step('local provider settings variant', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await legacy.locator('.settings-button').click()
      await react.getByRole('button', { name: 'Settings', exact: true }).click()
      await legacy.locator('#model-provider-select').selectOption('lmstudio')
      await react.locator('#model-provider-select').selectOption('lmstudio')
      await expect(legacy.locator('#local-endpoint-settings')).toBeVisible()
      await expect(react.getByText('Local / Custom Server', { exact: true }).last()).toBeVisible()
      await capturePair(legacy, react, '33-settings-local-provider')
    })
  })

  if (startAt <= 34) await test.step('OpenAI voice settings variant', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await legacy.locator('.settings-button').click()
      await react.getByRole('button', { name: 'Settings', exact: true }).click()
      await legacy.locator('#tts-toggle').evaluate((element: HTMLInputElement) => element.click())
      await react.locator('#setting-dm-voice').evaluate((element: HTMLInputElement) => element.click())
      await legacy.locator('#tts-engine-select').selectOption('openai')
      await react.locator('#tts-engine-select').selectOption('openai')
      await legacy.locator('#tts-voice-select').selectOption('fable')
      await react.locator('#tts-voice-select').selectOption('fable')
      await expect(legacy.locator('#dm-voice-settings-section')).toBeVisible()
      await expect(legacy.locator('#tts-voice-select')).toHaveValue('fable')
      await expect(react.locator('#tts-voice-select')).toHaveValue('fable')
      await capturePair(legacy, react, '34-settings-openai-voice')
    })
  })

  if (startAt <= 35) await test.step('confirmed exit overlay', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      for (const page of [legacy, react]) page.once('dialog', (dialog) => void dialog.accept())
      await legacy.locator('#exit-button').click()
      await react.getByRole('button', { name: '× Exit', exact: true }).click()
      await expect(legacy.getByText('Thank you for playing!', { exact: true })).toBeVisible()
      await expect(react.getByText('Thank you for playing!', { exact: true })).toBeVisible()
      await capturePair(legacy, react, '35-exit-overlay')
    })
  })

  if (startAt <= 36) await test.step('compression completion', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await resetScenario(legacyContext, 'compression')
      await legacy.waitForTimeout(100)
      await resetScenario(legacyContext, 'compression-complete')
      await expect(legacy.getByText(/Chronicle compression complete!/)).toBeVisible()
      await expect(react.getByText(/Chronicle compression complete!/)).toBeVisible()
      await capturePair(legacy, react, '36-compression-complete')
    })
  })

  if (startAt <= 37) await test.step('module completion', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await resetScenario(legacyContext, 'module-progress')
      await legacy.waitForTimeout(100)
      await resetScenario(legacyContext, 'module-complete')
      await expect(legacy.locator('#module-progress-modal')).toBeVisible()
      await expect(react.locator('.neq-module-progress-parity')).toBeVisible()
      await capturePair(legacy, react, '37-module-complete')
    })
  })

  if (startAt <= 38) await test.step('module safe failure', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await resetScenario(legacyContext, 'module-failed-progress')
      await legacy.waitForTimeout(100)
      await resetScenario(legacyContext, 'module-failed')
      await expect(legacy.getByText('Adventure forging failed safely.', { exact: true })).toBeVisible()
      await expect(react.getByText('Adventure forging failed safely.', { exact: true })).toBeVisible()
      await capturePair(legacy, react, '38-module-failed')
    })
  })

  if (startAt <= 39) await test.step('recovered reconnect', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext, reactContext }) => {
      await Promise.all([legacyContext.setOffline(true), reactContext.setOffline(true)])
      await expect(legacy.locator('#status-text')).toHaveText('Disconnected')
      await expect(react.getByLabel('Disconnected')).toBeVisible()
      await Promise.all([legacyContext.setOffline(false), reactContext.setOffline(false)])
      await settlePair(legacy, react)
      await expect(legacy.locator('#status-text')).toHaveText('Connected')
      await expect(react.getByLabel('Connected')).toBeVisible()
      await capturePair(legacy, react, '39-recovered-reconnect')
    })
  })
})
