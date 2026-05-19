"use client";

import { Color } from "@tiptap/extension-color";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import TextAlign from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Palette,
} from "lucide-react";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

interface RichTextEditorProps {
  /** HTML inicial. Si llega texto plano (sin tags) Tiptap lo envuelve
   *  automáticamente en `<p>` al hidratar. */
  initialHtml: string;
  /** Devuelve el HTML actual cada vez que cambia. El padre persiste o
   *  acumula en su propio estado. */
  onChange: (html: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /** className opcional para el contenedor exterior. */
  className?: string;
}

/**
 * Editor WYSIWYG simple para el cuerpo HTML de los correos de outreach
 * (v0.14.0). Toolbar minimalista (negrita / cursiva / link / lista) —
 * todo lo que sale es HTML semántico safe para email (Tiptap NO emite
 * `<div style>` ni atributos style; eso lo añade premailer en backend).
 *
 * SSR-safe: el componente usa `"use client"` y `useEditor` espera al
 * primer render para hidratar. Si `initialHtml` cambia tras el primer
 * render (porque el padre carga datos async), un useEffect sincroniza
 * el contenido del editor sin perder el cursor del usuario activo.
 */
export function RichTextEditor({
  initialHtml,
  onChange,
  placeholder = "Escribe el cuerpo del correo…",
  disabled = false,
  className,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Quitamos extensiones que no aportan en email (heading h1
        // queda raro dentro del slot; bloque code/codeBlock idem).
        // `link` también deshabilitado aquí porque lo configuramos
        // explícitamente abajo con openOnClick=false (Starter en v3
        // lo incluye con defaults distintos — evitamos warning de
        // "duplicate extension").
        heading: false,
        codeBlock: false,
        horizontalRule: false,
        link: false,
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
      }),
      Placeholder.configure({ placeholder }),
      // v0.15.0 — TextStyle es prerequisito de Color (Tiptap requiere
      // un mark base donde colgar el atributo `style`).
      TextStyle,
      Color,
      // TextAlign aplica `style="text-align:..."` a <p>. Email-safe.
      TextAlign.configure({
        types: ["paragraph"],
        alignments: ["left", "center", "right"],
        defaultAlignment: "left",
      }),
    ],
    content: initialHtml || "",
    editable: !disabled,
    immediatelyRender: false, // Next.js 15 RSC — evita hydration mismatch
    onUpdate: ({ editor: e }) => {
      onChange(e.getHTML());
    },
  });

  // Sincroniza contenido externo (cuando el padre cambia initialHtml
  // sin que el editor lo haya pedido). Comprueba para no re-setear
  // mientras el usuario está escribiendo (causaría reset de cursor).
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    if (current !== initialHtml && !editor.isFocused) {
      editor.commands.setContent(initialHtml || "", { emitUpdate: false });
    }
  }, [editor, initialHtml]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [editor, disabled]);

  if (!editor) {
    // Skeleton mientras Tiptap inicializa (un tick tras el primer render).
    return (
      <div
        className={cn(
          "min-h-[200px] rounded-sm border border-wcm-detail/70 bg-wcm-primary p-2 text-xs text-muted-foreground",
          className,
        )}
      >
        Cargando editor…
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-sm border border-wcm-detail/70 bg-wcm-primary text-xs",
        disabled && "opacity-50",
        className,
      )}
    >
      <Toolbar editor={editor} disabled={disabled} />
      <EditorContent
        editor={editor}
        className="prose-wcm min-h-[180px] max-h-[420px] overflow-y-auto px-3 py-2 text-[12.5px] leading-relaxed text-wcm-text focus-within:outline-none [&_a]:text-wcm-accent [&_a]:underline [&_p]:my-2 [&_strong]:text-wcm-text [&_ul]:my-2 [&_ul]:ml-5 [&_ul]:list-disc [&_ol]:my-2 [&_ol]:ml-5 [&_ol]:list-decimal"
      />
    </div>
  );
}

interface ToolbarProps {
  editor: ReturnType<typeof useEditor>;
  disabled: boolean;
}

function Toolbar({ editor, disabled }: ToolbarProps) {
  const colorInputRef = useRef<HTMLInputElement>(null);

  if (!editor) return null;

  const promptLink = () => {
    const previous = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("URL del enlace (vacío = quitar)", previous ?? "https://");
    if (url === null) return; // cancel
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  };

  const currentColor =
    (editor.getAttributes("textStyle").color as string | undefined) ?? "#000000";

  const openColorPicker = () => {
    colorInputRef.current?.click();
  };

  const handleColorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    editor.chain().focus().setColor(e.target.value).run();
  };

  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-wcm-detail/40 bg-wcm-secondary/30 px-2 py-1">
      <ToolButton
        active={editor.isActive("bold")}
        disabled={disabled}
        onClick={() => editor.chain().focus().toggleBold().run()}
        ariaLabel="Negrita"
      >
        <Bold size={13} aria-hidden />
      </ToolButton>
      <ToolButton
        active={editor.isActive("italic")}
        disabled={disabled}
        onClick={() => editor.chain().focus().toggleItalic().run()}
        ariaLabel="Cursiva"
      >
        <Italic size={13} aria-hidden />
      </ToolButton>
      <ToolButton
        active={editor.isActive("link")}
        disabled={disabled}
        onClick={promptLink}
        ariaLabel="Enlace"
      >
        <LinkIcon size={13} aria-hidden />
      </ToolButton>
      <span className="mx-1 h-4 w-px bg-wcm-detail/50" aria-hidden />
      <ToolButton
        active={editor.isActive("bulletList")}
        disabled={disabled}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        ariaLabel="Lista con viñetas"
      >
        <List size={13} aria-hidden />
      </ToolButton>
      <ToolButton
        active={editor.isActive("orderedList")}
        disabled={disabled}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        ariaLabel="Lista numerada"
      >
        <ListOrdered size={13} aria-hidden />
      </ToolButton>
      <span className="mx-1 h-4 w-px bg-wcm-detail/50" aria-hidden />
      <ToolButton
        active={editor.isActive({ textAlign: "left" })}
        disabled={disabled}
        onClick={() => editor.chain().focus().setTextAlign("left").run()}
        ariaLabel="Alinear a la izquierda"
      >
        <AlignLeft size={13} aria-hidden />
      </ToolButton>
      <ToolButton
        active={editor.isActive({ textAlign: "center" })}
        disabled={disabled}
        onClick={() => editor.chain().focus().setTextAlign("center").run()}
        ariaLabel="Alinear al centro"
      >
        <AlignCenter size={13} aria-hidden />
      </ToolButton>
      <ToolButton
        active={editor.isActive({ textAlign: "right" })}
        disabled={disabled}
        onClick={() => editor.chain().focus().setTextAlign("right").run()}
        ariaLabel="Alinear a la derecha"
      >
        <AlignRight size={13} aria-hidden />
      </ToolButton>
      <span className="mx-1 h-4 w-px bg-wcm-detail/50" aria-hidden />
      <ToolButton
        active={false}
        disabled={disabled}
        onClick={openColorPicker}
        ariaLabel={`Color del texto (actual ${currentColor})`}
      >
        <Palette
          size={13}
          aria-hidden
          style={{ color: currentColor === "#000000" ? undefined : currentColor }}
        />
      </ToolButton>
      <input
        ref={colorInputRef}
        type="color"
        value={currentColor}
        onChange={handleColorChange}
        disabled={disabled}
        aria-label="Selector de color del texto"
        className="sr-only"
        // Mantener fuera del flow visual pero accesible (sr-only).
      />
    </div>
  );
}

function ToolButton({
  active,
  disabled,
  onClick,
  ariaLabel,
  children,
}: {
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  ariaLabel: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={active}
      className={cn(
        "rounded-sm px-1.5 py-1 text-wcm-text/70 transition-colors hover:bg-wcm-detail/30 hover:text-wcm-text disabled:cursor-not-allowed disabled:opacity-50",
        active && "bg-wcm-accent/15 text-wcm-accent",
      )}
    >
      {children}
    </button>
  );
}
