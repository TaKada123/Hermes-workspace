# Web theme and design tokens

## Compact token summary

- **Stack / CSS architecture:** React 19 + Vite 8; Tailwind CSS 4.3.3 through `@tailwindcss/vite`; `web/src/index.css` imports Tailwind plus `@nous-research/ui@0.18.2` `fonts.css` and `globals.css`. There is no repository `tailwind.config.*`; local extensions use Tailwind 4 `@theme inline`. The external package CSS is not present in this checkout, so only repository-owned raw sources are dumped below.
- **Theme application:** there is **no `.dark` selector**. `:root` contains the static Hermes Teal defaults; `ThemeProvider` switches named themes by writing inline CSS custom properties on `<html>`. User YAML themes can additionally inject scoped custom CSS, assets, component variables, color overrides, and layout variants.

### Colors

| Theme | Canvas/background | Primary text + accent (`midground`) | Foreground layer | Terminal | Notes |
|---|---:|---:|---:|---:|---|
| Hermes Teal (`default`) | `#041c1c` | `#ffe6cb` | `#ffffff` at alpha `0` | bg `#000000`, fg fallback `#f0e6d2` | Default `:root`; input series `#ffe6cb`, output series `#34d399` |
| Hermes Teal Large | same as default | same as default | same as default | fallback defaults | 18px base, spacious density |
| Nous Blue | `#E8F2FD` | `#0053FD` | `#170d02` at alpha `0` | bg `#f5f8fc`, fg `#170d02` | Light theme; series `#001934` / `#0053fd` |
| Midnight | `#08081c` | `#ddd6ff` | `#ffffff` at alpha `0` | fallback defaults | Brand stroke source `#8b80e8` |
| Ember | `#160800` | `#ffd8b0` | `#ffffff` at alpha `0` | fallback defaults | Destructive override `#c92d0f`, warning `#f97316` |
| Mono | `#0e0e0e` | `#eaeaea` | `#ffffff` at alpha `0` | fallback defaults | Zero radius |
| Cyberpunk | `#000a00` | `#00ff41` | `#ffffff` at alpha `0` | fallback defaults | success `#00ff88`, warning `#ffd700`, destructive `#ff0055` |
| Rosé | `#1a0f15` | `#ffd4e1` | `#ffffff` at alpha `0` | fallback defaults | Warm glow `rgba(249, 168, 212, 0.3)` |

Default shadcn-compatible semantics derive from the active three-layer palette: `foreground`, `card`/`popover` (4% midground mixed into background), `secondary` (6%), `muted` (8%), `accent` (10%), and `border`/`input` (15% midground over transparent). Fixed status colors are destructive `#fb2c36`, destructive foreground `#ffffff`, success `#4ade80`, warning `#ffbd38`; ring and primary use `midground`. Theme-specific `colorOverrides` win.

### Fonts and typography

- Default sans/display: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`.
- Default mono: `ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace`; code elements and `.font-mono*` use it.
- Bundled terminal face: **JetBrains Mono** (`400`, `700`, and italic `400`) from `/fonts-terminal/*.woff2`.
- Theme faces: Midnight `Inter` + `JetBrains Mono`; Ember `Spectral` + `IBM Plex Mono`; Mono `IBM Plex Sans` + `IBM Plex Mono`; Cyberpunk `Share Tech Mono` + `JetBrains Mono`; Rosé `Fraunces` + `DM Mono`. Fonts are loaded by vetted stylesheet URLs.
- User font override catalog: System Sans/Serif/Mono, Inter, IBM Plex Sans, Work Sans, Atkinson Hyperlegible, DM Sans, Spectral, Fraunces, Source Serif 4, JetBrains Mono, IBM Plex Mono, Space Mono.
- Base typography: `15px`, line-height `1.55`, letter-spacing `0`; Hermes Teal Large uses `18px` / `1.65`. Midnight letter-spacing is `-0.005em`. Explicit local element sizes: `small` = `1.0625rem` (15.9375px at the default 15px root; 19.125px in Large), `code` = `0.875rem` (13.125px default; 15.75px Large). No complete custom type scale is declared locally; Tailwind 4 and the imported Nous UI stylesheet supply utility/component scales.

### Spacing, radius, shadows, breakpoints

- Spacing base: `--spacing: calc(0.25rem * --theme-spacing-mul)`. Density multipliers: compact `0.85` (0.2125rem / 3.4px at 16px), comfortable `1` (0.25rem / 4px), spacious `1.2` (0.3rem / 4.8px).
- Radius base/default: `0.5rem`; derived `sm = base - 4px`, `md = base - 2px`, `lg = base`, `xl = base + 4px`. Theme bases: Midnight `0.75rem`, Ember `0.25rem`, Mono/Cyberpunk `0`, Rosé `1rem`, all others `0.5rem`.
- No custom global shadow token scale is declared. Components use Tailwind `shadow-sm`, `shadow-md`, `shadow-lg`, and `shadow-2xl`; explicit shadows found in web UI include terminal `0 8px 32px rgba(0, 0, 0, 0.4)`, theme menu `0 12px 32px -8px rgba(0,0,0,0.6)`, and Docs inset bevel `inset -1px -1px 0 0 #00000080, inset 1px 1px 0 0 #ffffff80`.
- Tailwind default breakpoints used by utilities: `sm 640px`, `md 768px`, `lg 1024px`, `xl 1280px`, `2xl 1536px` (not locally overridden). Local responsive logic also uses `640px` for mobile sheets, `1024px` for the app shell/sidebar, and one global CSS media query at `max-width: 768px` for document scrolling/height behavior.

## Raw source dumps

The following are complete repository source files relevant to web theme construction. `apps/shared/src/theme-presets.ts` is included because four web built-ins project their actual colors from that shared source of truth.

### `web/src/index.css`

```css
@import 'tailwindcss';
/* `fonts.css` must come BEFORE `globals.css`: as of @nous-research/ui 0.14.x,
   `globals.css` only declares the `--font-*` CSS variables (Collapse, Rules
   Compressed/Expanded, Mondwest). The `@font-face` registrations live in
   `fonts.css`, so without this import the DS variables resolve to font
   families the browser never loads and components fall back to a system
   stack (Tabs, Segmented, Typography, Buttons, etc. all look unstyled). */
@import '@nous-research/ui/styles/fonts.css';
@import '@nous-research/ui/styles/globals.css';

/* Scan the published design-system bundle so its utility classes survive
   Tailwind's JIT purge. */
@source '../node_modules/@nous-research/ui/dist';

/* ------------------------------------------------------------------ */
/* JetBrains Mono — bundled for the embedded TUI (/chat tab).          */
/* Gives the terminal a proper monospace font even on systems where    */
/* the user doesn't have one installed locally; xterm.js picks it up   */
/* via ChatPage's `fontFamily` option.                                 */
/* Apache-2.0.                                                         */
/* ------------------------------------------------------------------ */

@font-face {
  font-family: 'JetBrains Mono';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts-terminal/JetBrainsMono-Regular.woff2') format('woff2');
}
@font-face {
  font-family: 'JetBrains Mono';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url('/fonts-terminal/JetBrainsMono-Bold.woff2') format('woff2');
}
@font-face {
  font-family: 'JetBrains Mono';
  font-style: italic;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts-terminal/JetBrainsMono-Italic.woff2') format('woff2');
}

/* ------------------------------------------------------------------ */
/* Hermes Agent — Nous DS with the LENS_0 (Hermes teal) palette applied
   statically as the default dashboard theme. */
/* ------------------------------------------------------------------ */

:root {
  /* LENS_0 — from design-language/src/ui/components/overlays/index.tsx.
     These are the defaults for the `default` (Hermes Teal) dashboard theme;
     ThemeProvider rewrites them as inline styles when a user switches themes. */
  --foreground: color-mix(in srgb, #ffffff 0%, transparent);
  --foreground-base: #ffffff;
  --foreground-alpha: 0;
  --midground: color-mix(in srgb, #ffe6cb 100%, transparent);
  --midground-base: #ffe6cb;
  --midground-alpha: 1;
  --background: color-mix(in srgb, #041c1c 100%, transparent);
  --background-base: #041c1c;
  --background-alpha: 1;

  /* Typography tokens — rewritten by ThemeProvider. Defaults match the
     system stack so themes that don't override look native. */
  --theme-font-sans: system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  --theme-font-mono: ui-monospace, "SF Mono", "Cascadia Mono", Menlo,
    Consolas, monospace;
  --theme-font-display: var(--theme-font-sans);
  --theme-base-size: 15px;
  --theme-line-height: 1.55;
  --theme-letter-spacing: 0;

  /* Layout tokens. */
  --radius: 0.5rem;
  --theme-radius: 0.5rem;
  --theme-spacing-mul: 1;
  --theme-density: comfortable;

  /* Data-series accents — consumed by Analytics + Models pages for the
     input-vs-output token visualisations (chart bars, table values,
     legend swatches). Defaults are tuned for the Hermes-teal LENS_0
     look: cream input + emerald-400 output read as warm/cool against
     the dark canvas. Themes override via ThemeProvider, which emits
     these as `--series-input-token` / `--series-output-token`. */
  --series-input-token: #ffe6cb;
  --series-output-token: #34d399;
}

/* Theme tokens cascade into the document root so every descendant inherits
   the font stack, base size, and letter spacing without explicit calls. */
html {
  font-family: var(--theme-font-sans);
  font-size: var(--theme-base-size);
  line-height: var(--theme-line-height);
  letter-spacing: var(--theme-letter-spacing);
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
}

body {
  font-family: var(--theme-font-sans);
  min-height: 0;
  height: 100%;
  margin: 0;
  overflow: hidden;
}

code, kbd, pre, samp, .font-mono, .font-mono-ui {
  font-family: var(--theme-font-mono);
}

/* Density: scale the shadcn spacing utilities via a multiplier. The DS
   components use `p-N` / `gap-N` / `space-*` classes which resolve against
   Tailwind's spacing scale; multiplying `--spacing` at :root scales them
   all proportionally in Tailwind v4. */
@theme inline {
  --spacing: calc(0.25rem * var(--theme-spacing-mul, 1));
  --font-sans: var(--theme-font-sans);
  --font-mono: var(--theme-font-mono);
}

#root {
  min-height: 0;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

@media (max-width: 768px) {
  html,
  body,
  #root {
    min-height: 100dvh;
    height: auto;
    max-height: none;
    overflow-x: hidden;
    overflow-y: auto;
  }
}

/* Nousnet's hermes-agent layout bumps `small` and `code` to readable
   dashboard sizes. Keep in sync. */
small { font-size: 1.0625rem; }
code { font-size: 0.875rem; }

/* Shadcn-compat tokens.
   The dashboard's page code predates the Nous DS and uses shadcn-style
   utility classes (bg-card, text-muted-foreground, border-border, etc.)
   extensively. Rather than rewrite every call site, we expose those
   tokens on top of the Nous palette so classes continue to resolve. */
@theme inline {
  /* Remap foreground to midground so `text-foreground` / `bg-foreground`
     stay visible — in LENS_0, `--foreground` itself has alpha 0. */
  --color-foreground: var(--midground);

  --color-card: color-mix(in srgb, var(--midground-base) 4%, var(--background-base));
  --color-card-foreground: var(--midground);
  --color-primary: var(--midground);
  --color-primary-foreground: var(--background-base);
  --color-secondary: color-mix(in srgb, var(--midground-base) 6%, var(--background-base));
  --color-secondary-foreground: var(--midground);
  --color-muted: color-mix(in srgb, var(--midground-base) 8%, var(--background-base));
  /* Routes the shadcn `muted-foreground` slot through the DS semantic
     text-secondary token (defaults to midground 80%) so legacy call
     sites that use `text-muted-foreground` get a readable color
     instead of the old 55%-transparent default. */
  --color-muted-foreground: var(--color-text-secondary);
  --color-accent: color-mix(in srgb, var(--midground-base) 10%, var(--background-base));
  --color-accent-foreground: var(--midground);
  --color-destructive: #fb2c36;
  --color-destructive-foreground: #ffffff;
  --color-success: #4ade80;
  --color-warning: #ffbd38;
  --color-border: color-mix(in srgb, var(--midground-base) 15%, transparent);
  --color-input: color-mix(in srgb, var(--midground-base) 15%, transparent);
  --color-ring: var(--midground);
  --color-popover: color-mix(in srgb, var(--midground-base) 4%, var(--background-base));
  --color-popover-foreground: var(--midground);

  --radius-sm: calc(var(--theme-radius) - 4px);
  --radius-md: calc(var(--theme-radius) - 2px);
  --radius-lg: var(--theme-radius);
  --radius-xl: calc(var(--theme-radius) + 4px);
}


/* Collapsed sidebar tooltip entrance — skipped when moving between items. */
@keyframes sidebar-tooltip-in {
  from { opacity: 0; transform: translateY(-50%) translateX(-4px); }
  to   { opacity: 1; transform: translateY(-50%) translateX(0); }
}

/* Toast animations used by `components/Toast.tsx`. */
@keyframes toast-in {
  from { opacity: 0; transform: translateX(16px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes toast-out {
  from { opacity: 1; transform: translateX(0); }
  to   { opacity: 0; transform: translateX(16px); }
}

/* Generic fade + dialog entrance used by popovers and confirm dialogs. */
@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes dialog-in {
  from { opacity: 0; transform: translateY(4px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* Hide scrollbar utility — used by the header's overflow-x nav row. */
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-none::-webkit-scrollbar {
  display: none;
}

/* System UI-monospace stack — distinct from `font-courier` (Courier
   Prime), used for dense data readouts where the display font would
   break the grid. Routes through the theme's mono stack so themes
   with a different monospace (JetBrains Mono, IBM Plex Mono, etc.)
   still apply here. */
.font-mono-ui {
  font-family: var(--theme-font-mono);
}

/* Subtle grain overlay for badges. */
.grain {
  position: relative;
}
.grain::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.12;
  pointer-events: none;
  background: repeating-conic-gradient(currentColor 0% 25%, #0000 0% 50%) 0 0 /
    2px 2px;
}

/* RTL support — Arabic and any future right-to-left locale. The i18n provider
   sets `dir` on <html>; Tailwind v4's logical spacing utilities (ms-/me-,
   ps-/pe-) and logical properties then flip automatically. Scoped so the
   default LTR layout is untouched. */
html[dir="rtl"] {
  direction: rtl;
}
```

### `web/src/themes/types.ts`

```ts
/**
 * Dashboard theme model.
 *
 * Themes customise three orthogonal layers:
 *
 *   1. `palette`       — the 3-layer color triplet (background/midground/
 *                         foreground). Legacy `warmGlow` / `noiseOpacity`
 *                         fields remain for theme YAML compat but are unused
 *                         by the lightweight shell.
 *   2. `typography`    — font families, base font size, line height,
 *                         letter spacing. An optional `fontUrl` is injected
 *                         as `<link rel="stylesheet">` so self-hosted and
 *                         Google/Bunny/etc-hosted fonts both work.
 *   3. `layout`        — corner radius and density (spacing multiplier).
 *
 * Plus an optional `colorOverrides` escape hatch for themes that want to
 * pin specific shadcn tokens to exact values (e.g. a pastel theme that
 * needs a softer `destructive` red than the derived default).
 */

/** A color layer: hex base + alpha (0–1). */
export interface ThemeLayer {
  alpha: number;
  hex: string;
}

export interface ThemePalette {
  /** Deepest canvas color (typically near-black). */
  background: ThemeLayer;
  /** Primary text + accent. Most UI chrome reads this. */
  midground: ThemeLayer;
  /** Top-layer highlight. In LENS_0 this is white @ alpha 0 — invisible by
   *  default but still drives `--color-ring`-style accents. */
  foreground: ThemeLayer;
  /** Legacy palette field — kept for theme YAML compat. */
  warmGlow: string;
  /** Legacy palette field — kept for theme YAML compat. */
  noiseOpacity: number;
}

export interface ThemeTypography {
  /** CSS font-family stack for sans-serif body copy. */
  fontSans: string;
  /** CSS font-family stack for monospace / code blocks. */
  fontMono: string;
  /** Optional display/heading font stack. Falls back to `fontSans`. */
  fontDisplay?: string;
  /** Optional external stylesheet URL (e.g. Google Fonts, Bunny Fonts,
   *  self-hosted .woff2 @font-face sheet). Injected as a <link> in <head>
   *  on theme switch. Same URL is never injected twice. */
  fontUrl?: string;
  /** Root font size (controls rem scale). Example: `"14px"`, `"16px"`. */
  baseSize: string;
  /** Default line-height. Example: `"1.5"`, `"1.65"`. */
  lineHeight: string;
  /** Default letter-spacing. Example: `"0"`, `"0.01em"`, `"-0.01em"`. */
  letterSpacing: string;
}

export type ThemeDensity = "compact" | "comfortable" | "spacious";

export interface ThemeLayout {
  /** Corner-radius token. Example: `"0"`, `"0.25rem"`, `"0.5rem"`,
   *  `"1rem"`. Maps to `--radius` and cascades into every component. */
  radius: string;
  /** Spacing multiplier. `compact` = 0.85, `comfortable` = 1.0 (default),
   *  `spacious` = 1.2. Applied via the `--spacing-mul` CSS var. */
  density: ThemeDensity;
}

/** Overall layout variant the shell renders. `standard` = default single-
 *  column page layout. `cockpit` = reserves a left sidebar rail for a
 *  plugin slot (intended for HUD-style themes with persistent status panels).
 *  `tiled` = relaxes the main content max-width so pages can use the full
 *  viewport width. Themes set this; plugins react via CSS vars /
 *  `[data-layout-variant="..."]` selectors. */
export type ThemeLayoutVariant = "standard" | "cockpit" | "tiled";

/** Named hero/background assets a theme can populate. Each value is
 *  emitted as a CSS var (`--theme-asset-<name>`). Plugin slots and
 *  shell chrome may consume these via CSS. */
export interface ThemeAssets {
  /** Full-viewport background image URL. Exposed as `--theme-asset-bg` for
   *  the `backdrop` plugin slot or theme `customCSS`. */
  bg?: string;
  /** Hero render (Gundam, mascot, wallpaper) — for plugin sidebars/overlays. */
  hero?: string;
  /** Logo mark — header slot consumers use this. */
  logo?: string;
  /** Faction/brand crest — header-left decoration. */
  crest?: string;
  /** Secondary sidebar illustration. */
  sidebar?: string;
  /** Alternate header artwork. */
  header?: string;
  /** User-defined named assets. Keyed by [a-zA-Z0-9_-] only.
   *  Emitted as `--theme-asset-custom-<key>`. */
  custom?: Record<string, string>;
}

/** Component-style override buckets. Each bucket's entries become CSS
 *  vars (`--component-<bucket>-<kebab-property>`) that shell components
 *  (Card, App header/footer, etc.) read. Values are plain CSS
 *  strings — we don't parse them, so themes can use `clip-path`,
 *  `border-image`, `background`, `box-shadow`, and anything else CSS
 *  accepts. */
export interface ThemeComponentStyles {
  card?: Record<string, string>;
  header?: Record<string, string>;
  footer?: Record<string, string>;
  sidebar?: Record<string, string>;
  tab?: Record<string, string>;
  progress?: Record<string, string>;
  badge?: Record<string, string>;
  backdrop?: Record<string, string>;
  page?: Record<string, string>;
}

/** Data-series accent colors for chart + table visualisations (Analytics,
 *  Models, etc.). Themes provide hex strings; the provider emits them as
 *  `--series-input-token` / `--series-output-token` CSS vars consumed
 *  inline by pages that render input-vs-output token flows. Themes can
 *  omit either field to inherit the default token defined in
 *  `index.css` (Hermes-teal `#ffe6cb` for input, `#34d399` for output). */
export interface ThemeSeriesColors {
  /** Input-tokens series accent (Analytics chart bars + table values). */
  inputTokenAccent?: string;
  /** Output-tokens series accent. */
  outputTokenAccent?: string;
}

/** Optional hex overrides keyed by shadcn-compat token name (without the
 *  `--color-` prefix). Any key set here wins over the DS cascade. */
export interface ThemeColorOverrides {
  card?: string;
  cardForeground?: string;
  popover?: string;
  popoverForeground?: string;
  primary?: string;
  primaryForeground?: string;
  secondary?: string;
  secondaryForeground?: string;
  muted?: string;
  mutedForeground?: string;
  accent?: string;
  accentForeground?: string;
  destructive?: string;
  destructiveForeground?: string;
  success?: string;
  warning?: string;
  border?: string;
  input?: string;
  ring?: string;
}

export interface DashboardTheme {
  description: string;
  label: string;
  name: string;
  palette: ThemePalette;
  typography: ThemeTypography;
  layout: ThemeLayout;
  /** Overall shell layout. Defaults to `"standard"` when absent. */
  layoutVariant?: ThemeLayoutVariant;
  /** Named + custom asset URLs exposed as CSS vars on theme apply. */
  assets?: ThemeAssets;
  /** Raw CSS injected as a scoped `<style>` tag on theme apply, cleaned up
   *  on theme switch. Intended for selector-level chrome that's too
   *  expressive for componentStyles alone (e.g. `::before` pseudo-elements,
   *  complex animations, media queries). */
  customCSS?: string;
  /** Per-component CSS-var overrides. See `ThemeComponentStyles`. */
  componentStyles?: ThemeComponentStyles;
  colorOverrides?: ThemeColorOverrides;
  /** Data-series accent colors for Analytics/Models token charts. */
  seriesColors?: ThemeSeriesColors;
  /** Explicit 3-color swatch override for the theme picker. Order matches the
   *  default swatch cells: [background, midground, warmGlow]. */
  swatchColors?: [string, string, string];
  /** Background color for the embedded terminal pane (xterm.js).
   *  Hex string. Defaults to `"#000000"` when absent. */
  terminalBackground?: string;
  /** Default text/cursor color for the embedded terminal pane (xterm.js).
   *  Hex string. Defaults to `"#f0e6d2"` when absent. */
  terminalForeground?: string;
}

/**
 * Wire response shape for `GET /api/dashboard/themes`.
 *
 * The `themes` list is intentionally partial — built-in themes are fully
 * defined in `presets.ts`; user themes carry their full definition so the
 * client can apply them without a second round-trip.
 */
export interface ThemeListEntry {
  description: string;
  label: string;
  name: string;
  /** Full theme definition. Present for user-defined themes loaded from
   *  `~/.hermes/dashboard-themes/*.yaml`; undefined for built-ins (the
   *  client already has those in `BUILTIN_THEMES`). */
  definition?: DashboardTheme;
}

export interface ThemeListResponse {
  active: string;
  themes: ThemeListEntry[];
}
```

### `web/src/themes/fonts.ts`

```ts
/**
 * Curated UI-font catalog for the dashboard font override.
 *
 * The font override is an independent layer that sits ON TOP of the active
 * theme: a theme still ships its own `typography.fontSans` default, but a
 * user can pick any font here and it persists across theme switches. Picking
 * "Theme default" clears the override and returns to whatever the active
 * theme specifies.
 *
 * Why a curated catalog instead of a free-text font name + URL box: the
 * `fontUrl` is injected into the page as a `<link rel="stylesheet">`, so
 * accepting an arbitrary user-supplied URL would be a self-XSS / SSRF-ish
 * footgun in the dashboard. A vetted catalog keeps the injected origins
 * fixed (system stacks + Google Fonts) while still giving real choice. The
 * matching allow-list on the backend (`_FONT_CHOICES` in web_server.py)
 * rejects any id not defined here.
 *
 * Keep `FONT_CHOICES` in sync with `_FONT_CHOICES` in
 * `hermes_cli/web_server.py` — the ids must match exactly.
 */

/** System stacks reused from presets so "System" choices need no webfont. */
const SYSTEM_SANS =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const SYSTEM_MONO =
  'ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace';
const SYSTEM_SERIF =
  'Georgia, Cambria, "Times New Roman", Times, serif';

export type FontCategory = "sans" | "serif" | "mono";

export interface FontChoice {
  /** Stable id persisted in config / localStorage. */
  id: string;
  /** Human-readable label shown in the picker. */
  label: string;
  /** Rough grouping for the picker. */
  category: FontCategory;
  /** CSS font-family stack applied to `--theme-font-sans` (+ display). */
  stack: string;
  /** Optional Google-Fonts (or other vetted) stylesheet URL. */
  fontUrl?: string;
}

/** Sentinel id meaning "no override — use the active theme's font". */
export const THEME_DEFAULT_FONT_ID = "theme";

const GF = (family: string): string =>
  `https://fonts.googleapis.com/css2?family=${family}&display=swap`;

/**
 * The curated set. Order is the display order in the picker (grouped by
 * category in the UI). `stack` always ends in a system fallback so a font
 * that fails to load still renders something sane.
 */
export const FONT_CHOICES: FontChoice[] = [
  // ── System (no webfont fetch) ──────────────────────────────────────────
  { id: "system-sans", label: "System Sans", category: "sans", stack: SYSTEM_SANS },
  { id: "system-serif", label: "System Serif", category: "serif", stack: SYSTEM_SERIF },
  { id: "system-mono", label: "System Mono", category: "mono", stack: SYSTEM_MONO },

  // ── Sans ────────────────────────────────────────────────────────────────
  {
    id: "inter",
    label: "Inter",
    category: "sans",
    stack: `"Inter", ${SYSTEM_SANS}`,
    fontUrl: GF("Inter:wght@400;500;600;700"),
  },
  {
    id: "ibm-plex-sans",
    label: "IBM Plex Sans",
    category: "sans",
    stack: `"IBM Plex Sans", ${SYSTEM_SANS}`,
    fontUrl: GF("IBM+Plex+Sans:wght@400;500;600;700"),
  },
  {
    id: "work-sans",
    label: "Work Sans",
    category: "sans",
    stack: `"Work Sans", ${SYSTEM_SANS}`,
    fontUrl: GF("Work+Sans:wght@400;500;600;700"),
  },
  {
    id: "atkinson-hyperlegible",
    label: "Atkinson Hyperlegible",
    category: "sans",
    stack: `"Atkinson Hyperlegible", ${SYSTEM_SANS}`,
    fontUrl: GF("Atkinson+Hyperlegible:wght@400;700"),
  },
  {
    id: "dm-sans",
    label: "DM Sans",
    category: "sans",
    stack: `"DM Sans", ${SYSTEM_SANS}`,
    fontUrl: GF("DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700"),
  },

  // ── Serif ─────────────────────────────────────────────────────────────
  {
    id: "spectral",
    label: "Spectral",
    category: "serif",
    stack: `"Spectral", ${SYSTEM_SERIF}`,
    fontUrl: GF("Spectral:wght@400;500;600;700"),
  },
  {
    id: "fraunces",
    label: "Fraunces",
    category: "serif",
    stack: `"Fraunces", ${SYSTEM_SERIF}`,
    fontUrl: GF("Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600"),
  },
  {
    id: "source-serif",
    label: "Source Serif 4",
    category: "serif",
    stack: `"Source Serif 4", ${SYSTEM_SERIF}`,
    fontUrl: GF("Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700"),
  },

  // ── Mono ──────────────────────────────────────────────────────────────
  {
    id: "jetbrains-mono",
    label: "JetBrains Mono",
    category: "mono",
    stack: `"JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl: GF("JetBrains+Mono:wght@400;500;700"),
  },
  {
    id: "ibm-plex-mono",
    label: "IBM Plex Mono",
    category: "mono",
    stack: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl: GF("IBM+Plex+Mono:wght@400;500;700"),
  },
  {
    id: "space-mono",
    label: "Space Mono",
    category: "mono",
    stack: `"Space Mono", ${SYSTEM_MONO}`,
    fontUrl: GF("Space+Mono:wght@400;700"),
  },
];

const FONT_BY_ID: Record<string, FontChoice> = Object.fromEntries(
  FONT_CHOICES.map((f) => [f.id, f]),
);

/** Look up a font choice by id. Returns undefined for the theme-default
 *  sentinel and for any unknown id. */
export function getFontChoice(id: string | null | undefined): FontChoice | undefined {
  if (!id || id === THEME_DEFAULT_FONT_ID) return undefined;
  return FONT_BY_ID[id];
}

/** Whether an id refers to a real catalog font (vs. theme-default/unknown). */
export function isOverrideFont(id: string | null | undefined): boolean {
  return getFontChoice(id) !== undefined;
}
```

### `web/src/themes/presets.ts`

```ts
import { parseColor, THEME_PRESET_PALETTES, type ThemePresetPalette } from "@hermes/shared";
import type { DashboardTheme, ThemePalette, ThemeTypography, ThemeLayout } from "./types";

/**
 * Built-in dashboard themes.
 *
 * Each theme defines its own palette, typography, and layout so switching
 * themes produces visible changes beyond just color — fonts, density, and
 * corner-radius all shift to match the theme's personality.
 *
 * Theme names must stay in sync with the backend's
 * `_BUILTIN_DASHBOARD_THEMES` list in `hermes_cli/web_server.py`.
 *
 * Presets that also ship on the desktop (midnight, ember, mono, cyberpunk)
 * take their colours from `@hermes/shared` `THEME_PRESET_PALETTES` so both
 * surfaces render one palette; only typography/layout/overrides live here.
 */

// ---------------------------------------------------------------------------
// Shared typography / layout presets
// ---------------------------------------------------------------------------

/** Default system stack — neutral, safe fallback for every platform. */
const SYSTEM_SANS =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const SYSTEM_MONO =
  'ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace';

const DEFAULT_TYPOGRAPHY: ThemeTypography = {
  fontSans: SYSTEM_SANS,
  fontMono: SYSTEM_MONO,
  baseSize: "15px",
  lineHeight: "1.55",
  letterSpacing: "0",
};

const DEFAULT_LAYOUT: ThemeLayout = {
  radius: "0.5rem",
  density: "comfortable",
};

/**
 * Project a shared (desktop-shaped) preset palette onto the dashboard's
 * 3-slot model. The dashboard's `midground` is its text + primary-fill
 * colour, which is the desktop's `primary`; its `warmGlow` is the brand
 * accent stroke, which is the desktop's `midground` (falling back to `ring`).
 * `foreground` stays the dashboard's invisible white overlay. Dark palettes
 * are the dashboard's home turf, so a preset shipping `darkColors` is read
 * from that side.
 */
export function webPresetFromShared(
  preset: ThemePresetPalette,
): Omit<ThemePalette, "noiseOpacity"> {
  const colors = preset.darkColors ?? preset.colors;
  const [r, g, b] = parseColor(colors.midground ?? colors.ring) ?? [255, 255, 255];
  return {
    background: { hex: colors.background, alpha: 1 },
    midground: { hex: colors.primary, alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: `rgba(${r}, ${g}, ${b}, 0.3)`,
  };
}

// ---------------------------------------------------------------------------
// Themes
// ---------------------------------------------------------------------------

export const defaultTheme: DashboardTheme = {
  name: "default",
  label: "Hermes Teal",
  description: "Classic dark teal — the canonical Hermes look",
  palette: {
    background: { hex: "#041c1c", alpha: 1 },
    midground: { hex: "#ffe6cb", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(255, 189, 56, 0.35)",
    noiseOpacity: 1,
  },
  typography: DEFAULT_TYPOGRAPHY,
  layout: DEFAULT_LAYOUT,
  terminalBackground: "#000000",
};

export const midnightTheme: DashboardTheme = {
  name: "midnight",
  label: "Midnight",
  description: "Deep blue-violet with cool accents",
  palette: {
    ...webPresetFromShared(THEME_PRESET_PALETTES.midnight),
    noiseOpacity: 0.8,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Inter", ${SYSTEM_SANS}`,
    fontMono: `"JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap",
    letterSpacing: "-0.005em",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0.75rem",
  },
};

export const emberTheme: DashboardTheme = {
  name: "ember",
  label: "Ember",
  description: "Warm crimson and bronze — forge vibes",
  palette: {
    ...webPresetFromShared(THEME_PRESET_PALETTES.ember),
    noiseOpacity: 1,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Spectral", Georgia, "Times New Roman", serif`,
    fontMono: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0.25rem",
  },
  colorOverrides: {
    destructive: "#c92d0f",
    warning: "#f97316",
  },
};

export const monoTheme: DashboardTheme = {
  name: "mono",
  label: "Mono",
  description: "Clean grayscale — minimal and focused",
  palette: {
    ...webPresetFromShared(THEME_PRESET_PALETTES.mono),
    noiseOpacity: 0.6,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"IBM Plex Sans", ${SYSTEM_SANS}`,
    fontMono: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0",
  },
};

export const cyberpunkTheme: DashboardTheme = {
  name: "cyberpunk",
  label: "Cyberpunk",
  description: "Neon green on black — matrix terminal",
  palette: {
    ...webPresetFromShared(THEME_PRESET_PALETTES.cyberpunk),
    noiseOpacity: 1.2,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Share Tech Mono", "JetBrains Mono", ${SYSTEM_MONO}`,
    fontMono: `"Share Tech Mono", "JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=JetBrains+Mono:wght@400;700&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0",
  },
  colorOverrides: {
    success: "#00ff88",
    warning: "#ffd700",
    destructive: "#ff0055",
  },
};

export const roseTheme: DashboardTheme = {
  name: "rose",
  label: "Rosé",
  description: "Soft pink and warm ivory — easy on the eyes",
  palette: {
    background: { hex: "#1a0f15", alpha: 1 },
    midground: { hex: "#ffd4e1", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(249, 168, 212, 0.3)",
    noiseOpacity: 0.9,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Fraunces", Georgia, serif`,
    fontMono: `"DM Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=DM+Mono:wght@400;500&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "1rem",
  },
};

/** Light mode — vivid Nous-blue accents on a cream canvas. */
export const nousBlueTheme: DashboardTheme = {
  name: "nous-blue",
  label: "Nous Blue",
  description: "Light mode — vivid Nous-blue accents on cream canvas",
  palette: {
    background: { hex: "#E8F2FD", alpha: 1 },
    midground: { hex: "#0053FD", alpha: 1 },
    foreground: { hex: "#170d02", alpha: 0 },
    warmGlow: "rgba(0, 83, 253, 0.12)",
    noiseOpacity: 0,
  },
  typography: DEFAULT_TYPOGRAPHY,
  layout: DEFAULT_LAYOUT,
  terminalBackground: "#f5f8fc",
  terminalForeground: "#170d02",
  seriesColors: {
    inputTokenAccent: "#001934",
    outputTokenAccent: "#0053fd",
  },
  swatchColors: ["#170d02", "#0053FD", "#E8F2FD"],
};

/**
 * Same look as ``defaultTheme`` but with a larger root font size, looser
 * line-height, and ``spacious`` density so every rem-based size in the
 * dashboard scales up. For users who find the default 15px UI too dense.
 */
export const defaultLargeTheme: DashboardTheme = {
  name: "default-large",
  label: "Hermes Teal (Large)",
  description: "Hermes Teal with bigger fonts and roomier spacing",
  palette: defaultTheme.palette,
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    baseSize: "18px",
    lineHeight: "1.65",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    density: "spacious",
  },
};

export const BUILTIN_THEMES: Record<string, DashboardTheme> = {
  default: defaultTheme,
  "default-large": defaultLargeTheme,
  "nous-blue": nousBlueTheme,
  midnight: midnightTheme,
  ember: emberTheme,
  mono: monoTheme,
  cyberpunk: cyberpunkTheme,
  rose: roseTheme,
};
```

### `web/src/themes/context.tsx`

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { BUILTIN_THEMES, defaultTheme } from "./presets";
import {
  FONT_CHOICES,
  THEME_DEFAULT_FONT_ID,
  getFontChoice,
  type FontChoice,
} from "./fonts";
import type {
  DashboardTheme,
  ThemeAssets,
  ThemeColorOverrides,
  ThemeComponentStyles,
  ThemeDensity,
  ThemeLayer,
  ThemeLayout,
  ThemeLayoutVariant,
  ThemeListEntry,
  ThemePalette,
  ThemeSeriesColors,
  ThemeTypography,
} from "./types";
import { api } from "@/lib/api";

/** LocalStorage key — pre-applied before the React tree mounts to avoid
 *  a visible flash of the default palette on theme-overridden installs. */
const STORAGE_KEY = "hermes-dashboard-theme";

/** LocalStorage key for the font override (independent of theme). Holds a
 *  font id from the catalog in `fonts.ts`, or the `THEME_DEFAULT_FONT_ID`
 *  sentinel / absent = "use the active theme's font". Pre-applied before
 *  the React tree mounts (see `main.tsx`) to avoid a font flash. */
const FONT_STORAGE_KEY = "hermes-dashboard-font";

/** Renames of built-in theme keys we've shipped previously. Without this,
 *  users who saved one of the old names in localStorage (or had it
 *  persisted server-side) would silently fall back to `defaultTheme`
 *  because the lookup in `resolveTheme` no longer finds the stale key.
 *  Keep entries here until enough release cycles have passed that we can
 *  reasonably assume nobody still has the old value persisted. */
const THEME_NAME_ALIASES: Record<string, string> = {
  // Renamed during the LENS_5I port + Nous-blue rebrand.
  "lens-5i": "nous-blue",
};

function migrateThemeName(name: string): string {
  return THEME_NAME_ALIASES[name] ?? name;
}

/** Tracks fontUrls we've already injected so multiple theme switches don't
 *  pile up <link> tags. Keyed by URL. */
const INJECTED_FONT_URLS = new Set<string>();

// ---------------------------------------------------------------------------
// CSS variable builders
// ---------------------------------------------------------------------------

/** Turn a ThemeLayer into the two CSS expressions the DS consumes:
 *  `--<name>` (color-mix'd with alpha) and `--<name>-base` (opaque hex). */
function layerVars(
  name: "background" | "midground" | "foreground",
  layer: ThemeLayer,
): Record<string, string> {
  const pct = Math.round(layer.alpha * 100);
  return {
    [`--${name}`]: `color-mix(in srgb, ${layer.hex} ${pct}%, transparent)`,
    [`--${name}-base`]: layer.hex,
    [`--${name}-alpha`]: String(layer.alpha),
  };
}

function paletteVars(palette: ThemePalette): Record<string, string> {
  return {
    ...layerVars("background", palette.background),
    ...layerVars("midground", palette.midground),
    ...layerVars("foreground", palette.foreground),
  };
}

const DENSITY_MULTIPLIERS: Record<ThemeDensity, string> = {
  compact: "0.85",
  comfortable: "1",
  spacious: "1.2",
};

function typographyVars(typo: ThemeTypography): Record<string, string> {
  return {
    "--theme-font-sans": typo.fontSans,
    "--theme-font-mono": typo.fontMono,
    "--theme-font-display": typo.fontDisplay ?? typo.fontSans,
    "--theme-base-size": typo.baseSize,
    "--theme-line-height": typo.lineHeight,
    "--theme-letter-spacing": typo.letterSpacing,
  };
}

function layoutVars(layout: ThemeLayout): Record<string, string> {
  return {
    "--radius": layout.radius,
    "--theme-radius": layout.radius,
    "--theme-spacing-mul": DENSITY_MULTIPLIERS[layout.density] ?? "1",
    "--theme-density": layout.density,
  };
}

/** Map a color-overrides key (camelCase) to its `--color-*` CSS var. */
const OVERRIDE_KEY_TO_VAR: Record<keyof ThemeColorOverrides, string> = {
  card: "--color-card",
  cardForeground: "--color-card-foreground",
  popover: "--color-popover",
  popoverForeground: "--color-popover-foreground",
  primary: "--color-primary",
  primaryForeground: "--color-primary-foreground",
  secondary: "--color-secondary",
  secondaryForeground: "--color-secondary-foreground",
  muted: "--color-muted",
  mutedForeground: "--color-muted-foreground",
  accent: "--color-accent",
  accentForeground: "--color-accent-foreground",
  destructive: "--color-destructive",
  destructiveForeground: "--color-destructive-foreground",
  success: "--color-success",
  warning: "--color-warning",
  border: "--color-border",
  input: "--color-input",
  ring: "--color-ring",
};

/** Keys we might have written on a previous theme — needed to know which
 *  properties to clear when a theme with fewer overrides replaces one
 *  with more. */
const ALL_OVERRIDE_VARS = Object.values(OVERRIDE_KEY_TO_VAR);

function overrideVars(
  overrides: ThemeColorOverrides | undefined,
): Record<string, string> {
  if (!overrides) return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(overrides)) {
    if (!value) continue;
    const cssVar = OVERRIDE_KEY_TO_VAR[key as keyof ThemeColorOverrides];
    if (cssVar) out[cssVar] = value;
  }
  return out;
}

/** Map data-series accents to their CSS vars. Themes omit either field to
 *  inherit the `:root` default from `index.css`; when omitted we also
 *  proactively clear any leftover value from a previous theme so switches
 *  don't carry stale colors. */
const SERIES_KEY_TO_VAR: Record<keyof ThemeSeriesColors, string> = {
  inputTokenAccent: "--series-input-token",
  outputTokenAccent: "--series-output-token",
};

const ALL_SERIES_VARS = Object.values(SERIES_KEY_TO_VAR);

function seriesColorVars(
  series: ThemeSeriesColors | undefined,
): Record<string, string> {
  if (!series) return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(series)) {
    if (!value) continue;
    const cssVar = SERIES_KEY_TO_VAR[key as keyof ThemeSeriesColors];
    if (cssVar) out[cssVar] = value;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Asset + component-style + layout variant vars
// ---------------------------------------------------------------------------

/** Well-known named asset slots a theme may populate. Kept in sync with
 *  `_THEME_NAMED_ASSET_KEYS` in `hermes_cli/web_server.py`. */
const NAMED_ASSET_KEYS = ["bg", "hero", "logo", "crest", "sidebar", "header"] as const;

/** Component buckets mirrored from the backend's `_THEME_COMPONENT_BUCKETS`.
 *  Each bucket emits `--component-<bucket>-<kebab-prop>` CSS vars. */
const COMPONENT_BUCKETS = [
  "card", "header", "footer", "sidebar", "tab",
  "progress", "badge", "backdrop", "page",
] as const;

/** Camel → kebab (`clipPath` → `clip-path`). */
function toKebab(s: string): string {
  return s.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`);
}

/** Build `--theme-asset-*` CSS vars from the assets block. Values are wrapped
 *  in `url(...)` when they look like a bare path/URL; raw CSS expressions
 *  (`linear-gradient(...)`, pre-wrapped `url(...)`, `none`) pass through. */
function assetVars(assets: ThemeAssets | undefined): Record<string, string> {
  if (!assets) return {};
  const out: Record<string, string> = {};
  const wrap = (v: string): string => {
    const trimmed = v.trim();
    if (!trimmed) return "";
    // Already a CSS image/gradient/url/none — don't re-wrap.
    if (/^(url\(|linear-gradient|radial-gradient|conic-gradient|none$)/i.test(trimmed)) {
      return trimmed;
    }
    // Bare path / http(s) URL / data: URL → wrap in url().
    return `url("${trimmed.replace(/"/g, '\\"')}")`;
  };
  for (const key of NAMED_ASSET_KEYS) {
    const val = assets[key];
    if (typeof val === "string" && val.trim()) {
      out[`--theme-asset-${key}`] = wrap(val);
      out[`--theme-asset-${key}-raw`] = val;
    }
  }
  if (assets.custom) {
    for (const [key, val] of Object.entries(assets.custom)) {
      if (typeof val !== "string" || !val.trim()) continue;
      if (!/^[a-zA-Z0-9_-]+$/.test(key)) continue;
      out[`--theme-asset-custom-${key}`] = wrap(val);
      out[`--theme-asset-custom-${key}-raw`] = val;
    }
  }
  return out;
}

/** Build `--component-<bucket>-<prop>` CSS vars from the componentStyles
 *  block. Values pass through untouched so themes can use any CSS expression. */
function componentStyleVars(
  styles: ThemeComponentStyles | undefined,
): Record<string, string> {
  if (!styles) return {};
  const out: Record<string, string> = {};
  for (const bucket of COMPONENT_BUCKETS) {
    const props = (styles as Record<string, Record<string, string> | undefined>)[bucket];
    if (!props) continue;
    for (const [prop, value] of Object.entries(props)) {
      if (typeof value !== "string" || !value.trim()) continue;
      // Same guardrail as backend — camelCase or kebab-case alnum only.
      if (!/^[a-zA-Z0-9_-]+$/.test(prop)) continue;
      out[`--component-${bucket}-${toKebab(prop)}`] = value;
    }
  }
  return out;
}

// Tracks keys we set on the previous theme so we can clear them when the
// next theme has fewer assets / component vars. Without this, switching
// from a richly-decorated theme to a plain one would leave stale vars.
let _PREV_DYNAMIC_VAR_KEYS: Set<string> = new Set();

/** ID for the injected <style> tag that carries a theme's customCSS.
 *  A single tag is reused + replaced on every theme switch. */
const CUSTOM_CSS_STYLE_ID = "hermes-theme-custom-css";

function applyCustomCSS(css: string | undefined) {
  if (typeof document === "undefined") return;
  let el = document.getElementById(CUSTOM_CSS_STYLE_ID) as HTMLStyleElement | null;
  if (!css || !css.trim()) {
    if (el) el.remove();
    return;
  }
  if (!el) {
    el = document.createElement("style");
    el.id = CUSTOM_CSS_STYLE_ID;
    el.setAttribute("data-hermes-theme-css", "true");
    document.head.appendChild(el);
  }
  el.textContent = css;
}

function applyLayoutVariant(variant: ThemeLayoutVariant | undefined) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const final: ThemeLayoutVariant = variant ?? "standard";
  root.dataset.layoutVariant = final;
  root.style.setProperty("--theme-layout-variant", final);
}

// ---------------------------------------------------------------------------
// Font stylesheet injection
// ---------------------------------------------------------------------------

function injectFontStylesheet(url: string | undefined) {
  if (!url || typeof document === "undefined") return;
  if (INJECTED_FONT_URLS.has(url)) return;
  // Also skip if the page already has this href (e.g. SSR'd or persisted).
  const existing = document.querySelector<HTMLLinkElement>(
    `link[rel="stylesheet"][href="${CSS.escape(url)}"]`,
  );
  if (existing) {
    INJECTED_FONT_URLS.add(url);
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = url;
  link.setAttribute("data-hermes-theme-font", "true");
  document.head.appendChild(link);
  INJECTED_FONT_URLS.add(url);
}

// ---------------------------------------------------------------------------
// Font override (independent of theme)
// ---------------------------------------------------------------------------

/** The active font-override id, mirrored at module scope so `applyTheme`
 *  can re-assert it after every theme switch (theme application rewrites
 *  `--theme-font-sans`, so the override has to win again afterwards). */
let _ACTIVE_FONT_OVERRIDE: string = THEME_DEFAULT_FONT_ID;

/** Apply (or clear) the font override on `:root`. When a catalog font is
 *  active we override `--theme-font-sans` and `--theme-font-display` and
 *  inject its webfont; the theme keeps ownership of `--theme-font-mono`
 *  (code/terminal) so picking a body font doesn't mangle code blocks.
 *  Passing the theme-default sentinel removes the override so the theme's
 *  own font shows through. */
function applyFontOverride(fontId: string | undefined) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const choice: FontChoice | undefined = getFontChoice(fontId);
  if (!choice) {
    // Clear → fall back to whatever the active theme set (applyTheme already
    // wrote the theme's --theme-font-sans/-display before this runs).
    root.style.removeProperty("--theme-font-override-sans");
    return;
  }
  injectFontStylesheet(choice.fontUrl);
  // Set both the override marker var (used by the picker for diagnostics)
  // and the live consumed vars. We re-set the consumed vars directly so the
  // change is immediate and survives the next applyTheme via _ACTIVE_FONT_OVERRIDE.
  root.style.setProperty("--theme-font-override-sans", choice.stack);
  root.style.setProperty("--theme-font-sans", choice.stack);
  root.style.setProperty("--theme-font-display", choice.stack);
}

// ---------------------------------------------------------------------------
// Apply a full theme to :root
// ---------------------------------------------------------------------------

function applyTheme(theme: DashboardTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;

  // Clear any overrides from a previous theme before applying the new set.
  for (const cssVar of ALL_OVERRIDE_VARS) {
    root.style.removeProperty(cssVar);
  }
  // Same clear-then-set for series colors so a theme that defines them
  // (e.g. Nous Blue) doesn't leave its values behind when the user
  // switches to a theme that inherits the `:root` defaults.
  for (const cssVar of ALL_SERIES_VARS) {
    root.style.removeProperty(cssVar);
  }
  // Clear dynamic (asset/component) vars from the previous theme so the
  // new one starts clean — otherwise stale notched clip-paths, hero URLs,
  // etc. would bleed across theme switches.
  for (const prevKey of _PREV_DYNAMIC_VAR_KEYS) {
    root.style.removeProperty(prevKey);
  }

  const assetMap = assetVars(theme.assets);
  const componentMap = componentStyleVars(theme.componentStyles);
  _PREV_DYNAMIC_VAR_KEYS = new Set([
    ...Object.keys(assetMap),
    ...Object.keys(componentMap),
  ]);

  const vars = {
    ...paletteVars(theme.palette),
    ...typographyVars(theme.typography),
    ...layoutVars(theme.layout),
    ...overrideVars(theme.colorOverrides),
    ...seriesColorVars(theme.seriesColors),
    ...assetMap,
    ...componentMap,
  };
  for (const [k, v] of Object.entries(vars)) {
    root.style.setProperty(k, v);
  }

  injectFontStylesheet(theme.typography.fontUrl);
  applyCustomCSS(theme.customCSS);
  applyLayoutVariant(theme.layoutVariant);

  // Terminal colors — read by ChatPage via useTheme(); also available as CSS vars.
  root.style.setProperty(
    "--theme-terminal-background",
    theme.terminalBackground ?? "#000000",
  );
  root.style.setProperty(
    "--theme-terminal-foreground",
    theme.terminalForeground ?? "#f0e6d2",
  );

  // Re-assert the font override last: theme application just rewrote
  // --theme-font-sans/-display, so an active override has to win again.
  applyFontOverride(_ACTIVE_FONT_OVERRIDE);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ThemeProvider({ children }: { children: ReactNode }) {
  /** Name of the currently active theme (built-in id or user YAML name). */
  const [themeName, setThemeName] = useState<string>(() => {
    if (typeof window === "undefined") return "default";
    const stored = window.localStorage.getItem(STORAGE_KEY) ?? "default";
    const migrated = migrateThemeName(stored);
    // Write the migrated name back so future reads converge on the new
    // key and we eventually retire the alias entry.
    if (migrated !== stored) {
      window.localStorage.setItem(STORAGE_KEY, migrated);
    }
    return migrated;
  });

  /** All selectable themes (shown in the picker). Starts with just the
   *  built-ins; the API call below merges in user themes. */
  const [availableThemes, setAvailableThemes] = useState<ThemeListEntry[]>(() =>
    Object.values(BUILTIN_THEMES).map((t) => ({
      name: t.name,
      label: t.label,
      description: t.description,
    })),
  );

  /** Full definitions for user themes keyed by name — the API provides
   *  these so custom YAMLs apply without a client-side stub. */
  const [userThemeDefs, setUserThemeDefs] = useState<
    Record<string, DashboardTheme>
  >({});

  /** Active font-override id (independent of theme). `THEME_DEFAULT_FONT_ID`
   *  = no override. Seeded from localStorage so it's applied flash-free. */
  const [fontId, setFontId] = useState<string>(() => {
    if (typeof window === "undefined") return THEME_DEFAULT_FONT_ID;
    const stored = window.localStorage.getItem(FONT_STORAGE_KEY);
    const valid = stored && getFontChoice(stored) ? stored : THEME_DEFAULT_FONT_ID;
    _ACTIVE_FONT_OVERRIDE = valid;
    return valid;
  });

  // Resolve a theme name to a full DashboardTheme, falling back to default
  // only when neither a built-in nor a user theme is found.
  const resolveTheme = useCallback(
    (name: string): DashboardTheme => {
      return (
        BUILTIN_THEMES[name] ??
        userThemeDefs[name] ??
        defaultTheme
      );
    },
    [userThemeDefs],
  );

  // Apply the active theme (and re-assert the font override at its tail)
  // whenever the theme, the resolver, OR the font override changes. Folding
  // font into the same effect means clearing the override re-runs applyTheme,
  // which restores the theme's own font; setting it re-asserts the override.
  useEffect(() => {
    _ACTIVE_FONT_OVERRIDE = fontId;
    applyTheme(resolveTheme(themeName));
  }, [themeName, resolveTheme, fontId]);

  // Load server-side themes (built-ins + user YAMLs) once on mount.
  useEffect(() => {
    let cancelled = false;
    api
      .getThemes()
      .then((resp) => {
        if (cancelled) return;
        if (resp.themes?.length) {
          setAvailableThemes(
            resp.themes.map((t) => ({
              name: t.name,
              label: t.label,
              description: t.description,
              definition: t.definition,
            })),
          );
          // Index any definitions the server shipped (user themes).
          const defs: Record<string, DashboardTheme> = {};
          for (const entry of resp.themes) {
            if (entry.definition) {
              defs[entry.name] = entry.definition;
            }
          }
          if (Object.keys(defs).length > 0) setUserThemeDefs(defs);
        }
        if (resp.active) {
          const migratedActive = migrateThemeName(resp.active);
          if (migratedActive !== themeName) {
            setThemeName(migratedActive);
            window.localStorage.setItem(STORAGE_KEY, migratedActive);
          }
          // If the server is still persisting the stale key, push the
          // migrated value back so it converges too — otherwise every
          // future page load would re-trigger this branch.
          if (migratedActive !== resp.active) {
            api.setTheme(migratedActive).catch(() => {});
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load the server-persisted font override once on mount. The server is
  // the source of truth across browsers; localStorage just avoids the flash.
  useEffect(() => {
    let cancelled = false;
    api
      .getFontPref()
      .then((resp) => {
        if (cancelled) return;
        const serverId =
          resp?.font && getFontChoice(resp.font) ? resp.font : THEME_DEFAULT_FONT_ID;
        if (serverId !== fontId) {
          setFontId(serverId);
          if (typeof window !== "undefined") {
            window.localStorage.setItem(FONT_STORAGE_KEY, serverId);
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setTheme = useCallback(
    (name: string) => {
      // Accept any name the server told us exists OR any built-in.
      const knownNames = new Set<string>([
        ...Object.keys(BUILTIN_THEMES),
        ...availableThemes.map((t) => t.name),
        ...Object.keys(userThemeDefs),
      ]);
      const next = knownNames.has(name) ? name : "default";
      setThemeName(next);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, next);
      }
      api.setTheme(next).catch(() => {});
    },
    [availableThemes, userThemeDefs],
  );

  const setFont = useCallback((id: string) => {
    const next = getFontChoice(id) ? id : THEME_DEFAULT_FONT_ID;
    setFontId(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(FONT_STORAGE_KEY, next);
    }
    api.setFontPref(next).catch(() => {});
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme: resolveTheme(themeName),
      themeName,
      availableThemes,
      setTheme,
      fontId,
      fontChoices: FONT_CHOICES,
      setFont,
    }),
    [themeName, availableThemes, setTheme, resolveTheme, fontId, setFont],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: defaultTheme,
  themeName: "default",
  availableThemes: Object.values(BUILTIN_THEMES).map((t) => ({
    name: t.name,
    label: t.label,
    description: t.description,
  })),
  setTheme: () => {},
  fontId: THEME_DEFAULT_FONT_ID,
  fontChoices: FONT_CHOICES,
  setFont: () => {},
});

interface ThemeContextValue {
  availableThemes: ThemeListEntry[];
  setTheme: (name: string) => void;
  theme: DashboardTheme;
  themeName: string;
  /** Active font-override id (`THEME_DEFAULT_FONT_ID` = no override). */
  fontId: string;
  /** Curated font catalog for the picker. */
  fontChoices: FontChoice[];
  /** Set the font override (independent of theme). */
  setFont: (id: string) => void;
}
```

### `web/src/themes/index.ts`

```ts
export { ThemeProvider, useTheme } from "./context";
export { BUILTIN_THEMES, defaultTheme } from "./presets";
export {
  FONT_CHOICES,
  THEME_DEFAULT_FONT_ID,
  getFontChoice,
  isOverrideFont,
} from "./fonts";
export type { FontChoice, FontCategory } from "./fonts";
export type { DashboardTheme, ThemeLayer, ThemeListEntry, ThemeListResponse, ThemePalette } from "./types";
```

### `apps/shared/src/theme-presets.ts`

```ts
/**
 * Raw palette table for every built-in Hermes theme preset — the single source
 * of truth shared by the desktop app (which layers OKLCH synthesis, terminal
 * palettes and typography on top) and the web dashboard (which projects each
 * preset down to its 3-slot background/midground/foreground model via
 * `webPresetFromShared`). Edit a preset's colours HERE; both surfaces follow.
 *
 * The palette-bearing presets (nous, github, catppuccin, everforest, solarized)
 * are forks of their VS Code originals converted by the desktop's
 * `buildThemeFromMarketplace`; re-convert from the upstream extension rather
 * than hand-editing hexes. `nous-alt` is first-party — do not re-derive it.
 */

/** Tailwind-style colour slots a preset carries (light palette, or the only palette). */
export interface ThemePresetColors {
  background: string
  foreground: string
  card: string
  cardForeground: string
  muted: string
  mutedForeground: string
  popover: string
  popoverForeground: string
  primary: string
  primaryForeground: string
  secondary: string
  secondaryForeground: string
  accent: string
  accentForeground: string
  border: string
  input: string
  /** Generic focus ring — buttons, inputs, etc. */
  ring: string
  /**
   * Brand-accent stroke — focus rings, streaming cursors, active session
   * pills, branded scrollbars, text selection. Falls back to `ring`.
   * Aliased to the DS `--midground` token.
   */
  midground?: string
  /** Auto-derived from `midground` luminance when omitted. */
  midgroundForeground?: string
  /** Composer outline / focus color. Falls back to `midground`. */
  composerRing?: string
  destructive: string
  destructiveForeground: string
  sidebarBackground?: string
  sidebarBorder?: string
  userBubble?: string
  userBubbleBorder?: string
}

export interface ThemePresetPalette {
  /** Light palette (also reused for dark when `darkColors` is omitted). */
  colors: ThemePresetColors
  /** Hand-tuned dark palette. Skins like `nous` ship one. */
  darkColors?: ThemePresetColors
}

const NOUS_ALT_BLUE = '#0053FD'
const NOUS_ALT_NAVY = '#1540B1'
const NOUS_ALT_CREAM = '#FFE6CB'

const nousAltTint = (pct: number) => `color-mix(in srgb, ${NOUS_ALT_BLUE} ${pct}%, #FFFFFF)`
const nousAltTintTransparent = (pct: number) => `color-mix(in srgb, ${NOUS_ALT_BLUE} ${pct}%, transparent)`

export const THEME_PRESET_PALETTES = {
  github: {
    colors: {
      background: '#ffffff',
      foreground: '#1f2328',
      card: '#f6f8fa',
      cardForeground: '#1f2328',
      muted: '#f6f6f6',
      mutedForeground: '#656d76',
      popover: '#ffffff',
      popoverForeground: '#1f2328',
      primary: '#196d31',
      primaryForeground: '#ffffff',
      secondary: '#dfebe2',
      secondaryForeground: '#1f2328',
      accent: '#e3ede6',
      accentForeground: '#1f2328',
      border: '#d0d7de',
      input: '#ffffff',
      ring: '#196d31',
      midground: '#196d31',
      midgroundForeground: '#ffffff',
      composerRing: '#196d31',
      destructive: '#cf222e',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#f6f8fa',
      sidebarBorder: '#d0d7de',
      userBubble: '#dbe7e2',
      userBubbleBorder: '#d0d7de'
    },
    darkColors: {
      background: '#0d1117',
      foreground: '#e6edf3',
      card: '#010409',
      cardForeground: '#e6edf3',
      muted: '#1a1e24',
      mutedForeground: '#7d8590',
      popover: '#161b22',
      popoverForeground: '#e6edf3',
      primary: '#4f9e5e',
      primaryForeground: '#ffffff',
      secondary: '#1f382b',
      secondaryForeground: '#e6edf3',
      accent: '#192a24',
      accentForeground: '#e6edf3',
      border: '#30363d',
      input: '#0d1117',
      ring: '#4f9e5e',
      midground: '#4f9e5e',
      midgroundForeground: '#ffffff',
      composerRing: '#4f9e5e',
      destructive: '#f85149',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#010409',
      sidebarBorder: '#30363d',
      userBubble: '#0f2018',
      userBubbleBorder: '#30363d'
    }
  },
  nous: {
    colors: {
      background: '#ffffff',
      foreground: '#1f2328',
      card: '#f6f8fa',
      cardForeground: '#1f2328',
      muted: '#f6f6f6',
      mutedForeground: '#656d76',
      popover: '#ffffff',
      popoverForeground: '#1f2328',
      primary: '#0053fd',
      primaryForeground: '#ffffff',
      secondary: '#deeaff',
      secondaryForeground: '#1f2328',
      accent: '#e3edff',
      accentForeground: '#1f2328',
      border: '#d0d7de',
      input: '#ffffff',
      ring: '#0053fd',
      midground: '#0053fd',
      midgroundForeground: '#ffffff',
      composerRing: '#0053fd',
      destructive: '#cf222e',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#f6f8fa',
      sidebarBorder: '#d0d7de',
      userBubble: '#dae7fd',
      userBubbleBorder: '#d0d7de'
    },
    darkColors: {
      background: '#0d1117',
      foreground: '#e6edf3',
      card: '#010409',
      cardForeground: '#e6edf3',
      muted: '#1a1e24',
      mutedForeground: '#7d8590',
      popover: '#161b22',
      popoverForeground: '#e6edf3',
      primary: '#4a84fe',
      primaryForeground: '#161616',
      secondary: '#1d2e4f',
      secondaryForeground: '#e6edf3',
      accent: '#17243a',
      accentForeground: '#e6edf3',
      border: '#30363d',
      input: '#0d1117',
      ring: '#4a84fe',
      midground: '#4a84fe',
      midgroundForeground: '#161616',
      composerRing: '#4a84fe',
      destructive: '#f85149',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#010409',
      sidebarBorder: '#30363d',
      userBubble: '#07162c',
      userBubbleBorder: '#30363d'
    }
  },
  catppuccin: {
    colors: {
      background: '#eff1f5',
      foreground: '#4c4f69',
      card: '#e6e9ef',
      cardForeground: '#4c4f69',
      muted: '#e8ebef',
      mutedForeground: '#4c4f69',
      popover: '#e6e9ef',
      popoverForeground: '#4c4f69',
      primary: '#6d2ebf',
      primaryForeground: '#ffffff',
      secondary: '#ddd6ed',
      secondaryForeground: '#4c4f69',
      accent: '#dfdaef',
      accentForeground: '#4c4f69',
      border: '#acb0be',
      input: '#ccd0da',
      ring: '#6d2ebf',
      midground: '#6d2ebf',
      midgroundForeground: '#ffffff',
      composerRing: '#6d2ebf',
      destructive: '#d20f39',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#e6e9ef',
      sidebarBorder: '#acb0be',
      userBubble: '#d7d3e9',
      userBubbleBorder: '#acb0be'
    },
    darkColors: {
      background: '#1e1e2e',
      foreground: '#cdd6f4',
      card: '#181825',
      cardForeground: '#cdd6f4',
      muted: '#29293a',
      mutedForeground: '#cdd6f4',
      popover: '#181825',
      popoverForeground: '#cdd6f4',
      primary: '#cba6f7',
      primaryForeground: '#ffffff',
      secondary: '#4e4466',
      secondaryForeground: '#cdd6f4',
      accent: '#3d3652',
      accentForeground: '#cdd6f4',
      border: '#585b70',
      input: '#313244',
      ring: '#cba6f7',
      midground: '#cba6f7',
      midgroundForeground: '#ffffff',
      composerRing: '#cba6f7',
      destructive: '#f38ba8',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#181825',
      sidebarBorder: '#585b70',
      userBubble: '#38324b',
      userBubbleBorder: '#585b70'
    }
  },
  everforest: {
    colors: {
      background: '#fdf6e3',
      foreground: '#5c6a72',
      card: '#fdf6e3',
      cardForeground: '#5c6a72',
      muted: '#f7f0de',
      mutedForeground: '#939f91',
      popover: '#fdf6e3',
      popoverForeground: '#5c6a72',
      primary: '#586b35',
      primaryForeground: '#ffffff',
      secondary: '#e6e3cb',
      secondaryForeground: '#5c6a72',
      accent: '#e9e5ce',
      accentForeground: '#5c6a72',
      border: '#fdf6e3',
      input: '#fdf6e3',
      ring: '#586b35',
      midground: '#586b35',
      midgroundForeground: '#ffffff',
      composerRing: '#586b35',
      destructive: '#f1706f',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#fdf6e3',
      sidebarBorder: '#fdf6e3',
      userBubble: '#e9e5ce',
      userBubbleBorder: '#fdf6e3'
    },
    darkColors: {
      background: '#2d353b',
      foreground: '#d3c6aa',
      card: '#2d353b',
      cardForeground: '#d3c6aa',
      muted: '#373e42',
      mutedForeground: '#859289',
      popover: '#2d353b',
      popoverForeground: '#d3c6aa',
      primary: '#a7c080',
      primaryForeground: '#ffffff',
      secondary: '#4f5c4e',
      secondaryForeground: '#d3c6aa',
      accent: '#434e47',
      accentForeground: '#d3c6aa',
      border: '#2d353b',
      input: '#2d353b',
      ring: '#a7c080',
      midground: '#a7c080',
      midgroundForeground: '#ffffff',
      composerRing: '#a7c080',
      destructive: '#da6362',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#2d353b',
      sidebarBorder: '#2d353b',
      userBubble: '#434e47',
      userBubbleBorder: '#2d353b'
    }
  },
  solarized: {
    colors: {
      background: '#fdf6e3',
      foreground: '#1f1f1f',
      card: '#d3cbb7',
      cardForeground: '#1f1f1f',
      muted: '#f4eddb',
      mutedForeground: '#9ca8a6',
      popover: '#eee8d5',
      popoverForeground: '#1f1f1f',
      primary: '#675e34',
      primaryForeground: '#ffffff',
      secondary: '#e8e1cb',
      secondaryForeground: '#1f1f1f',
      accent: '#ebe4ce',
      accentForeground: '#1f1f1f',
      border: '#ddd6c1',
      input: '#ddd6c1',
      ring: '#675e34',
      midground: '#675e34',
      midgroundForeground: '#ffffff',
      composerRing: '#675e34',
      destructive: '#e25563',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#eee8d5',
      sidebarBorder: '#ddd6c1',
      userBubble: '#c6bea7',
      userBubbleBorder: '#ddd6c1'
    },
    darkColors: {
      background: '#002b36',
      foreground: '#839496',
      card: '#002b36',
      cardForeground: '#839496',
      muted: '#08313c',
      mutedForeground: '#586e75',
      popover: '#001f26',
      popoverForeground: '#839496',
      primary: '#6ea1c4',
      primaryForeground: '#ffffff',
      secondary: '#1f4c5e',
      secondaryForeground: '#839496',
      accent: '#144050',
      accentForeground: '#839496',
      border: '#234751',
      input: '#073642',
      ring: '#6ea1c4',
      midground: '#6ea1c4',
      midgroundForeground: '#ffffff',
      composerRing: '#6ea1c4',
      destructive: '#e35957',
      destructiveForeground: '#ffffff',
      sidebarBackground: '#001f26',
      sidebarBorder: '#234751',
      userBubble: '#144050',
      userBubbleBorder: '#234751'
    }
  },
  'nous-alt': {
    colors: {
      background: '#F8FAFF',
      foreground: '#17171A',
      card: '#FFFFFF',
      cardForeground: '#17171A',
      muted: nousAltTint(5),
      mutedForeground: '#666678',
      popover: '#FFFFFF',
      popoverForeground: '#17171A',
      primary: NOUS_ALT_BLUE,
      primaryForeground: '#FCFCFC',
      secondary: nousAltTint(7),
      secondaryForeground: '#242432',
      accent: nousAltTint(10),
      accentForeground: '#202030',
      border: nousAltTintTransparent(22),
      input: nousAltTintTransparent(30),
      ring: NOUS_ALT_BLUE,
      midground: NOUS_ALT_BLUE,
      composerRing: NOUS_ALT_BLUE,
      destructive: '#C72E4D',
      destructiveForeground: '#FFFFFF',
      sidebarBackground: '#F3F7FF',
      sidebarBorder: nousAltTintTransparent(18),
      userBubble: nousAltTint(6),
      userBubbleBorder: nousAltTintTransparent(24)
    },
    darkColors: {
      background: '#0D2F86',
      foreground: NOUS_ALT_CREAM,
      card: '#12378F',
      cardForeground: NOUS_ALT_CREAM,
      muted: '#183F9A',
      mutedForeground: '#B5C7F3',
      popover: '#123A96',
      popoverForeground: NOUS_ALT_CREAM,
      primary: NOUS_ALT_CREAM,
      primaryForeground: '#0D2F86',
      secondary: '#1B45A4',
      secondaryForeground: '#E0E8FF',
      accent: NOUS_ALT_NAVY,
      accentForeground: '#F0F4FF',
      border: '#3158AD',
      input: '#0B2566',
      ring: NOUS_ALT_CREAM,
      midground: NOUS_ALT_BLUE,
      composerRing: NOUS_ALT_CREAM,
      destructive: '#C0473A',
      destructiveForeground: '#FEF2F2',
      sidebarBackground: '#09286F',
      sidebarBorder: '#234A9C',
      userBubble: '#143B91',
      userBubbleBorder: '#3A63BD'
    }
  },
  midnight: {
    colors: {
      background: '#08081c',
      foreground: '#ddd6ff',
      card: '#0d0d28',
      cardForeground: '#ddd6ff',
      muted: '#13133a',
      mutedForeground: '#7c7ab0',
      popover: '#0f0f2e',
      popoverForeground: '#ddd6ff',
      primary: '#ddd6ff',
      primaryForeground: '#08081c',
      secondary: '#1a1a4a',
      secondaryForeground: '#c4bff0',
      accent: '#1a1a44',
      accentForeground: '#d0c8ff',
      border: '#1e1e52',
      input: '#1e1e52',
      ring: '#8b80e8',
      midground: '#8b80e8',
      destructive: '#b03060',
      destructiveForeground: '#fef2f2',
      sidebarBackground: '#06061a',
      sidebarBorder: '#12123a',
      userBubble: '#14143a',
      userBubbleBorder: '#242466'
    }
  },
  ember: {
    colors: {
      background: '#160800',
      foreground: '#ffd8b0',
      card: '#1e0e04',
      cardForeground: '#ffd8b0',
      muted: '#2a1408',
      mutedForeground: '#aa7a56',
      popover: '#221008',
      popoverForeground: '#ffd8b0',
      primary: '#ffd8b0',
      primaryForeground: '#160800',
      secondary: '#341800',
      secondaryForeground: '#f0c090',
      accent: '#301600',
      accentForeground: '#e8c080',
      border: '#3a1c08',
      input: '#3a1c08',
      ring: '#d97316',
      midground: '#d97316',
      destructive: '#c43010',
      destructiveForeground: '#fef2f2',
      sidebarBackground: '#100600',
      sidebarBorder: '#2a1004',
      userBubble: '#2a1000',
      userBubbleBorder: '#4a2010'
    }
  },
  mono: {
    colors: {
      background: '#0e0e0e',
      foreground: '#eaeaea',
      card: '#141414',
      cardForeground: '#eaeaea',
      muted: '#1e1e1e',
      mutedForeground: '#808080',
      popover: '#181818',
      popoverForeground: '#eaeaea',
      primary: '#eaeaea',
      primaryForeground: '#0e0e0e',
      secondary: '#262626',
      secondaryForeground: '#c8c8c8',
      accent: '#222222',
      accentForeground: '#d8d8d8',
      border: '#2a2a2a',
      input: '#2a2a2a',
      ring: '#9a9a9a',
      midground: '#9a9a9a',
      destructive: '#a84040',
      destructiveForeground: '#fef2f2',
      sidebarBackground: '#0a0a0a',
      sidebarBorder: '#202020',
      userBubble: '#1a1a1a',
      userBubbleBorder: '#363636'
    }
  },
  cyberpunk: {
    colors: {
      background: '#000a00',
      foreground: '#00ff41',
      card: '#001200',
      cardForeground: '#00ff41',
      muted: '#001a00',
      mutedForeground: '#1a8a30',
      popover: '#001000',
      popoverForeground: '#00ff41',
      primary: '#00ff41',
      primaryForeground: '#000a00',
      secondary: '#002800',
      secondaryForeground: '#00cc34',
      accent: '#002000',
      accentForeground: '#00e038',
      border: '#003000',
      input: '#003000',
      ring: '#00ff41',
      midground: '#00ff41',
      destructive: '#ff003c',
      destructiveForeground: '#000a00',
      sidebarBackground: '#000600',
      sidebarBorder: '#001800',
      userBubble: '#001400',
      userBubbleBorder: '#004800'
    }
  },
  slate: {
    colors: {
      background: '#0d1117',
      foreground: '#c9d1d9',
      card: '#161b22',
      cardForeground: '#c9d1d9',
      muted: '#21262d',
      mutedForeground: '#8b949e',
      popover: '#1c2128',
      popoverForeground: '#c9d1d9',
      primary: '#c9d1d9',
      primaryForeground: '#0d1117',
      secondary: '#2a3038',
      secondaryForeground: '#adb5bf',
      accent: '#1e2530',
      accentForeground: '#c0c8d0',
      border: '#30363d',
      input: '#30363d',
      ring: '#58a6ff',
      midground: '#58a6ff',
      destructive: '#cf4848',
      destructiveForeground: '#fef2f2',
      sidebarBackground: '#090d13',
      sidebarBorder: '#1c2228',
      userBubble: '#1e2a38',
      userBubbleBorder: '#2e4060'
    }
  }
} satisfies Record<string, ThemePresetPalette>

export type ThemePresetName = keyof typeof THEME_PRESET_PALETTES
```

### `web/vite.config.ts`

```ts
import { defineConfig, type Plugin } from "vite";
import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";

/** React Compiler preset scoped to modules that can actually contain
 *  components/hooks (JSX syntax or a react-ish import). The preset's default
 *  code filter matches any PascalCase/use* declaration — effectively every TS
 *  module — which made the babel pass parse the whole codebase. */
function compilerPreset() {
  const preset = reactCompilerPreset();
  preset.rolldown.filter.code = /\/>|<\/|from\s*['"][^'"]*react/;
  return preset;
}
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { fileURLToPath } from "node:url";

const configDir: string = fileURLToPath(new URL(".", import.meta.url));

const BACKEND = process.env.HERMES_DASHBOARD_URL ?? "http://127.0.0.1:9119";

/**
 * In production the Python `hermes dashboard` server injects a one-shot
 * session token into `index.html` (see `hermes_cli/web_server.py`). The
 * Vite dev server serves its own `index.html`, so unless we forward that
 * token, every protected `/api/*` call 401s.
 *
 * This plugin fetches the running dashboard's `index.html` on each dev page
 * load and forwards its runtime bootstrap values into the dev HTML. No-op in
 * production builds.
 */
function hermesDevToken(): Plugin {
  const TOKEN_RE = /window\.__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"/;
  const EMBEDDED_RE =
    /window\.__HERMES_DASHBOARD_EMBEDDED_CHAT__\s*=\s*(true|false)/;
  const INITIAL_PROFILE_RE =
    /window\.__HERMES_INITIAL_PROFILE__\s*=\s*("(?:\\.|[^"\\])*")/;

  return {
    name: "hermes:dev-session-token",
    apply: "serve",
    async transformIndexHtml() {
      try {
        const res = await fetch(BACKEND, { headers: { accept: "text/html" } });
        const html = await res.text();
        const match = html.match(TOKEN_RE);
        if (!match) {
          console.warn(
            `[hermes] Could not find session token in ${BACKEND} — ` +
              `is \`hermes dashboard\` running? /api calls will 401.`,
          );
          return;
        }
        const embeddedMatch = html.match(EMBEDDED_RE);
        const embeddedJs = embeddedMatch ? embeddedMatch[1] : "true";
        const initialProfileMatch = html.match(INITIAL_PROFILE_RE);
        const initialProfileJs = initialProfileMatch?.[1] ?? '""';
        return [
          {
            tag: "script",
            injectTo: "head",
            children:
              `window.__HERMES_SESSION_TOKEN__="${match[1]}";` +
              `window.__HERMES_DASHBOARD_EMBEDDED_CHAT__=${embeddedJs};` +
              `window.__HERMES_INITIAL_PROFILE__=${initialProfileJs};`,
          },
        ];
      } catch (err) {
        console.warn(
          `[hermes] Dashboard at ${BACKEND} unreachable — ` +
            `start it with \`hermes dashboard\` or set HERMES_DASHBOARD_URL. ` +
            `(${(err as Error).message})`,
        );
      }
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [compilerPreset()] }),
    tailwindcss(),
    hermesDevToken(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(configDir, "./src"),
      "@hermes/shared": path.resolve(configDir, "../apps/shared/src"),
    },
    // When @nous-research/ui is symlinked via `file:../../design-language`,
    // Node's module resolution would pick up shared deps from
    // design-language/node_modules/*, giving us two copies + breaking
    // hooks (useRef-of-null), webgl contexts, etc. Force everything that
    // exists in BOTH places to use the dashboard's copy.
    //
    // Don't list packages here that only exist in the DS (nanostores,
    // @nanostores/react) — Vite dedupe errors out when it can't find
    // them at the project root.
    dedupe: [
      "react",
      "react-dom",
      "@react-three/fiber",
      "@observablehq/plot",
      "three",
      "leva",
      "gsap",
    ],
  },
  build: {
    outDir: "../hermes_cli/web_dist",
    emptyOutDir: true,
    // Shell stays a bit over Vite's 500 kB default after vendor splits;
    // page/xterm chunks load on demand. Keep a modest ceiling so a true
    // regression still warns.
    chunkSizeWarningLimit: 600,
    // Split heavy vendors so the first dashboard paint does not download
    // xterm/three/plot/etc. until a route actually needs them. Lazy page
    // imports in App.tsx create the route boundaries; these groups keep
    // shared node_modules out of every page chunk.
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20_000,
          groups: [
            {
              name: "react-vendor",
              test: /node_modules[\\/](react|react-dom|scheduler|react-router|react-router)([\\/]|$)/,
            },
            {
              name: "xterm",
              test: /node_modules[\\/]@xterm[\\/]/,
            },
            {
              name: "three",
              test: /node_modules[\\/](three|@react-three)([\\/]|$)/,
            },
            {
              name: "plot",
              test: /node_modules[\\/]@observablehq[\\/]plot([\\/]|$)/,
            },
            {
              name: "motion",
              test: /node_modules[\\/](motion|framer-motion)([\\/]|$)/,
            },
            {
              name: "ui",
              test: /node_modules[\\/]@nous-research[\\/]ui([\\/]|$)/,
            },
            {
              name: "vendor",
              test: /node_modules[\\/]/,
            },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: BACKEND,
        ws: true,
      },
      // Same host as `hermes dashboard` must serve these; Vite has no
      // dashboard-plugins/* files, so without this, plugin scripts 404
      // or receive index.html in dev.
      "/dashboard-plugins": BACKEND,
    },
  },
});
```

### `web/package.json`

```json
{
  "name": "web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "node ../scripts/build/web.mjs",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "fix": "npm run lint:fix",
    "preview": "vite preview",
    "typecheck": "tsc -p . --noEmit",
    "test": "vitest run",
    "check": "npm run typecheck && npm run test && npm run lint"
  },
  "dependencies": {
    "@hermes/shared": "file:../apps/shared",
    "@nous-research/ui": "0.18.2",
    "@observablehq/plot": "0.6.17",
    "@react-three/fiber": "9.6.1",
    "@tailwindcss/vite": "4.3.3",
    "@xterm/addon-fit": "0.11.0",
    "@xterm/addon-unicode11": "0.9.0",
    "@xterm/addon-web-links": "0.12.0",
    "@xterm/addon-webgl": "0.19.0",
    "@xterm/xterm": "6.0.0",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "gsap": "3.15.0",
    "leva": "0.10.1",
    "lucide-react": "0.577.0",
    "motion": "12.42.2",
    "qrcode": "1.5.4",
    "react": "19.2.7",
    "react-dom": "19.2.7",
    "react-router": "8.3.0",
    "tailwind-merge": "3.6.0",
    "tailwindcss": "4.3.3",
    "unicode-animations": "1.0.3"
  },
  "devDependencies": {
    "@babel/core": "8.0.1",
    "@rolldown/plugin-babel": "0.2.3",
    "@types/babel__core": "7.20.5",
    "@types/node": "22.20.1",
    "@types/qrcode": "1.5.6",
    "@types/react": "19.2.17",
    "@types/react-dom": "19.2.3",
    "@vitejs/plugin-react": "6.0.3",
    "babel-plugin-react-compiler": "1.0.0",
    "eslint-plugin-react-refresh": "0.5.3",
    "three": "0.180.0",
    "typescript": "6.0.3",
    "vite": "8.2.0",
    "vitest": "4.1.10"
  }
}
```
