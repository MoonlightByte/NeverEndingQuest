/**
 * Inventory tab (plan Task 4.4d): currency three-coin grid under a Cinzel
 * header, plus the equipment list with a sort dropdown and a text filter.
 * Renders player_data_response{inventory} (full character file) from the
 * player store; field names ported from the legacy displayInventory renderer.
 */
import { useMemo, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, usePlayer } from '../../stores'
import {
  equipmentList,
  filterEquipment,
  sortEquipment,
  type InventorySort,
} from './characterData'

const SORT_OPTIONS: ReadonlyArray<{ value: InventorySort; label: string }> = [
  { value: 'name-asc', label: 'Sort: Name A-Z' },
  { value: 'name-desc', label: 'Sort: Name Z-A' },
  { value: 'type', label: 'Sort: Type' },
  { value: 'quantity', label: 'Sort: Quantity' },
]

export function InventoryTab() {
  const inventory = usePlayer((s) => s.inventory)
  const error = usePlayer((s) => s.dataErrors.inventory)
  const [sort, setSort] = useState<InventorySort>('name-asc')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)

  const items = useMemo(() => (inventory ? equipmentList(inventory) : []), [inventory])
  const visible = useMemo(() => {
    const searched = filterEquipment(items, query)
    const filtered = searched.filter((item) => {
      if (category === 'weapon') return item.type.toLowerCase().includes('weapon')
      if (category === 'armor') return item.type.toLowerCase().includes('armor')
      if (category === 'consumable') return /consumable|potion|scroll/.test(`${item.type} ${item.subtype}`.toLowerCase())
      if (category === 'magical') return item.magical
      if (category === 'equipped') return item.equipped
      return true
    })
    return sortEquipment(filtered, sort)
  }, [items, query, category, sort])

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (!inventory) {
    return <p className="p-4 font-body text-sm text-secondary">Loading inventory...</p>
  }

  const openStorage = () => {
    emitC('request_storage_data', undefined)
    useDialogs.getState().openDialog('storage')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-[10px] bg-page p-[10px] font-body">
      <button
        type="button"
        onClick={openStorage}
        className="shrink-0 rounded border-0 bg-[#4caf50] px-3 py-2 font-chrome text-sm font-bold text-white hover:bg-[#45a049]"
      >
        View Player Storage
      </button>

      <div className="flex shrink-0 items-center gap-3 rounded border border-card bg-panel p-2">
        <button type="button" onClick={() => setSearchOpen(true)} className="rounded border border-soft bg-[#444] px-3 py-1.5 font-chrome text-xs text-primary">Search</button>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as InventorySort)}
          aria-label="Sort inventory"
          className="min-w-0 flex-1 rounded border border-soft bg-panel px-2 py-1.5 font-chrome text-xs text-primary"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter inventory" className="min-w-0 flex-1 rounded border border-soft bg-panel px-2 py-1.5 font-chrome text-xs text-primary">
          <option value="">Filter</option><option value="weapon">Weapons</option><option value="armor">Armor</option><option value="consumable">Consumables</option><option value="magical">Magical</option><option value="equipped">Equipped</option>
        </select>
        <button type="button" onClick={() => { setQuery(''); setCategory(''); setSort('name-asc') }} className="rounded border border-soft bg-[#444] px-3 py-1.5 font-chrome text-xs text-primary">Clear</button>
      </div>

      {/* equipment list */}
      <section className="flex min-h-0 flex-1 flex-col rounded border border-card bg-panel p-2">
        <div className="flex shrink-0 items-baseline justify-between">
          <h4 className="font-display text-xs text-accent">Equipment</h4>
        </div>
        <div className="mt-1 min-h-0 flex-1 overflow-y-auto">
          {visible.length === 0 ? (
            <p className="text-sm text-secondary">
              {items.length === 0 ? 'No equipment' : 'No items match the filter'}
            </p>
          ) : (
            visible.map((item, i) => (
              <div
                key={`${item.name}-${i}`}
                className="group relative border-b border-card/60 py-1 text-sm last:border-b-0"
              >
                <span className="text-accent">{'\u25CF'} </span>
                <span className={item.equipped ? 'text-primary' : 'text-secondary'}>
                  {item.name}
                  {item.quantity > 1 ? ` \u00D7${item.quantity}` : ''}
                </span>
                <span className="text-secondary"> ({item.type.toLowerCase()})</span>
                {item.magical && <span className="text-emerald-1"> *</span>}
                {item.description !== '' && (
                  <div className="pointer-events-none absolute left-2 top-full z-20 hidden w-64 rounded border-2 border-card bg-panel p-2 shadow-lg group-hover:block">
                    <div className="font-display text-xs text-accent">{item.name}</div>
                    <div className="mt-1 text-xs text-secondary">{item.description}</div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </section>
      {searchOpen && <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70" onClick={() => setSearchOpen(false)}><div role="dialog" aria-label="Search Inventory" className="w-[500px] rounded border-2 border-card bg-panel p-3" onClick={(event) => event.stopPropagation()}><div className="mb-3 flex items-center justify-between"><h3 className="font-display text-lg text-accent">Search Inventory</h3><button type="button" aria-label="Close" onClick={() => setSearchOpen(false)} className="text-xl text-secondary">×</button></div><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') setSearchOpen(false) }} placeholder="Search items..." className="w-full rounded border border-card bg-page px-3 py-2 text-primary outline-none focus:border-accent" /></div></div>}
    </div>
  )
}
