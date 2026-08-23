import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
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
          if (id.includes('node_modules')) {
            if (id.includes('vis-timeline') || id.includes('vis-data')) {
              return 'vis';
            }
            if (id.includes('moment')) {
              return 'moment';
            }
            if (id.includes('leaflet')) {
              return 'leaflet';
            }
            return 'vendor';
          }
        },
      },
    },
    manifest: "manifest.json",
    outDir: path.resolve(__dirname, '../assets_vite'), // Output directory for built assets
    emptyOutDir: true, // Clean output directory before building
  },
}));
