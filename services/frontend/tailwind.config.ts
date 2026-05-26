import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas:   "rgb(var(--color-canvas) / <alpha-value>)",
        card:     "rgb(var(--color-card) / <alpha-value>)",
        elevated: "rgb(var(--color-elevated) / <alpha-value>)",
        sidebar:  "rgb(var(--color-sidebar) / <alpha-value>)",
        border:   "rgb(var(--color-border) / <alpha-value>)",
        brand: {
          DEFAULT: "rgb(var(--color-brand) / <alpha-value>)",
          hover:   "rgb(var(--color-brand-hover) / <alpha-value>)",
          subtle:  "rgb(var(--color-brand-subtle) / <alpha-value>)",
        },
        tx: {
          primary:   "rgb(var(--color-tx-primary) / <alpha-value>)",
          secondary: "rgb(var(--color-tx-secondary) / <alpha-value>)",
          muted:     "rgb(var(--color-tx-muted) / <alpha-value>)",
          inverse:   "rgb(var(--color-tx-inverse) / <alpha-value>)",
        },
        status: {
          good: "rgb(var(--color-status-good) / <alpha-value>)",
          warn: "rgb(var(--color-status-warn) / <alpha-value>)",
          bad:  "rgb(var(--color-status-bad) / <alpha-value>)",
          info: "rgb(var(--color-status-info) / <alpha-value>)",
        },
      },
      fontFamily: {
        heading: ["Plus Jakarta Sans", "sans-serif"],
        body:    ["Inter", "sans-serif"],
        mono:    ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card:    "0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.3)",
        "card-hover": "0 4px 16px 0 rgb(31 63 254 / 0.15), 0 2px 8px -2px rgb(0 0 0 / 0.4)",
        glow:    "0 0 20px rgb(31 63 254 / 0.35)",
        "glow-sm": "0 0 10px rgb(31 63 254 / 0.25)",
        "status-good": "0 0 12px rgb(52 211 153 / 0.3)",
        "status-bad":  "0 0 12px rgb(248 113 113 / 0.3)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "fade-in":    "fadeIn 0.4s ease-out forwards",
        "slide-up":   "slideUp 0.4s cubic-bezier(0.16,1,0.3,1) forwards",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:  { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: { "0%": { opacity: "0", transform: "translateY(16px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 10px rgb(31 63 254 / 0.2)" },
          "50%":      { boxShadow: "0 0 24px rgb(31 63 254 / 0.5)" },
        },
      },
      transitionTimingFunction: {
        spring:   "cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      backgroundImage: {
        "gradient-brand": "linear-gradient(135deg, #1F3FFE 0%, #4F46E5 100%)",
        "gradient-dark":  "linear-gradient(180deg, #0A0E1F 0%, #06091A 100%)",
        "gradient-card":  "linear-gradient(135deg, rgb(var(--color-card)) 0%, rgb(var(--color-elevated)) 100%)",
        "noise":          "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E\")",
      },
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
    },
  },
  plugins: [],
};

export default config;
