import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

// Opt-in template rendering probe. All network is intercepted: no generation,
// pack mutation, upload, key access or backend jobs are possible in this fixture.
test.skip(process.env.NEQ_E2E_WORKBENCH !== '1', 'Opt-in isolated workbench review')
const root = path.resolve(process.cwd(), '../..')
const socketFixture = 'window.__workbenchListeners=new Map; window.io=()=>({on(name,handler){window.__workbenchListeners.set(name,handler);return this},emit(){return this}})'
for (const width of [1586, 390]) {
  for (const surface of ['module_toolkit', 'module_builder']) {
    test(`${surface} ${width} controls and local fonts`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 992 })
      const errors: string[] = []
      page.on('pageerror', e => errors.push(e.message))
      await page.route('**/*', async route => {
        const url = new URL(route.request().url())
        if (url.hostname === 'cdn.socket.io') return route.fulfill({ contentType: 'application/javascript', body: socketFixture })
        if (url.pathname === '/') {
          const template = await readFile(path.join(root, 'web/templates', `${surface}.html`), 'utf8')
          return route.fulfill({ contentType: 'text/html', body: template.replace(/\{\{ url_for\('static', filename='((?:css|js)\/ember-[^']+)'\) \}\}/g, '/static/$1') })
        }
        if (url.pathname.startsWith('/static/css/ember-') || url.pathname.startsWith('/static/js/ember-') || url.pathname.startsWith('/static/fonts/ember/')) {
          const file = path.resolve(root, 'web', '.' + url.pathname)
          if (!file.startsWith(path.join(root, 'web/static') + path.sep)) return route.abort()
          return route.fulfill({ body: await readFile(file), contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : 'font/woff2' })
        }
        if (url.origin !== 'http://ember-workbench.test') return route.abort()
        return route.fulfill({ contentType: 'application/json', body: '[]' })
      })
      await page.goto('http://ember-workbench.test/')
      await page.evaluate(() => document.fonts.ready)
      expect(await page.evaluate(() => document.fonts.check('18px "Crimson Text"'))).toBe(true)
      await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(8, 13, 13)')
      if (surface === 'module_toolkit') {
        const tabs = ['packs', 'generator', 'npcs', 'videos', 'builder', 'media-gen']
        for (let i = 0; i < tabs.length; i++) {
          await page.locator('.tabs .tab').nth(i).click()
          await expect(page.locator(`#${tabs[i]}-tab`)).toBeVisible()
          await page.locator(`#${tabs[i]}-tab`).evaluate(el => el.getAnimations().forEach(a => a.finish()))
          const overflow = await page.evaluate(() => Array.from(document.querySelectorAll('body *')).filter(el => {const b=el.getBoundingClientRect();return b.width>0 && b.right>innerWidth+1}).map(el=> `${el.tagName}.${el.className}#${el.id}`).slice(0,12))
          expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${tabs[i]}: ${overflow.join(', ')}`).toBe(true)
          await page.screenshot({ path: info.outputPath(`${tabs[i]}.png`), fullPage: true })
        }
        for (const id of ['pack-confirm-modal', 'merge-confirm-modal', 'export-to-pack-modal']) {
          await page.locator(`#${id}`).evaluate(el => { (el as HTMLElement).style.display = 'flex' })
          await expect(page.locator(`#${id}`)).toBeVisible()
          const box = await page.locator(`#${id} .modal-content`).boundingBox()
          expect(box!.width).toBeLessThanOrEqual(width)
          await page.screenshot({ path: info.outputPath(`${id}.png`) })
          await page.locator(`#${id}`).evaluate(el => { (el as HTMLElement).style.display = 'none' })
        }
      } else {
        await expect(page.locator('#module-name')).toBeVisible()
        await page.locator('#module-name').fill('Review only')
        await expect(page.locator('#module-name')).toHaveValue('Review only')
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await page.screenshot({ path: info.outputPath('builder.png'), fullPage: true })
      }
      expect(errors).toEqual([])
    })
  }
}

for (const width of [1586, 390]) {
  test(`toolkit modal lifecycle ${width}: real open/cancel and nested focus`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 992 })
    const writes: string[] = []
    const errors: string[] = []
    let exportStatus = 200
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', async route => {
      const url = new URL(route.request().url())
      if (route.request().method() !== 'GET') {
        writes.push(`${route.request().method()} ${url.pathname}`)
        return route.abort()
      }
      if (url.hostname === 'cdn.socket.io') return route.fulfill({ contentType: 'application/javascript', body: socketFixture })
      if (url.origin !== 'http://ember-workbench.test') return route.abort()
      if (url.pathname === '/') {
        const template = await readFile(path.join(root, 'web/templates/module_toolkit.html'), 'utf8')
        return route.fulfill({ contentType: 'text/html', body: template.replace(/\{\{ url_for\('static', filename='((?:css|js)\/ember-[^']+)'\) \}\}/g, '/static/$1') })
      }
      if (/^\/static\/(css|js|fonts)\/ember[-/]/.test(url.pathname)) {
        const file = path.resolve(root, 'web', '.' + url.pathname)
        if (!file.startsWith(path.join(root, 'web/static') + path.sep)) return route.abort()
        return route.fulfill({ body: await readFile(file), contentType: file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : 'font/woff2' })
      }
      if (url.pathname.endsWith('/export')) {
        if (exportStatus === 500) return route.fulfill({ status: 500, contentType: 'text/html', body: '<p>Export failed: synthetic server failure.</p>' })
        // Deliberately slower than the template's notice timer: elapsed time is
        // not evidence of success, even while the response is still pending.
        await new Promise(resolve => setTimeout(resolve, 2800))
        return route.fulfill({ contentType: 'application/zip', headers: { 'Content-Disposition': 'attachment; filename="review-only.zip"' }, body: 'Synthetic download fixture' })
      }
      const data = url.pathname === '/api/toolkit/packs' ? [
        { name: 'photorealistic', display_name: 'Photorealistic', is_active: true },
        { name: 'review_pack', display_name: 'Review Pack', is_active: false },
      ] : url.pathname === '/api/toolkit/modules' ? [{ moduleName: 'review_module', levelRange: { min: 1, max: 3 } }]
        : url.pathname === '/api/toolkit/monsters' ? [{ id: 'review_wolf', name: 'Review Wolf', source: 'bestiary' }]
          : url.pathname.endsWith('/npcs') ? [{ id: 'review_guide', name: 'Review Guide', has_portrait: false }]
            : url.pathname.endsWith('/unified-assets') ? { success: true, assets: [{ id: 'review_guide', name: 'Review Guide', type: 'npc', has_description: true, has_image: false }], summary: { total_assets: 1, total_npcs: 1, total_monsters: 0, with_descriptions: 1, with_images: 0 } }
              : url.pathname.includes('styles') ? { builtin: { photorealistic: { name: 'Photorealistic', prompt: 'Existing photorealistic treatment' } }, custom: {} }
                : url.pathname.includes('get_style_prompt') ? { prompt: 'Existing photorealistic treatment' } : []
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
    })
    await page.goto('http://ember-workbench.test/')
    await page.evaluate(() => document.fonts.ready)
    // Deliver synthetic completion payloads through the actual registered
    // template handlers. No request or paid generation is issued.
    await page.evaluate(() => {
      const listeners = (window as unknown as { __workbenchListeners: Map<string, (data: unknown) => void> }).__workbenchListeners
      localStorage.removeItem('neq_media_revision')
      listeners.get('generation_complete')!({ successful: [], failed: ['fixture-failure'] })
      listeners.get('npc_generation_complete')!({ successful: [], failed: [] })
      listeners.get('unified_generation_complete')!({ success: false, error: 'fixture-failure' })
    })
    expect(await page.evaluate(() => localStorage.getItem('neq_media_revision'))).toBeNull()
    await expect(page.locator('#media-gen-status-message')).toHaveText('Generation Failed - See log for details')
    await expect(page.locator('#mediaGenLog .log-entry.error')).toContainText('fixture-failure')
    await expect(page.locator('#mediaGenLog .log-entry.success')).toHaveCount(0)
    await expect(page.locator('#media-gen-progress-text')).not.toHaveText('100%')
    for (const [event, payload, marker] of [
      ['generation_complete', { successful: ['review_wolf'], failed: [] }, 'monster-generation'],
      ['npc_generation_complete', { successful: [{ npc_name: 'Review Guide' }], failed: [] }, 'npc-generation'],
      ['unified_generation_complete', { success: true, generated_count: 1 }, 'module-media-generation'],
    ] as const) {
      await page.evaluate(({ event, payload }) => {
        (window as unknown as { __workbenchListeners: Map<string, (data: unknown) => void> }).__workbenchListeners.get(event)!(payload)
      }, { event, payload })
      expect(await page.evaluate(() => localStorage.getItem('neq_media_revision'))).toContain(marker)
    }
    await expect(page.locator('#media-gen-status-message')).toHaveText('Generation Complete!')
    await expect(page.locator('#media-gen-progress-text')).toHaveText('100%')
    await expect(page.locator('#mediaGenLog .log-entry.success')).toContainText('Generation completed successfully!')
    const activate = page.getByTitle('Activate Pack', { exact: true })
    await activate.click()
    const activation = page.getByRole('dialog', { name: 'Confirm Pack Activation' })
    await expect(activation).toBeVisible()
    expect(await page.locator('.backup-name').evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true)
    await expect(activation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
    await expect(page.locator('body > .container')).toHaveAttribute('inert', '')
    await page.keyboard.press('Tab')
    await expect(activation.getByRole('button', { name: 'Activate Pack', exact: true })).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(activation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
    await page.screenshot({ path: info.outputPath('activation-keyboard.png') })
    await page.keyboard.press('Escape')
    await expect(activation).toBeHidden()
    await expect(activate).toBeFocused()
    await expect(page.locator('body > .container')).not.toHaveAttribute('inert', '')

    // Public backend Merge is an existing no-op placeholder. The reachable UI
    // now explains its unavailability instead of offering a false-success flow.
    const merge = page.getByRole('button', { name: 'Merge into Active Pack', exact: true })
    await expect(merge).toBeDisabled()
    await expect(merge).toHaveAttribute('aria-describedby', 'pack-merge-unavailable')
    await expect(page.locator('#pack-merge-unavailable')).toHaveText('Pack merging is not available in this public release.')
    await merge.evaluate(node => (node as HTMLButtonElement).click())
    await expect(page.getByRole('dialog', { name: 'Confirm Pack Merge' })).toHaveCount(0)
    expect(writes).toEqual([])

    // A navigation request is not completion evidence, including while the
    // browser is still waiting for a slow download response.
    const exportPack = page.getByTitle('Export Pack', { exact: true }).first()
    const downloaded = page.waitForEvent('download')
    await exportPack.click()
    await downloaded
    const exportRequested = page.getByRole('dialog', { name: 'Download Requested', exact: true })
    await expect(exportRequested).toBeVisible()
    await expect(exportRequested).toContainText("Check your browser's downloads for status or errors.")
    await expect(exportRequested).not.toContainText('Export Complete')
    await expect(exportRequested).not.toContainText('has been downloaded')
    await page.keyboard.press('Escape')
    await expect(exportRequested).toBeHidden()
    await expect(exportPack).toBeFocused()

    await page.locator('.tabs .tab').nth(1).click()
    await page.locator('input[name="monster"]').check()
    const exporting = page.getByRole('button', { name: 'Export Selected to New Pack', exact: true })
    await exporting.click()
    const exportDialog = page.getByRole('dialog', { name: 'Export Monsters to New Pack' })
    await expect(exportDialog).toBeVisible()
    await exportDialog.getByLabel('Pack Name (Internal ID)').fill('discard_me')
    await page.keyboard.press('Escape')
    await expect(exportDialog).toBeHidden()
    await expect(page.locator('#export-pack-name')).toHaveValue('')
    await expect(exporting).toBeFocused()

    const generate = page.locator('button[onclick="startGeneration()"]')
    await generate.click()
    const generating = page.getByRole('dialog', { name: 'Confirm Image Generation' })
    await expect(generating).toBeVisible()
    await expect(generating.getByRole('button', { name: 'Cancel', exact: true })).toHaveCSS('background-color', 'rgb(12, 17, 17)')
    await expect(generating.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
    await page.screenshot({ path: info.outputPath('generation-keyboard.png') })
    // Exercise the real existing media opener on top of a confirmation, without
    // loading private artwork or invoking generation. This is a synthetic nested
    // presentation sequence, not a backend operation.
    await page.evaluate(() => {
      const app = window as unknown as { showNpcMediaPopup: (event: { currentTarget: HTMLElement }) => void }
      const item = document.createElement('div'); item.className = 'npc-item'
      item.innerHTML = '<label class="monster-label"><span>Review Guide</span></label><div class="npc-thumbnail-preview"></div>'
      const thumb = item.lastElementChild as HTMLElement
      app.showNpcMediaPopup({ currentTarget: thumb })
    })
    const media = page.getByRole('dialog', { name: 'Review Guide', exact: true })
    await expect(media).toBeVisible()
    await expect(media.getByRole('button', { name: 'Close media' })).toBeFocused()
    await expect(generating).toHaveAttribute('inert', '')
    await page.keyboard.press('Escape')
    await expect(media).toBeHidden()
    await expect(generating).toBeVisible()
    await expect(generating.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(generating).toBeHidden()
    await expect(generate).toBeFocused()
    expect(await page.evaluate(() => 'generationSettings' in window)).toBe(false)

    await page.locator('.tabs .tab').nth(2).click()
    await page.locator('#npcModuleSelect').selectOption('review_module')
    await page.locator('input[name="npc-select"]').check()
    await page.locator('#npcStyleSelect').selectOption('photorealistic')
    await page.locator('#npcStylePromptBox').fill('Existing photorealistic treatment')
    const npcGenerate = page.locator('button[onclick="startNpcGeneration()"]')
    await npcGenerate.click()
    const npcDialog = page.getByRole('dialog', { name: 'Confirm Portrait Generation' })
    await expect(npcDialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(npcDialog).toBeHidden()
    await expect(npcGenerate).toBeFocused()
    expect(await page.evaluate(() => 'npcGenerationSettings' in window)).toBe(false)

    await page.locator('.tabs .tab').nth(5).click()
    await page.locator('#media-gen-module-select').selectOption('review_module')
    await page.locator('#scan-module-btn').click()
    await page.locator('.asset-checkbox').check()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (width === 390) {
      const table = page.getByRole('region', { name: 'Module assets (scroll horizontally for all columns)' })
      await table.focus()
      await table.press('ArrowRight')
      await expect.poll(() => table.evaluate(node => node.scrollLeft)).toBeGreaterThan(0)
      await table.press('ArrowLeft')
    }
    await page.locator('#generate-assets-btn').click()
    const assetsDialog = page.getByRole('dialog', { name: 'Module Media Generation Plan' })
    await expect(assetsDialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(assetsDialog).toBeHidden()
    await expect(page.locator('#generate-assets-btn')).toBeFocused()
    expect(await page.evaluate(() => Boolean((window as unknown as { pendingMediaGeneration?: unknown }).pendingMediaGeneration))).toBe(false)
    const beforeFailureRevision = await page.evaluate(() => localStorage.getItem('neq_media_revision'))
    await page.evaluate(() => {
      const listeners = (window as unknown as { __workbenchListeners: Map<string, (data: unknown) => void> }).__workbenchListeners
      document.getElementById('generation-progress-container')!.style.display = 'block'
      document.getElementById('generate-assets-btn')!.style.display = 'none'
      listeners.get('unified_generation_progress')!({ percent: 37, message: 'Processing synthetic fixture' })
      listeners.get('unified_generation_complete')!({ success: false, error: 'Synthetic provider failure' })
    })
    await expect(page.locator('#media-gen-status-message')).toHaveText('Generation Failed - See log for details')
    await expect(page.locator('#media-gen-progress-text')).toHaveText('37%')
    await expect(page.locator('.asset-checkbox')).toBeChecked()
    await expect(page.locator('#generate-assets-btn')).toBeVisible()
    await expect(page.locator('#generate-assets-btn')).toBeEnabled()
    expect(await page.evaluate(() => localStorage.getItem('neq_media_revision'))).toBe(beforeFailureRevision)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const toastBounds = await page.locator('#ember-notifications').evaluate(node => {
      const rect = node.getBoundingClientRect()
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: innerWidth, height: innerHeight }
    })
    expect(toastBounds.left).toBeGreaterThanOrEqual(0)
    expect(toastBounds.right).toBeLessThanOrEqual(toastBounds.width)
    expect(toastBounds.top).toBeGreaterThanOrEqual(0)
    expect(toastBounds.bottom).toBeLessThanOrEqual(toastBounds.height)
    await page.screenshot({ path: info.outputPath('generation-failure.png'), fullPage: true })
    // A refreshed list can remove an opener while the dialog is still visible.
    await page.locator('#generate-assets-btn').click()
    await expect(assetsDialog).toBeVisible()
    await page.locator('#generate-assets-btn').evaluate(node => node.remove())
    await page.keyboard.press('Escape')
    await expect(assetsDialog).toBeHidden()
    await expect(page.locator('.tabs .tab.active')).toBeFocused()
    expect(await page.locator('body').evaluate(node => node.style.overflow)).toBe('')
    // HTTP failures use the existing navigation behavior: the server error page
    // replaces the workbench. It must not contain a fabricated completion.
    await page.locator('.tabs .tab').first().click()
    exportStatus = 500
    const failedResponse = page.waitForResponse(response => response.url().endsWith('/export'))
    await exportPack.click()
    expect((await failedResponse).status()).toBe(500)
    await expect(page.locator('body')).toContainText('Export failed: synthetic server failure.')
    await expect(page.locator('body')).not.toContainText('Export Complete')
    await expect(page.locator('body')).not.toContainText('has been downloaded')
    expect(writes).toEqual([])
    expect(errors).toEqual([])
  })
}
