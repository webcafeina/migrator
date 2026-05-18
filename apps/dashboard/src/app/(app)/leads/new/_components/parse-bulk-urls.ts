/**
 * Parsing del textarea de bulk paste. Determinístico y testable de
 * forma aislada (sin React).
 *
 * Reglas:
 * - Una URL por línea.
 * - Líneas vacías ignoradas silenciosamente (no aparecen ni como
 *   válidas ni como inválidas).
 * - Líneas que empiezan por `#` (tras trim) ignoradas como comments.
 * - Cada línea no-vacía y no-comment se valida con `new URL(...)`.
 *   Si lanza, va a `invalid` con su número de línea original (útil
 *   para que el operador encuentre la línea problemática).
 *
 * `lineNumber` es 1-based (matchea con UIs de editores).
 */

export interface BulkParseResult {
  valid: string[];
  invalid: Array<{ line: number; raw: string }>;
}

export function parseBulkUrls(raw: string): BulkParseResult {
  const valid: string[] = [];
  const invalid: BulkParseResult["invalid"] = [];

  const lines = raw.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const trimmed = (lines[i] ?? "").trim();
    if (trimmed === "") continue;
    if (trimmed.startsWith("#")) continue;

    try {
      // Rechazo previo: URLs reales no contienen espacios sin encoder.
      // El constructor `URL` de Chromium los tolera codificándolos en
      // %20, lo cual NO es lo que un operador quiere si pegó accidental-
      // mente una línea descriptiva. Mejor fallar explícito.
      if (/\s/.test(trimmed)) {
        throw new Error("contiene espacios");
      }
      // Si la línea YA trae un esquema (`xxx://`) que no es http/https,
      // la rechazamos directamente (sin prepender) para no aceptar
      // ftp://, file://, javascript:, etc.
      const hasScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed);
      if (hasScheme && !/^https?:\/\//i.test(trimmed)) {
        throw new Error("protocolo no soportado");
      }
      const candidate = hasScheme ? trimmed : `https://${trimmed}`;
      const url = new URL(candidate);
      if (url.protocol !== "http:" && url.protocol !== "https:") {
        throw new Error("protocolo no soportado");
      }
      if (!url.hostname || !url.hostname.includes(".")) {
        // Sin TLD (`https://foo`) tampoco es una web pública válida.
        throw new Error("host sin TLD");
      }
      valid.push(candidate);
    } catch {
      invalid.push({ line: i + 1, raw: trimmed });
    }
  }

  return { valid, invalid };
}
