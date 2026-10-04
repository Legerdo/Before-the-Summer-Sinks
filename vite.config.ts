import { defineConfig } from "vite";

// Relative base so the build works from Electron's app:// protocol and any static host.
export default defineConfig({
  base: "./",
  publicDir: "public",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 2000,
  },
  // Unusual ports: other projects on this machine already use the common Vite ports.
  server: { port: 47813, strictPort: true },
  preview: { port: 47814, strictPort: true },
});
