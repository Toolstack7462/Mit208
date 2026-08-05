// Vitest setup, loaded before every test file (see vite.config.js -> test.setupFiles).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.localStorage.clear();
});

// jsdom implements neither of these, and both are used by the app.
if (!navigator.clipboard) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    writable: true,
  });
}

if (!window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
}
