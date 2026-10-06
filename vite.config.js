import { defineConfig } from "vite";

export default defineConfig({
  // Relative base so the build works from any path, including a subdirectory.
  base: "./",
  build: {
    target: "es2022",
    outDir: "dist",
    assetsDir: "assets",
    // The content bundle is already compact; inlining it would only bloat JS.
    assetsInlineLimit: 4096,
    // ~500 KB is almost entirely CodeMirror, which every implement step needs.
    // Splitting it would only move the same bytes behind a second request.
    chunkSizeWarningLimit: 700,
  },
  server: {
    port: 5273,
    open: true,
  },
  // Pyodide is loaded from a CDN inside a classic worker, not bundled.
  optimizeDeps: {
    exclude: ["pyodide"],
  },
});
