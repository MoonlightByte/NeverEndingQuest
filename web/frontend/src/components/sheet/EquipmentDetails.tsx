import type { EquipmentItem } from './characterData'

export function EquipmentDetails({ item }: { item: EquipmentItem }) {
  return <><dl>
    <dt>Type</dt><dd>{item.type}</dd>
    {item.subtype && <><dt>Subtype</dt><dd>{item.subtype}</dd></>}
    {item.spellLevel !== null && <><dt>Spell level</dt><dd>{item.spellLevel === 0 ? 'Cantrip' : item.spellLevel}</dd></>}
    <dt>Quantity</dt><dd>{item.quantity}</dd>
    {item.equipped && <><dt>Equipment</dt><dd>Equipped</dd></>}
    {item.magical && <><dt>Magic</dt><dd>Magical item</dd></>}
    {item.consumable && <><dt>Use</dt><dd>Consumable</dd></>}
    {item.charges && <><dt>Charges</dt><dd>{item.charges.current} / {item.charges.max}</dd></>}
  </dl><p>{item.description || 'No description available.'}</p></>
}
