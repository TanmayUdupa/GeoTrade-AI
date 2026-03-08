// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/risk": "http://localhost:8003",
      "/compare": "http://localhost:8003",
      "/forecast": "http://localhost:8004",
      "/volatility": "http://localhost:8004",
      "/alternatives": "http://localhost:8004",
      "/alerts": "http://localhost:8005",
      "/ingest": "http://localhost:8001",
    }
  }
});
