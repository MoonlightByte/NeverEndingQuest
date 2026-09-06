// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CharacterChip } from './CharacterChip'
import { resolveClickMedia, type MediaSource } from './media'
import { NpcCardDialog } from './NpcCardDialog'
import { usePlayer } from '../../stores'

vi.mock('../layout/EmberPresentation', () => ({ useEmberDesktop: () => true }))
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../sheet/useSpellReference', () => ({ useSpellReference: () => ({ data: {}, status: 'ready', retry: vi.fn() }) }))
vi.mock('./media', async (importOriginal) => ({
  ...await importOriginal<typeof import('./media')>(),
  resolveFirstImage: vi.fn().mockResolvedValue(null),
  resolveClickMedia: vi.fn(),
}))

const initialPlayer = usePlayer.getState()
afterEach(() => { cleanup(); usePlayer.setState(initialPlayer, true); vi.clearAllMocks() })

function heldMedia() {
  let finish!: (media: MediaSource | null) => void
  vi.mocked(resolveClickMedia).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  return () => act(async () => { finish({ kind: 'image', src: '/media/npcs/elen.jpg' }) })
}

function chip(name: string, onOpenMedia = vi.fn(), onOpenDetails = vi.fn()) {
  return <CharacterChip name={name} displayName={name} variant="party-npc" stats={{ name }}
    thumbCandidates={[]} clickMedia={{ videoUrl: '/media/npcs/elen_video.mp4', imageCandidates: ['/media/npcs/elen.jpg'] }}
    onOpenMedia={onOpenMedia} onOpenDetails={onOpenDetails} />
}

it('cancels a held portrait request before opening the same NPC full card', async () => {
  const finish = heldMedia()
  const openMedia = vi.fn(), openDetails = vi.fn()
  render(chip('Elen', openMedia, openDetails))
  fireEvent.click(screen.getByRole('button', { name: 'Elen' }))
  expect(screen.getByRole('button', { name: 'Elen' }).getAttribute('aria-busy')).toBe('true')
  fireEvent.click(screen.getByRole('button', { name: 'Elen full character details' }))
  expect(openDetails).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Elen' }).getAttribute('aria-busy')).toBe('false')
  await finish()
  expect(openMedia).not.toHaveBeenCalled()
  expect(screen.queryByText('No media available')).toBeNull()
})

it('opening another NPC full card also cancels a previously selected rail portrait', async () => {
  const finish = heldMedia()
  const openMedia = vi.fn(), openDetails = vi.fn()
  render(<>{chip('Elen', openMedia)}{chip('Marcus', vi.fn(), openDetails)}</>)
  fireEvent.click(screen.getByRole('button', { name: 'Elen' }))
  fireEvent.click(screen.getByRole('button', { name: 'Marcus full character details' }))
  expect(openDetails).toHaveBeenCalledOnce()
  await finish()
  expect(openMedia).not.toHaveBeenCalled()
})

it('still opens the resolved portrait when no later Details selection cancels it', async () => {
  const finish = heldMedia()
  const openMedia = vi.fn()
  render(chip('Elen', openMedia))
  fireEvent.click(screen.getByRole('button', { name: 'Elen' }))
  await finish()
  await waitFor(() => expect(openMedia).toHaveBeenCalledOnce())
  expect(openMedia.mock.calls[0]?.[0]).toMatchObject({ src: '/media/npcs/elen.jpg', selection: { name: 'Elen' } })
})

it('a nested full-card menu cancels pending header media and restores its own opener focus', async () => {
  const finish = heldMedia()
  usePlayer.setState({ npcs: [{ name: 'Elen', skills: { Perception: 4 } }], dataErrors: {} })
  render(<NpcCardDialog name="Elen" onClose={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Elen' }))
  const inventory = screen.getByRole('button', { name: 'Skills' })
  inventory.focus()
  fireEvent.click(inventory)
  expect(screen.getAllByRole('dialog', { hidden: true })).toHaveLength(2)
  expect(screen.getByRole('dialog', { name: "Elen's Skills" }).textContent).toContain('Perception')
  await finish()
  expect(screen.queryByRole('dialog', { name: 'Character media' })).toBeNull()
  expect(screen.getAllByRole('dialog', { hidden: true })).toHaveLength(2)
  fireEvent.keyDown(document.activeElement ?? document, { key: 'Escape' })
  expect(screen.queryByRole('dialog', { name: "Elen's Skills" })).toBeNull()
  expect(document.activeElement).toBe(inventory)
})

it('roster card opens the bio while its separate portrait opens media only', async () => {
  const openMedia = vi.fn(), openDetails = vi.fn()
  vi.mocked(resolveClickMedia).mockResolvedValueOnce({ kind: 'image', src: '/media/npcs/elen.jpg' })
  const { container } = render(<CharacterChip name="Elen" displayName="Elen" variant="party-npc"
    stats={{ name: 'Elen', currentHp: 12, maxHp: 14 }} showVitals thumbCandidates={[]}
    clickMedia={{ videoUrl: '/media/npcs/elen_video.mp4', imageCandidates: ['/media/npcs/elen.jpg'] }} onOpenMedia={openMedia} onOpenDetails={openDetails} />)
  fireEvent.click(screen.getByRole('button', { name: 'Elen full character details' }))
  expect(openDetails).toHaveBeenCalledOnce()
  expect(resolveClickMedia).not.toHaveBeenCalled()
  expect(screen.queryByText('Details')).toBeNull()
  expect(container.querySelector('button button')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Elen portrait' }))
  await waitFor(() => expect(openMedia).toHaveBeenCalledOnce())
  expect(openDetails).toHaveBeenCalledOnce()
})

it('opening a roster bio cancels a pending portrait so media cannot cover the bio later', async () => {
  const finish = heldMedia()
  const openMedia = vi.fn(), openDetails = vi.fn()
  render(<CharacterChip name="Elen" displayName="Elen" variant="party-npc" stats={{ name: 'Elen' }}
    showVitals thumbCandidates={[]} clickMedia={{ videoUrl: '/media/npcs/elen_video.mp4', imageCandidates: ['/media/npcs/elen.jpg'] }}
    onOpenMedia={openMedia} onOpenDetails={openDetails} />)
  fireEvent.click(screen.getByRole('button', { name: 'Elen portrait' }))
  fireEvent.click(screen.getByRole('button', { name: 'Elen full character details' }))
  await finish()
  expect(openDetails).toHaveBeenCalledOnce()
  expect(openMedia).not.toHaveBeenCalled()
})
