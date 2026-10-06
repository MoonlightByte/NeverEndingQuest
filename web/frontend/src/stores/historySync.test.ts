import { beforeEach, expect, it } from 'vitest'
import { useLog } from './log'

beforeEach(() => useLog.getState().clear())
it('replaces stale interviews on reconnect but keeps output arriving during hydration', () => {
  const log = useLog.getState()
  log.append({ type: 'narration', message_id: 'old', content: 'Choose your name.' })
  log.beginHistorySync()
  log.append({ type: 'narration', message_id: 'live', content: 'The door opens.' })
  log.replaceAll([{ type: 'narration', message_id: 'scene', content: 'You reach the tower.' }])
  expect(useLog.getState().messages.map(m => m.message_id)).toEqual(['scene', 'live'])
  expect(useLog.getState().previousSessionCount).toBe(1)
})
it('accepts an empty history and excludes transient reconnect notices', () => {
  const log = useLog.getState()
  log.append({ type: 'narration', content: 'Old save' })
  log.beginHistorySync()
  log.replaceAll([])
  log.append({ type: 'system', content: 'Reconnected to your game in progress.' })
  expect(useLog.getState().messages).toEqual([])
})
