import { useState } from 'react'
import { DesktopInventoryTable } from './DesktopInventoryTable'
import { equipmentList, filterEquipment, sortEquipment, type InventorySort } from './characterData'

export function NpcInventoryPanel({ npc }: { npc: Record<string, unknown> }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<InventorySort>('name-asc')
  const items = equipmentList(npc)
  const categories = [...new Set(items.map(item => item.type))].sort()
  const visible = sortEquipment(filterEquipment(items, query).filter(item => category === 'equipped' ? item.equipped : !category || item.type === category), sort)
  return <section className="tis-inventory" aria-label="NPC inventory">
    <div className="tis-inventory-toolbar">
      <input aria-label="Search NPC inventory" placeholder="Find an item…" value={query} onChange={event => setQuery(event.target.value)} />
      <select aria-label="Filter NPC inventory" value={category} onChange={event => setCategory(event.target.value)}><option value="">All items</option><option value="equipped">Equipped</option>{categories.map(type => <option key={type} value={type}>{type}</option>)}</select>
      <select aria-label="Sort NPC inventory" value={sort} onChange={event => setSort(event.target.value as InventorySort)}><option value="name-asc">Name A–Z</option><option value="type">Type</option><option value="quantity">Quantity</option></select>
      <span className="tis-item-count">{visible.length} / {items.length} entries</span>
    </div>
    <DesktopInventoryTable items={visible} empty={items.length ? 'No items match the filter.' : 'No items in inventory.'} />
  </section>
}
