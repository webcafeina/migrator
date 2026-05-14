import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

/**
 * Tailwind con la paleta Webcafeína (CLAUDE.md §3).
 *
 * Decisiones:
 * - Paleta extendida (no override del namespace de Tailwind), accesible
 *   como `bg-wcm-primary`, `text-wcm-accent`, etc.
 * - Fuente mono única en todo el UI (JetBrains Mono) según preferencia
 *   del operador — coherente con la naturaleza técnica de la herramienta.
 * - Border radius reducido (4-8px) para look técnico-denso.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        wcm: {
          primary: "#0E1218",   // Background primario (azul marino casi negro)
          secondary: "#1A222D", // Background secundario (azul marino oscuro)
          text: "#E2E8F0",      // Texto claro (gris claro azulado)
          detail: "#3D4A5C",    // Detalle (azul gris medio: bordes, separadores)
          accent: "#B1F100",    // Lima — solo CTAs/numeración/datos clave
          danger: "#FF5252",
          warning: "#FFAB00",
        },
        // Aliases shadcn-compatible para los componentes generados
        border: "#3D4A5C",
        input: "#1A222D",
        ring: "#B1F100",
        background: "#0E1218",
        foreground: "#E2E8F0",
        primary: {
          DEFAULT: "#B1F100",
          foreground: "#0E1218",
        },
        secondary: {
          DEFAULT: "#1A222D",
          foreground: "#E2E8F0",
        },
        destructive: {
          DEFAULT: "#FF5252",
          foreground: "#E2E8F0",
        },
        muted: {
          DEFAULT: "#1A222D",
          foreground: "#56657A",
        },
        accent: {
          DEFAULT: "#B1F100",
          foreground: "#0E1218",
        },
        popover: {
          DEFAULT: "#1A222D",
          foreground: "#E2E8F0",
        },
        card: {
          DEFAULT: "#1A222D",
          foreground: "#E2E8F0",
        },
      },
      fontFamily: {
        // JetBrains Mono via next/font (configurado en app/layout.tsx).
        // La var CSS --font-jetbrains se setea allí.
        sans: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "8px",
        md: "6px",
        sm: "4px",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [animate],
};

export default config;
