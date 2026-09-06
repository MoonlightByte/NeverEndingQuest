import { expect, test, type WebSocketRoute } from '@playwright/test'

test.skip(process.env.NEQ_E2E_REAL_RUNTIME !== '1', 'Requires disposable Flask runtime')
test.beforeEach(async ({page,request}) => {
  await request.post('/__parity__/scenario/exploration')
  await page.setViewportSize({width:1586,height:992})
  await page.goto('/play/')
  await expect(page.locator('.neq-character-name')).toHaveText('Arden Vale')
})

test('all seven full NPC detail surfaces retain information and nested spell focus', async ({page}, info) => {
  await page.getByRole('tab',{name:'NPCs',exact:true}).click()
  const sheet = page.locator('.neq-npc-character-sheet').filter({has:page.getByRole('heading',{name:'Mira Thorne',exact:true})})
  await expect(sheet).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({path:info.outputPath('npc-sheet.png')})
  for (const [action,title,content] of [
    ['Saving Throw','Saving Throws','Wisdom'],['Skills','Skills','Nature'],['Inventory','Inventory','Longbow'],
    ['Key Abilities','Key Abilities','Mark a foe.'],['Racial Traits','Racial Traits','Adaptable training.'],
    ['Background','Background','Excellent memory for maps.'],['Spells','Spellcasting','Goodberry'],
  ]) {
    const trigger = sheet.getByRole('button',{name:action,exact:true})
    await trigger.click()
    const dialog = page.getByRole('dialog',{name:`Mira Thorne's ${title}`,exact:true})
    await expect(dialog).toContainText(content)
    if(action === 'Inventory') {
      await dialog.getByRole('button',{name:'Scroll of Goodberry',exact:true}).click()
      const scroll = page.getByRole('dialog',{name:'Scroll of Goodberry details'})
      await expect(scroll).toContainText('Materials')
      await page.keyboard.press('Escape')
      await expect(scroll).toHaveCount(0)
    }
    if(action === 'Spells') {
      await expect(dialog).toContainText('Prepared')
      const spell = dialog.getByRole('button',{name:'Goodberry',exact:true})
      await spell.click()
      const inspection = page.getByRole('dialog',{name:'Goodberry details'})
      await expect(inspection).toContainText('Materials')
      await expect(inspection.getByRole('button',{name:'Close Goodberry details'})).toBeFocused()
      await page.screenshot({path:info.outputPath('npc-spell-inspection.png')})
      await page.keyboard.press('Escape')
      await expect(inspection).toHaveCount(0)
      await expect(dialog).toBeVisible()
      await expect(spell).toBeFocused()
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(trigger).toBeFocused()
  }
})

test('party details open the full NPC card through the keyboard', async ({page}) => {
  const trigger = page.locator('.ember-people').getByRole('button',{name:'Mira Thorne full character details',exact:true})
  await trigger.focus()
  await trigger.press('Enter')
  const inspection = page.getByRole('dialog',{name:'Mira Thorne — Character'})
  await expect(inspection).toContainText('HP')
  await expect(inspection.getByRole('button',{name:'Inventory',exact:true})).toBeVisible()
  await expect(inspection.getByRole('button',{name:'Close',exact:true})).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(inspection).toHaveCount(0)
  await expect(trigger).toBeFocused()
})

test('open NPC inventory receives updated quantities through the actual socket listener', async ({page}) => {
  let client: WebSocketRoute | undefined
  let latest: Record<string, unknown> | undefined
  await page.routeWebSocket('**/socket.io/**', socket => {
    client = socket
    const server=socket.connectToServer()
    server.onMessage(message => {
      if(typeof message === 'string' && message.startsWith('42')) {
        try { const [event,payload]=JSON.parse(message.slice(2)); if(event === 'player_data_response' && payload.dataType === 'npcs') latest=payload } catch { /* Engine.IO non-event frame */ }
      }
      socket.send(message)
    })
  })
  await page.reload()
  await page.getByRole('tab',{name:'NPCs',exact:true}).click()
  const sheet=page.locator('.neq-npc-character-sheet').filter({has:page.getByRole('heading',{name:'Mira Thorne',exact:true})})
  await sheet.getByRole('button',{name:'Inventory',exact:true}).click()
  const dialog=page.getByRole('dialog',{name:"Mira Thorne's Inventory",exact:true})
  await expect.poll(() => Boolean(latest)).toBe(true)
  const packet=structuredClone(latest!)
  const npcs=packet.data as Array<Record<string,unknown>>
  const npc=npcs.find(entry => entry.name === 'Mira Thorne')!
  const equipment=npc.equipment as Array<Record<string,unknown>>
  equipment.find(entry => entry.item_name === 'Longbow')!.quantity=9
  packet.revision=Number(packet.revision ?? 0)+1
  client!.send(`42${JSON.stringify(['player_data_response',packet])}`)
  await expect(dialog.locator('.neq-npc-inventory-item').filter({has:page.getByRole('button',{name:'Longbow',exact:true})})).toContainText('x9')
  await expect(dialog.getByRole('button',{name:'Close',exact:true})).toBeFocused()
  await dialog.getByRole('button',{name:'Close',exact:true}).click()
  await sheet.getByRole('button',{name:'Key Abilities',exact:true}).click()
  const features=page.getByRole('dialog',{name:"Mira Thorne's Key Abilities",exact:true})
  const feature=(npc.classFeatures as Array<Record<string,unknown>>)[0]
  ;(feature.usage as Record<string,unknown>).current=0
  packet.revision=Number(packet.revision)+1
  client!.send(`42${JSON.stringify(['player_data_response',packet])}`)
  await expect(features).toContainText('0/3')
  await features.getByRole('button',{name:'Close',exact:true}).click()
  await sheet.getByRole('button',{name:'Spells',exact:true}).click()
  const spells=page.getByRole('dialog',{name:"Mira Thorne's Spellcasting",exact:true})
  const casting=npc.spellcasting as Record<string,unknown>
  const slots=casting.spellSlots as Record<string,Record<string,unknown>>
  slots.level1.current=1
  packet.revision=Number(packet.revision)+1
  client!.send(`42${JSON.stringify(['player_data_response',packet])}`)
  await expect(spells).toContainText('1/3 slots')
})

test('existing NPC portrait opens a bounded media viewer with visible close and failure recovery', async ({page,request},info) => {
  await request.post('/__parity__/scenario/media-image')
  await page.reload()
  const chip=page.locator('.ember-people').getByRole('button',{name:'Eirik Hearthwise',exact:true})
  await expect(chip).toBeVisible()
  await chip.click()
  const dialog=page.getByRole('dialog',{name:'Character media',exact:true})
  await expect(dialog).toBeVisible({timeout:20000})
  await expect(dialog.getByRole('button',{name:'Close',exact:true})).toBeVisible()
  await page.screenshot({path:info.outputPath('npc-media.png')})
  await page.setViewportSize({width:1024,height:768})
  const media=dialog.locator('img,video')
  const box=await media.boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y+box!.height).toBeLessThanOrEqual(768)
  await media.evaluate(element => element.dispatchEvent(new Event('error')))
  if (await dialog.locator('img').count()) await dialog.locator('img').evaluate(element => element.dispatchEvent(new Event('error')))
  await expect(dialog.getByRole('status')).toContainText('could not be loaded')
  await dialog.getByRole('button',{name:'Close',exact:true}).click()
  await expect(dialog).toHaveCount(0)
})
