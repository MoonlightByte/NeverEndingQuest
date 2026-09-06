// @vitest-environment jsdom
/**
 * Component logic tests for the party / initiative rail group (plan Task
 * 4.4c). services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  uploadedPortraitCandidates,
  uploadedPortraitPath,
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

  it('keeps the strict initiative filename first and appends the canonical upload fallback', () => {
    expect(initiativePlayerThumbCandidates("O'Malley Prime")).toEqual([
      '/static/portraits/o_malley_prime.png',
      "/static/portraits/o'malley_prime.png",
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

describe('scoped portrait upload freshness', () => {
  beforeEach(() => { invalidateMediaCaches() })
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

  function images(available: (src: string) => boolean = () => true) {
    const requested: string[] = []
    class ImageDouble {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(value: string) {
        requested.push(value)
        queueMicrotask(() => available(value.split('?')[0]!) ? this.onload?.() : this.onerror?.())
      }
    }
    vi.stubGlobal('Image', ImageDouble)
    return requested
  }

  function selection(name: string) {
    return { kind: 'image' as const, src: '/old-portrait.png', selection: { name, recipe: partyClickMedia(name, 'player'), thumbnail: '/old-thumb.png' } }
  }

  for (const name of ["O'Brien", 'Arden-Vale']) {
    it(`discovers canonical ${name} uploads after negative probes and replaces older aliases`, async () => {
      let present = false
      images(src => present && src === uploadedPortraitPath(name))
      const candidates = playerThumbCandidates(name)
      expect(await resolveFirstImage(candidates)).toBeNull()
      present = true
      invalidateMediaCaches(name, true)
      const selected = uploadedPortraitCandidates(name, candidates)
      expect(selected).toEqual([uploadedPortraitPath(name)])
      expect(await resolveFirstImage(selected)).toContain(`${uploadedPortraitPath(name)}?neq_media=`)
      // Even if all old aliases now exist, explicit successful upload wins.
      images()
      invalidateMediaCaches(name, true)
      expect(await resolveFirstImage(uploadedPortraitCandidates(name, initiativePlayerThumbCandidates(name)))).toContain(`${uploadedPortraitPath(name)}?neq_media=`)
      expect((await resolveClickMedia(partyClickMedia(name, 'player'), '/old-thumb.png'))?.src).toContain(`${uploadedPortraitPath(name)}?neq_media=`)
      invalidateMediaCaches()
      expect(uploadedPortraitCandidates(name, candidates)).toEqual(candidates)
    })
  }

  it('cache-busts exact normalization aliases without prefix revision collisions', async () => {
    images()
    invalidateMediaCaches("O'Brien")
    for (const path of ["/static/portraits/o'brien.png", '/static/portraits/obrien.png', '/static/portraits/o_brien.png']) {
      expect(await resolveFirstImage([path])).toContain('?neq_media=')
    }
    invalidateMediaCaches('Ann')
    const ann = await resolveFirstImage(['/static/portraits/ann.png'])
    invalidateMediaCaches('Ann Marie')
    const marie = await resolveFirstImage(['/static/portraits/ann_marie.png'])
    expect(ann?.split('?')[1]).not.toBe(marie?.split('?')[1])
    expect(await resolveFirstImage(['/static/portraits/ann.png'])).toBe(ann)
  })

  it('keeps legacy literal-percent names probeable without URI decoding errors', async () => {
    images()
    invalidateMediaCaches('Hero 100%')
    expect(await resolveFirstImage(['/static/portraits/hero_100%.png'])).toContain('/hero_100%.png?neq_media=')
  })

  it('versions repeated uploads for player names ending in Thumb or Video without stripping their name', async () => {
    images()
    for (const name of ['Tom Thumb', 'Hero Video']) {
      const path = uploadedPortraitPath(name)
      invalidateMediaCaches(name, true)
      const first = await resolveFirstImage([path])
      invalidateMediaCaches(name, true)
      const second = await resolveFirstImage([path])
      expect(first).toContain(`${path}?neq_media=`)
      expect(second).toContain(`${path}?neq_media=`)
      expect(second).not.toBe(first)
    }
  })

  it('still versions generated NPC thumbnail and animation suffixes together', async () => {
    images()
    const requested: string[] = []
    const create = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag, options) => {
      if (tag !== 'video') return create(tag, options)
      const video = { onloadedmetadata: null as (() => void) | null, onerror: null as (() => void) | null,
        removeAttribute: vi.fn(), load: vi.fn(),
        set src(src: string) { requested.push(src); queueMicrotask(() => video.onloadedmetadata?.()) } }
      return video as unknown as HTMLVideoElement
    })
    invalidateMediaCaches('Scout Kira')
    const thumb = await resolveFirstImage(npcThumbCandidates('Scout Kira'))
    const first = await resolveClickMedia(partyClickMedia('Scout Kira', 'npc'), null)
    expect(first?.kind).toBe('video')
    expect(first?.src.split('?')[1]).toBe(thumb?.split('?')[1])
    invalidateMediaCaches('Scout Kira')
    const second = await resolveClickMedia(partyClickMedia('Scout Kira', 'npc'), null)
    expect(second?.src).not.toBe(first?.src)
    expect(requested[1]).toBe(second?.src)
  })

  it('refreshes both full-size and generated thumbnail images for NPC Tom Thumb', async () => {
    images()
    const full = partyClickMedia('Tom Thumb', 'npc').imageCandidates[0]!
    const thumb = npcThumbCandidates('Tom Thumb')[0]!
    invalidateMediaCaches('Tom Thumb')
    const firstFull = await resolveFirstImage([full])
    const firstThumb = await resolveFirstImage([thumb])
    invalidateMediaCaches('Tom Thumb')
    const secondFull = await resolveFirstImage([full])
    const secondThumb = await resolveFirstImage([thumb])
    expect(secondFull).not.toBe(firstFull)
    expect(secondThumb).not.toBe(firstThumb)
    expect(secondFull?.split('?')[1]).toBe(secondThumb?.split('?')[1])
    // That full-size filename can also be Tom's generated thumbnail: either
    // identity changing must invalidate the one physical resource.
    invalidateMediaCaches('Tom')
    expect(await resolveFirstImage([full])).not.toBe(secondFull)
  })

  it('keeps video-first behavior unless an explicit uploaded photo overrides it, and restores it on session change', async () => {
    images()
    const create = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag, options) => {
      if (tag !== 'video') return create(tag, options)
      const video = { onloadedmetadata: null as (() => void) | null, onerror: null as (() => void) | null,
        removeAttribute: vi.fn(), load: vi.fn(),
        set src(_src: string) { queueMicrotask(() => video.onloadedmetadata?.()) } }
      return video as unknown as HTMLVideoElement
    })
    const recipe = partyClickMedia('Video Hero', 'player')
    expect((await resolveClickMedia(recipe, null))?.kind).toBe('video')
    invalidateMediaCaches('Video Hero', true)
    expect((await resolveClickMedia(recipe, null))?.kind).toBe('image')
    invalidateMediaCaches()
    expect((await resolveClickMedia(recipe, null))?.kind).toBe('video')
  })

  it('refreshes the same open viewer, preserves focus, ignores unrelated updates, and closes on global change', async () => {
    images()
    const close = vi.fn()
    render(<MediaPopup media={selection("O'Brien")} onClose={close} />)
    const button = screen.getByRole('button', { name: 'Close' }); button.focus()
    await act(async () => { invalidateMediaCaches("O'Brien", true) })
    await waitFor(() => expect(screen.getByAltText('Character portrait').getAttribute('src')).toContain("/o'brien.png?neq_media="))
    expect(document.activeElement).toBe(button)
    const src = screen.getByAltText('Character portrait').getAttribute('src')
    await act(async () => { invalidateMediaCaches('Other Hero', true) })
    expect(screen.getByAltText('Character portrait').getAttribute('src')).toBe(src)
    expect(close).not.toHaveBeenCalled()
    act(() => { invalidateMediaCaches() })
    expect(close).toHaveBeenCalledOnce()
    expect(screen.queryByAltText('Character portrait')).toBeNull()
  })

  it('shows refresh failure without stale art and can recover on a later successful update', async () => {
    let available = false
    images(() => available)
    render(<MediaPopup media={selection('Hero')} onClose={vi.fn()} />)
    await act(async () => { invalidateMediaCaches('Hero', true) })
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('could not be loaded'))
    expect(screen.queryByAltText('Character portrait')).toBeNull()
    available = true
    await act(async () => { invalidateMediaCaches('Hero', true) })
    await waitFor(() => expect(screen.getByAltText('Character portrait').getAttribute('src')).toContain('/hero.png?neq_media='))
  })

  it('does not let delayed A refresh replace B or return after dismissal', async () => {
    const pending: Array<{ onload: (() => void) | null; onerror: (() => void) | null }> = []
    class DelayedImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_value: string) { pending.push(this) }
    }
    vi.stubGlobal('Image', DelayedImage)
    const close = vi.fn()
    const { rerender } = render(<MediaPopup media={selection('A')} onClose={close} />)
    act(() => { invalidateMediaCaches('A', true) })
    expect(screen.getByRole('status').textContent).toContain('Refreshing')
    rerender(<MediaPopup media={{ ...selection('B'), src: '/B.png' }} onClose={close} />)
    await act(async () => { pending[0]!.onload?.() })
    expect(screen.getByAltText('Character portrait').getAttribute('src')).toBe('/B.png')
    act(() => { invalidateMediaCaches('B', true) })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    rerender(<MediaPopup media={null} onClose={close} />)
    await act(async () => { pending[1]!.onload?.() })
    expect(screen.queryByRole('dialog')).toBeNull()
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
