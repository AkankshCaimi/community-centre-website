import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // The shadcn components import from "@/..." (docs/specs/ui-theme.md, D2).
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  server: {
    // During development the form talks to the Flask backend.
    proxy: { "/api": "http://127.0.0.1:5000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.js"],
  },
});
