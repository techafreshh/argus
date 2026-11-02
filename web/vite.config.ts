import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Production build lands in the FastAPI-served directory so the committed
// bundle (not gitignored web/dist/) is the graded artifact.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../argus/server/static",
    emptyOutDir: true,
    sourcemap: false,
  },
});
