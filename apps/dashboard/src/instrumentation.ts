// Next.js 15 hook: se ejecuta una vez al arrancar el server runtime.
// Carga el config Sentry adecuado según el runtime (nodejs | edge).

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  } else if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}
