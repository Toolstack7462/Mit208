/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy used for the sidebar / brand chrome (matches MIHE prototype).
        navy: {
          DEFAULT: "#0b1430",
          800: "#152149",
          900: "#0b1430",
          950: "#070d20",
        },
        brand: {
          DEFAULT: "#2f6bff",
          50: "#eef3ff",
          100: "#dde7ff",
          600: "#2f6bff",
          700: "#2456d6",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)",
        cardhover: "0 4px 12px rgba(16,24,40,0.08)",
      },
      borderRadius: {
        xl: "0.875rem",
      },
    },
  },
  plugins: [],
};
