// Sentry — config del browser (client components).
//
// Sin NEXT_PUBLIC_SENTRY_DSN, no se inicializa (perezoso, igual que API/worker).
// El DSN es público por diseño en clientes browser: Sentry lo acepta y filtra
// por origin/whitelist en su panel.

import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: Number(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.2",
    ),
    replaysOnErrorSampleRate: 0,
    replaysSessionSampleRate: 0,
    // PII off — el dashboard interno no debe enviar datos personales a Sentry.
    sendDefaultPii: false,
    initialScope: {
      tags: { component: "dashboard" },
    },
  });
}
