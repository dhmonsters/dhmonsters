import { dirname } from "node:path";
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const realProjectRoot = realpathSync.native(projectRoot);

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [projectRoot, realProjectRoot],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
