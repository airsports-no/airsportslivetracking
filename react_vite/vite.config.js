import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path';
import fs from 'fs';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/', // This should match Django's settings.STATIC_URL
  resolve: {
    alias: {
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
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
        assetFileNames: `css/[name].css`,
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
})
