import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // Ensure 'base' is set to the GCS URL for production
  base: mode === 'production' 
    ? 'https://storage.googleapis.com/airsports-static/' 
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
        entryFileNames: `js/[name]-bundle.js`,
        chunkFileNames: `js/[name]-chunk.js`,
        assetFileNames: (assetInfo) => {
          // Keep CSS in css/ folder
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'css/[name].css';
          }
          // Put other assets (images, fonts) in an assets/ folder
          return 'assets/[name][extname]';
        },
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
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
