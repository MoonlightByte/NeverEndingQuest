// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { InventoryViewProvider, useInventoryView } from './InventoryViewState'
import { useSession } from '../../stores'

afterEach(cleanup)
function View() {
  const { view, setView } = useInventoryView()
  return <><output>{JSON.stringify(view)}</output><button onClick={() => setView({ query: 'Scroll', sort: 'quantity', sortTouched: true, category: 'consumable', scrollTop: 320 })}>Choose view</button></>
}
it('retains every inventory view field across tab unmount and resets only for a new server identity', () => {
  useSession.setState({ serverInstanceId: 'first' })
  const { rerender } = render(<InventoryViewProvider><View /></InventoryViewProvider>)
  fireEvent.click(screen.getByText('Choose view'))
  const chosen = screen.getByRole('status').textContent
  rerender(<InventoryViewProvider><span>Another tab</span></InventoryViewProvider>)
  rerender(<InventoryViewProvider><View /></InventoryViewProvider>)
  expect(screen.getByRole('status').textContent).toBe(chosen)
  act(() => { useSession.setState({ serverInstanceId: null }) })
  act(() => { useSession.setState({ serverInstanceId: 'first' }) })
  expect(screen.getByRole('status').textContent).toBe(chosen)
  act(() => { useSession.setState({ serverInstanceId: 'second' }) })
  expect(JSON.parse(screen.getByRole('status').textContent!)).toEqual({ query: '', category: '', scrollTop: 0, sort: 'name-asc', sortTouched: false })
})
