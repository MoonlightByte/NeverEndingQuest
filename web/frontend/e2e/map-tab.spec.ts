import { expect, test } from '@playwright/test'

/**
 * Task 9 Part 1: real Playwright coverage of the Map tab, run against the
 * lighter e2e path this repo already uses for player-shell.spec.ts -- the
 * built `dist/` app served by a mocked socket.io server (e2e/mock-server.mjs),
 * no Flask/Docker involved. mock-server.mjs answers `request_map_data`
 * (auto-emitted by the client's refreshAuthoritativeState() on connect) with
 * the canned, mid-reveal `map_data_response` fixture -- a checked-in,
 * hand-maintained, server-shaped spoiler-safe projection (see
 * src/components/sheet/__fixtures__/mapDataMidReveal.json).
 *
 * Component-level behavior (reveal/diff/pan-zoom/cache semantics) is already
 * covered exhaustively by MapTab.test.tsx (mocked mapper-lib) and
 * MapTab.integration.test.tsx (real mapper-lib, jsdom). This spec's job is
 * narrower and complementary: prove the whole stack wires together in an
 * actual browser -- the Map tab button exists, clicking it renders the real
 * SVG the vendored mapper produces from a genuine server-shaped payload, and
 * the fog-of-war spoiler boundary holds in that real DOM.
 */

const REDACTED_ROOM_REAL_NAME = 'Militia Barracks' // A04, deliberately unrevealed in the fixture

test('Map tab renders a real fog-of-war SVG from a server-shaped payload', async ({ page }) => {
  await page.goto('/play/')
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('tab', { name: 'Map' }).click()

  const svg = page.locator('svg[data-mapper]')
  await expect(svg).toBeVisible()

  const roomGroups = svg.locator('[data-room]')
  await expect(roomGroups).toHaveCount(6) // the fixture's 6 rooms (A01-A06)

  // Spoiler audit: an unrevealed room's real name must never reach the DOM.
  await expect(page.locator('svg[data-mapper]')).not.toContainText(REDACTED_ROOM_REAL_NAME)

  // Toolbar sanity: the Map tab's own fit/whole buttons are present and
  // enabled once a map exists. The glyph-prefixed labels ("⊙ fit", "▭ whole")
  // are unique in the shell, so a plain accessible-name match is unambiguous.
  await expect(page.getByRole('button', { name: '⊙ fit' })).toBeEnabled()
  await expect(page.getByRole('button', { name: '▭ whole' })).toBeEnabled()
})

test('theme toggle persists across reload and the expand view opens and closes', async ({ page }) => {
  await page.goto('/play/')
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: '☀ day' }).click()
  await expect(page.getByRole('button', { name: '☾ night' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.neq-map-tab')).toHaveAttribute('data-map-theme', 'night')
  await page.reload()
  await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('button', { name: '☾ night' })).toBeVisible()
  await page.getByRole('button', { name: '⤢ expand' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.locator('svg[data-mapper]')).toBeVisible()
  await expect(dialog.getByText(/places discovered/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('button', { name: '⤢ expand' })).toBeFocused()
})
