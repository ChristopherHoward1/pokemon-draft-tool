import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy backend routes so the client can run same-origin in dev — no
    // VITE_API_URL needed. `ws: true` also forwards the draft/lobby sockets.
    proxy: {
      "/session": { target: "http://localhost:8000", ws: true, changeOrigin: true },
      "/sprites": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
