/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy used for the sidebar / brand chrome.
        navy: {
          DEFAULT: "#0b1437",
          50: "#eef1fb",
          800: "#111c44",
          900: "#0b1437",
          950: "#070d24",
        },
        brand: {
          DEFAULT: "#2f6bff",
          600: "#2f6bff",
          700: "#2455d6",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(16,24,40,0.1), 0 1px 2px rgba(16,24,40,0.06)",
      },
    },
  },
  plugins: [],
};
