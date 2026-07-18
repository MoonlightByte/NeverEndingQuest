import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'
import fs from 'node:fs/promises'
import {
  assertNamedPair,
  captureStable,
  declareScrollPosition,
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

async function resetScenario(context: BrowserContext, name: string) {
  const response = await context.request.post(`/__parity__/scenario/${name}`)
  expect(response.ok(), `Parity scenario ${name} must reset successfully`).toBeTruthy()
}

async function capturePair(legacy: Page, react: Page, name: string) {
  // Several bounded terminal states have a deliberate two-second hold.  Run
  // the exact/stability transactions together so one side cannot consume the
  // other side's hold window.
  await Promise.all([
    captureStable(legacy, name, 'legacy'),
    captureStable(react, name, 'react'),
  ])
  await assertNamedPair(name)
}

async function expectConnectedHydration(legacy: Page, react: Page) {
  await expect(legacy.locator('#status-indicator')).toHaveClass(/connected/, { timeout: 15_000 })
  await expect(react.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  await expect(legacy.getByText('Mosswatch Gate', { exact: false }).first()).toBeVisible({ timeout: 15_000 })
  await expect(react.getByText('Mosswatch Gate', { exact: false }).first()).toBeVisible({ timeout: 15_000 })
  await expect(legacy.locator('.character-name')).toBeVisible({ timeout: 15_000 })
  await expect(react.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })
}

async function withPair(
  browser: Browser,
  run: (pair: Pair) => Promise<void>,
  options: { scenario?: string; settle?: boolean; blockSocket?: boolean } = {},
) {
  const legacyContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  const reactContext = await browser.newContext({ viewport: { width: 2048, height: 1228 }, deviceScaleFactor: 1 })
  await Promise.all([installDeterminism(legacyContext), installDeterminism(reactContext)])
  await resetScenario(legacyContext, options.scenario ?? 'baseline')
  if (options.blockSocket) {
    await Promise.all([
      legacyContext.route('**/socket.io/**', (route) => route.abort()),
      reactContext.route('**/socket.io/**', (route) => route.abort()),
    ])
  }
  const legacy = await legacyContext.newPage()
  const react = await reactContext.newPage()
  try {
    await Promise.all([legacy.goto('/'), react.goto('/play/')])
    if (options.settle ?? true) {
      await Promise.all([settleApplication(legacy, true), settleApplication(react, false)])
    }
    await run({ legacy, react, legacyContext, reactContext })
  } finally {
    await legacyContext.close()
    await reactContext.close()
  }
}

async function openSettings(legacy: Page, react: Page) {
  await Promise.all([
    legacy.locator('.settings-button').click(),
    react.getByRole('button', { name: 'Settings', exact: true }).click(),
  ])
  await expect(legacy.locator('#settings-dropdown')).toBeVisible()
  await expect(react.getByRole('menu', { name: 'Settings' })).toBeVisible()
}

async function selectProvider(legacy: Page, react: Page, value: 'gemini' | 'lmstudio') {
  await Promise.all([
    legacy.locator('#model-provider-select').selectOption(value),
    react.locator('#model-provider-select').selectOption(value),
  ])
  await expect(legacy.locator('#model-provider-select')).toHaveValue(value)
  await expect(react.locator('#model-provider-select')).toHaveValue(value)
}

async function openUpdate(legacy: Page, react: Page, context: BrowserContext) {
  await resetScenario(context, 'update')
  await expect(legacy.locator('#update-button')).toBeVisible()
  await expect(react.getByRole('button', { name: /Update Available/ })).toBeVisible()
  await Promise.all([
    legacy.locator('#update-button').click(),
    react.getByRole('button', { name: /Update Available/ }).click(),
  ])
  await expect(legacy.locator('#update-dialog-overlay')).toBeVisible()
  await expect(react.getByRole('heading', { name: '🔄 Update Available', exact: true })).toBeVisible()
}

test.beforeAll(async () => fs.mkdir(parityOutputRoot, { recursive: true }))

test('capture independently audited bounded visual families V40-V57', async ({ browser }) => {
  test.setTimeout(900_000)
  test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Requires deterministic real server')
  const startAt = Number(process.env.NEQ_BOUNDED_START_AT ?? '40')

  if (startAt <= 40) await test.step('V40 bootstrap loading without transport hydration', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await expect(legacy.locator('#status-text')).toHaveText('Disconnected')
      await expect(react.getByLabel('Disconnected')).toBeVisible()
      await expect(legacy.getByText('Loading character stats...', { exact: true })).toBeVisible()
      await expect(react.getByText('Loading character stats...', { exact: true })).toBeVisible()
      await expect(legacy.locator('#location-name')).toHaveText('Loading location...')
      await expect(react.getByText('Loading location...', { exact: true })).toBeVisible()
      await expect(react.locator('.neq-version')).toHaveText(await legacy.locator('#version-display').innerText())
      await capturePair(legacy, react, '40-bootstrap-loading')
    }, { scenario: 'bootstrap-loading', settle: false, blockSocket: true })
  })

  if (startAt <= 41) await test.step('V41 startup handoff in progress', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await expectConnectedHydration(legacy, react)
      await Promise.all([
        legacy.locator('#start-button').click(),
        react.getByRole('button', { name: /Start Game|New Game/ }).click(),
      ])
      await resetScenario(legacyContext, 'startup-in-progress')
      await expect(legacy.locator('#start-button')).toHaveText('Starting...')
      await expect(react.getByRole('button', { name: 'Starting...', exact: true })).toBeVisible()
      await expect(legacy.locator('#user-input')).toBeDisabled()
      await expect(react.getByPlaceholder('Enter your command...')).toBeDisabled()
      await capturePair(legacy, react, '41-startup-in-progress')
    }, { scenario: 'pre-start', settle: false })
  })

  if (startAt <= 42) await test.step('V42 startup handoff failed with recovery surface', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await expectConnectedHydration(legacy, react)
      await Promise.all([
        legacy.locator('#start-button').click(),
        react.getByRole('button', { name: /Start Game|New Game/ }).click(),
      ])
      await resetScenario(legacyContext, 'startup-failed')
      await expect(legacy.getByText('Startup handoff failed. You can use recovery from settings.', { exact: true })).toBeVisible()
      await expect(react.getByText('Startup handoff failed. You can use recovery from settings.', { exact: true })).toBeVisible()
      await expect(react.getByLabel('Startup recovery token')).toHaveCount(0)
      await expect(legacy.locator('#user-input')).toBeEnabled()
      await expect(legacy.locator('#send-button')).toBeEnabled()
      await expect(react.getByLabel('Player input')).toBeEnabled()
      await expect(react.getByRole('button', { name: 'Send', exact: true })).toBeEnabled()
      await capturePair(legacy, react, '42-startup-failed')
      const blockedCommand = 'do not queue during startup recovery'
      await Promise.all([
        legacy.locator('#user-input').fill(blockedCommand),
        react.getByLabel('Player input').fill(blockedCommand),
      ])
      await Promise.all([
        legacy.locator('#send-button').click(),
        react.getByRole('button', { name: 'Send', exact: true }).click(),
      ])
      await react.waitForTimeout(250)
      await expect(legacy.locator('.message.user-input', { hasText: blockedCommand })).toHaveCount(0)
      await expect(react.locator('[data-message-type="user-input"]', { hasText: blockedCommand })).toHaveCount(0)
    }, { scenario: 'pre-start', settle: false })
  })

  if (startAt <= 43) await test.step('V43 exploration chip overflow at declared mid-scroll', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await expectConnectedHydration(legacy, react)
      const legacyRail = legacy.locator('#party-display-container')
      const reactRail = react.locator('.neq-chip-scroller[aria-label="Party members"]')
      await expect(legacyRail.locator('.party-member-item, .location-npc-item')).toHaveCount(17, { timeout: 15_000 })
      await expect(reactRail.locator('[data-chip]')).toHaveCount(17, { timeout: 15_000 })
      await Promise.all([
        declareScrollPosition(legacyRail, { left: 240 }),
        declareScrollPosition(reactRail, { left: 240 }),
      ])
      await expect(legacy.locator('#scroll-left-btn')).toBeVisible()
      await expect(react.getByRole('button', { name: 'Scroll party members left' })).toBeVisible()
      expect(await legacyRail.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
      expect(await reactRail.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
      await capturePair(legacy, react, '43-exploration-overflow-mid-scroll')
    }, { scenario: 'exploration-overflow', settle: false })
  })

  if (startAt <= 44) await test.step('V44 top-party stats tooltip', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      const legacyChip = legacy.locator('#party-display-container .party-member-item.player').first()
      const reactChip = react.locator('[aria-label="Party members"] [data-chip="party-player"]').first()
      await Promise.all([legacyChip.hover(), reactChip.hover()])
      const legacyTip = legacy.locator('.stats-tooltip.visible')
      const reactTip = react.getByRole('tooltip')
      await expect(legacyTip).toContainText('Lvl 4 Ranger')
      await expect(reactTip).toContainText('Lvl 4 Ranger')
      await expect(legacyTip).toHaveCSS('position', 'fixed')
      await expect(reactTip).toHaveCSS('position', 'fixed')
      await capturePair(legacy, react, '44-party-stats-tooltip')
    })
  })

  if (startAt <= 45) await test.step('V45 party image media popup', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await expectConnectedHydration(legacy, react)
      const legacyChip = legacy.locator('#party-display-container .location-npc-item', { hasText: 'Eirik Hearthwise' })
      const reactChip = react.locator('[aria-label="Party members"] [data-chip="location-npc"]', { hasText: 'Eirik Hearthwise' })
      await expect(legacyChip).toBeVisible({ timeout: 15_000 })
      await expect(reactChip).toBeVisible({ timeout: 15_000 })
      await Promise.all([legacyChip.click(), reactChip.click()])
      await expect(legacy.locator('#media-popup.visible #popup-image')).toBeVisible({ timeout: 10_000 })
      await expect(react.getByRole('dialog', { name: 'Character media' }).getByAltText('Character Portrait')).toBeVisible({ timeout: 10_000 })
      expect(await legacy.locator('#popup-image').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
      expect(await react.getByAltText('Character Portrait').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
      await capturePair(legacy, react, '45-media-image-popup')
    }, { scenario: 'media-image', settle: false })
  })

  if (startAt <= 46) await test.step('V46 combat processing with initiative overflow', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await expectConnectedHydration(legacy, react)
      // Re-emit processing after both listeners exist; the tracker was already
      // on disk before navigation, so initiative hydration remains real.
      await resetScenario(legacyContext, 'combat-processing-overflow')
      const legacyRail = legacy.locator('#initiative-tracker-container')
      const reactRail = react.locator('.neq-chip-scroller[aria-label="Initiative order"]')
      await expect(legacyRail.locator('.initiative-item')).toHaveCount(20, { timeout: 15_000 })
      await expect(reactRail.locator('[data-chip]')).toHaveCount(20, { timeout: 15_000 })
      await Promise.all([
        declareScrollPosition(legacyRail, { left: 260 }),
        declareScrollPosition(reactRail, { left: 260 }),
      ])
      await expect(legacy.locator('#user-input')).toBeDisabled()
      await expect(react.getByPlaceholder('Resolving twenty combatants...')).toBeDisabled()
      await expect(legacy.locator('#scroll-left-btn')).toBeVisible()
      await expect(react.getByRole('button', { name: 'Scroll initiative order left' })).toBeVisible()
      await capturePair(legacy, react, '46-combat-processing-overflow')
    }, { scenario: 'combat-processing-overflow', settle: false })
  })

  if (startAt <= 47) await test.step('V47 long main log and Debug at declared scroll positions', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await resetScenario(legacyContext, 'debug-overflow')
      await expect(legacy.getByText('Deterministic diagnostic line 64:', { exact: false })).toBeAttached()
      await Promise.all([
        legacy.locator('.tab-button', { hasText: 'Debug' }).click(),
        react.getByRole('tab', { name: 'Debug', exact: true }).click(),
      ])
      await expect(react.getByText('Deterministic diagnostic line 64:', { exact: false })).toBeAttached()
      const legacyMain = legacy.locator('#game-output')
      const reactMain = react.locator('.neq-game-log')
      const legacyDebug = legacy.locator('#debug-output')
      const reactDebug = react.locator('.neq-debug-scrollable')
      await Promise.all([
        declareScrollPosition(legacyMain, { top: 720 }),
        declareScrollPosition(reactMain, { top: 728 }),
        declareScrollPosition(legacyDebug, { top: 180 }),
        declareScrollPosition(reactDebug, { top: 180 }),
      ])
      // The legacy and React logs have different total scroll heights. Align the
      // same semantic message after declaring a nonzero position so the visual
      // comparison measures rendering, not unrelated scroll-range math.
      const legacyAnchor = legacy.locator('.message.narration .message-text', { hasText: 'Watch 4:' }).first()
      const reactAnchor = react.locator('[data-message-type="narration"] .neq-message-text', { hasText: 'Watch 4:' }).first()
      const [legacyAnchorBox, reactAnchorBox, reactScrollTop] = await Promise.all([
        legacyAnchor.boundingBox(),
        reactAnchor.boundingBox(),
        reactMain.evaluate((element) => element.scrollTop),
      ])
      if (legacyAnchorBox && reactAnchorBox) {
        await declareScrollPosition(reactMain, { top: reactScrollTop + reactAnchorBox.y - legacyAnchorBox.y })
      }
      await expect(legacy.locator('#tpm-value')).toHaveText('4,321')
      await expect(react.getByText('98,765', { exact: true })).toBeVisible()
      expect(await legacyMain.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
      expect(await reactDebug.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
      await capturePair(legacy, react, '47-main-log-debug-declared-scroll')
    })
  })

  if (startAt <= 48) await test.step('V48 generated image attached to narration', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      const legacyButton = legacy.locator('.message.narration .image-generation-button').last()
      const reactButton = react.getByTitle('Generate an image for this scene').last()
      await Promise.all([legacyButton.click(), reactButton.click()])
      const legacyImage = legacy.locator('.message.narration .generated-image').last()
      const reactImage = react.locator('[data-message-type="narration"] img[alt^="Generated scene:"]').last()
      await expect(legacyImage).toBeVisible({ timeout: 10_000 })
      await expect(reactImage).toBeVisible({ timeout: 10_000 })
      await expect(legacyImage).toHaveAttribute('src', /midday\.jpg$/)
      await expect(reactImage).toHaveAttribute('src', /midday\.jpg$/)
      expect(await legacyImage.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
      await capturePair(legacy, react, '48-generated-image')
    })
  })

  if (startAt <= 49) await test.step('V49 character skill tooltip at viewport edge', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      const legacyAbility = legacy.locator('#stats-content .ability-score').last()
      const reactAbility = react.locator('.neq-ability-score').last()
      await Promise.all([legacyAbility.hover(), reactAbility.hover()])
      const legacyTip = legacy.locator('.skill-tooltip.visible')
      const reactTip = react.getByText('Charisma Skills', { exact: true }).locator('..')
      await expect(legacyTip).toContainText('Charisma Skills')
      await expect(reactTip).toBeVisible()
      for (const tip of [legacyTip, reactTip]) {
        const box = await tip.boundingBox()
        expect(box).not.toBeNull()
        expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(2040)
      }
      await capturePair(legacy, react, '49-character-skill-tooltip-edge')
    })
  })

  if (startAt <= 50) await test.step('V50 generic feature tooltip', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      const legacyFeature = legacy.locator('[data-tooltip-title="Favored Foe"]')
      const reactFeature = react.getByText('Favored Foe', { exact: true }).last()
      await Promise.all([legacyFeature.scrollIntoViewIfNeeded(), reactFeature.scrollIntoViewIfNeeded()])
      await Promise.all([legacyFeature.hover(), reactFeature.hover()])
      await expect(legacy.locator('.spell-tooltip.visible')).toContainText('Mark a foe.')
      await expect(react.getByText('Mark a foe.', { exact: true })).toBeVisible()
      await expect(legacy.locator('.spell-tooltip.visible')).toHaveCSS('pointer-events', 'none')
      await capturePair(legacy, react, '50-generic-feature-tooltip')
    })
  })

  if (startAt <= 51) await test.step('V51 journal error state', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await Promise.all([
        legacy.locator('#journal-btn').click(),
        react.getByRole('button', { name: 'Journal', exact: true }).click(),
      ])
      // Drain the initial successful requests before injecting the error; a
      // late response must not overwrite one side during the capture.
      await expect(legacy.locator('#journal-left-page')).toContainText('Current Objectives')
      await expect(react.getByRole('dialog', { name: 'Adventure Journal' })).toContainText('Current Objectives')
      await resetScenario(legacyContext, 'journal-error')
      await expect(legacy.locator('#journal-left-page')).toContainText('Could not load quest data.')
      await expect(react.getByRole('dialog', { name: 'Adventure Journal' })).toContainText('Could not load quest data.')
      await expect(legacy.locator('#journal-modal')).toHaveCSS('display', 'block')
      await capturePair(legacy, react, '51-journal-error')
    })
  })

  if (startAt <= 52) await test.step('V52 Gemini provider settings', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await openSettings(legacy, react)
      await selectProvider(legacy, react, 'gemini')
      await expect(legacy.locator('#gemini-key-settings')).toBeVisible()
      await expect(react.getByText('Gemini API Key', { exact: true })).toBeVisible()
      await expect(legacy.locator('#local-endpoint-settings')).toBeHidden()
      await expect(react.getByText('Local / Custom Server', { exact: true }).last()).toBeHidden()
      await capturePair(legacy, react, '52-settings-gemini')
    })
  })

  if (startAt <= 53) await test.step('V53 local endpoint result and Auto-play tooltip', async () => {
    await withPair(browser, async ({ legacy, react }) => {
      await openSettings(legacy, react)
      await selectProvider(legacy, react, 'lmstudio')
      await Promise.all([
        legacy.locator('#tts-toggle').evaluate((element: HTMLInputElement) => element.click()),
        react.locator('#setting-dm-voice').evaluate((element: HTMLInputElement) => element.click()),
      ])
      await Promise.all([
        legacy.locator('#local-test-btn').click(),
        react.getByRole('button', { name: 'Test Connection', exact: true }).click(),
      ])
      await expect(legacy.locator('#local-endpoint-status')).toContainText('PASS: Connected. 2 model(s) available.')
      await expect(react.getByRole('status')).toContainText('PASS: Connected. 2 model(s) available.')
      const legacyAuto = legacy.locator('#autoplay-toggle-item')
      const reactAuto = react.locator('.neq-settings-item', { hasText: 'Auto-play' })
      await Promise.all([legacyAuto.hover(), reactAuto.hover()])
      await expect(legacy.locator('.autoplay-tooltip.visible')).toContainText('Auto-play Voice')
      // This is intentionally strict.  At harness authoring time the React
      // toggle lacked the legacy explanatory tooltip; a soft assertion keeps
      // V54-V56 observable while still failing the full parity gate.
      await expect.soft(react.getByText('Auto-play Voice', { exact: true })).toBeVisible({ timeout: 2_000 })
      await capturePair(legacy, react, '53-local-result-autoplay-tooltip')
    })
  })

  if (startAt <= 54) await test.step('V54 update running with deterministic log', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await openUpdate(legacy, react, legacyContext)
      await Promise.all([
        legacy.getByRole('button', { name: 'Proceed with Update', exact: true }).click(),
        react.getByRole('button', { name: 'Proceed with Update', exact: true }).click(),
      ])
      await expect(legacy.locator('#update-status')).toHaveText('Validating frontend assets...')
      await expect(react.getByRole('status')).toContainText('Validating frontend assets...')
      await expect(legacy.getByRole('button', { name: 'Proceed with Update', exact: true })).toBeEnabled()
      await expect(react.getByRole('button', { name: 'Proceed with Update', exact: true })).toBeEnabled()
      await capturePair(legacy, react, '54-update-running-log')
    })
  })

  if (startAt <= 55) await test.step('V55 update complete hold', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await openUpdate(legacy, react, legacyContext)
      await Promise.all([
        legacy.getByRole('button', { name: 'Proceed with Update', exact: true }).click(),
        react.getByRole('button', { name: 'Proceed with Update', exact: true }).click(),
      ])
      await resetScenario(legacyContext, 'update-complete')
      await expect(legacy.locator('#update-status')).toContainText('Update complete! Server restarting... Please refresh the page.')
      await expect(react.getByRole('status')).toContainText('Update complete! Server restarting...')
      await capturePair(legacy, react, '55-update-complete-hold')
    })
  })

  if (startAt <= 56) await test.step('V56 compression error hold', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await resetScenario(legacyContext, 'compression')
      await expect(legacy.locator('#compression-progress.active')).toBeVisible()
      await expect(react.getByText('Chronicle Compression', { exact: true })).toBeVisible()
      await resetScenario(legacyContext, 'compression-error')
      const errorText = 'Chronicle compression failed: The chronicle archive is temporarily unavailable.'
      // Immutable legacy has no compression_error listener and therefore has
      // no source screen for this terminal event. Prove that behavior, then
      // separately prove React's fail-safe message instead of fabricating a
      // pixel-parity target that does not exist in legacy.
      await expect(legacy.locator('#compression-status')).toHaveText('Compressing section 2 of 4...')
      await expect(react.getByRole('status')).toContainText(errorText)
    })
  })

  if (startAt <= 57) await test.step('V57 startup wizard accepts input only after ready', async () => {
    await withPair(browser, async ({ legacy, react, legacyContext }) => {
      await expectConnectedHydration(legacy, react)
      await Promise.all([
        legacy.locator('#start-button').click(),
        react.getByRole('button', { name: /Start Game|New Game/ }).click(),
      ])
      await resetScenario(legacyContext, 'startup-input-ready')
      await expect(legacy.locator('#user-input')).toBeEnabled()
      await expect(react.getByLabel('Player input')).toBeEnabled()
      const wizardAnswer = 'Arden Vale'
      await Promise.all([
        legacy.locator('#user-input').fill(wizardAnswer),
        react.getByLabel('Player input').fill(wizardAnswer),
      ])
      await Promise.all([
        legacy.locator('#send-button').click(),
        react.getByRole('button', { name: 'Send', exact: true }).click(),
      ])
      await expect(legacy.locator('.message.user-input', { hasText: wizardAnswer })).toHaveCount(1)
      await expect(react.locator('[data-message-type="user-input"]', { hasText: wizardAnswer })).toHaveCount(1)
    }, { scenario: 'pre-start', settle: false })
  })
})
