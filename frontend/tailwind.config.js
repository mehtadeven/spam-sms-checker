/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14243b",
        muted: "#69788c",
        brand: "#2563eb",
      },
    },
  },
  plugins: [],
};
