import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  base: "/ui/",
  server: {
    proxy: {
      "/users":  "http://localhost:8000",
      "/brews":  "http://localhost:8000",
      "/stats":  "http://localhost:8000",
      "/status": "http://localhost:8000",
      "/kiosk":  "http://localhost:8000",
      "/ws":     { target: "ws://localhost:8000", ws: true },
    },
  },
})
