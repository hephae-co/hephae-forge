import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
    // Load env file based on `mode` in the current working directory.
    // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
    const env = loadEnv(mode, process.cwd(), '');

    return {
        plugins: [react()],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './src'),
                // Stub optional ADK database drivers that aren't installed
                '@mikro-orm/mariadb': path.resolve(__dirname, './src/tests/helpers/noop.ts'),
                '@mikro-orm/mssql': path.resolve(__dirname, './src/tests/helpers/noop.ts'),
            },
        },
        test: {
            environment: 'jsdom',
            globals: true,
            hookTimeout: 120_000, // Cleanup hooks may call Firestore/BQ deletes
            setupFiles: ['./src/tests/setup.ts'],
            include: ['src/tests/**/*.test.{ts,tsx}'],
            // Force Vite to process @google/adk so our aliases for
            // optional deps (@mikro-orm/*) are resolved through Vite
            server: {
                deps: {
                    inline: [/@google\/adk/],
                },
            },
            // Load all vars from .env into test environment
            env: {
                ...env,
            }
        },
    };
});
