/**
 * `<DiffViewer />` — visualiza diff antes/después para Brief refinement.
 *
 * Sprint v0.27.0 B3. Soporta 3 shapes:
 * - **string vs string**: word-level inline diff (insert/delete).
 * - **object vs object**: key-value comparison side-by-side.
 * - **array vs array** (reorder): muestra orden antes/después con flechas.
 *
 * El algoritmo de strings usa una LCS simplificada por palabras —
 * suficiente para texto corto (headlines, CTAs) sin dependencias externas.
 */

import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";

interface DiffViewerProps {
  before: unknown;
  after: unknown;
  className?: string;
}

export function DiffViewer({ before, after, className }: DiffViewerProps) {
  // Reorder: arrays de mismo tamaño con permutación.
  if (Array.isArray(before) && Array.isArray(after)) {
    return <ArrayReorderDiff before={before} after={after} className={className} />;
  }

  // Object vs object.
  if (isPlainObject(before) && isPlainObject(after)) {
    return <ObjectDiff before={before} after={after} className={className} />;
  }

  // String vs string (fallback): incluso si vienen como otros tipos
  // los stringify para mostrar algo útil.
  const beforeStr = toDisplayString(before);
  const afterStr = toDisplayString(after);
  return (
    <StringDiff
      before={beforeStr}
      after={afterStr}
      className={className}
    />
  );
}

// ---------------------------------------------------------------------------
// String diff (word-level)
// ---------------------------------------------------------------------------

interface StringDiffProps {
  before: string;
  after: string;
  className?: string;
}

function StringDiff({ before, after, className }: StringDiffProps) {
  const tokens = diffWords(before, after);
  return (
    <div
      className={cn(
        "rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-2 text-[11px] leading-relaxed",
        className,
      )}
    >
      {tokens.map((token, i) => {
        if (token.type === "equal") {
          return <span key={i}>{token.value}</span>;
        }
        if (token.type === "delete") {
          return (
            <span
              key={i}
              className="bg-wcm-danger/20 text-wcm-danger/80 line-through decoration-wcm-danger/60"
            >
              {token.value}
            </span>
          );
        }
        return (
          <span key={i} className="bg-wcm-accent/20 font-medium text-wcm-accent">
            {token.value}
          </span>
        );
      })}
    </div>
  );
}

interface DiffToken {
  type: "equal" | "insert" | "delete";
  value: string;
}

/**
 * LCS por palabras (whitespace-split). Para texto corto (headlines,
 * CTAs) es perfectamente rápido. Devuelve tokens listos para render.
 */
export function diffWords(before: string, after: string): DiffToken[] {
  const a = tokenize(before);
  const b = tokenize(after);
  const n = a.length;
  const m = b.length;

  // DP de longitudes LCS.
  const lcs: number[][] = Array.from({ length: n + 1 }, () =>
    new Array(m + 1).fill(0),
  );
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      if (a[i] === b[j]) {
        lcs[i + 1]![j + 1] = lcs[i]![j]! + 1;
      } else {
        lcs[i + 1]![j + 1] = Math.max(lcs[i]![j + 1]!, lcs[i + 1]![j]!);
      }
    }
  }

  // Backtracking + agrupación de tokens consecutivos del mismo tipo.
  const reversed: DiffToken[] = [];
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      reversed.push({ type: "equal", value: a[i - 1]! });
      i--;
      j--;
    } else if (lcs[i - 1]![j]! >= lcs[i]![j - 1]!) {
      reversed.push({ type: "delete", value: a[i - 1]! });
      i--;
    } else {
      reversed.push({ type: "insert", value: b[j - 1]! });
      j--;
    }
  }
  while (i > 0) {
    reversed.push({ type: "delete", value: a[i - 1]! });
    i--;
  }
  while (j > 0) {
    reversed.push({ type: "insert", value: b[j - 1]! });
    j--;
  }

  // Consolida tokens consecutivos del mismo tipo en strings unidos.
  const out: DiffToken[] = [];
  for (let k = reversed.length - 1; k >= 0; k--) {
    const t = reversed[k]!;
    const prev = out[out.length - 1];
    if (prev && prev.type === t.type) {
      prev.value += t.value;
    } else {
      out.push({ ...t });
    }
  }
  return out;
}

/** Tokeniza preservando whitespace como tokens propios. */
function tokenize(s: string): string[] {
  if (!s) return [];
  // Split por límites palabra/whitespace conservando ambos.
  const matches = s.match(/(\s+|\S+)/g);
  return matches ?? [];
}

// ---------------------------------------------------------------------------
// Object diff (side-by-side por key)
// ---------------------------------------------------------------------------

interface ObjectDiffProps {
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  className?: string;
}

function ObjectDiff({ before, after, className }: ObjectDiffProps) {
  const allKeys = Array.from(
    new Set([...Object.keys(before), ...Object.keys(after)]),
  );
  return (
    <div
      className={cn(
        "rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-2 text-[10.5px]",
        className,
      )}
    >
      <table className="w-full table-fixed border-collapse">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="w-1/4 pb-1 pr-2 font-normal">key</th>
            <th className="w-3/8 pb-1 pr-2 font-normal">antes</th>
            <th className="w-3/8 pb-1 font-normal">después</th>
          </tr>
        </thead>
        <tbody>
          {allKeys.map((k) => {
            const b = before[k];
            const a = after[k];
            const changed = !isEqual(b, a);
            return (
              <tr
                key={k}
                className={cn(
                  "border-t border-wcm-detail/30 align-top",
                  changed ? "" : "opacity-60",
                )}
              >
                <td className="py-1 pr-2 font-mono text-wcm-text/80">{k}</td>
                <td
                  className={cn(
                    "py-1 pr-2 break-words",
                    changed
                      ? "bg-wcm-danger/10 text-wcm-danger/80 line-through decoration-wcm-danger/50"
                      : "text-wcm-text/70",
                  )}
                >
                  {b === undefined ? "—" : toDisplayString(b)}
                </td>
                <td
                  className={cn(
                    "py-1 break-words",
                    changed
                      ? "bg-wcm-accent/10 font-medium text-wcm-accent"
                      : "text-wcm-text/70",
                  )}
                >
                  {a === undefined ? "—" : toDisplayString(a)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Array reorder
// ---------------------------------------------------------------------------

interface ArrayReorderDiffProps {
  before: unknown[];
  after: unknown[];
  className?: string;
}

function ArrayReorderDiff({
  before,
  after,
  className,
}: ArrayReorderDiffProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-sm border border-wcm-detail/40 bg-wcm-primary/40 p-2 text-[10.5px]",
        className,
      )}
    >
      <span className="text-muted-foreground">orden:</span>
      <code className="rounded-sm bg-wcm-danger/10 px-1.5 py-0.5 text-wcm-danger/80 line-through">
        [{before.map(toDisplayString).join(", ")}]
      </code>
      <ArrowRight className="h-3 w-3 text-muted-foreground" aria-hidden />
      <code className="rounded-sm bg-wcm-accent/10 px-1.5 py-0.5 text-wcm-accent">
        [{after.map(toDisplayString).join(", ")}]
      </code>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return (
    typeof v === "object"
    && v !== null
    && !Array.isArray(v)
    && Object.getPrototypeOf(v) === Object.prototype
  );
}

function toDisplayString(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function isEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a == null || b == null) return false;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}
