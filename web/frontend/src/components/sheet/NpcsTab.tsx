/**
 * NPCs tab (plan Task 4.4d): party NPC roster from party_data_response
 * (members with type 'npc' -- the frozen contract's request_player_data has
 * no npcs dataType, so the roster rides the party feed). Clicking a roster
 * card opens NpcDetailModal, which drives the request_npc_* events.
 */
import { useState } from 'react'
import { useWorld } from '../../stores'
import { NpcDetailModal } from './NpcDetailModal'
import { hpPercent, hpTone, num, str } from './characterData'

export function NpcsTab() {
  const party = useWorld((s) => s.party)
  const [selected, setSelected] = useState<string | null>(null)

  const npcs = party.filter((member) => str(member['type']) === 'npc')

  return (
    <div className="h-full overflow-y-auto p-3 font-body">
      <h3 className="font-display text-sm tracking-wide text-accent">Party NPCs</h3>
      {npcs.length === 0 ? (
        <p className="mt-2 text-sm italic text-secondary">No NPCs have joined the party.</p>
      ) : (
        npcs.map((npc, i) => {
          const name = str(npc['name'], 'Unknown NPC')
          const hp = num(npc['currentHp'])
          const maxHp = num(npc['maxHp'])
          const tone = hpTone(hp, maxHp)
          const hpColor =
            tone === 'low' ? '#e74c3c' : tone === 'medium' ? '#e67e22' : 'var(--accent)'
          return (
            <button
              key={`${name}-${i}`}
              type="button"
              onClick={() => setSelected(name)}
              className="mt-2 block w-full rounded border-2 border-card bg-page p-2 text-left hover:border-accent"
            >
              <div className="flex items-baseline justify-between">
                <span className="font-display text-sm text-primary">{name}</span>
                <span className="font-chrome text-xs text-secondary">
                  Level {num(npc['level'], 1)} {str(npc['class'], 'Unknown')}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded bg-panel">
                  <div
                    className="h-full rounded"
                    style={{ width: `${hpPercent(hp, maxHp)}%`, backgroundColor: hpColor }}
                  />
                </div>
                <span className="font-chrome text-xs text-secondary">
                  HP {hp}/{maxHp}
                </span>
                <span className="font-chrome text-xs text-secondary">
                  AC {num(npc['ac'], 10)}
                </span>
              </div>
            </button>
          )
        })
      )}
      {selected !== null && (
        <NpcDetailModal npcName={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
