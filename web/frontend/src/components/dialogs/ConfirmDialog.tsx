import { useRef } from 'react'
import { createPortal } from 'react-dom'
import { DialogShell, dialogButtonDanger, dialogButtonSecondary } from './DialogShell'

/** Public action confirmation. Cancellation is the initial, safe keyboard action. */
export function ConfirmDialog({ title, message, confirmLabel, onCancel, onConfirm, pending = false, disabled = false, error }: {
  title: string; message: string; confirmLabel: string; onCancel: () => void
  onConfirm: () => void; pending?: boolean; disabled?: boolean; error?: string
}) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  return createPortal(
    <DialogShell title={title} onClose={onCancel} initialFocusRef={cancelRef}>
      <p>{message}</p>
      {pending && <p role="status">Preparing server restart...</p>}
      {error && <p role="alert">{error}</p>}
      <div className="neq-dialog-buttons-parity">
        <button ref={cancelRef} type="button" className={dialogButtonSecondary} onClick={onCancel}>Cancel</button>
        <button type="button" className={dialogButtonDanger} disabled={pending || disabled} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </DialogShell>, document.body,
  )
}
