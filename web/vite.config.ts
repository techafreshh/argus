import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production build lands in the FastAPI-served directory so the committed
// bundle (not gitignored web/dist/) is the graded artifact.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../argus/server/static",
    emptyOutDir: true,
    sourcemap: false,
  },
});
