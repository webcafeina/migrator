import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combina classNames con dedupe de Tailwind. Estándar shadcn/ui.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Formato compacto de fechas ISO → "13/05/26 14:32".
 * En contexto de tabla densa preferimos abreviado.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(2);
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}/${mm}/${yy} ${hh}:${mn}`;
}

/**
 * Trunca texto a N caracteres + "…".
 */
export function truncate(s: string | null | undefined, n: number): string {
  if (!s) return "—";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/**
 * Tiempo relativo compacto en es-ES: "ahora", "hace 12 min", "hace 3 h",
 * "hace 5 d", "hace 3 sem", "hace 6 mes", "hace 2 a". Optimizado para
 * tabular nums en columnas estrechas (4-5 caracteres típicos).
 *
 * Para uso en listas densas donde la unidad importa más que la precisión.
 * Si necesitas formato absoluto, usa `formatDate`.
 */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const diffMs = Date.now() - d.getTime();
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return "ahora";
  const min = Math.round(sec / 60);
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  const days = Math.round(h / 24);
  if (days < 14) return `hace ${days} d`;
  const weeks = Math.round(days / 7);
  if (weeks < 8) return `hace ${weeks} sem`;
  const months = Math.round(days / 30);
  if (months < 12) return `hace ${months} mes`;
  const years = Math.round(days / 365);
  return `hace ${years} a`;
}
