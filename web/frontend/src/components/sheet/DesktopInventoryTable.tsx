import { EmberInspection } from './EmberInspection'
import { EquipmentDetails } from './EquipmentDetails'
import { SpellDetails } from './spellDetails'
import { spellKey } from './spellKey'
import { useSpellReference } from './useSpellReference'
import type { EquipmentItem } from './characterData'
import '../../theme/tavern-inventory-spells.css'

export function DesktopInventoryTable({ items, empty = 'No items in inventory.' }: { items: EquipmentItem[]; empty?: string }) {
  const reference = useSpellReference()
  if (!items.length) return <p role="status">{empty}</p>
  return <div className="tis-inventory-table-wrap"><table className="tis-inventory-table" aria-label="Inventory items">
    <thead><tr><th scope="col">Item</th><th scope="col">Type</th><th scope="col">Qty</th><th scope="col">Status</th><th scope="col">Charges</th></tr></thead>
    <tbody>{items.map((item, index) => <tr key={`${item.name}-${index}`}>
      <td><EmberInspection label={item.name}><EquipmentDetails item={item} />{(item.subtype.toLowerCase() === 'scroll' || /scroll/i.test(item.type)) && <SpellDetails detail={reference.data[spellKey(item.name.replace(/^scroll\s+(of\s+)?/i, ''))]} fallbackName={item.name} />}</EmberInspection>{item.description && <span className="tis-item-description">{item.description}</span>}</td>
      <td>{item.type}</td><td className="tis-quantity">×{item.quantity}</td><td><span className={item.equipped ? 'tis-equipped' : 'tis-carried'}>{item.equipped ? 'Equipped' : 'Carried'}</span></td><td className="tis-charges">{item.charges ? `${item.charges.current}/${item.charges.max}` : '—'}</td>
    </tr>)}</tbody>
  </table></div>
}
