import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    // Uploads this build's sourcemaps to Sentry (tagged with the same release string the
    // frontend runtime reports - see BUILD_ID in live_tracking_map/settings.py, injected via
    // display.context_processors.sentry_settings) so production JS crashes symbolicate to real
    // file/line/function instead of minified names. Only active when SENTRY_AUTH_TOKEN is set
    // (the Docker build passes it via a BuildKit secret, see Dockerfile) - a local `npm run
    // build`/`watch` without it just skips this plugin entirely, same as how the backend and
    // frontend Sentry SDKs stay inactive without a DSN.
    process.env.SENTRY_AUTH_TOKEN &&
      sentryVitePlugin({
        org: 'airports-live-tracking',
        project: 'javascript-react',
        authToken: process.env.SENTRY_AUTH_TOKEN,
        release: { name: process.env.SENTRY_RELEASE },
        // Deliberately NOT using sourcemaps.filesToDeleteAfterUpload here: verified locally that
        // it deletes the local .map files even when the Sentry upload itself fails (e.g. a bad
        // token - 401), which would silently ship a release with no sourcemaps anywhere (not in
        // Sentry, not in /static/) instead of today's status quo of "unused but at least present"
        // public maps. Leaving them in /static/ is an existing, pre-this-change tradeoff (source
        // is already exposed there today), not one this fix should risk making worse.
      }),
  ],
  test: {
    globals: true,
    // Pure-logic tests run fine in plain node; a file that needs a DOM
    // (e.g. testing something that touches Leaflet/browser APIs) opts in
    // per-file with a `// @vitest-environment jsdom` comment rather than
    // paying the jsdom cost for every test.
    environment: 'node',
  },
  // Use /static/ for production to leverage same-origin GCLB/CDN caching.
  base: mode === 'production' 
    ? '/static/' 
    : '/static/',
  resolve: {
    alias: {
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
    sourcemap: true,
    rollupOptions: {
      // Dynamically create entry points from files in the 'containers' directory that end with .jsx or .tsx.
      input: Object.fromEntries(
        fs.readdirSync(path.resolve(__dirname, 'src'))
          .filter(f => f.endsWith('.jsx') || f.endsWith('.tsx'))
          .map(f => {
            const ext = path.extname(f); // Get the file extension
            const name = path.basename(f, ext); // Get the filename without the extension
            const resolvedPath = path.resolve(__dirname, `src/${f}`);
            return [name, resolvedPath];
          }),
      ),
      output: {
        // Output JS bundles to js/ directory with -bundle suffix
        entryFileNames: `js/[name]-[hash].js`,
        chunkFileNames: `js/[name]-[hash].js`,
        assetFileNames: (assetInfo) => {
          // Keep CSS in css/ folder
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'css/[name]-[hash].css';
          }
          // Put other assets (images, fonts) in an assets/ folder
          return 'assets/[name]-[hash][extname]';
        },
        manualChunks: (id) => {
          if (!id.includes('node_modules')) return;
          if (id.includes('vis-timeline') || id.includes('vis-data')) {
            return 'vis';
          }
          if (id.includes('moment')) {
            return 'moment';
          }
          if (id.includes('leaflet')) {
            return 'leaflet';
          }
          // recharts (and the d3 internals it pulls in) is only used by the admin-only flight
          // activity dashboard - splitting it out of the shared vendor chunk means every other
          // page stops shipping/parsing it on every load.
          if (id.includes('recharts') || id.includes('/d3-') || id.includes('victory-vendor')) {
            return 'recharts';
          }
          // Only the scheduling/mission-dashboard/contest-management forms use these - keeping
          // them out of vendor means pages that never render a form skip them entirely.
          if (
            id.includes('react-select') ||
            id.includes('rc-slider') ||
            id.includes('react-hook-form') ||
            id.includes('@hookform') ||
            id.includes('/zod/')
          ) {
            return 'forms';
          }
          if (id.includes('@tanstack/react-table')) {
            return 'table';
          }
          // Loaded from FrontendApp.tsx on every page regardless, so splitting it out doesn't
          // reduce first-load bytes - but it does mean a Sentry SDK bump no longer invalidates
          // every page's cached vendor chunk (and vice versa).
          if (id.includes('@sentry')) {
            return 'sentry';
          }
          return 'vendor';
        },
      },
    },
    manifest: "manifest.json",
    outDir: path.resolve(__dirname, '../assets_vite'), // Output directory for built assets
    emptyOutDir: true, // Clean output directory before building
  },
}));
