/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        panel: "var(--panel)",
        line: "var(--line)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        acid: "#b9f36a",
        lilac: "#aab3ff",
        coral: "#ff8d6b"
      },
      fontFamily: {
        sans: ["DM Sans Variable", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"]
      },
      boxShadow: {
        float: "0 28px 90px rgba(0,0,0,.28)",
        glow: "0 0 60px rgba(185,243,106,.12)"
      }
    }
  },
  plugins: []
};
