import { emitC } from '../../services/socket'
import { useDialogs, useSession } from '../../stores'

/** #1399 G2: run the New game or Load the player pressed before the key was saved. */
export function resumeGatedAction(): void {
  const dialogs = useDialogs.getState()
  const action = dialogs.keyGate
  dialogs.setKeyGate(null)
  dialogs.closeDialog()
  if (action === 'load') {
    dialogs.openDialog('load')
  } else if (action === 'start') {
    useSession.getState().startRequested()
    emitC('start_game', undefined)
  }
}
