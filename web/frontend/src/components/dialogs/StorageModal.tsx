import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'
import './dialog-parity.css'

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
  const storageError = useWorld((s) => s.storageError)

  // Refresh storage data every time the modal opens.
  useEffect(() => {
    emitC('request_storage_data', undefined)
  }, [])

  let body
  if (storageError) {
    body = <p className="p-8 text-center font-body text-secondary">No player storage found.</p>
  } else if (storage === null) {
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
        <div>
          {containers.map((container, i) => (
            <section
              key={`${container.name}-${i}`}
              aria-label={container.name}
              className="neq-storage-container-parity"
            >
              <div className="neq-storage-container-header-parity">
                <span className="neq-storage-name-parity">{container.name}</span>
                <span className="neq-storage-location-parity">{container.location}</span>
              </div>
              <ul className="neq-storage-list-parity">
                {container.contents.length === 0 ? (
                  <li className="neq-storage-item-parity">This container is empty.</li>
                ) : (
                  container.contents.map((item, j) => (
                    <li key={`${item.name}-${j}`} className="neq-storage-item-parity">
                      <span className="neq-storage-item-name-parity">{item.name}</span>{' '}
                      <span className="neq-storage-item-quantity-parity">(x{item.quantity})</span>
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
      className="neq-storage-overlay-parity"
      role="dialog"
      aria-modal="true"
      aria-labelledby="player-storage-title"
      onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog() }}
    >
      <div className="neq-storage-modal-parity">
        <div className="neq-storage-header-parity">
          <h3 id="player-storage-title" className="neq-storage-title-parity">Player Storage</h3>
          <button type="button" onClick={closeDialog} aria-label="Close" className="neq-storage-close-parity">&times;</button>
        </div>
        <div className="neq-storage-body-parity">{body}</div>
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
