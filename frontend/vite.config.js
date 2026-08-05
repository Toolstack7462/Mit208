import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    // Component tests need a DOM; node's default environment has none.
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
    css: false,
    coverage: {
      reporter: ["text", "html"],
      include: ["src/**/*.{js,jsx}"],
      exclude: ["src/main.jsx", "src/test/**"],
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to the FastAPI backend during development.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
