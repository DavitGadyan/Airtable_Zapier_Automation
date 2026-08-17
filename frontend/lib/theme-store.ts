/**
 * Resolved light/dark theme, as a `useSyncExternalStore` source.
 *
 * The 3D graph draws to a canvas and cannot use CSS variables, so it needs the
 * resolved theme as a value. Kept as an external store rather than React state
 * because the OS can change it while the page is open -- mid-recording, in the
 * worst case -- and the canvas has to repaint when that happens.
 */

export type ResolvedTheme = "light" | "dark";

const listeners = new Set<() => void>();
let current: ResolvedTheme = "light";
let mediaQuery: MediaQueryList | null = null;

function detect(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  const explicit = document.documentElement.dataset.theme;
  if (explicit === "dark" || explicit === "light") return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function publish() {
  const next = detect();
  if (next === current) return;
  current = next;
  for (const listener of listeners) listener();
}

export function subscribeResolved(onChange: () => void): () => void {
  listeners.add(onChange);

  if (typeof window !== "undefined" && !mediaQuery) {
    mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", publish);
    current = detect();
  }

  return () => {
    listeners.delete(onChange);
  };
}

export function getResolvedSnapshot(): ResolvedTheme {
  if (typeof window !== "undefined") current = detect();
  return current;
}

/**
 * Must return a stable value: returning a fresh one each call makes React
 * loop on hydration.
 */
export function getResolvedServerSnapshot(): ResolvedTheme {
  return "light";
}

export function setTheme(theme: ResolvedTheme | "system"): void {
  if (typeof document === "undefined") return;
  if (theme === "system") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = theme;
  }
  publish();
}
