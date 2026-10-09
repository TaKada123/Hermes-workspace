# Shared UI components — `web/`

> Generated from the checked-in React sources. Scope is limited to reusable, project-owned UI components; page modules, tests, domain-specific feature panels, and dependency sources are excluded.

## Stack and primitive ownership

- React 19 + Vite + TypeScript.
- Tailwind CSS 4 utility styling.
- Base primitives come from `@nous-research/ui@0.18.2` (not copied here because their source is dependency-owned, outside `web/`): Button, Input, Label, Select, Switch, Card, Badge, Dialog, BottomSheet, Spinner, Toast, typography, list/segmented controls.
- Icons come from `lucide-react`.

## Project-owned shared components

## AllowlistInput

- Source: `web/src/components/AllowlistInput.tsx`
- Description: Editable allowlist control that normalizes a comma/newline-delimited value into add/remove input rows.
- Key props: `id, label, value, onChange, invalid`

```tsx
import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { Button } from '@nous-research/ui/ui/components/button'
import { Input } from '@nous-research/ui/ui/components/input'

interface Row {
  id: number
  value: string
}

// Row identity for React keys and focus.
let rowSeq = 0

/** Allowlists are stored as one comma-separated env value; a pasted list may also use newlines. */
export function splitAllowlist(raw: string | null | undefined): string[] {
  return (raw || '')
    .split(/[,\n]/)
    .map(entry => entry.trim())
    .filter(Boolean)
}

export function joinAllowlist(entries: string[]): string {
  return [...new Set(entries.map(entry => entry.trim()).filter(Boolean))].join(',')
}

function toRows(raw: string | null | undefined): Row[] {
  const entries = splitAllowlist(raw)
  return (entries.length ? entries : ['']).map(value => ({ id: rowSeq++, value }))
}

/** One input per allowed user/ID, with + to add and × to remove; reports one comma-separated value. */
export function AllowlistInput({
  id,
  label,
  value,
  onChange,
  invalid
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  invalid?: boolean
}) {
  const [rows, setRows] = useState<Row[]>(() => toRows(value))
  const [focusId, setFocusId] = useState<number | null>(null)

  const commit = (next: Row[]) => {
    setRows(next)
    onChange(joinAllowlist(next.map(row => row.value)))
  }

  const change = (rowId: number, text: string) => {
    // A pasted "123, 456" becomes one box per entry.
    const parts = /[,\n]/.test(text) ? splitAllowlist(text) : [text]
    const index = rows.findIndex(row => row.id === rowId)
    const replacement = parts.length
      ? parts.map((part, i) => ({ id: i === 0 ? rowId : rowSeq++, value: part }))
      : [{ id: rowId, value: '' }]
    commit([...rows.slice(0, index), ...replacement, ...rows.slice(index + 1)])
  }

  const add = () => {
    const rowId = rowSeq++
    setFocusId(rowId)
    setRows([...rows, { id: rowId, value: '' }])
  }

  const remove = (rowId: number) => {
    const next = rows.filter(row => row.id !== rowId)
    commit(next.length ? next : [{ id: rowSeq++, value: '' }])
  }

  const lone = rows.length === 1 && !rows[0].value

  return (
    <div className="grid gap-1.5" data-slot="allowlist-input">
      {rows.map((row, index) => (
        <div className="flex items-center gap-2" key={row.id}>
          <Input
            id={index === 0 ? id : undefined}
            aria-label={`${label} ${index + 1}`}
            aria-invalid={invalid}
            autoFocus={row.id === focusId}
            type="text"
            className="text-base leading-6 sm:text-xs sm:leading-4"
            placeholder="Enter an ID"
            value={row.value}
            onChange={e => change(row.id, e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && row.value.trim()) {
                e.preventDefault()
                add()
              }
            }}
          />
          <Button ghost size="icon" aria-label="Remove" title="Remove" disabled={lone} onClick={() => remove(row.id)}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ))}
      <div>
        <Button ghost size="sm" onClick={add} prefix={<Plus className="h-3.5 w-3.5" />}>
          Add another
        </Button>
      </div>
    </div>
  )
}
```

## AutoField

- Source: `web/src/components/AutoField.tsx`
- Description: Schema-driven field renderer for booleans, selects, numbers, text, lists, and nested values.
- Key props: `schemaKey, schema, value, onChange`

```tsx
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";

function FieldHint({ schema, schemaKey }: { schema: Record<string, unknown>; schemaKey: string }) {
  const keyPath = schemaKey.includes(".") ? schemaKey : "";
  const description = schema.description ? String(schema.description) : "";

  if (!keyPath && !description) return null;

  return (
    <div className="flex flex-col gap-0.5">
      {keyPath && <span className="text-xs font-mono text-text-tertiary">{keyPath}</span>}
      {description && <span className="text-xs text-text-secondary">{description}</span>}
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatScalar(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function NestedValueEditor({
  fieldKey,
  value,
  onChange,
}: {
  fieldKey: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (isRecord(value)) {
    return (
      <div className="grid gap-2 border border-border p-2">
        {Object.entries(value).map(([subKey, subVal]) => (
          <div key={subKey} className="grid gap-1">
            <Label className="text-xs text-muted-foreground">{subKey}</Label>
            <NestedValueEditor
              fieldKey={`${fieldKey}.${subKey}`}
              value={subVal}
              onChange={(next) => onChange({ ...value, [subKey]: next })}
            />
          </div>
        ))}
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div className="grid gap-2">
        {value.map((item, index) => (
          <div key={`${fieldKey}.${index}`} className="grid gap-1">
            <Label className="text-xs text-muted-foreground">Item {index + 1}</Label>
            <NestedValueEditor
              fieldKey={`${fieldKey}.${index}`}
              value={item}
              onChange={(next) =>
                onChange(value.map((existing, i) => (i === index ? next : existing)))
              }
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <Input
      value={formatScalar(value)}
      onChange={(e) => onChange(e.target.value)}
      className="text-xs"
    />
  );
}

export function AutoField({
  schemaKey,
  schema,
  value,
  onChange,
}: AutoFieldProps) {
  const rawLabel = schemaKey.split(".").pop() ?? schemaKey;
  const label = rawLabel.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  if (isRecord(value) || (Array.isArray(value) && value.some((item) => isRecord(item)))) {
    return (
      <div className="grid gap-3 border border-border p-3">
        <Label className="text-xs font-medium">{label}</Label>
        <FieldHint schema={schema} schemaKey={schemaKey} />
        <NestedValueEditor fieldKey={schemaKey} value={value} onChange={onChange} />
      </div>
    );
  }

  if (schema.type === "boolean") {
    return (
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col gap-0.5">
          <Label className="text-sm">{label}</Label>
          <FieldHint schema={schema} schemaKey={schemaKey} />
        </div>
        <Switch checked={!!value} onCheckedChange={onChange} />
      </div>
    );
  }

  if (schema.type === "select") {
    const options = (schema.options as string[]) ?? [];
    return (
      <div className="grid gap-1.5">
        <Label className="text-sm">{label}</Label>
        <FieldHint schema={schema} schemaKey={schemaKey} />
        <Select value={String(value ?? "")} onValueChange={(v) => onChange(v)}>
          {options.map((opt) => (
            <SelectOption key={opt} value={opt}>
              {opt || "(none)"}
            </SelectOption>
          ))}
        </Select>
      </div>
    );
  }

  if (schema.type === "number") {
    return (
      <div className="grid gap-1.5">
        <Label className="text-sm">{label}</Label>
        <FieldHint schema={schema} schemaKey={schemaKey} />
        <Input
          type="number"
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") {
              onChange(0);
              return;
            }
            const n = Number(raw);
            if (!Number.isNaN(n)) {
              onChange(n);
            }
          }}
        />
      </div>
    );
  }

  if (schema.type === "text") {
    return (
      <div className="grid gap-1.5">
        <Label className="text-sm">{label}</Label>
        <FieldHint schema={schema} schemaKey={schemaKey} />
        <textarea
          className="flex min-h-[80px] w-full border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }

  if (schema.type === "list") {
    return (
      <div className="grid gap-1.5">
        <Label className="text-sm">{label}</Label>
        <FieldHint schema={schema} schemaKey={schemaKey} />
        <Input
          value={Array.isArray(value) ? value.join(", ") : String(value ?? "")}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          placeholder="comma-separated values"
        />
      </div>
    );
  }

  return (
    <div className="grid gap-1.5">
      <Label className="text-sm">{label}</Label>
      <FieldHint schema={schema} schemaKey={schemaKey} />
      <Input value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

interface AutoFieldProps {
  schemaKey: string;
  schema: Record<string, unknown>;
  value: unknown;
  onChange: (v: unknown) => void;
}
```

## ConfirmDialog

- Source: `web/src/components/ConfirmDialog.tsx`
- Description: Accessible portal-based confirmation dialog with destructive and loading states.
- Key props: `open, title, description, confirmLabel, cancelLabel, destructive, loading, onConfirm, onCancel`

```tsx
import { Button } from "@nous-research/ui/ui/components/button";
import { AlertTriangle } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { cn, themedBody } from "@/lib/utils";

interface ConfirmDialogProps {
  cancelLabel?: string;
  confirmLabel?: string;
  description?: string;
  destructive?: boolean;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: string;
}

export function ConfirmDialog({
  cancelLabel = "Cancel",
  confirmLabel = "Confirm",
  description,
  destructive = false,
  loading = false,
  onCancel,
  onConfirm,
  open,
  title,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const prevActive = document.activeElement as HTMLElement | null;
    dialogRef.current
      ?.querySelector<HTMLButtonElement>("[data-confirm]")
      ?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };

    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      prevActive?.focus?.();
    };
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby={description ? "confirm-dialog-desc" : undefined}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/85 p-4"
    >
      <div
        ref={dialogRef}
        className={cn(
          themedBody,
          "relative w-full max-w-md border border-border bg-card shadow-2xl",
        )}
      >
        <div className="flex items-start gap-3 p-4 border-b border-border">
          {destructive && (
            <div aria-hidden className="mt-0.5 shrink-0 text-destructive">
              <AlertTriangle className="h-4 w-4" />
            </div>
          )}

          <div className="flex-1 min-w-0 flex flex-col gap-1">
            <h2
              id="confirm-dialog-title"
              className="font-mondwest text-display text-base tracking-wider"
            >
              {title}
            </h2>

            {description && (
              <p
                id="confirm-dialog-desc"
                className="text-xs text-muted-foreground leading-relaxed whitespace-pre-line"
              >
                {description}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-3">
          <Button type="button" outlined onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            data-confirm
            type="button"
            destructive={destructive}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

## DeleteConfirmDialog

- Source: `web/src/components/DeleteConfirmDialog.tsx`
- Description: Localized destructive-confirmation wrapper used by management pages.
- Key props: `open, title, description, confirmLabel, cancelLabel, loading, onConfirm, onCancel`

```tsx
import { ConfirmDialog } from "@nous-research/ui/ui/components/confirm-dialog";
import { useI18n } from "@/i18n";

export function DeleteConfirmDialog({
  cancelLabel,
  confirmLabel,
  description,
  loading,
  onCancel,
  onConfirm,
  open,
  title,
}: DeleteConfirmDialogProps) {
  const { t } = useI18n();

  return (
    <ConfirmDialog
      open={open}
      onCancel={onCancel}
      onConfirm={onConfirm}
      title={title}
      description={description}
      loading={loading}
      destructive
      confirmLabel={confirmLabel ?? t.common.delete}
      cancelLabel={cancelLabel ?? t.common.cancel}
    />
  );
}

interface DeleteConfirmDialogProps {
  cancelLabel?: string;
  confirmLabel?: string;
  description?: string;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: string;
}
```

## LanguageSwitcher

- Source: `web/src/components/LanguageSwitcher.tsx`
- Description: Responsive locale picker that renders as a dropdown or mobile bottom sheet.
- Key props: `collapsed, dropUp`

```tsx
import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Check } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { BottomSheet } from "@nous-research/ui/ui/components/bottom-sheet";
import { Typography } from "@nous-research/ui/ui/components/typography/index";
import { useBelowBreakpoint } from "@nous-research/ui/hooks/use-below-breakpoint";
import { useI18n } from "@/i18n/context";
import { LOCALE_META } from "@/i18n";
import type { Locale } from "@/i18n";
import { cn } from "@/lib/utils";

/**
 * Language picker — shows the current language's endonym, opens a dropdown
 * of all supported locales when clicked.  Persists choice to localStorage via
 * the I18n context.
 *
 * Replaces the older two-state EN↔ZH toggle now that we ship 16 locales
 * (en, zh, zh-hant, ja, de, es, fr, tr, uk, af, ko, it, ga, pt, ru, hu).
 *
 * No country flags by design — languages aren't countries, and flag pairings
 * inevitably create political mismappings (e.g. Mandarin variants ≠ any single
 * jurisdiction, English ≠ GB, Portuguese ≠ PT). Endonyms are unambiguous.
 *
 * When placed at the bottom of the sidebar (next to ThemeSwitcher), pass
 * `dropUp` so the list opens above the trigger and avoids clipping below the
 * viewport / overflow ancestors. Below the `sm` breakpoint, `dropUp` uses a
 * bottom sheet portaled to `document.body` instead of an anchored dropdown.
 */
export function LanguageSwitcher({ collapsed = false, dropUp = false }: LanguageSwitcherProps) {
  const { locale, setLocale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const narrowViewport = useBelowBreakpoint(640);
  const useMobileSheet = Boolean(dropUp && narrowViewport);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open || useMobileSheet) return;

    function onPointerDown(e: PointerEvent) {
      const target = e.target as Node;
      if (containerRef.current?.contains(target)) return;
      if (dropdownRef.current?.contains(target)) return;
      setOpen(false);
    }

    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, useMobileSheet]);

  const current = LOCALE_META[locale];
  const allLocales = Object.entries(LOCALE_META) as Array<[Locale, typeof current]>;
  const sheetTitle = t.language.switchTo;

  return (
    <div ref={containerRef} className="relative inline-flex">
      <Button
        ghost
        onClick={() => setOpen((v) => !v)}
        title={t.language.switchTo}
        aria-label={t.language.switchTo}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "px-2 py-1 normal-case tracking-normal font-normal text-xs text-text-secondary hover:text-foreground",
          collapsed && "hover:bg-transparent",
        )}
      >
        <span className="inline-flex items-center gap-1.5">
          <Typography
            className="hidden sm:inline text-display tracking-wide text-xs"
          >
            {locale === "en" ? "EN" : current.name}
          </Typography>
        </span>
      </Button>

      {useMobileSheet && (
        <BottomSheet
          backdropDismissLabel={t.common.close}
          onClose={() => setOpen(false)}
          open={open}
          title={sheetTitle}
        >
          <div aria-label={sheetTitle} role="listbox">
            <LanguageSwitcherOptions
              allLocales={allLocales}
              locale={locale}
              setLocale={setLocale}
              setOpen={setOpen}
            />
          </div>
        </BottomSheet>
      )}

      {open && !useMobileSheet && (() => {
        const rect = containerRef.current?.getBoundingClientRect();
        const dropdown = (
          <div
            ref={dropdownRef}
            aria-label={sheetTitle}
            className={cn(
              "min-w-[10rem] border border-border bg-popover shadow-md py-1 max-h-80 overflow-y-auto",
              dropUp ? "fixed z-[100]" : "absolute z-50 right-0 top-full mt-1",
            )}
            role="listbox"
            style={
              dropUp && rect
                ? { bottom: window.innerHeight - rect.top + 4, left: rect.left }
                : undefined
            }
          >
            <LanguageSwitcherOptions
              allLocales={allLocales}
              locale={locale}
              setLocale={setLocale}
              setOpen={setOpen}
            />
          </div>
        );
        return dropUp ? createPortal(dropdown, document.body) : dropdown;
      })()}
    </div>
  );
}

function LanguageSwitcherOptions({
  allLocales,
  locale,
  setLocale,
  setOpen,
}: LanguageSwitcherOptionsProps) {
  return (
    <>
      {allLocales.map(([code, meta]) => {
        const selected = code === locale;

        return (
          <button
            aria-selected={selected}
            className={cn(
              "w-full text-left px-3 py-1.5 flex items-center gap-2 cursor-pointer",
              "font-sans text-display text-xs tracking-[0.08em]",
              "hover:bg-accent hover:text-accent-foreground transition-colors",
              selected ? "font-semibold text-foreground" : "text-muted-foreground",
            )}
            key={code}
            onClick={() => {
              setLocale(code);
              setOpen(false);
            }}
            role="option"
            type="button"
          >
            <span className="truncate">{meta.name}</span>

            {selected && <Check className="ml-auto h-3 w-3 shrink-0 text-midground" />}
          </button>
        );
      })}
    </>
  );
}

interface LanguageSwitcherOptionsProps {
  allLocales: Array<[Locale, (typeof LOCALE_META)[Locale]]>;
  locale: Locale;
  setLocale: (code: Locale) => void;
  setOpen: (open: boolean) => void;
}

interface LanguageSwitcherProps {
  collapsed?: boolean;
  dropUp?: boolean;
}
```

## LoadErrorNotice

- Source: `web/src/components/LoadErrorNotice.tsx`
- Description: Persistent inline load-failure card with details and a retry action.
- Key props: `what, detail, onRetry, className`

```tsx
import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card } from "@nous-research/ui/ui/components/card";

import { useI18n } from "@/i18n";
import { loadErrorCopy } from "@/lib/load-error-copy";
import { cn } from "@/lib/utils";

interface LoadErrorNoticeProps {
  /** What failed to load, already translated (e.g. `t.cron.loadWhat`). */
  what: string;
  /** The humanized error (`errorMessage(err)`), shown as a dimmed detail line. */
  detail?: string | null;
  onRetry: () => void;
  className?: string;
}

/**
 * Persistent "could not load X" card with a Retry button. Used instead of an
 * error toast for page loaders: a toast vanishes after 3s and cannot carry a
 * retry action, so the user was left with an empty page and no next step.
 */
export function LoadErrorNotice({ what, detail, onRetry, className }: LoadErrorNoticeProps) {
  const { t } = useI18n();
  const copy = loadErrorCopy(t.common, what, detail);

  return (
    <Card
      role="alert"
      className={cn(
        "flex items-start gap-2 border-destructive/40 bg-destructive/5 px-3 py-2 text-xs",
        className,
      )}
    >
      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1">
        <div className="text-destructive">{copy.title}</div>
        {copy.details && <div className="mt-0.5 text-muted-foreground">{copy.details}</div>}
        <Button
          size="sm"
          outlined
          className="mt-1"
          onClick={onRetry}
          prefix={<RotateCcw className="h-3.5 w-3.5" />}
        >
          {t.common.retry}
        </Button>
      </div>
    </Card>
  );
}
```

## Markdown

- Source: `web/src/components/Markdown.tsx`
- Description: Lightweight shared Markdown renderer with syntax blocks, links, highlighting, and streaming caret.
- Key props: `content, highlightTerms, streaming`

```tsx
import { useMemo, type ReactNode } from "react";

/**
 * Lightweight markdown renderer for LLM output.
 * Handles: code blocks, inline code, bold, italic, headers, links, lists, horizontal rules.
 * NOT a full CommonMark parser — optimized for typical assistant message patterns.
 *
 * `streaming` renders a blinking caret at the tail of the last block so it
 * appears to hug the final character instead of wrapping onto a new line
 * after a block element (paragraph/list/code/…).
 */
export function Markdown({
  content,
  highlightTerms,
  streaming,
}: {
  content: string;
  highlightTerms?: string[];
  streaming?: boolean;
}) {
  const blocks = useMemo(() => parseBlocks(content), [content]);
  const caret = streaming ? <StreamingCaret /> : null;

  return (
    <div className="text-sm text-foreground leading-relaxed space-y-2">
      {blocks.map((block, i) => (
        <Block
          key={i}
          block={block}
          highlightTerms={highlightTerms}
          caret={caret && i === blocks.length - 1 ? caret : null}
        />
      ))}
      {blocks.length === 0 && caret}
    </div>
  );
}

function StreamingCaret() {
  return (
    <span
      aria-hidden
      className="inline-block w-[0.5em] h-[1em] ml-0.5 align-[-0.15em] bg-foreground/50 animate-pulse"
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type BlockNode =
  | { type: "code"; lang: string; content: string }
  | { type: "heading"; level: number; content: string }
  | { type: "hr" }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "paragraph"; content: string };

/* ------------------------------------------------------------------ */
/*  Block parser                                                       */
/* ------------------------------------------------------------------ */

function parseBlocks(text: string): BlockNode[] {
  const lines = text.split("\n");
  const blocks: BlockNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    const fenceMatch = line.match(/^```(\w*)/);
    if (fenceMatch) {
      const lang = fenceMatch[1] || "";
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push({ type: "code", lang, content: codeLines.join("\n") });
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        content: headingMatch[2],
      });
      i++;
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // Unordered list
    if (/^[-*+]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*+]\s/, ""));
        i++;
      }
      blocks.push({ type: "list", ordered: false, items });
      continue;
    }

    // Ordered list
    if (/^\d+[.)]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+[.)]\s/, ""));
        i++;
      }
      blocks.push({ type: "list", ordered: true, items });
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph — collect consecutive non-empty, non-special lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].match(/^```/) &&
      !lines[i].match(/^#{1,4}\s/) &&
      !lines[i].match(/^[-*+]\s/) &&
      !lines[i].match(/^\d+[.)]\s/) &&
      !lines[i].match(/^[-*_]{3,}\s*$/)
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push({ type: "paragraph", content: paraLines.join("\n") });
    }
  }

  return blocks;
}

/* ------------------------------------------------------------------ */
/*  Block renderer                                                     */
/* ------------------------------------------------------------------ */

function Block({
  block,
  highlightTerms,
  caret,
}: {
  block: BlockNode;
  highlightTerms?: string[];
  caret?: ReactNode;
}) {
  switch (block.type) {
    case "code":
      return (
        <pre className="bg-secondary/60 border border-border px-3 py-2.5 text-xs font-mono leading-relaxed overflow-x-auto">
          <code>
            {block.content}
            {caret}
          </code>
        </pre>
      );

    case "heading": {
      const Tag = `h${Math.min(block.level, 4)}` as "h1" | "h2" | "h3" | "h4";
      const sizes: Record<string, string> = {
        h1: "text-base font-bold",
        h2: "text-sm font-bold",
        h3: "text-sm font-semibold",
        h4: "text-sm font-medium",
      };
      return (
        <Tag className={sizes[Tag]}>
          <InlineContent text={block.content} highlightTerms={highlightTerms} />
          {caret}
        </Tag>
      );
    }

    case "hr":
      return (
        <>
          <hr className="border-border" />
          {caret}
        </>
      );

    case "list": {
      const Tag = block.ordered ? "ol" : "ul";
      const last = block.items.length - 1;
      return (
        <Tag
          className={`space-y-0.5 ${block.ordered ? "list-decimal" : "list-disc"} pl-5 text-sm`}
        >
          {block.items.map((item, i) => (
            <li key={i}>
              <InlineContent text={item} highlightTerms={highlightTerms} />
              {i === last ? caret : null}
            </li>
          ))}
        </Tag>
      );
    }

    case "paragraph":
      return (
        <p>
          <InlineContent text={block.content} highlightTerms={highlightTerms} />
          {caret}
        </p>
      );
  }
}

/* ------------------------------------------------------------------ */
/*  Inline parser + renderer                                           */
/* ------------------------------------------------------------------ */

type InlineNode =
  | { type: "text"; content: string }
  | { type: "code"; content: string }
  | { type: "bold"; content: string }
  | { type: "italic"; content: string }
  | { type: "link"; text: string; href: string }
  | { type: "br" };

function parseInline(text: string): InlineNode[] {
  const nodes: InlineNode[] = [];
  // Pattern priority: code > link > bold > italic > bare URL > line break
  const pattern =
    /(`[^`]+`)|(\[([^\]]+)\]\(([^)]+)\))|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(\bhttps?:\/\/[^\s<>)\]]+)|(\n)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }

    if (match[1]) {
      // Inline code
      nodes.push({ type: "code", content: match[1].slice(1, -1) });
    } else if (match[2]) {
      // [text](url) link
      nodes.push({ type: "link", text: match[3], href: match[4] });
    } else if (match[5]) {
      // **bold**
      nodes.push({ type: "bold", content: match[6] });
    } else if (match[7]) {
      // *italic*
      nodes.push({ type: "italic", content: match[8] });
    } else if (match[9]) {
      // Bare URL
      nodes.push({ type: "link", text: match[9], href: match[9] });
    } else if (match[10]) {
      // Line break within paragraph
      nodes.push({ type: "br" });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push({ type: "text", content: text.slice(lastIndex) });
  }

  return nodes;
}

function InlineContent({
  text,
  highlightTerms,
}: {
  text: string;
  highlightTerms?: string[];
}) {
  const nodes = useMemo(() => parseInline(text), [text]);

  return (
    <>
      {nodes.map((node, i) => {
        switch (node.type) {
          case "text":
            return (
              <HighlightedText
                key={i}
                text={node.content}
                terms={highlightTerms}
              />
            );
          case "code":
            return (
              <code
                key={i}
                className="bg-secondary/60 px-1.5 py-0.5 text-xs font-mono text-primary/90"
              >
                {node.content}
              </code>
            );
          case "bold":
            return (
              <strong key={i} className="font-semibold">
                <HighlightedText text={node.content} terms={highlightTerms} />
              </strong>
            );
          case "italic":
            return (
              <em key={i}>
                <HighlightedText text={node.content} terms={highlightTerms} />
              </em>
            );
          case "link": {
            // Security: only render http(s)/mailto links. Other schemes
            // (javascript:, data:, vbscript:) are dropped to plain text so a
            // crafted link in agent/message content can't execute on click.
            const href = node.href.trim();
            if (!/^(https?:|mailto:)/i.test(href)) {
              return (
                <HighlightedText
                  key={i}
                  text={node.text}
                  terms={highlightTerms}
                />
              );
            }
            return (
              <a
                key={i}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline underline-offset-2 decoration-primary/30 hover:decoration-primary/60 transition-colors"
              >
                {node.text}
              </a>
            );
          }
          case "br":
            return <br key={i} />;
        }
      })}
    </>
  );
}

/** Highlight search terms within a plain text string. */
function HighlightedText({ text, terms }: { text: string; terms?: string[] }) {
  if (!terms || terms.length === 0) return <>{text}</>;

  // Build a regex that matches any of the search terms (case-insensitive)
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-warning/30 text-warning px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
```

## ThemeSwitcher

- Source: `web/src/components/ThemeSwitcher.tsx`
- Description: Responsive dashboard theme and font picker for sidebar/header chrome.
- Key props: `collapsed, dropUp`

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Palette, Check, Type } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { BottomSheet } from "@nous-research/ui/ui/components/bottom-sheet";
import { Typography } from "@nous-research/ui/ui/components/typography/index";
import { useBelowBreakpoint } from "@nous-research/ui/hooks/use-below-breakpoint";
import { BUILTIN_THEMES, THEME_DEFAULT_FONT_ID, useTheme } from "@/themes";
import type { DashboardTheme, FontChoice, ThemeListEntry } from "@/themes";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

/**
 * Compact theme picker mounted next to the language switcher in the header.
 * Each dropdown row shows a 3-stop swatch (background / midground / warm
 * glow) so users can preview the palette before committing. User-defined
 * themes from `~/.hermes/dashboard-themes/*.yaml` use their API-provided
 * definitions so they show real palette swatches just like built-ins.
 *
 * When placed at the bottom of a container (e.g. the sidebar rail), pass
 * `dropUp` so the menu opens above the trigger instead of clipping below
 * the viewport. On viewports below the `sm` breakpoint, `dropUp` uses a
 * bottom sheet portaled to `document.body` so the picker is not clipped by
 * the sidebar (same idea as a responsive Drawer).
 */
export function ThemeSwitcher({ collapsed = false, dropUp = false }: ThemeSwitcherProps) {
  const { themeName, availableThemes, setTheme, fontId, fontChoices, setFont } = useTheme();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const narrowViewport = useBelowBreakpoint(640);
  const useMobileSheet = Boolean(dropUp && narrowViewport);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  useEffect(() => {
    if (!open || useMobileSheet) return;
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (wrapperRef.current?.contains(target)) return;
      if (dropdownRef.current?.contains(target)) return;
      close();
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open, close, useMobileSheet]);

  const current = availableThemes.find((th) => th.name === themeName);
  const label = current?.label ?? themeName;
  const sheetTitle = t.theme?.title ?? "Theme";

  return (
    <div ref={wrapperRef} className="relative">
      <Button
        ghost
        size={collapsed ? "icon" : undefined}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          collapsed
            ? "text-text-secondary hover:text-foreground hover:bg-transparent"
            : "px-2 py-1 normal-case tracking-normal font-normal text-xs text-text-secondary hover:text-foreground",
        )}
        title={`${t.theme?.switchTheme ?? "Switch theme"}: ${label}`}
        aria-label={t.theme?.switchTheme ?? "Switch theme"}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="inline-flex items-center gap-1.5">
          <Palette className="h-3.5 w-3.5" />

          {!collapsed && (
            <Typography
              className="hidden sm:inline text-display tracking-wide text-xs"
            >
              {label}
            </Typography>
          )}
        </span>
      </Button>

      {useMobileSheet && (
        <BottomSheet
          backdropDismissLabel={t.common.close}
          onClose={close}
          open={open}
          title={sheetTitle}
        >
          <div aria-label={sheetTitle} role="listbox">
            <ThemeSwitcherOptions
              availableThemes={availableThemes}
              close={close}
              setTheme={setTheme}
              themeName={themeName}
            />
            <FontSection
              fontChoices={fontChoices}
              fontId={fontId}
              setFont={setFont}
            />
          </div>
        </BottomSheet>
      )}

      {open && !useMobileSheet && (() => {
        const rect = wrapperRef.current?.getBoundingClientRect();
        const dropdown = (
          <div
            ref={dropdownRef}
            aria-label={sheetTitle}
            className={cn(
              "min-w-[240px] max-h-[70dvh] overflow-y-auto",
              "border border-current/20 bg-background-base/95",
              "shadow-[0_12px_32px_-8px_rgba(0,0,0,0.6)]",
              dropUp ? "fixed z-[100]" : "absolute z-50 right-0 top-full mt-1",
            )}
            role="listbox"
            style={
              dropUp && rect
                ? { bottom: window.innerHeight - rect.top + 4, left: rect.left }
                : undefined
            }
          >
            <div className="border-b border-current/20 px-3 py-2">
              <Typography
                className="text-display text-xs tracking-[0.12em] text-text-tertiary"
              >
                {sheetTitle}
              </Typography>
            </div>

            <ThemeSwitcherOptions
              availableThemes={availableThemes}
              close={close}
              setTheme={setTheme}
              themeName={themeName}
            />
            <FontSection
              fontChoices={fontChoices}
              fontId={fontId}
              setFont={setFont}
            />
          </div>
        );
        return dropUp ? createPortal(dropdown, document.body) : dropdown;
      })()}
    </div>
  );
}

function ThemeSwitcherOptions({
  availableThemes,
  close,
  setTheme,
  themeName,
}: ThemeSwitcherOptionsProps) {
  return (
    <>
      {availableThemes.map((th) => {
        const isActive = th.name === themeName;
        const paletteTheme = BUILTIN_THEMES[th.name] ?? th.definition;

        return (
          <ListItem
            active={isActive}
            aria-selected={isActive}
            className="gap-3"
            key={th.name}
            onClick={() => {
              setTheme(th.name);
              close();
            }}
            role="option"
          >
            {paletteTheme ? (
              <ThemeSwatch theme={paletteTheme} />
            ) : (
              <PlaceholderSwatch />
            )}

            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <Typography
                className="truncate text-display text-xs tracking-wide"
              >
                {th.label}
              </Typography>
              {th.description && (
                <Typography className="truncate text-xs tracking-normal text-text-tertiary">
                  {th.description}
                </Typography>
              )}
            </div>

            <Check
              className={cn(
                "h-3 w-3 shrink-0 text-midground",
                isActive ? "opacity-100" : "opacity-0",
              )}
            />
          </ListItem>
        );
      })}
    </>
  );
}

const FONT_CATEGORY_LABEL_KEY: Record<FontChoice["category"], "fontSans" | "fontSerif" | "fontMono"> = {
  sans: "fontSans",
  serif: "fontSerif",
  mono: "fontMono",
};

/** Font-override section rendered below the theme list. Lets the user pick
 *  any catalog font independently of the active theme, or "Theme default"
 *  to clear the override. Each row previews itself in its own font. */
function FontSection({ fontChoices, fontId, setFont }: FontSectionProps) {
  const { t } = useI18n();
  const order: FontChoice["category"][] = ["sans", "serif", "mono"];
  return (
    <>
      <div className="mt-1 border-t border-current/20 px-3 pb-1 pt-2">
        <span className="inline-flex items-center gap-1.5">
          <Type className="h-3 w-3 text-text-tertiary" />
          <Typography
            className="text-display text-xs tracking-[0.12em] text-text-tertiary"
          >
            {t.theme?.fontTitle ?? "Font"}
          </Typography>
        </span>
      </div>

      {/* Theme-default (clears the override). */}
      <ListItem
        active={fontId === THEME_DEFAULT_FONT_ID}
        aria-selected={fontId === THEME_DEFAULT_FONT_ID}
        className="gap-3"
        onClick={() => setFont(THEME_DEFAULT_FONT_ID)}
        role="option"
      >
        <span aria-hidden className="h-4 w-9 shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <Typography className="truncate text-xs tracking-normal">
            {t.theme?.fontDefault ?? "Theme default"}
          </Typography>
          <Typography className="truncate text-xs tracking-normal text-text-tertiary">
            {t.theme?.fontDefaultHint ?? "Use the active theme's font"}
          </Typography>
        </div>
        <Check
          className={cn(
            "h-3 w-3 shrink-0 text-midground",
            fontId === THEME_DEFAULT_FONT_ID ? "opacity-100" : "opacity-0",
          )}
        />
      </ListItem>

      {order.map((cat) => {
        const fonts = fontChoices.filter((f) => f.category === cat);
        if (fonts.length === 0) return null;
        const catLabel = t.theme?.[FONT_CATEGORY_LABEL_KEY[cat]] ?? cat;
        return (
          <div key={cat}>
            <div className="px-3 pb-0.5 pt-1.5">
              <Typography className="text-[0.65rem] uppercase tracking-[0.1em] text-text-tertiary">
                {catLabel}
              </Typography>
            </div>
            {fonts.map((f) => {
              const isActive = f.id === fontId;
              return (
                <ListItem
                  active={isActive}
                  aria-selected={isActive}
                  className="gap-3"
                  key={f.id}
                  onClick={() => setFont(f.id)}
                  role="option"
                >
                  <span aria-hidden className="h-4 w-9 shrink-0" />
                  <div className="flex min-w-0 flex-1 flex-col">
                    {/* Preview the font in its own stack. */}
                    <span
                      className="truncate text-sm"
                      style={{ fontFamily: f.stack }}
                    >
                      {f.label}
                    </span>
                  </div>
                  <Check
                    className={cn(
                      "h-3 w-3 shrink-0 text-midground",
                      isActive ? "opacity-100" : "opacity-0",
                    )}
                  />
                </ListItem>
              );
            })}
          </div>
        );
      })}
    </>
  );
}

function ThemeSwatch({ theme }: { theme: DashboardTheme }) {
  const [c1, c2, c3] = theme.swatchColors ?? [
    theme.palette.background.hex,
    theme.palette.midground.hex,
    theme.palette.warmGlow,
  ];
  return (
    <div
      aria-hidden
      className="flex h-4 w-9 shrink-0 overflow-hidden border border-current/20"
    >
      <span className="flex-1" style={{ background: c1 }} />
      <span className="flex-1" style={{ background: c2 }} />
      <span className="flex-1" style={{ background: c3 }} />
    </div>
  );
}

function PlaceholderSwatch() {
  return (
    <div
      aria-hidden
      className="h-4 w-9 shrink-0 border border-dashed border-current/20"
    />
  );
}

interface ThemeSwitcherOptionsProps {
  availableThemes: ThemeListEntry[];
  close: () => void;
  setTheme: (name: string) => void;
  themeName: string;
}

interface FontSectionProps {
  fontChoices: FontChoice[];
  fontId: string;
  setFont: (id: string) => void;
}

interface ThemeSwitcherProps {
  collapsed?: boolean;
  dropUp?: boolean;
}
```
