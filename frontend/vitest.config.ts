import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    // The data tests are pure TypeScript with no DOM and no network, so they
    // run anywhere -- including CI with the backend stopped, which is the
    // point: this content is what a demo depends on.
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
