import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
    channel: process.env.CI ? undefined : 'msedge',
    headless: true,
    video: process.env.CI ? 'off' : 'on',
  },
  webServer: [
    {
      command: '.\\.venv\\Scripts\\python.exe -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8100',
      cwd: '../..',
      url: 'http://127.0.0.1:8100/api/v1/health',
      reuseExistingServer: process.env.E2E_REUSE_SERVER === '1',
      env: {
        LLM_PROVIDER: 'mock',
        EMBEDDING_PROVIDER: 'hash',
        CROSS_ENCODER_ENABLED: 'false',
        LANGFUSE_ENABLED: 'false',
      },
    },
    {
      command: 'npm run dev -- --port 5174',
      cwd: '.',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: process.env.E2E_REUSE_SERVER === '1',
      env: { VITE_API_PROXY_TARGET: 'http://127.0.0.1:8100' },
    },
  ],
})
