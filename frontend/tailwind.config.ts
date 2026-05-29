import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Google Sans",
          "Product Sans",
          "var(--font-space-grotesk)",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "var(--font-space-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        phone: "0 28px 90px rgba(0, 0, 0, 0.34)",
      },
    },
  },
  plugins: [],
};

export default config;
