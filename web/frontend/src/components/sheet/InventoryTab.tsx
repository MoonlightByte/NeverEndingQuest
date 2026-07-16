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
  currencyOf,
  equipmentList,
  filterEquipment,
  sortEquipment,
  type InventorySort,
} from './characterData'

const COINS = [
  { key: 'gold', label: 'GP', color: '#FFD700' },
  { key: 'silver', label: 'SP', color: '#C0C0C0' },
  { key: 'copper', label: 'CP', color: '#B87333' },
] as const

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

  const items = useMemo(() => (inventory ? equipmentList(inventory) : []), [inventory])
  const visible = useMemo(
    () => sortEquipment(filterEquipment(items, query), sort),
    [items, query, sort],
  )

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (!inventory) {
    return <p className="p-4 font-body text-sm text-secondary">Loading inventory...</p>
  }

  const currency = currencyOf(inventory)

  const openStorage = () => {
    emitC('request_storage_data', undefined)
    useDialogs.getState().openDialog('storage')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-3 font-body">
      {/* currency grid */}
      <section className="shrink-0">
        <h3 className="font-display text-sm tracking-wide text-accent">Currency</h3>
        <div className="mt-1 grid grid-cols-3 gap-2">
          {COINS.map((coin) => (
            <div
              key={coin.key}
              className="rounded border-2 border-card bg-page p-2 text-center"
            >
              <div className="text-base text-primary">{currency[coin.key]}</div>
              <div className="font-display text-[10px]" style={{ color: coin.color }}>
                {coin.label}
              </div>
            </div>
          ))}
        </div>
      </section>

      <button
        type="button"
        onClick={openStorage}
        className="shrink-0 rounded border-2 border-card bg-page px-3 py-1.5 font-chrome text-xs text-accent hover:border-accent"
      >
        View Player Storage
      </button>

      {/* sort + text filter controls */}
      <div className="flex shrink-0 items-center gap-2">
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as InventorySort)}
          aria-label="Sort inventory"
          className="min-w-0 flex-1 rounded border-2 border-card bg-page px-2 py-1 font-chrome text-xs text-primary outline-none focus:border-accent"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter items..."
          aria-label="Filter inventory"
          className="min-w-0 flex-1 rounded border-2 border-card bg-page px-2 py-1 font-chrome text-xs text-primary outline-none focus:border-accent"
        />
      </div>

      {/* equipment list */}
      <section className="flex min-h-0 flex-1 flex-col rounded border-2 border-card bg-page p-2">
        <div className="flex shrink-0 items-baseline justify-between">
          <h4 className="font-display text-xs text-accent">Equipment</h4>
          <span className="font-chrome text-[10px] text-secondary">
            {visible.length} / {items.length} items
          </span>
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
    </div>
  )
}
