import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  // El plugin React configura el JSX automatic runtime (React 19) para
  // que los .tsx no necesiten `import React from "react"` en cada archivo.
  // Sin el plugin, esbuild de Vite cae al runtime clásico y los componentes
  // fallan con "React is not defined" al ejecutarse en Vitest.
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: false,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    exclude: ["tests/e2e/**", "node_modules/**", ".next/**"],
    setupFiles: ["./tests/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
