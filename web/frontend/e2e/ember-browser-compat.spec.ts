import { expect, test, type Page } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Requires the scripted populated Ember preview, never a real campaign')

async function openPreview(page: Page) {
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Smashing Jack')
  await page.evaluate(() => document.fonts.ready)
  const fontsLoaded = await page.evaluate(async () => {
    const families = ['Cinzel', 'Crimson Text']
    return Promise.all(families.map(async family => {
      const faces = await document.fonts.load(`400 20px "${family}"`, 'NeverEndingQuest')
      return faces.length > 0 && faces.every(face => face.status === 'loaded')
    }))
  })
  expect(fontsLoaded).toEqual([true, true])
}

test('populated desktop retains readable columns, original sample media and reachable controls', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1586, height: 992 })
  await openPreview(page)
  await page.locator('.ember-desktop img').evaluateAll(images => Promise.all(images.map(image => (image as HTMLImageElement).decode())))
  await expect(page.locator('.neq-character-chip')).toHaveCount(6)
  const decodedPortraits = await page.locator('.ember-chip-portrait').evaluateAll(nodes => Promise.all(nodes.map(async node => {
    const background = getComputedStyle(node).backgroundImage
    const match = background.match(/^url\(["']?(.*?)["']?\)$/)
    if (!match) return false
    const image = new Image()
    image.src = match[1]!
    await image.decode()
    return image.naturalWidth > 0 && image.naturalHeight > 0
  })))
  expect(decodedPortraits).toEqual([true, true, true, true, true, true])
  await expect(page.locator('.neq-inline-images img')).toHaveCount(1)
  const geometry = await page.evaluate(() => {
    const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect()
    return { sheet: box('.neq-rail-area').right, story: box('.neq-main-area').x,
      storyRight: box('.neq-main-area').right, people: box('.ember-people').x,
      overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(geometry.overflow).toBe(false)
  expect(Math.abs(geometry.story - 471)).toBeLessThan(3)
  expect(Math.abs(geometry.people - 1284)).toBeLessThan(3)
  expect(geometry.sheet).toBeLessThanOrEqual(geometry.story + 1)
  expect(geometry.storyRight).toBeLessThanOrEqual(geometry.people + 1)
  await expect(page.getByRole('textbox', { name: 'Player input' })).toBeInViewport()
  for (const name of ['D20', 'D12', 'D10', 'D8', 'D6', 'D4', 'Clear', 'Save', 'Load', 'Reset', 'Settings', 'Toolkit', '× Exit', 'Send']) {
    await expect(page.getByRole('button', { name, exact: true })).toBeInViewport()
  }
  await page.getByRole('textbox', { name: 'Player input' }).blur()
  await page.locator('.neq-game-log').evaluate(node => { node.scrollTop = 0 })
  // Diagnostic capture for personal review, not a Chromium-golden override or
  // cross-engine pixel-equality assertion against concept artwork.
  await page.screenshot({ path: info.outputPath('populated-desktop.png') })
  expect(errors).toEqual([])
})

test('equipment hover, pinned ownership and Escape preserve supplied details and focus', async ({ page }, info) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  await openPreview(page)
  await page.getByRole('tab', { name: 'Inventory', exact: true }).click()
  const input = page.getByRole('textbox', { name: 'Player input' })
  const maul = page.getByRole('button', { name: 'Maul', exact: true })
  const compass = page.getByRole('button', { name: 'Moonlit Compass', exact: true })
  await input.focus()
  await maul.hover()
  const details = page.getByRole('dialog', { name: 'Maul details', exact: true })
  await expect(details).toContainText('A sturdy two-handed maul.')
  await expect(details).toContainText('Equipped')
  await page.keyboard.press('Escape')
  await expect(details).toHaveCount(0)
  await expect(input).toBeFocused()
  await maul.click()
  const close = details.getByRole('button', { name: 'Close Maul details' })
  await expect(close).toBeFocused()
  await compass.hover()
  await expect(close).toBeFocused()
  await expect(page.locator('.ember-inspection')).toHaveCount(1)
  await page.screenshot({ path: info.outputPath('equipment-inspection.png') })
  await page.keyboard.press('Escape')
  await expect(details).toHaveCount(0)
  await expect(maul).toBeFocused()
})

test('alias-scroll hover and keyboard pin retain complete spell metadata in a short viewport', async ({ page }, info) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await openPreview(page)
  await page.getByRole('tab', { name: 'Spells & Magic', exact: true }).click()
  const scroll = page.getByRole('button', { name: /^Scroll of Melf/ })
  await scroll.hover()
  const details = page.getByRole('dialog', { name: /^Scroll of Melf.* details$/ })
  await expect(details).toContainText('powdered rhubarb leaf')
  for (const field of ['Range', 'Duration', 'Materials']) await expect(details).toContainText(field)
  await scroll.focus()
  await scroll.press('Enter')
  await expect(details.getByRole('button', { name: /^Close Scroll of Melf/ })).toBeFocused()
  const rect = await details.boundingBox()
  expect(rect!.x).toBeGreaterThanOrEqual(0)
  expect(rect!.y).toBeGreaterThanOrEqual(0)
  expect(rect!.x + rect!.width).toBeLessThanOrEqual(1024)
  expect(rect!.y + rect!.height).toBeLessThanOrEqual(768)
  await page.screenshot({ path: info.outputPath('alias-scroll-inspection.png') })
  await page.keyboard.press('Escape')
  await expect(details).toHaveCount(0)
  await expect(scroll).toBeFocused()
})

test('touch-enabled desktop opens and closes actual item inspection without game actions', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:4174', hasTouch: true, viewport: { width: 1586, height: 992 } })
  try {
    const page = await context.newPage()
    const outboundEvents: string[] = []
    const observeFrame = (frame: string) => {
      if (frame.startsWith('42')) outboundEvents.push(JSON.parse(frame.slice(frame.indexOf('[')))[0])
    }
    page.on('websocket', socket => socket.on('framesent', ({ payload }) => {
      observeFrame(payload.toString())
    }))
    page.on('request', request => {
      const url = new URL(request.url())
      if (request.method() === 'POST' && url.pathname === '/socket.io/' && url.searchParams.get('transport') === 'polling') {
        for (const frame of (request.postData() ?? '').split('\x1e')) observeFrame(frame)
      }
    })
    await openPreview(page)
    await page.getByRole('tab', { name: 'Inventory', exact: true }).tap()
    const maul = page.getByRole('button', { name: 'Maul', exact: true })
    await maul.tap()
    const details = page.getByRole('dialog', { name: 'Maul details', exact: true })
    await expect(details).toBeVisible()
    await details.getByRole('button', { name: 'Close Maul details' }).tap()
    await expect(details).toHaveCount(0)
    await expect(maul).toBeFocused()
    // Observe real outgoing Socket.IO events, including hydration, so this is
    // not a vacuous assertion against an unattached transport observer.
    expect(outboundEvents).toContain('request_player_data')
    const readOnlyEvents = new Set(['request_player_data', 'request_location_data', 'request_party_data', 'request_initiative_data', 'request_plot_data', 'request_storage_data', 'request_ui_snapshot', 'request_map_data', 'request_npc_saves', 'request_npc_skills', 'request_npc_spells', 'request_npc_inventory', 'request_module_list', 'get_model_provider', 'get_local_endpoint', 'get_openai_key', 'get_gemini_key'])
    expect(outboundEvents.filter(event => !readOnlyEvents.has(event))).toEqual([])
  } finally { await context.close() }
})
