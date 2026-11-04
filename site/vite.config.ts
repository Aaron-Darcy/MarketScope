import { copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

const siteRoot = fileURLToPath(new URL('.', import.meta.url));
const exportDir = fileURLToPath(new URL('../data/site', import.meta.url));
const outDir = fileURLToPath(new URL('./build', import.meta.url));

// GitHub Pages has no rewrite rules, so a deep link such as /MarketScope/banks/19617 is
// answered with 404.html. Serving the app from that file lets the router take the path.
function githubPagesFallback(): Plugin {
  return {
    name: 'github-pages-fallback',
    apply: 'build',
    async closeBundle() {
      await copyFile(`${outDir}/index.html`, `${outDir}/404.html`);
    },
  };
}

export default defineConfig({
  base: '/MarketScope/',
  plugins: [react(), githubPagesFallback()],
  build: {
    outDir,
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    // Every table is published as its own file, however small, so the deployed site carries
    // the export as committed rather than some of it folded into the script.
    assetsInlineLimit: (file) => (file.endsWith('.parquet') ? false : undefined),
  },
  // The committed export sits outside the site directory (decision 0044).
  server: { fs: { allow: [siteRoot, exportDir] } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
