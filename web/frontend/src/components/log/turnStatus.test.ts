import { describe, expect, it } from 'vitest'
import { turnStatusText } from './turnStatus'

describe('turn status presentation', () => {
  it.each([
    ['Companion voices are ready; the storyteller is weaving them in', 'Your companions are sharing their thoughts…'],
    ['Updating character info...', 'Your deeds leave their mark…'],
    ['Compressing conversation history...', 'Your tale is being recorded…'],
    ['Loading location data...', 'The path ahead comes into view…'],
    ['Processing combat round...', 'The clash unfolds…'],
  ])('translates %s', (raw, expected) => expect(turnStatusText(raw)).toBe(expected))
  it.each(['Retrying response (attempt 2/3)...', 'Provider quota exceeded', 'Open Settings to update your API key (401).', 'Provider billing needs attention (402).', 'Gameplay is paused. Return to menu.'])('preserves actionable information: %s', raw => {
    expect(turnStatusText(raw)).toBe(raw)
  })
})
