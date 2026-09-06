// @vitest-environment jsdom
/**
 * Component logic tests for the party / initiative rail group (plan Task
 * 4.4c). services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { usePlayer, useSession, useWorld } from '../../stores'
import { PartyStrip } from './PartyStrip'
import { InitiativeTracker } from './InitiativeTracker'
import { AdventureBox, timeOfDayImage } from './AdventureBox'
import { MediaPopup } from './MediaPopup'
import { StatsTooltip } from './StatsTooltip'
import {
  altPluralName,
  chipFontSize,
  combatantDisplayName,
  monsterClickMedia,
  monsterThumbCandidates,
  npcClassFallbackPortrait,
  initiativeNpcClickMedia,
  initiativeNpcThumbCandidates,
  initiativePlayerThumbCandidates,
  npcThumbCandidates,
  partyClickMedia,
  playerThumbCandidates,
  resolveClickMedia,
  invalidateMediaCaches,
  resolveFirstImage,
} from './media'

const initialSession = useSession.getState()
const initialWorld = useWorld.getState()
const initialPlayer = usePlayer.getState()

beforeEach(() => {
  useSession.setState(initialSession, true)
  useWorld.setState(initialWorld, true)
  usePlayer.setState(initialPlayer, true)
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
  cleanup()
})

describe('media url helpers', () => {
  it('builds monster thumb candidates with png and plural fallbacks', () => {
    expect(monsterThumbCandidates('Dire Wolf')).toEqual([
      '/media/monsters/dire_wolf_thumb.jpg',
      '/media/monsters/dire_wolf_thumb.png',
      '/media/monsters/dire_wolfs_thumb.jpg',
      '/media/monsters/dire_wolfs_thumb.png',
    ])
  })

  it('toggles a trailing s for the alternate monster name', () => {
    expect(altPluralName('skeletons')).toBe('skeleton')
    expect(altPluralName('skeleton')).toBe('skeletons')
  })

  it('monster click media is video first, then full-size images', () => {
    const media = monsterClickMedia('Skeleton')
    expect(media.videoUrl).toBe('/media/monsters/skeleton_video.mp4')
    expect(media.imageCandidates).toEqual([
      '/media/monsters/skeleton.jpg',
      '/media/monsters/skeletons.jpg',
      '/media/monsters/skeleton.png',
      '/media/monsters/skeletons.png',
    ])
  })

  it('player and npc portrait paths mirror the legacy interface', () => {
    expect(playerThumbCandidates('Eirik')).toEqual(['/static/portraits/eirik.png'])
    expect(npcThumbCandidates('Scout Kira')).toEqual(['/media/npcs/scout_kira_thumb.jpg'])
    expect(partyClickMedia('Scout Kira', 'npc')).toEqual({
      videoUrl: '/media/npcs/scout_kira_video.mp4',
      imageCandidates: ['/media/npcs/scout_kira.jpg', '/media/npcs/scout_kira.png'],
    })
  })

  it('uses the stricter legacy initiative filenames without party-strip fallbacks', () => {
    expect(initiativePlayerThumbCandidates("O'Malley Prime")).toEqual([
      '/static/portraits/o_malley_prime.png',
    ])
    expect(initiativeNpcThumbCandidates("Scout O'Malley")).toEqual([
      "/media/npcs/scout_o'malley_thumb.jpg",
    ])
    expect(initiativeNpcClickMedia("Scout O'Malley")).toEqual({
      videoUrl: "/media/npcs/scout_o'malley_video.mp4",
      imageCandidates: ["/media/npcs/scout_o'malley.jpg"],
    })
  })

  it('falls back from video to full image and finally the resolved thumbnail', async () => {
    const realCreateElement = document.createElement.bind(document)
    const createElement = vi.spyOn(document, 'createElement').mockImplementation((tagName, options) => {
      if (tagName.toLowerCase() !== 'video') return realCreateElement(tagName, options)
      const video = {
        preload: '',
        onloadedmetadata: null as (() => void) | null,
        onerror: null as (() => void) | null,
        set src(_value: string) { queueMicrotask(() => video.onerror?.()) },
      }
      return video as unknown as HTMLVideoElement
    })
    class FakeImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(value: string) {
        queueMicrotask(() => value.includes('found') ? this.onload?.() : this.onerror?.())
      }
    }
    vi.stubGlobal('Image', FakeImage)
    await expect(resolveClickMedia({
      videoUrl: '/unique/fallback-video.mp4',
      imageCandidates: ['/unique/missing.jpg', '/unique/found.jpg'],
    }, '/unique/thumb.jpg')).resolves.toEqual({ kind: 'image', src: '/unique/found.jpg' })
    await expect(resolveClickMedia({
      videoUrl: '/unique/thumb-video.mp4',
      imageCandidates: ['/unique/also-missing.jpg'],
    }, '/unique/thumb.jpg')).resolves.toEqual({ kind: 'image', src: '/unique/thumb.jpg' })
    createElement.mockRestore()
    vi.unstubAllGlobals()
  })

  it('falls back to class portraits by npc name keyword', () => {
    expect(npcClassFallbackPortrait('Scout Kira')).toBe('/static/media/class_portraits/rogue.png')
    expect(npcClassFallbackPortrait('Elder Mage Thorn')).toBe(
      '/static/media/class_portraits/wizard.png',
    )
    expect(npcClassFallbackPortrait('Innkeeper Bram')).toBe(
      '/static/media/class_portraits/default_npc.png',
    )
  })

  it('strips trailing numbers from enemy and npc display names', () => {
    expect(combatantDisplayName('Skeleton_2', 'enemy')).toBe('Skeleton')
    expect(combatantDisplayName('Dire_Wolf_1', 'enemy')).toBe('Dire Wolf')
    expect(combatantDisplayName('Eirik', 'player')).toBe('Eirik')
  })

  it('sizes chip labels by name length', () => {
    expect(chipFontSize('Eirik')).toBe(11)
    expect(chipFontSize('Scout Kira')).toBe(9)
    expect(chipFontSize('Ancient Red Dragon')).toBe(8)
  })
})

describe('MediaPopup', () => {
  it('falls back after video playback fails and reports missing image without losing close', () => {
    render(<MediaPopup media={{kind:'video', src:'/broken.mp4',fallback:'/portrait.jpg'}} onClose={vi.fn()} />)
    fireEvent.error(document.querySelector('video')!)
    expect(screen.getByAltText('Character portrait').getAttribute('src')).toBe('/portrait.jpg')
    fireEvent.error(screen.getByAltText('Character portrait'))
    expect(screen.getByRole('status').textContent).toContain('could not be loaded')
    expect(screen.getByRole('button',{name:'Close'})).toBeTruthy()
  })
  it('provides a visible close action and native playback controls', () => {
    const close = vi.fn()
    render(<MediaPopup media={{ kind: 'video', src: '/media/npcs/kira_video.mp4', anchor: { top: 100, bottom: 160, left: 40, width: 60 } }} onClose={close} />)
    const dialog = screen.getByRole('dialog', { name: 'Character media' })
    const video = dialog.querySelector('video') as HTMLVideoElement
    expect(video.muted).toBe(true)
    expect(video.controls).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(close).toHaveBeenCalledOnce()
  })

  it('closes on Escape from the focused dialog', () => {
    const close = vi.fn()
    render(<MediaPopup media={{ kind: 'image', src: '/media/npcs/kira.jpg' }} onClose={close} />)
    expect(screen.getByRole('dialog', { name: 'Character media' }).querySelector('img')?.getAttribute('src')).toBe('/media/npcs/kira.jpg')
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(close).toHaveBeenCalledOnce()
  })
})

it('invalidates stale negative portrait probes after a successful upload', async () => {
  let available = false
  class ImageDouble {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    set src(_src: string) { queueMicrotask(() => available ? this.onload?.() : this.onerror?.()) }
  }
  vi.stubGlobal('Image', ImageDouble)
  expect(await resolveFirstImage(['/static/portraits/new_hero.png'])).toBeNull()
  available = true
  invalidateMediaCaches('New Hero')
  expect(await resolveFirstImage(['/static/portraits/new_hero.png'])).toMatch(/^\/static\/portraits\/new_hero.png\?neq_media=/)
  vi.unstubAllGlobals()
})

describe('StatsTooltip', () => {
  it('matches the legacy rows and clamps below the top-right viewport edge', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 })
    const anchor = document.createElement('div')
    anchor.getBoundingClientRect = vi.fn(() => ({
      x: 760, y: 5, top: 5, left: 760, width: 60, height: 60,
      right: 820, bottom: 65, toJSON: () => ({}),
    }))
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains('neq-stats-tooltip-parity')) {
        return {
          x: 0, y: 0, top: 0, left: 0, width: 220, height: 200,
          right: 220, bottom: 200, toJSON: () => ({}),
        }
      }
      return {
        x: 0, y: 0, top: 0, left: 0, width: 0, height: 0,
        right: 0, bottom: 0, toJSON: () => ({}),
      }
    })
    render(<StatsTooltip anchor={anchor} stats={{
      name: 'Arden_Vale', level: 4, class: 'Rogue', currentHp: 24, maxHp: 30,
      ac: 15, speed: 30, initiative: 4,
      primaryAttack: { name: 'Rapier', bonus: 6, damage: '1d8+4' },
      ammunition: [{ name: 'bolt', quantity: 12 }],
      spellSlots: { level1: { current: 1, max: 2 }, level2: { current: 2, max: 3 } },
      spells: { 0: ['Mage Hand'], 1: ['Disguise Self'] },
      classFeatures: [{ name: 'Sneak Attack', usage: '1/turn' }],
      conditions: ['Blessed'],
    }} />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.classList.contains('neq-stats-tooltip-parity')).toBe(true)
    expect(tooltip.style.left).toBe('572px')
    expect(tooltip.style.top).toBe('73px')
    expect(tooltip.textContent).toContain('Lvl 4 Rogue')
    expect(tooltip.textContent).toContain('24/30 HP')
    expect(tooltip.textContent).toContain('Spell Slots: L1: 1/2 • L2: 2/3')
    expect(tooltip.textContent).toContain('• Sneak Attack (1/turn)')
    expect(tooltip.textContent).toContain('Conditions: Blessed')
  })
})

describe('timeOfDayImage', () => {
  it('maps game hours to the environment art', () => {
    expect(timeOfDayImage('06:30:00')).toBe('/static/media/environment/sunrise.jpg')
    expect(timeOfDayImage('12:00:00')).toBe('/static/media/environment/midday.jpg')
    expect(timeOfDayImage('18:15:00')).toBe('/static/media/environment/sunset.jpg')
    expect(timeOfDayImage('23:00:00')).toBe('/static/media/environment/nightfall.jpg')
    expect(timeOfDayImage('03:00:00')).toBe('/static/media/environment/nightfall.jpg')
    expect(timeOfDayImage(null)).toBe('/static/media/environment/midday.jpg')
  })
})

describe('PartyStrip', () => {
  it('renders party member and location npc chips outside combat', () => {
    act(() => {
      useWorld.getState().setParty({
        members: [{ name: 'Eirik', type: 'player' }],
        location_npcs: [{ name: 'Scout Kira', type: 'npc' }],
      })
    })
    render(<PartyStrip />)
    const player = screen.getByRole('button', { name: 'Eirik' })
    const npc = screen.getByRole('button', { name: 'Scout Kira' })
    expect(player.getAttribute('data-chip')).toBe('party-player')
    expect(npc.getAttribute('data-chip')).toBe('location-npc')
  })

  it('applies the legacy location-NPC opacity and purple hover glow', () => {
    vi.useFakeTimers()
    act(() => {
      useWorld.getState().setParty({
        members: [],
        location_npcs: [{ name: 'Scout Kira', type: 'npc' }],
      })
    })
    render(<PartyStrip />)
    const npc = screen.getByRole('button', { name: 'Scout Kira' })
    expect(npc.style.opacity).toBe('0.8')
    fireEvent.mouseEnter(npc)
    act(() => vi.advanceTimersByTime(50))
    expect(npc.style.opacity).toBe('1')
    expect(npc.style.transform).toBe('scale(1.05)')
    expect(npc.style.boxShadow).toContain('156, 39, 176')
    vi.useRealTimers()
  })

  it('shows conditional arrows and scrolls the shared rail by 200px', () => {
    act(() => {
      useWorld.getState().setParty({
        members: Array.from({ length: 8 }, (_, index) => ({ name: `Hero ${index}`, type: 'player' })),
      })
    })
    render(<PartyStrip />)
    const rail = screen.getByLabelText('Party members') as HTMLDivElement
    Object.defineProperties(rail, {
      clientWidth: { configurable: true, value: 200 },
      scrollWidth: { configurable: true, value: 600 },
      scrollLeft: { configurable: true, writable: true, value: 0 },
    })
    const scrollBy = vi.fn((options?: ScrollToOptions | number) => {
      rail.scrollLeft += typeof options === 'number' ? options : Number(options?.left ?? 0)
      fireEvent.scroll(rail)
    })
    Object.defineProperty(rail, 'scrollBy', { configurable: true, value: scrollBy })
    fireEvent(window, new Event('resize'))
    expect(screen.queryByRole('button', { name: 'Scroll party members left' })).toBeNull()
    const right = screen.getByRole('button', { name: 'Scroll party members right' })
    fireEvent.click(right)
    expect(scrollBy).toHaveBeenCalledWith({ left: 200, behavior: 'smooth' })
    expect(screen.getByRole('button', { name: 'Scroll party members left' })).toBeTruthy()
  })

  it('yields to the initiative tracker during combat', () => {
    act(() => {
      useWorld.getState().setParty({ members: [{ name: 'Eirik', type: 'player' }] })
      useWorld.getState().setInitiative({
        active: true,
        combatants: [{ name: 'Eirik', type: 'player' }],
        round: 2,
      })
    })
    const { container } = render(<PartyStrip />)
    expect(container.firstChild).toBeNull()
  })
})

describe('InitiativeTracker', () => {
  it('renders nothing while inactive', () => {
    const { container } = render(<InitiativeTracker />)
    expect(container.firstChild).toBeNull()
  })

  it('renders typed combatant chips without duplicating the shell round badge', () => {
    act(() => {
      useWorld.getState().setInitiative({
        active: true,
        round: 3,
        combatants: [
          { name: 'Eirik', type: 'player' },
          { name: 'Scout_Kira', type: 'npc' },
          { name: 'Skeleton_2', type: 'enemy', monsterType: 'Skeleton' },
        ],
      })
    })
    render(<InitiativeTracker />)
    expect(screen.getByRole('button', { name: 'Eirik' }).getAttribute('data-chip')).toBe(
      'init-player',
    )
    expect(screen.getByRole('button', { name: 'Scout Kira' }).getAttribute('data-chip')).toBe(
      'init-npc',
    )
    expect(screen.getByRole('button', { name: 'Skeleton' }).getAttribute('data-chip')).toBe(
      'init-enemy',
    )
    expect(screen.queryByText('Round')).toBeNull()
  })

  it('highlights the player chip only when input is unlocked', () => {
    act(() => {
      useSession.getState().setStatus({ message: '', is_processing: false })
      usePlayer.setState({ stats: { name: 'Eirik' } })
      useWorld.getState().setInitiative({
        active: true,
        round: 1,
        combatants: [
          { name: 'Eirik', type: 'player' },
          { name: 'Skeleton_1', type: 'enemy' },
        ],
      })
    })
    render(<InitiativeTracker />)
    expect(screen.getByRole('button', { name: 'Eirik' }).getAttribute('data-active')).toBe('true')
    expect(screen.getByRole('button', { name: 'Skeleton' }).getAttribute('data-active')).toBe(
      'false',
    )
  })

  it('does not highlight anyone while the DM is processing', () => {
    act(() => {
      useSession.getState().setStatus({ message: 'Rolling...', is_processing: true })
      useWorld.getState().setInitiative({
        active: true,
        round: 1,
        combatants: [{ name: 'Eirik', type: 'player' }],
      })
    })
    render(<InitiativeTracker />)
    expect(screen.getByRole('button', { name: 'Eirik' }).getAttribute('data-active')).toBe('false')
  })

  it('does not guess the active player when the player name is unavailable', () => {
    act(() => {
      useSession.getState().setStatus({ message: '', is_processing: false })
      useWorld.getState().setInitiative({
        active: true,
        round: 1,
        combatants: [{ name: 'Eirik', type: 'player' }],
      })
    })
    render(<InitiativeTracker />)
    const player = screen.getByRole('button', { name: 'Eirik' })
    expect(player.getAttribute('data-active')).toBe('false')
    expect(player.getAttribute('data-media-enabled')).toBe('false')
  })

  it('uses the same conditional 200px scroller during combat', () => {
    act(() => {
      useWorld.getState().setInitiative({
        active: true,
        round: 1,
        combatants: Array.from({ length: 8 }, (_, index) => ({ name: `Skeleton_${index}`, type: 'enemy' })),
      })
    })
    render(<InitiativeTracker />)
    const rail = screen.getByLabelText('Initiative order') as HTMLDivElement
    Object.defineProperties(rail, {
      clientWidth: { configurable: true, value: 200 },
      scrollWidth: { configurable: true, value: 600 },
      scrollLeft: { configurable: true, writable: true, value: 0 },
    })
    const scrollBy = vi.fn((options?: ScrollToOptions | number) => {
      rail.scrollLeft += typeof options === 'number' ? options : Number(options?.left ?? 0)
      fireEvent.scroll(rail)
    })
    Object.defineProperty(rail, 'scrollBy', { configurable: true, value: scrollBy })
    fireEvent(window, new Event('resize'))
    fireEvent.click(screen.getByRole('button', { name: 'Scroll initiative order right' }))
    expect(scrollBy).toHaveBeenCalledWith({ left: 200, behavior: 'smooth' })
  })
})

describe('AdventureBox', () => {
  it('shows the time-of-day art outside combat', () => {
    act(() => {
      useWorld.getState().setLocation({
        data: {
          currentLocation: 'The Gilded Griffin',
          currentArea: 'Harrowmere',
          currentLocationId: 'A01',
          currentAreaId: 'HH001',
          time: '19:00:00',
          day: 12,
          month: 'Frostfall',
          year: 1024,
        },
      })
    })
    const { container } = render(<AdventureBox />)
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img?.getAttribute('src')).toBe('/static/media/environment/sunset.jpg')
    expect(screen.queryByText('COMBAT')).toBeNull()
  })

  it('becomes the COMBAT round box while initiative is active', () => {
    act(() => {
      useWorld.getState().setInitiative({
        active: true,
        round: 4,
        combatants: [{ name: 'Eirik', type: 'player' }],
      })
    })
    const { container } = render(<AdventureBox />)
    expect(screen.getByText('COMBAT')).toBeTruthy()
    expect(screen.getByText('4')).toBeTruthy()
    expect(container.querySelector('img')).toBeNull()
  })
})
