import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: browser talks only to :5173; /api is forwarded to the FastAPI backend.
// This keeps dev same-origin so there is no cookie/CORS trap at all.
//
// NOTE ON WINDOWS APP-CONTROL MACHINES: some corporate Windows setups block
// rollup's native .node binary (ERR_DLOPEN_FAILED), which breaks `vite build`.
// package.json uses an npm override to swap rollup for @rollup/wasm-node (a
// drop-in pure-JS build) so the bundle works even under that policy. On normal
// machines you can remove the override for the faster native compiler.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
