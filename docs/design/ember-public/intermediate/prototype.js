// Presentation-only study: no storage, fetch, sockets, inference or game events.
const savedScroll = new Map()
const openers = new Map()
document.querySelectorAll('[data-open]').forEach(button => {
  const dialog = document.getElementById(button.dataset.open)
  button.addEventListener('click', () => {
    openers.set(dialog, button)
    button.setAttribute('aria-expanded', 'true')
    dialog.showModal()
    const scroll = dialog.querySelector('.drawer-scroll')
    scroll.scrollTop = savedScroll.get(dialog.id) ?? 0
  })
})
function closeDrawer(dialog) {
  savedScroll.set(dialog.id, dialog.querySelector('.drawer-scroll').scrollTop)
  dialog.close()
  const opener = openers.get(dialog)
  opener?.setAttribute('aria-expanded', 'false')
  if (opener?.isConnected) opener.focus({ preventScroll: true })
}
document.querySelectorAll('.drawer').forEach(dialog => {
  dialog.querySelector('.close-drawer').addEventListener('click', () => closeDrawer(dialog))
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeDrawer(dialog) })
  // Native modal inertness keeps background actions unavailable; explicit
  // wrapping also prevents Tab leaving the document for browser chrome.
  dialog.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopPropagation(); closeDrawer(dialog); return
    }
    if (event.key !== 'Tab') return
    const controls = [...dialog.querySelectorAll('button,input,textarea,select,[tabindex]')]
      .filter(node => node.tabIndex >= 0 && !node.disabled && !node.closest('[hidden]'))
    const first = controls[0]
    const last = controls.at(-1)
    if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault(); (event.shiftKey ? last : first).focus()
    }
  })
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect()
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) closeDrawer(dialog)
  })
})
document.querySelectorAll('[data-sample-action]').forEach(button => button.addEventListener('click', () => {
  const dialog = button.closest('dialog')
  if (dialog) closeDrawer(dialog)
  document.getElementById('input-status').textContent = `Layout study: ${button.dataset.sampleAction} selected. No game action, provider call or saved-data change occurred.`
}))
const sheetScroll = document.getElementById('sheet-scroll')
const tabScroll = new Map()
document.querySelectorAll('[role=tab]').forEach(tab => tab.addEventListener('click', () => {
  const previous = document.querySelector('[role=tab][aria-selected=true]')
  tabScroll.set(previous.dataset.panel, sheetScroll.scrollTop)
  document.querySelectorAll('[role=tab]').forEach(candidate => {
    const selected = candidate === tab
    candidate.setAttribute('aria-selected', String(selected))
    candidate.tabIndex = selected ? 0 : -1
    document.getElementById(candidate.getAttribute('aria-controls')).hidden = !selected
  })
  sheetScroll.scrollTop = tabScroll.get(tab.dataset.panel) ?? 0
}))
document.querySelector('[role=tablist]').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  const tabs = [...event.currentTarget.querySelectorAll('[role=tab]')]
  const current = tabs.indexOf(event.target)
  if (current < 0) return
  event.preventDefault()
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
  tabs[next].focus(); tabs[next].click()
})
document.getElementById('inventory-filter').addEventListener('input', event => {
  let visible = 0
  document.querySelectorAll('[data-item]').forEach(item => {
    item.hidden = !item.dataset.item.includes(event.target.value.trim().toLowerCase())
    if (!item.hidden) visible++
  })
  document.getElementById('empty-inventory').hidden = visible > 0
})
document.getElementById('show-art').addEventListener('change', event => {
  document.getElementById('inline-art').hidden = !event.target.checked
})
const exploration = [
  ['Arden Vale', 'Your character · Level 4 Ranger', '/art/marcus'],
  ['Ranger Elen', 'Party companion', '/art/elen'],
  ['Scout Kira', 'Party companion', '/art/kira'],
  ['Captain Merek', 'Nearby · command post', '/art/merek'],
  ['Cira', 'Nearby · command post', '/art/cira'],
  ['Rusk', 'Nearby · command post', '/art/rusk'],
]
const combat = [
  ['Goblin', 'Enemy · sample initiative 18', '/art/goblin'],
  ['Arden Vale', 'Current turn · sample initiative 16', '/art/marcus'],
  ['Ranger Elen', 'Companion · sample initiative 12', '/art/elen'],
  ['Goblin scout', 'Enemy · sample initiative 9', '/art/goblin'],
  ['Scout Kira', 'Companion · sample initiative 7', '/art/kira'],
]
function renderRoster() {
  const inCombat = document.getElementById('sample-mode').value === 'combat'
  document.getElementById('people-title').textContent = inCombat ? 'Initiative · Round 2' : 'Party & nearby'
  document.getElementById('people-rail-label').textContent = inCombat ? 'Turns' : 'Party'
  document.getElementById('people-count').textContent = inCombat ? '5 actors' : '6 people'
  document.getElementById('combat-rail').hidden = !inCombat
  document.getElementById('roster-note').textContent = inCombat ? 'Fixed sample order, not a live combat state.' : 'Your party, then people at this location.'
  const roster = document.getElementById('roster')
  roster.replaceChildren()
  const entries = inCombat ? combat : exploration
  document.querySelectorAll('.mini-portraits img').forEach((image, index) => { image.src = entries[index][2] })
  entries.forEach(([name, detail, source], index) => {
    if (!inCombat && index === 3) {
      const divider = document.createElement('div'); divider.className = 'roster-divider'; divider.textContent = 'Nearby'; roster.append(divider)
    }
    const row = document.createElement('article'); row.className = `person${inCombat && index === 1 ? ' current' : ''}`
    const image = document.createElement('img'); image.src = source; image.alt = name
    const text = document.createElement('div'); const heading = document.createElement('h3'); heading.textContent = name
    const description = document.createElement('p'); description.textContent = detail
    text.append(heading, description); row.append(image, text); roster.append(row)
  })
  savedScroll.delete('people-drawer')
}
document.getElementById('sample-mode').addEventListener('change', renderRoster)
renderRoster()
// Existing public EmberDieIcon artwork, reproduced only for this static study.
// These are visual specimens; the prototype does not roll dice.
const dicePaths = [
  'M12 2 22 8v10l-10 5L2 18V8Zm0 0L7 15l5 8 5-8ZM2 8l5 7h10l5-7M2 18l5-3m10 0 5 3',
  'm12 2 9 6v10l-9 5-9-5V8Zm0 5 6 4-2 7H8l-2-7ZM12 2v5M3 8l3 3m15-3-3 3M3 18l5 0m13 0h-5m-4 5v-5',
  'm12 2 10 11-10 10L2 13Zm0 0 3 11-3 10-3-10ZM2 13h20',
  'm12 2 10 10-10 11L2 12Zm0 0v21M2 12l10-3 10 3',
  'M4 3h16v18H4ZM8 7h.01M16 7h.01M8 12h.01M16 12h.01M8 17h.01M16 17h.01',
  'm12 2 10 20H2Zm0 0v14M2 22l10-6 10 6',
]
document.querySelectorAll('.dice-dock > div > span').forEach((specimen, index) => {
  const label = specimen.textContent.match(/D\d+/)[0]
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.35', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' }).forEach(([name, value]) => svg.setAttribute(name, value))
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); path.setAttribute('d', dicePaths[index]); svg.append(path)
  specimen.replaceChildren(svg, document.createTextNode(label))
})
document.getElementById('composer').addEventListener('submit', event => {
  event.preventDefault()
  const command = document.getElementById('command')
  if (!command.value.trim()) { command.focus(); return }
  const article = document.createElement('article'); article.className = 'player-message'
  const header = document.createElement('header'); header.textContent = 'You · local input sample'
  const text = document.createElement('p'); text.textContent = command.value
  article.append(header, text); document.getElementById('story').append(article)
  command.value = ''
  document.getElementById('input-status').textContent = 'Sample input displayed locally. No game turn was sent.'
  command.focus()
})
