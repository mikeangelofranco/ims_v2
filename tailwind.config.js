/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/*.py",
    "./static/src/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "#2563EB",
          hover: "#1D4ED8",
          active: "#1E40AF",
        },
        status: {
          success: "#16A34A",
          warning: "#F59E0B",
          danger: "#DC2626",
          info: "#0891B2",
        },
        content: {
          primary: "#0F172A",
          secondary: "#475569",
          muted: "#94A3B8",
        },
        canvas: "#F8FAFC",
        surface: "#FFFFFF",
        ui: {
          default: "#E2E8F0",
          input: "#CBD5E1",
          sidebar: "#E5E7EB",
        },
        "info-accent": "#0EA5E9",
      },
      backgroundImage: {
        "gradient-brand": "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)",
        "gradient-info": "linear-gradient(135deg, #0891B2 0%, #0EA5E9 100%)",
      },
      borderRadius: {
        DEFAULT: "12px",
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.08)",
        elevated: "0 10px 25px -5px rgb(15 23 42 / 0.12), 0 8px 10px -6px rgb(15 23 42 / 0.08)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

