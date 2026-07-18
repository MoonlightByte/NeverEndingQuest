import { expect, type BrowserContext, type Locator, type Page } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const canonicalViewport = { width: 2048, height: 1228 }
export const parityOutputRoot = process.env.NEQ_PARITY_OUTPUT
  ?? path.join(os.tmpdir(), 'neverendingquest-strict-parity')

const here = path.dirname(fileURLToPath(import.meta.url))
const pixelOracle = path.join(here, 'pixel_oracle.py')

export type PixelMetrics = {
  expected: string
  actual: string
  expected_size: [number, number]
  actual_size: [number, number]
  differing_pixels: number
  total_pixels: number
  difference_ratio: number
  bounding_box: [number, number, number, number] | null
  error?: string
}

/** Install before navigation so both applications see identical entropy/time. */
export async function installDeterminism(
  context: BrowserContext,
  options: { dismissBanner?: boolean } = {},
) {
  const dismissBanner = options.dismissBanner ?? true
  await context.addInitScript(({ shouldDismissBanner }) => {
    const epoch = Date.parse('2026-07-18T14:20:00Z')
    const NativeDate = Date
    class FrozenDate extends NativeDate {
      constructor(...args: ConstructorParameters<typeof Date>) {
        super(...(args.length === 0 ? [epoch] : args))
      }
      static now() { return epoch }
    }
    Object.defineProperty(window, 'Date', { value: FrozenDate })

    // A constant is deliberate: the legacy and React trees consume random
    // values at different times during bootstrap. A shared PRNG seed would
    // still drift by call count before Reset/Compression opens. This fixed
    // value makes their user-visible random choices identical (reset code
    // 21250 and the first compression flavor) without touching production.
    Math.random = () => 0.125
    const originalGetRandomValues = crypto.getRandomValues.bind(crypto)
    crypto.getRandomValues = (<T extends ArrayBufferView | null>(array: T): T => {
      if (array instanceof Uint32Array) {
        for (let index = 0; index < array.length; index += 1) {
          array[index] = 19
        }
        return array as T
      }
      return originalGetRandomValues(array)
    }) as Crypto['getRandomValues']
    if (shouldDismissBanner) localStorage.setItem('neq_bannerDismissed', 'true')
  }, { shouldDismissBanner: dismissBanner })
}

/**
 * Declare a meaningful scrolled state that must survive freezePage().  The
 * default oracle still normalizes incidental browser/component scrolling to
 * zero; only positions named by a test are retained across warmup + duplicate
 * screenshots.  Attributes intentionally live on the disposable page DOM,
 * not in either application source.
 */
export async function declareScrollPosition(
  locator: Locator,
  position: { top?: number; left?: number },
) {
  await locator.evaluate((element, requested) => {
    const target = element as HTMLElement
    const top = requested.top ?? target.scrollTop
    const left = requested.left ?? target.scrollLeft
    target.setAttribute('data-neq-parity-scroll-top', String(top))
    target.setAttribute('data-neq-parity-scroll-left', String(left))
    target.scrollTop = top
    target.scrollLeft = left
    target.dispatchEvent(new Event('scroll', { bubbles: false }))
  }, position)
}

/** Freeze only nondeterminism; do not restyle either product surface. */
export async function freezePage(page: Page) {
  await page.addStyleTag({ content: `
    *, *::before, *::after {
      animation-delay: 0s !important;
      animation-play-state: paused !important;
      caret-color: transparent !important;
      transition-delay: 0s !important;
      transition-duration: 0s !important;
    }
    /* Infinite shimmer is the one animated pixel surface shared by both
       headers. Lock both implementations to their keyframe-zero value; merely
       pausing independent CSSAnimation objects can retain different hold
       times even when their reported currentTime is subsequently assigned. */
    .header h1, .neq-shimmer-title {
      animation: none !important;
      background-position: 0% 50% !important;
    }
  ` })
  await page.evaluate(async () => {
    await document.fonts.ready
    const normalizeAnimation = (animation: Animation) => {
      const endTime = animation.effect?.getComputedTiming().endTime
      if (typeof endTime === 'number' && Number.isFinite(endTime)) {
        // Finite entrance/exit animations are part of the final UI state, not
        // a source of ongoing entropy.  Holding them at t=0 can make content
        // such as the legacy Save details remain fully transparent.  Advance
        // them to their natural end instead; CSS then exposes the same
        // underlying end state a user sees after the short animation.
        try {
          animation.finish()
        } catch {
          animation.currentTime = endTime
          animation.pause()
        }
        return
      }
      // Infinite decorative animations never have a final state.  Normalize
      // those to a shared phase and hold them there for duplicate captures.
      animation.pause()
      animation.currentTime = 0
    }
    const animations = document.getAnimations({ subtree: true })
    await Promise.all(animations.map((animation) => animation.ready.catch(() => undefined)))
    for (const animation of animations) normalizeAnimation(animation)
    for (const video of document.querySelectorAll('video')) {
      video.pause()
      try { video.currentTime = 0 } catch { /* video may have no seekable data */ }
    }
    await Promise.all([...document.images].map((image) => {
      if (image.complete) return Promise.resolve()
      return new Promise<void>((resolve) => {
        image.addEventListener('load', () => resolve(), { once: true })
        image.addEventListener('error', () => resolve(), { once: true })
      })
    }))
    const restoreDeclaredScroll = () => {
      for (const element of document.querySelectorAll<HTMLElement>('[data-neq-parity-scroll-top], [data-neq-parity-scroll-left]')) {
        const top = Number(element.getAttribute('data-neq-parity-scroll-top') ?? '0')
        const left = Number(element.getAttribute('data-neq-parity-scroll-left') ?? '0')
        if (Number.isFinite(top)) element.scrollTop = top
        if (Number.isFinite(left)) element.scrollLeft = left
      }
    }
    for (const element of document.querySelectorAll<HTMLElement>('*')) {
      if (!element.hasAttribute('data-neq-parity-scroll-top')) element.scrollTop = 0
      if (!element.hasAttribute('data-neq-parity-scroll-left')) element.scrollLeft = 0
    }
    restoreDeclaredScroll()
    window.scrollTo(0, 0)
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    // Finishing or assigning currentTime schedules a style update. Reassert
    // the correct finite/infinite policy after the two-frame flush so neither
    // kind can retain a capture-time phase.
    for (const animation of document.getAnimations({ subtree: true })) normalizeAnimation(animation)
    // Finishing animations and the two-frame style flush can run component
    // layout effects. Reassert the explicitly declared oracle position after
    // that work, without emitting another scroll event that could mutate UI.
    restoreDeclaredScroll()
    void document.documentElement.offsetHeight
  })
}

export async function settleApplication(page: Page, legacy: boolean) {
  if (legacy) {
    await expect(page.locator('#status-indicator')).toHaveClass(/connected/, { timeout: 15_000 })
  } else {
    await expect(page.getByLabel('Connected')).toBeVisible({ timeout: 15_000 })
  }
  await expect(page.getByText('Mosswatch Gate', { exact: false }).first()).toBeVisible({ timeout: 15_000 })
  const chips = legacy
    ? page.locator('#party-display-container > .party-member-item, #party-display-container > .location-npc-item')
    : page.locator('[aria-label="Party members"] [data-chip]')
  await expect(chips, `${legacy ? 'Legacy' : 'React'} must hydrate all six top character chips`).toHaveCount(6, { timeout: 15_000 })
  await expect(legacy ? page.locator('.character-name') : page.getByAltText('Portrait of Arden Vale')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Mosswatch answers with a low silver bell. The road ahead is open.', { exact: true })).toBeVisible({ timeout: 15_000 })
  await freezePage(page)
}

export async function comparePixels(expected: string, actual: string, artifactStem: string): Promise<PixelMetrics> {
  const diff = path.join(parityOutputRoot, `${artifactStem}-diff.png`)
  const report = path.join(parityOutputRoot, `${artifactStem}-report.json`)
  await fs.mkdir(parityOutputRoot, { recursive: true })
  const result = spawnSync(process.env.PYTHON ?? 'python', [
    pixelOracle,
    expected,
    actual,
    '--diff', diff,
    '--report', report,
  ], { encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(`Pixel oracle failed (${result.status}): ${result.stderr || result.stdout}`)
  }
  return JSON.parse(result.stdout.trim()) as PixelMetrics
}

export async function captureStable(
  page: Page,
  stem: string,
  side: 'legacy' | 'react',
  options: { clip?: { x: number; y: number; width: number; height: number } } = {},
) {
  await freezePage(page)
  const first = path.join(parityOutputRoot, `${stem}-${side}.png`)
  const duplicate = path.join(parityOutputRoot, `${stem}-${side}-duplicate.png`)
  const warmup = path.join(parityOutputRoot, `${stem}-${side}-warmup.png`)
  await fs.mkdir(parityOutputRoot, { recursive: true })
  // Socket polling can commit an otherwise identical React tree between two
  // screenshots and cause a handful of glyph-edge pixels to be rerasterized.
  // Freeze JavaScript only for the capture transaction, warm the compositor,
  // then take the two oracle images from the exact same rendered frame. This
  // does not mask or tolerate pixels; the duplicate comparator remains zero.
  const cdp = await page.context().newCDPSession(page)
  try {
    await cdp.send('Emulation.setScriptExecutionDisabled', { value: true })
    // Do not ask Playwright to disable animations here. Its screenshot helper
    // cancels and later recreates infinite CSS animations independently per
    // page, which reintroduced different shimmer phases after our exact
    // currentTime=0 normalization.
    await page.screenshot({ path: warmup, caret: 'hide', ...options })
    await page.screenshot({ path: first, caret: 'hide', ...options })
    await page.screenshot({ path: duplicate, caret: 'hide', ...options })
  } finally {
    await cdp.send('Emulation.setScriptExecutionDisabled', { value: false })
    await cdp.detach()
    await fs.rm(warmup, { force: true })
  }
  const stability = await comparePixels(first, duplicate, `${stem}-${side}-stability`)
  expect.soft(
    stability.differing_pixels,
    `${side} capture is nondeterministic; see ${stem}-${side}-stability-report.json`,
  ).toBe(0)
  return first
}

export async function assertNamedPair(stem: string) {
  const legacy = path.join(parityOutputRoot, `${stem}-legacy.png`)
  const react = path.join(parityOutputRoot, `${stem}-react.png`)
  const metrics = await comparePixels(legacy, react, `${stem}-legacy-v-react`)
  expect.soft(
    metrics.differing_pixels,
    `${stem} differs in ${metrics.differing_pixels}/${metrics.total_pixels} pixels (${(metrics.difference_ratio * 100).toFixed(4)}%); see external diff/report in ${parityOutputRoot}`,
  ).toBe(0)
  return metrics
}
