/**
 * Store reducer tests (plan Task 4.2 Step 1). Tests the store setters the
 * socket service dispatches into -- no socket connection involved.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { useLog } from './log'
import { useSession } from './session'
import { usePlayer } from './player'
import { useWorld } from './world'
import { useDialogs } from './dialogs'

const initialLog = useLog.getState()
const initialSession = useSession.getState()
const initialPlayer = usePlayer.getState()
const initialWorld = useWorld.getState()
const initialDialogs = useDialogs.getState()

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
  usePlayer.setState(initialPlayer, true)
  useWorld.setState(initialWorld, true)
  useDialogs.setState(initialDialogs, true)
})

describe('log store', () => {
  it('game_output appends to the log', () => {
    useLog.getState().append({ type: 'narration', content: 'A cold wind rises.' })
    useLog.getState().append({ type: 'user-input', content: 'I draw my sword.' })
    expect(useLog.getState().messages).toEqual([
      { type: 'narration', content: 'A cold wind rises.' },
      { type: 'user-input', content: 'I draw my sword.' },
    ])
  })

  it('a delayed cached_messages payload preserves newer live messages', () => {
    useLog.getState().append({
      type: 'narration',
      content: 'live entry',
      message_id: 'live-1',
    })
    useLog.getState().replaceAll([
      { type: 'narration', content: 'restored one', message_id: 'cached-1' },
    ])
    expect(useLog.getState().messages).toHaveLength(2)
    expect(useLog.getState().messages[0]!.content).toBe('restored one')
    expect(useLog.getState().messages[1]!.content).toBe('live entry')
  })

  it('deduplicates cache/live/reconnect delivery by stable message_id', () => {
    const message = { type: 'narration' as const, content: 'same event', message_id: 'm-1' }
    useLog.getState().append(message)
    useLog.getState().append(message)
    useLog.getState().replaceAll([message])
    expect(useLog.getState().messages).toEqual([message])
  })
})

describe('player store', () => {
  it('keeps full NPC records separate from party summaries', () => {
    const npcs = [
      { name: 'Scout Kira', abilities: { dexterity: 17 }, equipment: [{ item_name: 'Bow' }] },
    ]
    usePlayer.getState().setPlayerData({ dataType: 'npcs', data: npcs })
    expect(usePlayer.getState().npcs).toEqual(npcs)
  })

  it('rejects an older resource revision', () => {
    usePlayer.getState().setPlayerData({ dataType: 'stats', data: { name: 'Current' }, revision: 10 })
    usePlayer.getState().setPlayerData({ dataType: 'stats', data: { name: 'Stale' }, revision: 9 })
    expect(usePlayer.getState().stats?.name).toBe('Current')
  })

  it('accepts a lower revision from a restarted server instance', () => {
    usePlayer.getState().setPlayerData({ dataType: 'stats', data: { name: 'Before restart' }, revision: 40, server_instance_id: 'server-a' })
    usePlayer.getState().setPlayerData({ dataType: 'stats', data: { name: 'After restart' }, revision: 1, server_instance_id: 'server-b' })
    expect(usePlayer.getState().stats?.name).toBe('After restart')
  })
})

describe('world convergence', () => {
  it('does not let delayed location data overwrite a newer revision', () => {
    const base = { currentArea: 'A', currentLocationId: 'L', currentAreaId: 'A', time: '12:00', day: 1, month: 'Spring', year: 1 }
    useWorld.getState().setLocation({ data: { ...base, currentLocation: 'New' }, revision: 4 })
    useWorld.getState().setLocation({ data: { ...base, currentLocation: 'Old' }, revision: 3 })
    expect(useWorld.getState().location?.currentLocation).toBe('New')
  })

  it('resets revision floors when the server instance changes', () => {
    const base = { currentArea: 'A', currentLocationId: 'L', currentAreaId: 'A', time: '12:00', day: 1, month: 'Spring', year: 1 }
    useWorld.getState().setLocation({ data: { ...base, currentLocation: 'Before restart' }, revision: 30, server_instance_id: 'server-a' })
    useWorld.getState().setLocation({ data: { ...base, currentLocation: 'After restart' }, revision: 1, server_instance_id: 'server-b' })
    expect(useWorld.getState().location?.currentLocation).toBe('After restart')
  })
})

describe('operation reducers', () => {
  it('terminates a failed compression instead of leaving its overlay running', () => {
    useDialogs.getState().compressionStart({ total_sections: 4 })
    useDialogs.getState().compressionFailed({ error: 'Provider unavailable' })
    expect(useDialogs.getState().compression).toMatchObject({ running: false, error: 'Provider unavailable', result: null })
  })

  it('keeps module progress monotonic and ignores foreign builds', () => {
    const progress = (build_id: string, percentage: number) => ({ build_id, stage: 1, total_stages: 9, stage_name: 'Forge', percentage, message: 'working', status: 'running', terminal: false })
    useDialogs.getState().moduleProgress(progress('build-a', 40))
    useDialogs.getState().moduleProgress(progress('build-a', 20))
    useDialogs.getState().moduleProgress(progress('build-b', 90))
    expect(useDialogs.getState().moduleOperation?.percentage).toBe(40)
    expect(useDialogs.getState().moduleOperation?.buildId).toBe('build-a')
  })

  it('recognizes production module terminal statuses', () => {
    useDialogs.getState().moduleProgress({ build_id: 'build-a', stage: 9, total_stages: 9, stage_name: 'Publish', percentage: 100, message: 'done', status: 'published', terminal: true, success: true })
    expect(useDialogs.getState().moduleOperation?.terminal).toBe(true)
    expect(useDialogs.getState().moduleOperation?.success).toBe(true)
  })
})

describe('session store', () => {
  it('status_update with is_processing true locks input', () => {
    useSession.getState().setStatus({ message: 'The DM is thinking...', is_processing: true })
    expect(useSession.getState().isProcessing).toBe(true)
    expect(useSession.getState().statusMessage).toBe('The DM is thinking...')
  })

  it('disconnect preserves game lifecycle while marking transport offline', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('welcome')
    expect(useSession.getState().mode).toBe('play')
    useSession.getState().setConnected(false)
    expect(useSession.getState().mode).toBe('play')
    expect(useSession.getState().connected).toBe(false)
  })

})
