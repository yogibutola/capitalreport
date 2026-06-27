import { defineConfig, devices } from '@playwright/test';
import path from 'path';

export default defineConfig({
    testDir: path.join(__dirname, 'e2e'),
    timeout: 300_000,          // 5 minutes — full flow takes ~3–4 min
    expect: { timeout: 15_000 },
    fullyParallel: false,   // steps depend on each other — run serially
    retries: 0,
    workers: 1,
    reporter: [['html', { open: 'never' }], ['list']],

    use: {
        baseURL: 'http://localhost:4200',
        headless: false,    // set true for CI
        viewport: { width: 1280, height: 800 },
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
        trace: 'on-first-retry',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
});
