import { defineConfig } from '@playwright/test'

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  ?? (process.platform === 'win32'
    ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
    : undefined)
const deterministicParityRaster = process.env.NEQ_PARITY_DISABLE_GPU === '1'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: 'list',
  webServer: externalBaseUrl ? undefined : {
    command: 'node e2e/mock-server.mjs',
    port: 4174,
    reuseExistingServer: true,
  },
  use: {
    baseURL: externalBaseUrl ?? 'http://127.0.0.1:4174',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      ...(executablePath ? { executablePath } : {}),
      // Chromium may independently promote one of the legacy/React pages to
      // a GPU compositing layer. That changes anti-aliasing around otherwise
      // identical rounded edges. The strict pixel oracle can opt both pages
      // into the same software raster path without changing either product.
      ...(deterministicParityRaster ? { args: ['--disable-gpu-compositing'] } : {}),
    },
  },
})
