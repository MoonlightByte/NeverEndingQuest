/**
 * Inventory tab (plan Task 4.4d): currency three-coin grid under a Cinzel
 * header, plus the equipment list with a sort dropdown and a text filter.
 * Renders player_data_response{inventory} (full character file) from the
 * player store; field names ported from the legacy displayInventory renderer.
 */
import { useMemo, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, usePlayer } from '../../stores'
import '../dialogs/dialog-parity.css'
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
  const [sortTouched, setSortTouched] = useState(false)
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
    return sortTouched ? sortEquipment(filtered, sort) : filtered
  }, [items, query, category, sort, sortTouched])

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
    <div className="neq-inventory-tab">
      <button
        type="button"
        onClick={openStorage}
        className="neq-storage-view-button"
      >
        View Player Storage
      </button>

      <div className="neq-inventory-controls">
        <button type="button" onClick={() => setSearchOpen(true)} className="neq-inventory-control">Search</button>
        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value as InventorySort); setSortTouched(true) }}
          aria-label="Sort inventory"
          className="neq-inventory-control neq-inventory-sort"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter inventory" className="neq-inventory-control neq-filter-dropdown">
          <option value="">Filter</option><option value="weapon">Weapons</option><option value="armor">Armor</option><option value="consumable">Consumables</option><option value="magical">Magical</option><option value="equipped">Equipped</option>
        </select>
        <button type="button" onClick={() => { setQuery(''); setCategory(''); setSort('name-asc'); setSortTouched(false) }} className="neq-inventory-control">Clear</button>
      </div>

      {/* equipment list */}
      <section className="neq-equipment-section">
        <h4>Equipment</h4>
        <div>
          {visible.length === 0 ? (
            <div className="neq-inventory-item"><span className="neq-feature-bullet">●</span><span className="neq-item-name">{items.length === 0 ? 'No equipment' : 'No items match the filter'}</span></div>
          ) : (
            visible.map((item, i) => (
              <div
                key={`${item.name}-${i}`}
                className="neq-inventory-item group relative"
              >
                <span className="neq-feature-bullet">{'\u25CF'}</span>
                <span className="neq-item-name">{`${item.name}${item.quantity > 1 ? ` \u00D7${item.quantity}` : ''}`}</span>
                <span className="neq-item-type">{` (${item.type.toLowerCase()})`}</span>
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
      {searchOpen && <div className="neq-search-overlay-parity" onClick={() => setSearchOpen(false)}><div role="dialog" aria-label="Search Inventory" className="neq-search-popup-parity" onClick={(event) => event.stopPropagation()}><div className="neq-search-header-parity"><h3 className="neq-search-title-parity">Search Inventory</h3><button type="button" aria-label="Close" onClick={() => setSearchOpen(false)} className="neq-search-close-parity">×</button></div><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') setSearchOpen(false) }} placeholder="Search items..." className="neq-search-input-parity" /></div></div>}
    </div>
  )
}
