// Sentry — server components, route handlers, server actions.

import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN_DASHBOARD;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.2"),
    sendDefaultPii: false,
    initialScope: {
      tags: { component: "dashboard-server" },
    },
  });
}
