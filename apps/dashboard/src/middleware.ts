import { NextResponse, type NextRequest } from "next/server";

/**
 * Middleware de auth.
 *
 * Si no hay cookie `wcm_session`, redirige a /login conservando el path
 * solicitado en `?from=` para volver tras autenticar.
 *
 * Excluye rutas estáticas, login y endpoint público de opt-out.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Rutas públicas
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/") || // rewrite al API real
    pathname === "/favicon.ico" ||
    pathname === "/opt-out"
  ) {
    return NextResponse.next();
  }

  const session = request.cookies.get("wcm_session");
  if (!session) {
    const loginUrl = new URL("/login", request.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("from", pathname);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match todas las rutas excepto:
     * - api/* (rewrites manejados aparte)
     * - _next/static, _next/image
     * - favicon
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
