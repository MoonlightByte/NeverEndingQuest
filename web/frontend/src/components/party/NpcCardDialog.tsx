import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { DialogShell } from '../dialogs/DialogShell'
import { NpcsTab } from '../sheet/NpcsTab'
import { emitC } from '../../services/socket'
import '../../theme/tavern-npc-review.css'
import '../../theme/tavern-player-review.css'

/** Same live character card and nested menus as the NPC tab, not a summary copy. */
export function NpcCardDialog({ name, onClose }: { name: string; onClose: () => void }) {
  useEffect(() => { emitC('request_player_data', { dataType: 'npcs' }) }, [name])
  return createPortal(<DialogShell title={`${name.replace(/_/g, ' ')} — Character`} onClose={onClose} maxWidth="1060px" className="ember-npc-full-card ember-sheet-fixed-frame ember-npc-tabbed-card">
    <NpcsTab npcName={name} />
  </DialogShell>, document.body)
}
