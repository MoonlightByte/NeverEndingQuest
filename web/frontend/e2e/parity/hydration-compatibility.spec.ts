import { expect, test } from '@playwright/test'

const modes = ['legacy', 'correlated', 'mixed', 'delayed'] as const

for (const mode of modes) {
  test(`React hydrates location and six character chips in ${mode} response mode`, async ({ page, request }) => {
    test.skip(Boolean(process.env.PLAYWRIGHT_BASE_URL), 'Exercises the bundled mock server compatibility modes')
    const response = await request.post(`/__e2e__/hydration/${mode}`)
    expect(response.ok()).toBe(true)
    await page.goto('/play/')
    await expect(page.getByText('Forsaken Crossroads (Stormglass Coast)', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('[aria-label="Party members"] [data-chip]')).toHaveCount(6, { timeout: 15_000 })
  })
}
