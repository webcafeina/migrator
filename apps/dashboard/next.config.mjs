/** @type {import('next').NextConfig} */
const nextConfig = {
  // Build standalone para systemd: produce .next/standalone/server.js
  // (ver infra/systemd/webcafeina-dashboard.service en Fase 12)
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // El API vive en /api/* del mismo dominio en producción (Nginx proxy).
  // En dev, API_URL apunta a http://localhost:8000.
  async rewrites() {
    const apiUrl = process.env.API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
      {
        source: "/api/auth/:path*",
        destination: `${apiUrl}/api/v1/auth/:path*`,
      },
    ];
  },
};

export default nextConfig;
