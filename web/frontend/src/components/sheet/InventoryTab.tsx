/**
 * Inventory tab (plan Task 4.4d): currency three-coin grid under a Cinzel
 * header, plus the equipment list with a sort dropdown and a text filter.
 * Renders player_data_response{inventory} (full character file) from the
 * player store; field names ported from the legacy displayInventory renderer.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, usePlayer } from '../../stores'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberInspection } from './EmberInspection'
import { EquipmentDetails } from './EquipmentDetails'
import { EmberCurrency } from './EmberCurrency'
import { useInventoryView } from './InventoryViewState'
import { useSpellReference } from './useSpellReference'
import { SpellDetails } from './spellDetails'
import { spellKey } from './spellKey'
import { useModalLayer } from '../dialogs/useModalLayer'
import '../dialogs/dialog-parity.css'
import {
  equipmentList,
  currencyOf,
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

function InventorySearch({ query, onQuery, onClose }: { query: string; onQuery: (query: string) => void; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null)
  useModalLayer(panel, onClose)
  return <div className="neq-search-overlay-parity" onClick={onClose}>
    <div ref={panel} role="dialog" aria-modal="true" aria-label="Search Inventory" tabIndex={-1} className="neq-search-popup-parity" onClick={event => event.stopPropagation()}>
      <div className="neq-search-header-parity"><h3 className="neq-search-title-parity">Search Inventory</h3><button type="button" aria-label="Close" onClick={onClose} className="neq-search-close-parity">×</button></div>
      <input value={query} onChange={event => onQuery(event.target.value)} placeholder="Search items..." aria-label="Search items" className="neq-search-input-parity" />
    </div>
  </div>
}

export function InventoryTab() {
  const ember = useEmberDesktop()
  const inventory = usePlayer((s) => s.inventory)
  const error = usePlayer((s) => s.dataErrors.inventory)
  const notice = usePlayer((s) => s.dataNotices.inventory)
  const { view, setView } = useInventoryView()
  const { sort, sortTouched, query, category } = view
  const setSort = (sort: InventorySort) => setView(previous => ({ ...previous, sort }))
  const setSortTouched = (sortTouched: boolean) => setView(previous => ({ ...previous, sortTouched }))
  const setQuery = (query: string) => setView(previous => ({ ...previous, query }))
  const setCategory = (category: string) => setView(previous => ({ ...previous, category }))
  const section = useRef<HTMLElement>(null)
  const { data: reference } = useSpellReference()
  useLayoutEffect(() => { if (section.current) section.current.scrollTop = view.scrollTop }, [inventory, view.scrollTop])
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
  if (notice) {
    return <p className="p-4 font-body text-sm text-secondary">{notice}</p>
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
      <section ref={section} className="neq-equipment-section" onScroll={event => { const scrollTop = event.currentTarget.scrollTop; setView(previous => ({ ...previous, scrollTop })) }}>
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
                <span className="neq-item-name">{ember ? <EmberInspection label={`${item.name}${item.quantity > 1 ? ` ×${item.quantity}` : ''}`}><EquipmentDetails item={item} />{(item.subtype === 'scroll' || /scroll/i.test(item.type)) && <SpellDetails detail={reference[spellKey(item.name.replace(/^scroll\s+(of\s+)?/i, ''))]} fallbackName={item.name} />}</EmberInspection> : `${item.name}${item.quantity > 1 ? ` ×${item.quantity}` : ''}`}</span>
                <span className="neq-item-type">{` (${item.type.toLowerCase()})`}</span>
                {ember && item.equipped && <span className="neq-item-type"> · Equipped</span>}
                {!ember && item.description !== '' && (
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
      {ember && <EmberCurrency currency={currencyOf(inventory)} />}
      {searchOpen && <InventorySearch query={query} onQuery={setQuery} onClose={() => setSearchOpen(false)} />}
    </div>
  )
}
