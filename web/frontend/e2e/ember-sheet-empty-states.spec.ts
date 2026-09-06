import { expect, test } from '@playwright/test'

test.skip(process.env.NEQ_E2E_EMBER_VISUAL !== '1', 'Only the isolated scripted preview; no campaign or provider calls')

test('non-caster notice uses Ember colors while narrow layouts retain their original styling', async ({ page }, info) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/play/')
  await page.getByRole('tab', { name: 'Spells & Magic', exact: true }).click()
  const notice = page.locator('.neq-no-spells')
  await expect(notice).toContainText('This character does not have spellcasting abilities.')
  await expect(notice).toHaveCSS('background-color', 'rgb(12, 17, 17)')
  await expect(notice).toHaveCSS('color', 'rgb(221, 214, 200)')
  await expect(notice).toHaveCSS('border-top-color', 'rgb(73, 59, 39)')
  await expect(notice).toHaveCSS('font-size', '18px')
  await expect(notice).toHaveAttribute('role', 'status')
  const consumable = page.locator('.neq-consumable').first()
  await expect(consumable).toHaveText('[1x]')
  await expect(consumable).toHaveCSS('background-color', 'rgb(12, 17, 17)')
  await expect(consumable).toHaveCSS('color', 'rgb(197, 160, 109)')
  await expect(consumable).toHaveCSS('border-top-color', 'rgb(73, 59, 39)')
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: info.outputPath('non-caster-desktop.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  // The pre-existing gray notice is only in the >=761px legacy stylesheet.
  // On phones, compare against the exact original class to verify no change.
  const phoneStyles = await notice.evaluate(node => {
    const properties = ['backgroundColor', 'color', 'borderTopColor', 'fontSize', 'fontStyle'] as const
    const before = properties.map(key => getComputedStyle(node)[key])
    const legacy = node.cloneNode(true) as HTMLElement
    legacy.classList.remove('ember-sheet-status'); node.parentElement!.append(legacy)
    const after = properties.map(key => getComputedStyle(legacy)[key]); legacy.remove()
    return { before, after }
  })
  expect(phoneStyles.before).toEqual(phoneStyles.after)
  await expect(notice).not.toHaveAttribute('role')
  await page.setViewportSize({ width: 900, height: 844 })
  await expect(notice).toHaveCSS('background-color', 'rgb(44, 44, 44)')
  await expect(notice).toHaveCSS('color', 'rgb(136, 136, 136)')
  await expect(notice).toHaveCSS('border-top-color', 'rgb(68, 68, 68)')
  await expect(consumable).toHaveText('[1x]')
  await expect(consumable).toHaveCSS('background-color', 'rgb(102, 102, 102)')
  await expect(consumable).toHaveCSS('color', 'rgb(255, 255, 255)')
  await expect(notice).not.toHaveAttribute('role')
})

for (const state of ['empty', 'error']) test(`NPC ${state} uses the shared desktop status surface without changing phone styling`, async ({ page }, info) => {
  // Transform only the isolated fixture's NPC response; retain the real
  // Socket.IO client/store/component path and all unrelated game state.
  await page.routeWebSocket('**/socket.io/**', socket => {
    const server = socket.connectToServer()
    server.onMessage(message => {
      if (typeof message === 'string' && message.startsWith('42')) {
        const [event, payload] = JSON.parse(message.slice(2))
        if (event === 'player_data_response' && payload.dataType === 'npcs') {
          payload.data = []
          if (state === 'error') payload.error = 'NPC data unavailable in this test'
          message = `42${JSON.stringify([event, payload])}`
        }
      }
      socket.send(message)
    })
  })
  await page.setViewportSize({ width: 1586, height: 992 })
  await page.goto('/play/')
  await page.getByRole('tab', { name: 'NPCs', exact: true }).click()
  const notice = page.locator(`.ember-sheet-status[data-state="${state}"]`)
  await expect(notice).toHaveCSS('background-color', 'rgb(12, 17, 17)')
  await expect(notice).toHaveCSS('font-size', '18px')
  await expect(notice).toHaveCSS('color', state === 'error' ? 'rgb(239, 170, 148)' : 'rgb(221, 214, 200)')
  await expect(notice).toHaveAttribute('role', state === 'error' ? 'alert' : 'status')
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: info.outputPath(`npc-${state}-desktop.png`) })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(notice).toHaveCSS('font-size', '14px')
  await expect(notice).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(notice).not.toHaveAttribute('role')
})
