const CHARACTER_SHEET_TABS = [{ id: 'character', label: 'Character sheet' }, { id: 'inventory', label: 'Inventory' }, { id: 'spells', label: 'Spells & magic' }] as const
export type CharacterSheetTab = typeof CHARACTER_SHEET_TABS[number]['id']

export function CharacterSheetTabs({ id, active, onChange, label }: { id: string; active: CharacterSheetTab; onChange: (tab: CharacterSheetTab) => void; label: string }) {
  return <div className="tps-tabs" role="tablist" aria-label={label} onKeyDown={event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
    const index = tabs.indexOf(event.target as HTMLButtonElement)
    if (index < 0) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
    tabs[next]?.focus(); tabs[next]?.click()
  }}>
    {CHARACTER_SHEET_TABS.map(tab => <button key={tab.id} type="button" role="tab" id={`${id}-${tab.id}`} aria-controls={`${id}-panel`} aria-selected={active === tab.id} tabIndex={active === tab.id ? 0 : -1} onClick={() => onChange(tab.id)}>{tab.label}</button>)}
  </div>
}
