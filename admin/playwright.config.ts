import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './src/tests/e2e',
    testMatch: '**/*.spec.ts',
    use: {
        baseURL: 'http://localhost:3000',
    },
    webServer: {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
    },
});
