import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'
import type { InventorySort } from './characterData'
import { useSession } from '../../stores'

interface View { sort: InventorySort; sortTouched: boolean; query: string; category: string; scrollTop: number }
const initial: View = { sort: 'name-asc', sortTouched: false, query: '', category: '', scrollTop: 0 }
const Context = createContext<{ view: View; setView: Dispatch<SetStateAction<View>> } | null>(null)
export function InventoryViewProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState(initial)
  const instance = useSession(state => state.serverInstanceId)
  const previous = useRef(instance)
  useEffect(() => {
    if (instance && previous.current && previous.current !== instance) setView(initial)
    if (instance) previous.current = instance
  }, [instance])
  return <Context value={{ view, setView }}>{children}</Context>
}
export function useInventoryView() {
  const shared = useContext(Context)
  const [view, setView] = useState(initial)
  return shared ?? { view, setView }
}
