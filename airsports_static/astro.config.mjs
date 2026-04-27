// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  // Use /static/ in production so assets are served via Django/CDN.
  // In development, Astro's internal server handles its own assets.
  base: process.env.NODE_ENV === 'production' ? '/static/' : '/',
  srcDir: './src',
  publicDir: './public',
  outDir: './dist',
  build: {
    // Keep assets in a subfolder within /static/ to avoid root clutter
    assets: '_astro'
  },
  vite: {
    plugins: [tailwindcss()],
    css: {
      transformer: 'lightningcss',
    },
    build: {
      cssMinify: 'lightningcss',
      minify: 'terser',
    }
  }
});
