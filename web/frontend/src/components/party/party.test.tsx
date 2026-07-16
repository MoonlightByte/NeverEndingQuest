// @vitest-environment jsdom
/**
 * Component logic tests for the party / initiative rail group (plan Task
 * 4.4c). services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { useLog, usePlayer, useSession, useWorld } from '../../stores'
import { emitC } from '../../services/socket'
import { PartyStrip } from './PartyStrip'
import { InitiativeTracker } from './InitiativeTracker'
import { AdventureBox, timeOfDayImage } from './AdventureBox'
import {
  altPluralName,
  chipFontSize,
  combatantDisplayName,
  monsterClickMedia,
  monsterThumbCandidates,
  npcClassFallbackPortrait,
  npcThumbCandidates,
  partyClickMedia,
  playerThumbCandidates,
} from './media'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

const initialLog = useLog.getState()
const initialSession = useSession.getState()
const initialWorld = useWorld.getState()
const initialPlayer = usePlayer.getState()

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
  useWorld.setState(initialWorld, true)
  usePlayer.setState(initialPlayer, true)
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

function requestCount(event: 'request_party_data' | 'request_initiative_data'): number {
  return vi.mocked(emitC).mock.calls.filter((call) => call[0] === event).length
}

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
  it('requests party data on mount and after each game_output', () => {
    render(<PartyStrip />)
    expect(requestCount('request_party_data')).toBe(1)
    act(() => {
      useLog.getState().append({ type: 'narration', content: 'The door creaks open.' })
    })
    expect(requestCount('request_party_data')).toBe(2)
  })

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
  it('requests initiative data on mount and renders nothing while inactive', () => {
    const { container } = render(<InitiativeTracker />)
    expect(container.firstChild).toBeNull()
    expect(requestCount('request_initiative_data')).toBe(1)
    act(() => {
      useLog.getState().append({ type: 'narration', content: 'A skeleton lunges!' })
    })
    expect(requestCount('request_initiative_data')).toBe(2)
  })

  it('renders typed combatant chips and the round badge during combat', () => {
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
    expect(screen.getByText('Round')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('highlights the player chip only when input is unlocked', () => {
    act(() => {
      useSession.getState().setStatus({ message: '', is_processing: false })
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
