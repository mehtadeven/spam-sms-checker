/** @type {import('tailwindcss').Config} */
// "Security console" theme: near-black greens, emerald for safe/brand,
// rose for danger, amber for caution. Space Grotesk + IBM Plex Mono.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: "#07110d",
        console: "#030806",
        panel: "#0d1a15",
        panel2: "#12241d",
        line: "#1f3a31",
        ink: "#e8f3ee",
        muted: "#8aa79c",
        brand: "#10b981",
        danger: "#f43f5e",
        warn: "#f59e0b",
      },
      fontFamily: {
        sans: ['"Space Grotesk Variable"', "system-ui", "Segoe UI", "Roboto", "Arial", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
