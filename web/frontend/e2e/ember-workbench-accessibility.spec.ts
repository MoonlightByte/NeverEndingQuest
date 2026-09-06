import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

test.skip(process.env.NEQ_E2E_WORKBENCH !== '1', 'Isolated static workbench accessibility review')
const web = path.resolve(process.cwd(), '../..')
async function fixture(page: Page) {
  const errors: string[] = [], writes: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (route.request().method() !== 'GET') { writes.push(url.pathname); return route.abort() }
    if (url.hostname === 'cdn.socket.io') return route.fulfill({ contentType: 'application/javascript', body: 'window.__emits=[];window.io=()=>({on(){return this},emit(name){window.__emits.push(name);return this}})' })
    if (url.origin !== 'http://ember-workbench.test') return route.abort()
    if (url.pathname === '/') {
      const template = await readFile(path.join(web, 'web/templates/module_toolkit.html'), 'utf8')
      return route.fulfill({ contentType: 'text/html', body: template.replace(/\{\{ url_for\('static', filename='((?:css|js)\/ember-[^']+)'\) \}\}/g, '/static/$1') })
    }
    if (/^\/static\/(css|js|fonts)\/ember[-/]/.test(url.pathname)) {
      const file = path.resolve(web, 'web', '.' + url.pathname)
      if (!file.startsWith(path.join(web, 'web/static') + path.sep)) return route.abort()
      return route.fulfill({ body: await readFile(file), contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : 'font/woff2' })
    }
    return route.fulfill({ contentType: 'application/json', body: '[]' })
  })
  await page.goto('http://ember-workbench.test/')
  await page.evaluate(() => document.fonts.ready)
  return { errors, writes }
}

for (const width of [1586, 390]) {
  test(`toolkit keyboard tabs expose all six panels and retain builder request at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 992 })
    const result = await fixture(page)
    const tabs = page.getByRole('tab')
    await expect(tabs).toHaveCount(6)
    const initialModuleRequests = await page.evaluate(() => (window as unknown as { __emits: string[] }).__emits.filter(name => name === 'request_module_list').length)
    await tabs.first().focus()
    for (const [key, index] of [['ArrowRight', 1], ['ArrowDown', 2], ['End', 5], ['Home', 0], ['ArrowLeft', 5], ['ArrowUp', 4]] as const) {
      await page.keyboard.press(key)
      await expect(tabs.nth(index)).toBeFocused()
      await expect(tabs.nth(index)).toHaveAttribute('aria-selected', 'true')
      await expect(tabs.nth(index)).toHaveAttribute('tabindex', '0')
      await expect(page.locator('[role="tab"][tabindex="0"]')).toHaveCount(1)
      await expect(page.getByRole('tabpanel')).toHaveCount(1)
      const panel = page.getByRole('tabpanel')
      await expect(panel).toHaveAttribute('id', (await tabs.nth(index).getAttribute('aria-controls'))!)
      await expect(panel).toHaveAttribute('aria-labelledby', (await tabs.nth(index).getAttribute('id'))!)
    }
    expect(await page.evaluate(() => (window as unknown as { __emits: string[] }).__emits.filter(name => name === 'request_module_list').length)).toBe(initialModuleRequests + 1)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('tabpanel')).toBeFocused()
    await page.keyboard.press('Tab')
    expect(await page.evaluate(() => !!document.activeElement?.closest('#builder-tab'))).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('tabpanel').evaluate(element => element.getAnimations({ subtree: true }).forEach(animation => animation.finish()))
    await page.screenshot({ path: info.outputPath(`tabs-${width}.png`) })
    expect(result).toEqual({ errors: [], writes: [] })
  })
}

test('workbench help supports focus, hover, Escape and hidden-panel exclusion', async ({ page }, info) => {
  await page.setViewportSize({ width: 1586, height: 992 })
  const result = await fixture(page)
  const help = page.getByRole('button', { name: 'Help: Import Graphic Pack', exact: true })
  await help.focus()
  await expect(page.getByRole('tooltip')).toHaveText('Import a graphic pack from a .zip file.')
  await expect(help).toHaveAttribute('aria-describedby', (await page.getByRole('tooltip').getAttribute('id'))!)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await expect(help).toBeFocused()
  await page.getByRole('tab').first().focus()
  await help.hover()
  await expect(page.getByRole('tooltip')).toBeVisible()
  await page.getByRole('tooltip').hover()
  await page.waitForTimeout(220)
  await expect(page.getByRole('tooltip')).toBeVisible()
  await page.mouse.move(1, 1)
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await help.click()
  await expect(page.getByRole('tooltip')).toBeVisible()
  await page.screenshot({ path: info.outputPath('help-desktop.png') })
  await page.getByRole('tab', { name: 'Module Builder', exact: true }).click()
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await expect(help).toBeHidden()
  expect(result).toEqual({ errors: [], writes: [] })
})

test('workbench help supports touch open/close inside the phone viewport', async ({ browser }, info) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true })
  try {
    const page = await context.newPage()
    const result = await fixture(page)
    const help = page.getByRole('button', { name: 'Help: Import Graphic Pack', exact: true })
    await help.tap()
    const tip = page.getByRole('tooltip')
    await expect(tip).toBeVisible()
    const box = (await tip.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(390)
    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.y + box.height).toBeLessThanOrEqual(844)
    await page.screenshot({ path: info.outputPath('help-phone.png') })
    await help.tap()
    await expect(tip).toHaveCount(0)
    await help.tap()
    await expect(tip).toBeVisible()
    await page.getByRole('tab').first().tap()
    await expect(tip).toHaveCount(0)
    expect(result).toEqual({ errors: [], writes: [] })
  } finally { await context.close() }
})
