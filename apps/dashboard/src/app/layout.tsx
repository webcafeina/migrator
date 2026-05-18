import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

/**
 * JetBrains Mono en TODO el UI por preferencia del operador.
 * Coherente con la naturaleza técnica de la herramienta (densidad de
 * tablas, mucho dato, estética terminal).
 */
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Webcafeína Migrator",
  description:
    "Dashboard interno de Webcafeína para prospección comercial y migración técnica de webs Wix/Hostinger/Webflow a WordPress + Bricks Builder.",
  robots: { index: false, follow: false }, // Herramienta interna
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // `suppressHydrationWarning` solo aquí — las extensiones del
    // navegador (LanguageTool, Grammarly, Dark Reader…) inyectan
    // atributos en `<html>` y `<body>` tras el SSR pero antes del
    // mount, lo que React detecta como hydration mismatch. Es el
    // patrón oficial documentado por Next.js para este caso. NO se
    // propaga a hijos.
    <html
      lang="es"
      className={`dark ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body suppressHydrationWarning>
        {children}
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#2B1A0E",
              border: "1px solid #5A3519",
              color: "#F2E8D2",
              fontFamily: "var(--font-jetbrains), ui-monospace, monospace",
            },
          }}
        />
      </body>
    </html>
  );
}
