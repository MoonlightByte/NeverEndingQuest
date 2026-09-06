/** Single playback owner for narration, browser speech and settings previews. */
let active: { owner: symbol; stop: () => void } | null = null
export function stopAudio(owner?: symbol) {
  if (owner && active?.owner !== owner) return
  const previous = active
  active = null
  previous?.stop()
}
export function claimAudio(owner: symbol, stop: () => void) {
  if (active?.owner !== owner) stopAudio()
  active = { owner, stop }
}
export function ownsAudio(owner: symbol) { return active?.owner === owner }
export function finishAudio(owner: symbol, idle: () => void) {
  if (!ownsAudio(owner)) return
  active = null
  idle()
}
