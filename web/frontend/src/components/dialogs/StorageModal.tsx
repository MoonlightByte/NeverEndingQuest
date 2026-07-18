import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'

interface StorageItem {
  name: string
  quantity: number
}

interface StorageContainer {
  name: string
  location: string
  contents: StorageItem[]
}

function toContainer(raw: unknown): StorageContainer {
  const r = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const contentsRaw = Array.isArray(r['contents']) ? (r['contents'] as unknown[]) : []
  return {
    name: typeof r['name'] === 'string' ? r['name'] : 'Unknown container',
    location: typeof r['location'] === 'string' ? r['location'] : '',
    contents: contentsRaw.map((item) => {
      const ir = typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : {}
      return {
        name: typeof ir['item_name'] === 'string' ? ir['item_name'] : 'Unknown item',
        quantity: typeof ir['quantity'] === 'number' ? ir['quantity'] : 1,
      }
    }),
  }
}

function StorageModalBody() {
  const closeDialog = useDialogs((s) => s.closeDialog)
  const storage = useWorld((s) => s.storage)

  // Refresh storage data every time the modal opens.
  useEffect(() => {
    emitC('request_storage_data', undefined)
  }, [])

  let body
  if (storage === null) {
    body = <p className="p-8 text-center font-body italic text-secondary">Fetching storage data...</p>
  } else {
    const success = storage['success'] === true
    const containers = (Array.isArray(storage['storage']) ? (storage['storage'] as unknown[]) : []).map(
      toContainer,
    )
    if (!success || containers.length === 0) {
      body = <p className="p-8 text-center font-body text-secondary">No player storage found.</p>
    } else {
      body = (
        <div className="flex flex-col gap-3">
          {containers.map((container, i) => (
            <section
              key={`${container.name}-${i}`}
              aria-label={container.name}
              className="rounded border-2 border-card bg-page p-3"
            >
              <div className="flex items-baseline justify-between gap-2 border-b border-card pb-2">
                <span className="font-display text-base text-primary">{container.name}</span>
                <span className="font-chrome text-xs text-secondary">{container.location}</span>
              </div>
              <ul className="mt-2 font-body text-sm">
                {container.contents.length === 0 ? (
                  <li className="italic text-secondary">This container is empty.</li>
                ) : (
                  container.contents.map((item, j) => (
                    <li key={`${item.name}-${j}`} className="flex justify-between py-0.5">
                      <span className="text-primary">{item.name}</span>
                      <span className="font-log text-xs text-secondary">x{item.quantity}</span>
                    </li>
                  ))
                )}
              </ul>
            </section>
          ))}
        </div>
      )
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      role="dialog"
      aria-modal="true"
      aria-labelledby="player-storage-title"
      onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog() }}
    >
      <div className="flex h-[85%] max-h-[90vh] w-[80%] max-w-[90vw] flex-col rounded-lg border-2 border-[#4caf50] bg-[#2c2c2c] p-5 font-chrome">
        <div className="mb-[15px] flex items-center justify-between border-b-2 border-card pb-[10px]">
          <h3 id="player-storage-title" className="text-xl font-bold text-accent">Player Storage</h3>
          <button type="button" onClick={closeDialog} aria-label="Close" className="border-0 bg-transparent text-[28px] font-bold leading-none text-[#aaa] hover:text-white">&times;</button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{body}</div>
      </div>
    </div>
  )
}

/** Player storage modal: containers + contents from storage_data_response (plan 4.4e). */
export function StorageModal() {
  const open = useDialogs((s) => s.open)
  if (open !== 'storage') return null
  return <StorageModalBody />
}
