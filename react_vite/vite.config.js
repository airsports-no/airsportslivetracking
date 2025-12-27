import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path';
import fs from 'fs';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/', // This should match Django's settings.STATIC_URL
  build: {
    rollupOptions: {
      // Dynamically create entry points from files in the 'containers' directory that end with .jsx or .tsx.
      input: Object.fromEntries(
        fs.readdirSync(path.resolve(__dirname, 'src/Apps'))
          .filter(f => f.endsWith('.jsx') || f.endsWith('.tsx'))
          .map(f => {
            const ext = path.extname(f); // Get the file extension
            const name = path.basename(f, ext); // Get the filename without the extension
            const resolvedPath = path.resolve(__dirname, `src/Apps/${f}`);
            return [name, resolvedPath];
          }),
      ),
      output: {
        // Output JS bundles to js/ directory with -bundle suffix
        entryFileNames: `js/[name]-bundle.js`,
        assetFileNames: `css/[name].css`,
      },
    },
    manifest: "manifest.json",
    outDir: path.resolve(__dirname, '../src/vite_static'), // Output directory for built assets
    emptyOutDir: true, // Clean output directory before building
  },
})
